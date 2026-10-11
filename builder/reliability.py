"""Build provenance, deadlines and submission gates (no model or network needed)."""
import contextlib
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


class BuildFailure(RuntimeError):
    pass


class Budget:
    def __init__(self, minutes, clock=time.monotonic):
        if not math.isfinite(minutes) or not 0 < minutes <= 30:
            raise ValueError("--minutes must be greater than zero and at most 30")
        self.clock = clock
        self.deadline = clock() + minutes * 60

    def remaining(self, reserve=0):
        return max(0, self.deadline - self.clock() - reserve)

    def timeout(self, maximum, reserve=0):
        left = self.remaining(reserve)
        if left <= 0:
            raise BuildFailure("Build time budget exhausted")
        return min(maximum, left)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_process(cmd, cwd, timeout):
    """Terminate the entire helper process group on timeout, including model CLIs."""
    with subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=True) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except BaseException as error:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            if isinstance(error, subprocess.TimeoutExpired):
                error.output, error.stderr = stdout, stderr
            raise
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


@contextlib.contextmanager
def workspace_lock(root):
    """Serialise builds: they share generated files and Freya's one simulation slot."""
    import fcntl
    with (Path(root) / ".builder.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BuildFailure("Another builder is using this workspace") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def archive_previous(root, slot, run_id):
    """Keep previous artifacts, but never let them satisfy this run's gates."""
    root = Path(root)
    archive = root / "build-history" / run_id
    paths = [root / "out" / (slot + suffix) for suffix in
             (".workflow.json", ".rules.json", ".rules.md", ".audit.json", ".audit.md",
              ".spec.json", ".rules.meta.json", ".rules.conflicts.md", ".cases.json",
              ".cases.meta.json", ".cases.rationale.md", ".rejected-export.json")]
    paths += [root / "out" / ("gen_" + slot + ".py")]
    paths += [root / "submission" / (slot + suffix) for suffix in (".workflow.json", ".manifest.json")]
    paths += [root / "traces" / (slot + suffix) for suffix in (".log", ".jsonl")]
    for path in paths:
        if path.exists():
            destination = archive / path.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.replace(destination)
    return archive


def platform_lint_view(workflow):
    """Ignore observed optional platform defaults for lint, preserving the export bytes.

    Candidates remain strict. Freya adds these nulls on save, including null API
    credentials for its managed models. Tool schemas and required model fields
    are never relaxed.
    """
    import copy
    view = copy.deepcopy(workflow)
    for group in ('nodes', 'global_nodes'):
        for node in (view.get(group) or {}).values():
            for key in ('max_turn_transition', 'passthrough_default_transition'):
                if key in node and node[key] is None:
                    del node[key]
    optional = {'apiKey', 'baseUrl', 'clientType', 'reaskPhrases', 'syncSource', 'recordingConsentText',
                'routingLlmConfig', 'backgroundSoundUrl', 'staticMessage', 'dynamicWait', 'checkInMessage',
                'closureMessage', 'llmPrompt', 'spokenMessage', 'triggerTimeout', 'silenceTimeoutPrompt',
                'extractionLlmConfig', 'analysisModel', 'summaryPrompt', 'problemDetectionPrompt',
                'problemDetectionInstructions'}
    def strip_defaults(obj):
        if isinstance(obj, dict):
            for key in list(obj):
                if key in optional and obj[key] is None:
                    del obj[key]
                else:
                    strip_defaults(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                strip_defaults(item)
    strip_defaults(view.get('agent_config', {}))
    return view


def validate_artifact(path, api_path, platform_export=False):
    from builder.lint import lint, ERROR
    data = json.loads(Path(path).read_text())
    wf = data.get("workflow", data)
    failures = [f["where"] + ": " + f["message"] for f in
                lint(platform_lint_view(wf) if platform_export else wf,
                     json.loads(Path(api_path).read_text())) if f["level"] == ERROR]
    if wf.get("test_variables"):
        failures.append("Remove test_variables: they override real call variables on the chat route")
    initial = (wf.get("nodes") or {}).get(wf.get("initial_node"), {})
    if initial.get("node_type") != "conversation":
        failures.append("Initial node must be conversation for chat and simulation parity")
    if failures:
        raise BuildFailure("Workflow rejected:\n" + "\n".join(failures))
    return data


def validate_audit(path, rules_path):
    report = json.loads(Path(path).read_text())
    rules = json.loads(Path(rules_path).read_text())
    active = {r["id"] for r in rules if r.get("in_force", True)}
    if not active:
        raise BuildFailure("Rule inventory has no active rules")
    rows = report.get("rules", [])
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise BuildFailure("Audit has duplicate rule ids")
    by_id = {r["id"]: r for r in rows}
    def verified_implementation(row):
        evidence = row.get("evidence")
        return (row.get("status") == "implemented" and row.get("evidence_found") is True and
                isinstance(evidence, str) and bool(evidence.strip()) and evidence.strip().lower() != "none")
    unresolved = [rid for rid in sorted(active) if rid not in by_id or
                  not verified_implementation(by_id[rid])]
    if unresolved:
        raise BuildFailure("Audit has unresolved or unverified active rules: " + ", ".join(unresolved))
    return report


def write_manifest(path, inputs, artifacts, run_id, started_at, seconds, audited):
    payload = {
        "run_id": run_id, "started_at": started_at,
        "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "seconds": round(seconds, 3), "status": "validated", "audited": audited,
        "inputs": [{"path": str(p), "sha256": sha256(p)} for p in inputs],
        "artifacts": [{"path": str(p), "sha256": sha256(p)} for p in artifacts],
        "note": "Validation is not a benchmark score or a guarantee of policy correctness.",
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")
    return payload
