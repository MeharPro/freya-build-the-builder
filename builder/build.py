#!/usr/bin/env python3
"""Builder entry point for the Build the Builder hackathon. One command, a brief in, a phone agent out.

    source env.sh
    python3 builder/build.py briefs/brief-a.md tools/openapi.json
    python3 builder/build.py briefs/brief-a.md briefs/brief-b.md tools/openapi.json     # Brief B builds on A: pass both
    python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.console.log

Every argument ending in .md is a brief; the argument ending in .json is the bank's tool API file.
The slot (and the name of every output file) is the file name of the last brief without .md.
Options: --cases <file> (practice cases to test against; auto-detected for the kit and synthetic briefs, none for
hidden briefs), --runner sim|freya (local simulator or the organisers' simulation; default sim), --minutes N (budget,
default 29), --no-rules / --no-audit to skip those steps.

One run, with no manual step:
  1. rules:    builder/rules.py extracts, merges and verifies the inventory -> rules, spec and conflict files
  2. build:    Claude (Claude Agent SDK) with the `build-phone-agent` skill writes out/gen_<slot>.py on builder/freyalib,
               generates out/<slot>.workflow.json, lints, dry-runs, saves it on Freya (freya.save_workflow), smoke-tests it
               over the chat route, audits rule coverage, runs the practice cases when there are any, and fixes what fails
  3. verify:   builder/lint.py on the final workflow, builder/audit.py coverage summary (evidence for the trace)
  4. export:   freya.export_workflow -> submission/<slot>.workflow.json (what gets scored)
  5. trace:    traces/<slot>.log (plain text: start/end, every model call, tests, what was created) + traces/<slot>.jsonl

Needs FREYA_API_KEY and FREYA_BANK_TEAM_KEY (env.sh), a Claude login or ANTHROPIC_API_KEY; OPENAI_API_KEY for the
local simulator's customer/judge models (otherwise it falls back to the Claude CLI).
BUILDER_MODEL sets the builder's own model (default claude-opus-5-5). The phone agent's model is fixed in freya.py.
"""
import argparse, asyncio, dataclasses, datetime, json, os, pathlib, re, subprocess, sys, time, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder.reliability import (BuildFailure, Budget, archive_previous, run_process,
                                 sha256, validate_artifact, validate_audit, workspace_lock, write_manifest)

SKILL = "build-phone-agent"
DEFAULT_BUILDER_MODEL = "claude-opus-5-5"
PY = sys.executable


def source_snapshot(root):
    """Fingerprint the builder inputs that generation is not allowed to rewrite."""
    patterns = ("builder/*.py", "builder/*.md", "builder/tests/*.py", "builder/smoke_scripts/*.json",
                ".claude/skills/*/SKILL.md", "CLAUDE.md", "freya.py", "tools/*.py",
                "public-test-set.json", "requirements.txt")
    return {str(p): sha256(p) for p in sorted({p for pattern in patterns for p in root.glob(pattern)
                                             if p.is_file()})}


def require_unchanged_source(root, expected):
    if source_snapshot(root) != expected:
        raise BuildFailure("Builder source or instructions changed during generation")


def scrub(text):
    """Remove API keys and the team key from anything that goes into a trace."""
    text = re.sub(r"fak_[A-Za-z0-9_\-]{8,}", "fak_***", text)
    text = re.sub(r"sk-[A-Za-z0-9_\-]{12,}", "sk-***", text)
    for name in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        v = os.environ.get(name)
        if v:
            text = text.replace(v, "<" + name + ">")
    return text


class Trace:
    def __init__(self, slot):
        d = ROOT / "traces"; d.mkdir(exist_ok=True)
        self.t0 = time.time()
        self.log = (d / (slot + ".log")).open("w")
        self.jsonl = (d / (slot + ".jsonl")).open("w")

    def line(self, msg):
        s = "[%s +%5.0fs] %s" % (time.strftime("%H:%M:%S"), time.time() - self.t0, scrub(msg))
        self.log.write(s + "\n"); self.log.flush(); print(s, flush=True)

    def raw(self, obj):
        self.jsonl.write(scrub(json.dumps(obj, default=str)) + "\n"); self.jsonl.flush()

    def elapsed_min(self):
        return (time.time() - self.t0) / 60

    def close(self):
        self.log.close(); self.jsonl.close()


def run_step(trace, name, cmd, timeout):
    """Run a helper script, copy its 'model call' lines and summary into the trace, return (returncode, stdout)."""
    trace.line("step %s: %s" % (name, " ".join(cmd)))
    try:
        p = run_process(cmd, cwd=ROOT, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        trace.raw({"step": name, "timeout": timeout, "stdout": decoded(error.output), "stderr": decoded(error.stderr)})
        for line in decoded(error.stderr).splitlines():
            if "model call" in line:
                trace.line(line.strip())
        trace.line("step %s: TIMEOUT after %d s" % (name, timeout)); return 1, ""
    trace.raw({"step": name, "command": cmd, "returncode": p.returncode,
               "stdout": p.stdout, "stderr": p.stderr})
    for l in (p.stderr or "").splitlines():
        if "model call" in l: trace.line(l.strip())
    out = (p.stdout or "").strip()
    tail = out.splitlines()[-3:] if out else []
    trace.line("step %s: exit %d%s" % (name, p.returncode, (" | " + " | ".join(t.strip()[:160] for t in tail)) if tail else ""))
    if p.returncode != 0 and p.stderr:
        trace.line("step %s stderr: %s" % (name, " ".join(p.stderr.split())[-400:]))
    return p.returncode, out


def detect_cases(briefs):
    """Practice cases for the kit's and the synthetic briefs; none for a hidden brief."""
    last = pathlib.Path(briefs[-1])
    if last.resolve() == (ROOT / "briefs" / "brief-a.md").resolve(): return str(ROOT / "public-test-set.json"), "A"
    if last.resolve() == (ROOT / "briefs" / "brief-b.md").resolve(): return str(ROOT / "public-test-set.json"), "B"
    cand = last.with_name(last.stem + ".cases.json")
    if cand.exists(): return str(cand), None
    return None, None


async def run_claude(briefs, tool_api, slot, trace, cases, brief_filter, runner, minutes_left):
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolResultBlock,
                                  ToolUseBlock, UserMessage, query)
    model = os.environ.get("BUILDER_MODEL", DEFAULT_BUILDER_MODEL)
    options = ClaudeAgentOptions(
        cwd=str(ROOT), model=model, skills=[SKILL], setting_sources=["project"],
        allowed_tools=["Skill", "Read", "Write", "Edit", "Glob", "Grep", "Bash"], permission_mode="dontAsk", max_turns=200,
        env={"BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1200000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
    )
    test_line = ("No practice cases exist for this brief: test with lint, dry run, the smoke scripts and the audit only."
                 if not cases else
                 "Practice cases: %s%s. Test runner: %s (%s)." % (cases, (" --brief " + brief_filter) if brief_filter else "", runner,
                 "python3 builder/sim.py <slot> --cases <file>%s --concurrency 2" % ((" --brief " + brief_filter) if brief_filter else "")
                 if runner == "sim" else "python3 tools/run_cases.py <agent_id> --cases <file>%s" % ((" --brief " + brief_filter) if brief_filter else "")))
    prompt = ("Use the %s skill to build a phone agent. Brief file(s): %s. Tool API file: %s. Slot name: %s. "
              "The rule inventory is at out/%s.rules.json (and .md). Read out/%s.spec.json and resolve "
              "out/%s.rules.conflicts.md against the brief. %s Time budget: %d minutes from now for everything, "
              "including your own tests; save a working agent early and improve it." % (SKILL, " ".join(briefs), tool_api, slot, slot, slot, slot, test_line, int(minutes_left)))
    trace.line("model call: %s | purpose: build, test and fix the phone agent from the brief | prompt: %s" % (model, prompt))
    async for message in query(prompt=prompt, options=options):
        trace.raw({"type": type(message).__name__, **dataclasses.asdict(message)})
        if isinstance(message, AssistantMessage):
            m = getattr(message, "model", None) or model
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text.strip(); first = text.splitlines()[0] if text else ""
                    if first: trace.line("model call: %s | says: %s" % (m, first[:220]))
                elif isinstance(block, ToolUseBlock):
                    arg = block.input.get("command") or block.input.get("file_path") or block.input.get("pattern") or ""
                    trace.line("model call: %s | tool %s | %s" % (m, block.name, " ".join(str(arg).split())[:220]))
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    text = block.content if isinstance(block.content, str) else json.dumps(block.content, default=str)
                    hits = [l.strip() for l in text.splitlines() if re.match(r"\s*(PASS|FAIL|RESULT:|ERROR|WARN)\b", l) or " passed" in l or "workflow_id" in l or "implemented" in l]
                    if hits: trace.line("test/tool result: " + " | ".join(h[:160] for h in hits[:24]))
        elif isinstance(message, ResultMessage):
            trace.line("agent run done: %s turns, %.0f s, $%.2f" % (message.num_turns, message.duration_ms / 1000, message.total_cost_usd or 0))
            if message.is_error:
                raise BuildFailure("Builder model failed: %s" % message.subtype)


def export(slot, trace, tool_api):
    """Export the phone agent exactly as it is on Freya. This file is what gets scored."""
    import freya
    f = ROOT / ".freya-agents.json"
    state = json.loads(f.read_text()) if f.exists() else {}
    if slot not in state:
        raise BuildFailure("No workflow saved for slot %r" % slot)
    wid, aid = state[slot]["workflow_id"], state[slot]["agent_id"]
    out = ROOT / "submission" / (slot + ".workflow.json"); out.parent.mkdir(exist_ok=True)
    candidate = ROOT / "out" / (slot + ".export-candidate.json")
    freya.export_workflow(wid, str(candidate))
    wf = validate_artifact(candidate, tool_api, platform_export=True)["workflow"]
    candidate.replace(out)
    nodes = wf.get("nodes") or {}
    n_tools = sum(len(n.get("tools") or []) for n in nodes.values()) + len(wf.get("tools") or [])
    trace.line("created on Freya: workflow_id=%s agent_id=%s published_version=%s | %d steps (%s), %d global nodes, %d tools | exported to %s"
               % (wid, aid, state[slot].get("version", 1), len(nodes), ", ".join(nodes), len(wf.get("global_nodes") or {}), n_tools, out.relative_to(ROOT)))
    return out


def publish(slot, path):
    """Publish exactly this candidate, including the first creation in a new workspace."""
    import freya
    wf = json.loads(Path(path).read_text())
    freya.validate_workflow(slot, wf)
    saved = freya.save_workflow(slot, wf)
    if "version" not in saved:
        saved["version"] = freya.update_workflow(saved["workflow_id"], wf)
        state_path = ROOT / ".freya-agents.json"
        state = json.loads(state_path.read_text())
        state[slot] = saved
        state_path.write_text(json.dumps(state, indent=1))
    print(json.dumps(saved))


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="One or more Markdown briefs followed by the OpenAPI JSON")
    ap.add_argument("--cases")
    ap.add_argument("--runner", choices=("sim", "freya"), default="sim")
    ap.add_argument("--minutes", type=float, default=29)
    ap.add_argument("--no-rules", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--preflight", action="store_true", help="Check inputs, environment and SDK without model/API calls")
    a = ap.parse_args(argv)
    if len(a.inputs) < 2 or any(Path(p).suffix.lower() != ".md" for p in a.inputs[:-1]) or Path(a.inputs[-1]).suffix.lower() != ".json":
        ap.error("Pass one or more .md briefs followed by exactly one .json tool API")
    try:
        Budget(a.minutes)
    except ValueError as e:
        ap.error(str(e))
    if a.no_rules and not a.no_audit:
        ap.error("--no-rules requires --no-audit")
    a.briefs = [str(Path(p).resolve()) for p in a.inputs[:-1]]
    a.tool_api = str(Path(a.inputs[-1]).resolve())
    if a.cases:
        a.cases = str(Path(a.cases).resolve())
    for p in a.briefs + [a.tool_api] + ([a.cases] if a.cases else []):
        if not Path(p).is_file():
            ap.error("not found: " + p)
    a.slot = Path(a.briefs[-1]).stem
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", a.slot):
        ap.error("Brief filename must use letters, numbers, dots, underscores or hyphens")
    return a


# Alias retained here to keep all paths explicit in argparse errors.
Path = pathlib.Path


def preflight(a):
    from builder.freyalib import tool_names, tool_spec
    api = json.loads(Path(a.tool_api).read_text())
    names = tool_names(api)
    if not names:
        raise BuildFailure("Tool API has no POST operations")
    for name in names:
        tool_spec(api, name)
    for key in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY"):
        value = os.environ.get(key, "")
        if not value or "your_key_here" in value or value.startswith("pick-any-secret"):
            raise BuildFailure(key + " is not set. source env.sh first.")
    try:
        from claude_agent_sdk import ClaudeAgentOptions
        ClaudeAgentOptions(skills=[SKILL], setting_sources=["project"])
    except (ImportError, TypeError) as e:
        raise BuildFailure("Install the pinned requirements with this Python interpreter: " + str(e)) from e


def required_step(trace, budget, name, cmd, maximum, reserve=0):
    code, output = run_step(trace, name, cmd, budget.timeout(maximum, reserve))
    if code:
        raise BuildFailure("Required step failed: " + name)
    return output


async def execute_build(a):
    budget = Budget(a.minutes)
    slot = a.slot
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    archive_previous(ROOT, slot, run_id)
    trace = Trace(slot)
    paths = [Path(p) for p in a.briefs + [a.tool_api]]
    hashes = {str(p): sha256(p) for p in paths}
    source_hashes = source_snapshot(ROOT)
    cases, brief_filter = (a.cases, None) if a.cases else detect_cases(a.briefs)
    case_hash = sha256(cases) if cases else None
    trace.line("build start %s | run_id=%s | slot=%s | budget=%.2f min" % (started_at, run_id, slot, a.minutes))
    trace.raw({"input_hashes": hashes, "cases": cases, "cases_hash": case_hash, "runner": a.runner})
    trace.raw({"source_hashes": source_hashes})
    wf_path = ROOT / "out" / (slot + ".workflow.json")
    rules_path = ROOT / "out" / (slot + ".rules.json")
    audit_path = ROOT / "out" / (slot + ".audit.json")
    gen = ROOT / "out" / ("gen_" + slot + ".py")
    out = ROOT / "submission" / (slot + ".workflow.json")
    success = False
    try:
        (ROOT / "out").mkdir(exist_ok=True)
        if not a.no_rules:
            required_step(trace, budget, "rules", [PY, "builder/rules.py", *a.briefs, "--api", a.tool_api,
                                                   "--out", str(rules_path)], 420, reserve=180)
        left = budget.timeout(1800, reserve=300)
        await asyncio.wait_for(run_claude(a.briefs, a.tool_api, slot, trace, cases, brief_filter, a.runner, left / 60), timeout=left)
        require_unchanged_source(ROOT, source_hashes)
        if cases and sha256(cases) != case_hash:
            raise BuildFailure("Practice case expectations changed during generation")
        if not wf_path.is_file() or not gen.is_file():
            raise BuildFailure("This run did not produce both a generator and a workflow")
        validate_artifact(wf_path, a.tool_api)
        required_step(trace, budget, "lint", [PY, "builder/lint.py", str(wf_path), "--api", a.tool_api], 60, reserve=60)
        # Re-save this run's validated local artifact. Never export an old remote slot after a failed save.
        required_step(trace, budget, "publish", [PY, "-c",
            "from builder.build import publish; import sys; publish(sys.argv[1],sys.argv[2])",
            slot, str(wf_path)], 120, reserve=30)
        # Export and lint the actual platform representation, including any platform transformations.
        required_step(trace, budget, "export", [PY, "-c",
            "from builder.build import export; import sys; "
            "t=type('Log',(),{'line':lambda self,x:print(x)})(); export(sys.argv[1],t,sys.argv[2])",
            slot, a.tool_api], 120, reserve=10)
        if not a.no_audit:
            required_step(trace, budget, "audit", [PY, "builder/audit.py", "--rules", str(rules_path),
                "--workflow", str(out), "--generator", str(gen), "--out", str(audit_path)], 360, reserve=5)
            validate_audit(audit_path, rules_path)
        if any(sha256(p) != hashes[str(p)] for p in paths):
            raise BuildFailure("Input files changed during the build")
        require_unchanged_source(ROOT, source_hashes)
        if cases and sha256(cases) != case_hash:
            raise BuildFailure("Practice case expectations changed during generation")
        budget.timeout(1)
        success = True
        trace.line("SUCCESS: current-run export passed required checks" + (" (audit disabled)" if a.no_audit else ""))
    except Exception as e:
        trace.line("FAILED: %s: %s" % (type(e).__name__, e))
        # Failed candidates remain reviewable, but cannot look like submission-ready exports.
        if out.exists():
            out.replace(ROOT / "out" / (slot + ".rejected-export.json"))
    finally:
        trace.line("build end %s | status=%s | total %.0f s" % (
            datetime.datetime.now(datetime.timezone.utc).isoformat(), "success" if success else "failed", time.time() - trace.t0))
        trace.close()
        import shutil
        for ext in ("log", "jsonl"):
            src = ROOT / "traces" / (slot + "." + ext)
            shutil.copy(src, ROOT / "traces" / (slot + "-" + run_id + "." + ext))
    if success:
        artifacts = [gen, wf_path, out, ROOT / "traces" / (slot + ".log"), ROOT / "traces" / (slot + ".jsonl")]
        artifacts += [ROOT / "out" / (slot + suffix) for suffix in (".spec.json", ".rules.meta.json", ".rules.conflicts.md")
                      if (ROOT / "out" / (slot + suffix)).is_file()]
        if not a.no_audit:
            artifacts += [rules_path, audit_path]
        write_manifest(ROOT / "submission" / (slot + ".manifest.json"), paths, artifacts,
                       run_id, started_at, time.time() - trace.t0, not a.no_audit)
    return 0 if success else 1


async def main(argv):
    a = parse_args(argv)
    try:
        preflight(a)
        if a.preflight:
            print("Preflight passed: files, tool API, Freya/team credential presence and SDK. Model credentials, authentication and credits not tested.")
            return 0
        with workspace_lock(ROOT):
            return await execute_build(a)
    except (BuildFailure, ValueError, OSError) as e:
        print("ERROR: " + scrub(str(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
