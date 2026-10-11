#!/usr/bin/env python3
"""Builder entry point for the Build the Builder hackathon. One command, a brief in, a phone agent out.

    source env.sh
    python3 builder/build.py briefs/brief-a.md tools/openapi.json
    python3 builder/build.py briefs/brief-a.md briefs/brief-b.md tools/openapi.json     # Brief B builds on A: pass both
    python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.console.log

Every argument ending in .md is a brief; the argument ending in .json is the bank's tool API file.
A single DIRECTORY argument is a case folder (the bank's own documents in Markdown/Word/PDF/Excel/JSON): it is bundled
into out/<slot>.brief.md by builder/casefolder.py and, when the folder has no OpenAPI file, the tool API is derived
from the documents by builder/apispec.py with --mock-url as the server. Slot defaults to "final" for a folder.
    python3 builder/build.py <case_folder> --mock-url https://<worker>.workers.dev
The slot (and the name of every output file) is the file name of the last brief without .md.
Options: --cases <file> (practice cases to test against; auto-detected for the kit and synthetic briefs, none for
hidden briefs), --runner sim|freya (local simulator or the organisers' simulation; default sim), --minutes N (budget,
default 29), --no-rules / --no-audit to skip those steps.

One run, with no manual step:
  1. rules:    builder/rules.py extracts, merges and verifies the inventory -> rules, spec and conflict files
  2. build:    Selected model (OpenAI Responses or Claude Agent SDK) with the `build-phone-agent` skill writes out/gen_<slot>.py on builder/freyalib,
               generates out/<slot>.workflow.json, lints, dry-runs, saves it on Freya (freya.save_workflow), smoke-tests it
               over the chat route, audits rule coverage, runs the practice cases when there are any, and fixes what fails
  3. verify:   builder/lint.py on the final workflow, builder/audit.py coverage summary (evidence for the trace)
  4. export:   freya.export_workflow -> submission/<slot>.workflow.json (what gets scored)
  5. trace:    traces/<slot>.log (plain text: start/end, every model call, tests, what was created) + traces/<slot>.jsonl

Needs FREYA_API_KEY and FREYA_BANK_TEAM_KEY, plus OPENAI_API_KEY or Anthropic access.
BUILDER_PROVIDER=auto|openai|claude selects generation and helper models; auto uses OpenAI when only its key is set.
BUILDER_MODEL overrides the selected provider default. The phone model stays fixed in freya.py.
"""
import argparse, asyncio, dataclasses, datetime, json, os, pathlib, re, shutil, subprocess, sys, tempfile, time, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder.reliability import (BuildFailure, Budget, archive_previous, run_process,
                                 platform_lint_view, sha256, validate_artifact, validate_audit,
                                 workspace_lock, write_manifest)

from builder.model_provider import provider, model_for

SKILL = "build-phone-agent"
DEFAULT_BUILDER_MODEL = "claude-opus-5-5"
PY = sys.executable
FINAL_GATE_SECONDS = 180
MIN_REPAIR_SECONDS = 45


def source_snapshot(root, slot=None):
    """Fingerprint the builder inputs that generation is not allowed to rewrite."""
    patterns = ("builder/**/*.py", "builder/**/*.md", "builder/**/*.json",
                ".claude/skills/*/SKILL.md", "CLAUDE.md", "freya.py", "tools/*.py",
                "public-test-set.json", "requirements.txt", "out/gen_*.py", ".claude/settings.json")
    return {str(p): sha256(p) for p in sorted({p for pattern in patterns for p in root.glob(pattern)
                                             if p.is_file() and p != root / "out" / ("gen_" + str(slot) + ".py")})}


def require_unchanged_source(root, expected, slot=None):
    if source_snapshot(root, slot) != expected:
        raise BuildFailure("Builder source or instructions changed during generation")


def builder_provenance(root, source_hashes):
    """Bind the frozen builder bytes to the Git revision used for this run."""
    root = Path(root)
    files = {str(Path(path).relative_to(root)): digest for path, digest in sorted(source_hashes.items())}

    def git_output(*args):
        try:
            result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    commit = git_output("rev-parse", "HEAD")
    status = git_output("status", "--porcelain=v1", "--untracked-files=all", "--", *files) if files else ""
    return {"git_commit": commit, "source_dirty": bool(status) if status is not None else None,
            "source_hashes": files}


def call_variable_names(briefs):
    """Read declared call-variable names, never their example values, from brief sections."""
    names = []
    for brief in briefs:
        section_level = None
        for line in Path(brief).read_text().splitlines():
            heading = re.match(r"^\s*(#{1,6})\s+(.+)", line)
            if heading:
                level, title = len(heading.group(1)), heading.group(2)
                call_heading = bool(re.search(r"\b(?:call\s+(?:variables?|inputs?)|initial\s+variables?)\b", title, re.I))
                if section_level is not None and level <= section_level:
                    section_level = None
                elif section_level is not None and not call_heading:
                    section_level = None
                if call_heading:
                    section_level = level
                continue
            if section_level is None:
                continue
            cells = line.split("|") if line.lstrip().startswith("|") else []
            first_cell = cells[1].strip() if len(cells) > 2 else ""
            candidates = re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", first_cell)
            if not candidates:
                bullet = re.match(r"^\s*[-*]\s+`([A-Za-z_][A-Za-z0-9_]*)`", line)
                candidates = [bullet.group(1)] if bullet else []
            for name in candidates:
                if name not in names:
                    names.append(name)
    if not names:
        # No "Call variables" heading: a sentence that announces the variables, followed by bullets with `names`.
        for brief in briefs:
            lines = Path(brief).read_text().splitlines()
            for i, line in enumerate(lines):
                if re.search(r"\bvariables?\b", line, re.I) and line.rstrip().endswith(":"):
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    while j < len(lines) and re.match(r"^\s*[-*]\s+`([A-Za-z_][A-Za-z0-9_]*)`", lines[j]):
                        name = re.match(r"^\s*[-*]\s+`([A-Za-z_][A-Za-z0-9_]*)`", lines[j]).group(1)
                        if name not in names:
                            names.append(name)
                        j += 1
    return names


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


async def run_claude(briefs, tool_api, slot, trace, cases, brief_filter, runner, minutes_left, repair_feedback=None, case_folder=None):
    test_line = ("No practice cases exist for this brief: test with lint, dry run, the smoke scripts and the audit only."
                 if not cases else
                 "Practice cases: %s%s. Test runner: %s (%s)." % (cases, (" --brief " + brief_filter) if brief_filter else "", runner,
                 "python3 builder/sim.py <slot> --cases <file>%s --concurrency 2" % ((" --brief " + brief_filter) if brief_filter else "")
                 if runner == "sim" else "python3 tools/run_cases.py <agent_id> --cases <file>%s" % ((" --brief " + brief_filter) if brief_filter else "")))
    folder_note = ((" The brief is a bundle of the bank's case folder %s (read the bundle; the raw files are there too)."
                    " The tool API file was derived from the bank's integration document and points at our mock of the"
                    " bank's services; read its x-notes.") % case_folder) if case_folder else ""
    prompt = ("Use the %s skill to build a phone agent. Brief file(s): %s. Tool API file: %s. Slot name: %s. "
              "The rule inventory is at out/%s.rules.json (and .md). Read out/%s.spec.json and resolve "
              "out/%s.rules.conflicts.md against the brief. %s Time budget: %d minutes from now for everything, "
              "including your own tests; save a working agent early and improve it." % (SKILL, " ".join(briefs), tool_api, slot, slot, slot, slot, test_line, int(minutes_left))) + folder_note
    prompt += (" Audit coverage before long practice batches. Start with one practice repetition or a small "
               "targeted subset; reserve time to repair and rerun failures. Three repetitions are useful only "
               "when they fit after required checks. Run each smoke separately so completed output is retained. ")
    if repair_feedback:
        prompt += (" This is a repair pass for the CURRENT generator, not a new build. Read the preserved audit at "
                   + str(repair_feedback) + ". Fix every unresolved active rule supported by the brief, including "
                   "partial coverage, without modifying the inventory or builder. Regenerate the workflow and "
                   "run targeted checks. Prioritize repairs over a full simulation batch.")
    if provider() == "openai":
        from builder.openai_agent import run_agent
        return await run_agent(ROOT, prompt, slot, trace, briefs + [tool_api] + ([cases] if cases else []), minutes_left, scrub)
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolResultBlock,
                                  ToolUseBlock, UserMessage, query)
    model = model_for("builder")
    options = ClaudeAgentOptions(
        cwd=str(ROOT), model=model, skills=[SKILL], setting_sources=["project"],
        allowed_tools=["Skill", "Read", "Write", "Edit", "Glob", "Grep", "Bash"], permission_mode="dontAsk", max_turns=200,
        env={"BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1200000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
    )
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
    ap.add_argument("inputs", nargs="+", help="One or more Markdown briefs followed by the OpenAPI JSON, or one case folder")
    ap.add_argument("--mock-url", help="Base address of the bank's (mock) services; the server of a tool API derived from a case folder")
    ap.add_argument("--slot", help="Output slot name (default: brief file name, or 'final' for a case folder)")
    ap.add_argument("--cases")
    ap.add_argument("--runner", choices=("sim", "freya"), default="sim")
    ap.add_argument("--minutes", type=float, default=29)
    ap.add_argument("--no-rules", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--preflight", action="store_true", help="Check inputs, environment and SDK without model/API calls")
    a = ap.parse_args(argv)
    a.case_folder = None
    if len(a.inputs) >= 1 and Path(a.inputs[0]).is_dir():
        if len(a.inputs) > 2 or (len(a.inputs) == 2 and Path(a.inputs[1]).suffix.lower() != ".json"):
            ap.error("Pass one case folder, optionally followed by one .json tool API")
        a.case_folder = str(Path(a.inputs[0]).resolve())
        a.slot = a.slot or "final"
        try:
            Budget(a.minutes)
        except ValueError as e:
            ap.error(str(e))
        if a.no_rules and not a.no_audit:
            ap.error("--no-rules requires --no-audit")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", a.slot):
            ap.error("Slot must use letters, numbers, dots, underscores or hyphens")
        a.cases = str(Path(a.cases).resolve()) if a.cases else None
        a.briefs = [str(ROOT / "out" / (a.slot + ".brief.md"))]
        explicit_api = Path(a.inputs[1]).resolve() if len(a.inputs) == 2 else None
        if explicit_api is None:
            from builder.casefolder import find_api_file
            explicit_api = find_api_file(a.case_folder)
        a.tool_api = str(explicit_api) if explicit_api else str(ROOT / "out" / (a.slot + ".openapi.json"))
        a.derive_api = explicit_api is None
        if a.derive_api and not a.mock_url:
            ap.error("A case folder without an OpenAPI file needs --mock-url (the address of your mock of the bank's services)")
        return a
    a.derive_api = False
    if len(a.inputs) < 2 or any(Path(p).suffix.lower() != ".md" for p in a.inputs[:-1]) or Path(a.inputs[-1]).suffix.lower() != ".json":
        ap.error("Pass one or more .md briefs followed by exactly one .json tool API, or one case folder")
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
    a.slot = a.slot or Path(a.briefs[-1]).stem
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", a.slot):
        ap.error("Brief filename must use letters, numbers, dots, underscores or hyphens")
    return a


# Alias retained here to keep all paths explicit in argparse errors.
Path = pathlib.Path


def preflight(a):
    from builder.freyalib import tool_names, tool_spec
    if getattr(a, "case_folder", None):
        from builder.casefolder import list_files
        if not list_files(a.case_folder):
            raise BuildFailure("The case folder has no files")
    if not getattr(a, "derive_api", False):
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
    if provider() == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise BuildFailure("OPENAI_API_KEY is not set. source your local env file.")
        return
    try:
        from claude_agent_sdk import ClaudeAgentOptions
        ClaudeAgentOptions(skills=[SKILL], setting_sources=["project"])
    except (ImportError, TypeError) as e:
        raise BuildFailure("Install the pinned requirements with this Python interpreter: " + str(e)) from e


def require_unchanged_files(expected, description):
    if any(not Path(path).is_file() or sha256(path) != digest for path, digest in expected.items()):
        raise BuildFailure(description + " changed during build")


def required_step(trace, budget, name, cmd, maximum, reserve=0):
    code, output = run_step(trace, name, cmd, budget.timeout(maximum, reserve))
    if code:
        raise BuildFailure("Required step failed: " + name)
    return output


def lint_command(workflow, tool_api, rules_path, call_vars):
    command = [PY, "builder/lint.py", str(workflow), "--api", str(tool_api), "--budget"]
    if rules_path and Path(rules_path).is_file():
        command += ["--rules", str(rules_path)]
    if call_vars:
        command += ["--call-vars", ",".join(call_vars)]
    return command


def lint_export(trace, budget, exported, tool_api, rules_path, call_vars, maximum, reserve):
    """Lint Freya's actual export through a normalized view; never rewrite the scored bytes."""
    data = json.loads(Path(exported).read_text())
    workflow = data.get("workflow", data) if isinstance(data, dict) else data
    with tempfile.TemporaryDirectory(prefix="freya-export-lint-") as directory:
        view = Path(directory) / "workflow.json"
        view.write_text(json.dumps(platform_lint_view(workflow)))
        required_step(trace, budget, "lint-export",
                      lint_command(view, tool_api, rules_path, call_vars), maximum, reserve)


async def execute_build(a):
    budget = Budget(a.minutes)
    slot = a.slot
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    archive_previous(ROOT, slot, run_id)
    trace = Trace(slot)
    if getattr(a, "case_folder", None):
        # Step 0: the bank sent a folder of documents. Bundle them into one brief; derive the tool API when needed.
        from builder.casefolder import bundle
        (ROOT / "out").mkdir(exist_ok=True)
        out_md, index = bundle(a.case_folder, a.briefs[0], str(ROOT / "out" / (slot + ".files.json")))
        trace.line("case folder %s: %d files, %d bundled into %s (%d bytes)" % (
            a.case_folder, len(index), sum(i["included"] for i in index), out_md.relative_to(ROOT), out_md.stat().st_size))
        trace.raw({"case_files": index})
        if a.derive_api:
            code, _ = run_step(trace, "apispec", [PY, "builder/apispec.py", a.briefs[0], "--mock-url", a.mock_url,
                                                  "--out", a.tool_api], 600)
            if code or not Path(a.tool_api).is_file():
                trace.line("FAILED: could not derive the tool API from the case documents")
                trace.close()
                return 1
            trace.line("tool API derived from the documents: %s | mock %s" % (Path(a.tool_api).relative_to(ROOT), a.mock_url))
    paths = [Path(p) for p in a.briefs + [a.tool_api]]
    hashes = {str(p): sha256(p) for p in paths}
    source_hashes = source_snapshot(ROOT, slot)
    provenance = builder_provenance(ROOT, source_hashes)
    call_vars = call_variable_names(a.briefs)
    cases, brief_filter = (a.cases, None) if a.cases else detect_cases(a.briefs)
    case_hash = sha256(cases) if cases else None
    trace.line("build start %s | run_id=%s | slot=%s | budget=%.2f min" % (started_at, run_id, slot, a.minutes))
    trace.raw({"input_hashes": hashes, "cases": cases, "cases_hash": case_hash, "runner": a.runner})
    trace.raw({"source_hashes": source_hashes})
    trace.raw({"builder_provenance": {"git_commit": provenance["git_commit"],
                                      "source_dirty": provenance["source_dirty"]},
               "declared_call_variables": call_vars})
    wf_path = ROOT / "out" / (slot + ".workflow.json")
    rules_path = ROOT / "out" / (slot + ".rules.json")
    audit_path = ROOT / "out" / (slot + ".audit.json")
    gen = ROOT / "out" / ("gen_" + slot + ".py")
    out = ROOT / "submission" / (slot + ".workflow.json")
    success = False
    validated_hashes = {}
    try:
        (ROOT / "out").mkdir(exist_ok=True)
        if not a.no_rules:
            required_step(trace, budget, "rules", [PY, "builder/rules.py", *a.briefs, "--api", a.tool_api,
                                                   "--out", str(rules_path)], 660, reserve=180)
        inventory_hashes = {str(p): sha256(p) for p in (ROOT / "out").glob(slot + ".rules*") if p.is_file()}
        spec_path = ROOT / "out" / (slot + ".spec.json")
        if spec_path.is_file():
            inventory_hashes[str(spec_path)] = sha256(spec_path)
        trace.raw({"inventory_hashes": inventory_hashes})
        protected = {**hashes, **inventory_hashes, **({cases: case_hash} if cases else {})}
        repair_feedback = None
        for attempt in range(3):
            # The last pass uses spare time while keeping a complete final gate available.
            left = budget.timeout((900, 420, 180)[attempt],
                                  reserve=300 if attempt == 0 else FINAL_GATE_SECONDS)
            try:
                await asyncio.wait_for(run_claude(a.briefs, a.tool_api, slot, trace, cases, brief_filter,
                    a.runner, left / 60, repair_feedback=repair_feedback,
                    case_folder=getattr(a, "case_folder", None)), timeout=left)
            except asyncio.TimeoutError:
                # Only current-run files exist here: archive_previous removed older artifacts.
                # Strict validation/audit still decides whether the saved candidate can be used.
                trace.line("Generation time slice ended; checking the current saved candidate")
            require_unchanged_source(ROOT, source_hashes, slot)
            require_unchanged_files(protected, "Inputs, rule inventory or case expectations")
            if not wf_path.is_file() or not gen.is_file():
                raise BuildFailure("This run did not produce both a generator and a workflow")
            validate_artifact(wf_path, a.tool_api)
            # An audit of a later revision cannot validate the candidate just linted here.
            candidate_hashes = {str(p): sha256(p) for p in (gen, wf_path)}
            late = attempt == 2
            lint_rules = rules_path if not a.no_rules else None
            required_step(trace, budget, "lint", lint_command(wf_path, a.tool_api, lint_rules, call_vars),
                          15 if late else 60, reserve=165 if late else 60)
            required_step(trace, budget, "publish", [PY, "-c",
                "from builder.build import publish; import sys; publish(sys.argv[1],sys.argv[2])",
                slot, str(wf_path)], 25 if late else 120, reserve=140 if late else 30)
            required_step(trace, budget, "export", [PY, "-c",
                "from builder.build import export; import sys; "
                "t=type('Log',(),{'line':lambda self,x:print(x)})(); export(sys.argv[1],t,sys.argv[2])",
                slot, a.tool_api], 25 if late else 120, reserve=115 if late else 10)
            if not out.is_file():
                raise BuildFailure("Freya export did not produce a workflow")
            export_hashes = {str(out): sha256(out)}
            lint_export(trace, budget, out, a.tool_api, lint_rules, call_vars,
                        20 if late else 60, reserve=95 if late else 10)
            if a.no_audit:
                validated_hashes = {**candidate_hashes, **export_hashes}
                require_unchanged_files(validated_hashes, "Validated generator, candidate or export")
                break
            required_step(trace, budget, "audit", [PY, "builder/audit.py", "--rules", str(rules_path),
                "--workflow", str(out), "--generator", str(gen), "--out", str(audit_path)],
                90 if late else 360, reserve=5)
            require_unchanged_files({**candidate_hashes, **export_hashes},
                                    "Validated generator, candidate or export")
            try:
                validate_audit(audit_path, rules_path)
                validated_hashes = {**candidate_hashes, **export_hashes, str(audit_path): sha256(audit_path)}
                require_unchanged_files(validated_hashes, "Validated generator, candidate, export or audit")
                break
            except BuildFailure as error:
                if attempt == 2 or budget.remaining() < FINAL_GATE_SECONDS + MIN_REPAIR_SECONDS:
                    raise
                saved = ROOT / "build-history" / run_id / ("attempt-%d" % (attempt + 1))
                saved.mkdir(parents=True, exist_ok=True)
                for artifact in (gen, wf_path, out, audit_path, audit_path.with_suffix(".md")):
                    if artifact.exists():
                        # Local candidate and platform export have distinct names.
                        name = "export.workflow.json" if artifact == out else artifact.name
                        shutil.copy2(artifact, saved / name)
                repair_feedback = saved / audit_path.name
                trace.line("Audit repair pass %d: %s | %.0f seconds remain" % (attempt + 1, error, budget.remaining()))
                out.unlink()  # The failed export cannot masquerade as a valid submission during repair.
        require_unchanged_files(protected, "Inputs, rule inventory or case expectations")
        require_unchanged_source(ROOT, source_hashes, slot)
        require_unchanged_files(validated_hashes, "Validated generator, candidate, export or audit")
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
        for ext in ("log", "jsonl"):
            src = ROOT / "traces" / (slot + "." + ext)
            shutil.copy(src, ROOT / "traces" / (slot + "-" + run_id + "." + ext))
    if success:
        artifacts = [gen, wf_path, out, ROOT / "traces" / (slot + ".log"), ROOT / "traces" / (slot + ".jsonl")]
        artifacts += [ROOT / "out" / (slot + suffix) for suffix in (".spec.json", ".rules.meta.json", ".rules.conflicts.md")
                      if (ROOT / "out" / (slot + suffix)).is_file()]
        if not a.no_audit:
            artifacts += [rules_path, audit_path]
        manifest_path = ROOT / "submission" / (slot + ".manifest.json")
        pending_manifest = manifest_path.with_name(manifest_path.name + ".tmp")
        try:
            require_unchanged_files(protected, "Inputs, rule inventory or case expectations")
            require_unchanged_source(ROOT, source_hashes, slot)
            require_unchanged_files(validated_hashes, "Validated generator, candidate, export or audit")
            artifact_hashes = {str(p): sha256(p) for p in artifacts}
            budget.timeout(1)
            manifest = write_manifest(pending_manifest, paths, artifacts,
                                      run_id, started_at, time.time() - trace.t0, not a.no_audit)
            for section, expected in (("inputs", hashes), ("artifacts", artifact_hashes)):
                if {row["path"]: row["sha256"] for row in manifest[section]} != expected:
                    raise BuildFailure("Manifest hashes do not match validated " + section)
            manifest["builder_provenance"] = provenance
            pending_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
            require_unchanged_files(protected, "Inputs, rule inventory or case expectations")
            require_unchanged_source(ROOT, source_hashes, slot)
            require_unchanged_files(artifact_hashes, "Validated submission artifacts")
            budget.timeout(1)
            pending_manifest.replace(manifest_path)
            require_unchanged_files(artifact_hashes, "Validated submission artifacts")
        except Exception as error:
            pending_manifest.unlink(missing_ok=True)
            manifest_path.unlink(missing_ok=True)
            if out.exists():
                out.replace(ROOT / "out" / (slot + ".rejected-export.json"))
            failure = "FAILED: manifest publication: %s: %s" % (type(error).__name__, scrub(str(error)))
            log_line = "[%s +%5.0fs] %s\n" % (time.strftime("%H:%M:%S"), time.time() - trace.t0, failure)
            for path in (ROOT / "traces" / (slot + ".log"),
                         ROOT / "traces" / (slot + "-" + run_id + ".log")):
                with path.open("a") as stream:
                    stream.write(log_line)
            print(log_line, end="", flush=True)
            success = False
    return 0 if success else 1


async def main(argv):
    a = parse_args(argv)
    try:
        preflight(a)
        if a.preflight:
            print("Preflight passed: files, tool API, credential presence and selected provider dependencies. Authentication and credits not tested.")
            return 0
        with workspace_lock(ROOT):
            return await execute_build(a)
    except (BuildFailure, ValueError, OSError) as e:
        print("ERROR: " + scrub(str(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
