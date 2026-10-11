#!/usr/bin/env python3
"""Coverage audit: for every rule of a rule inventory, The selected model reads the generator source and the workflow and says whether
the phone agent implements it.

    .venv/bin/python builder/audit.py --rules out/brief-a.rules.json --workflow out/brief-a.workflow.json \\
        --generator out/gen_brief-a.py --out out/brief-a.audit.json

As a function:

    from audit import audit
    report = audit("out/brief-a.rules.json", "out/brief-a.workflow.json", "out/gen_brief-a.py", "out/brief-a.audit.json")

Output JSON:
  {"rules": [{"id", "status", "where", "evidence", "fix_hint"}],      status: implemented | partial | missing | contradicted | superseded
   "summary": {"implemented": n, "partial": n, "missing": n, "contradicted": n, "superseded": n, "total": n},
   "top_fixes": [{"id", "why", "fix"}],                               the 5 most important missing/contradicted/partial rules
   "meta": {"model", "seconds", "cost_usd", "calls", "batches", ...}}
and a Markdown rendering next to it (<out with .md>).

What is sent to the model: not the raw workflow JSON (90 KB of repeated tool definitions) but the generator source plus a digest
of the generated workflow: system prompt, every node with its prompts, tools (deduplicated), extraction enums, transitions,
code and terminals. The rules are audited in batches (--batch, default 12 rules) run in parallel (--parallel, default 3);
each batch is one model call with the same context. One more small call ranks the gaps into top_fixes.
--workflow may be the export format ({"workflow": {...}}) or the plain workflow. --generator is optional (--generator "").

Needs OPENAI_API_KEY or Anthropic access. AUDIT_MODEL overrides the selected provider model.
Progress and every model call go to stderr ("model call: <model> | purpose: ..."); the one-line summary goes to stdout.
"""
import argparse, asyncio, json, os, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rules import ask_json_async  # noqa: E402  (same folder; the Claude call helper)

from model_provider import provider, model_for, cost_sum, cost_round, cost_label

DEFAULT_MODEL = "claude-opus-5-5"
STATUSES = ["implemented", "partial", "missing", "contradicted"]

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string", "enum": STATUSES},
                    "where": {"type": "string", "description": "node / prompt / code / transition / tool that implements it; '' when missing"},
                    "evidence": {"type": "string", "description": "one line quoted verbatim from the prompt, code, transition or tool (<= 240 chars); 'none' when missing"},
                    "fix_hint": {"type": "string", "description": "one concrete change; '' when implemented"},
                },
                "required": ["id", "status", "where", "evidence", "fix_hint"],
            },
        }
    },
    "required": ["rules"],
}

FIXES_SCHEMA = {
    "type": "object",
    "properties": {
        "top_fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "why": {"type": "string", "description": "why this gap fails test cases, one sentence"},
                    "fix": {"type": "string", "description": "the concrete change: node, element (prompt line / transition / code / tool field) and the text or logic to add"},
                },
                "required": ["id", "why", "fix"],
            },
        }
    },
    "required": ["top_fixes"],
}

PRIMER = """You audit a phone agent (a Freya workflow) against a rule inventory extracted from the bank's brief. You get:
(1) the generator: the Python program that writes the workflow JSON (prompts, code, tool definitions, transitions), and
(2) a digest of the workflow it produced: the system prompt, every node with its on_enter line, task_message, tools,
extraction schema, transitions, code and terminal, in the order a reader needs. The digest is the ground truth of what the
agent does; the generator shows how values are computed.

HOW A FREYA WORKFLOW WORKS (what to look for):
- Nodes. conversation: the dialogue model speaks with the customer following system_prompt + the node's task_message; on_enter
  tts text is spoken word for word when the node is entered (first_only = only the first time). code: runs Python once with a
  `vars` dict (call variables and everything written so far), passthrough to its transition, no speech. api_request: calls a
  tool on entry (pre_actions), optional on_enter tts line. end_call: speaks terminal spoken_message (the farewell) and hangs up.
- {{name}} in any text is replaced at runtime by the variable: call variables (customer_id, first_name, last_name, title, now),
  variables written by code nodes (vars['x'] = ...), tool results (<tool>_response.data.<field>) and response_mapping.
  So a prompt line like "Deadline: {{deadline_text}}" shows the model a date computed in code.
- Each customer turn: extraction_schema runs (an enum value per field, stored as a variable), then transitions are evaluated
  in order (equals / not_equals / greater_than / is_set on variables = deterministic code; matches_intent = a routing model that
  reads ONLY the transition's description/condition, never the task_message), then the dialogue model answers.
  Transitions are evaluated again right after a tool result, so a route on <tool>_response.data.ok fires in the same turn.
  Counters <tool>_success_count / <tool>_failure_count exist per tool. is_tool_call transitions are offered to the dialogue
  model as tools named transition_to_<node>; the model triggers them by calling the tool.
- Tools on conversation nodes: the model fills the body fields that have default "{{field}}"; fixed defaults are baked.
  pre_process_code may rewrite the request body (`config['body']`), post_process_code may rewrite `result` (for example add a
  what_to_do_next line). Global `tools` with config.alwaysRunsAt ["end_of_call"] run automatically when the call ends, with
  the variables as they are then (e.g. close_call reads vars outcome/reason set by the fin_* code nodes).
- LIFECYCLE TOOLS: a tool whose config.alwaysRunsAt is a non-empty list (e.g. ["end_of_call"]) is run by the engine at that
  moment, exactly once, and is NEVER shown to the dialogue model: the model cannot call it, early or twice. Do not flag
  "nothing forbids the model from calling close_call" (or "close_call might be called twice / not last") when close_call is
  such a lifecycle tool; judge only the values it sends (the outcome/reason variables the fin_* nodes write).
- on_enter {"type": "llm"} means the model writes the entry line from task_message; an on_enter prompt (shown as
  "on_enter llm prompt") overrides that entry instruction. A terminal with message_mode llm has the model write the
  farewell from llm_prompt; custom speaks spoken_message verbatim; none hangs up silently.
- Booleans from tools arrive as strings ("true"/"True"); routes test both. Nodes named fin_<x> set outcome/reason and lead
  to end_<x> terminals; the terminal's spoken_message is the farewell.

JUDGING, per rule:
- implemented: the workflow enforces or instructs the whole rule with the right values. Enforcement by structure (a route, a
  code node, a tool definition, a baked default, a terminal) counts; enforcement by an instruction in system_prompt /
  task_message / on_enter / tool description counts too. A date, amount or deadline computed in code and handed to the model as
  text counts when the code matches the rule's values exactly. "where" names the node and element, e.g.
  "negotiate.task_message item 3", "setup code: attempt1_date", "third_party transition -> fin_no_callback",
  "tool close_call pre_process_code", "end_promise terminal spoken_message".
- partial: part of the rule is there, a specific part is not, or the instruction is weaker/vaguer than the rule
  (say exactly which part is missing in fix_hint).
- contradicted: the workflow does something else: another value, another outcome/reason, another order, a forbidden word
  spoken, a verbatim sentence replaced by different words (small punctuation/capitalisation differences are fine).
- missing: nothing in the workflow addresses the rule.
Check values exactly (every holiday date, deadline formula, callback window, wrong-answer limit, enum name, queue name,
outcome/reason pairs). Verbatim sentences: look for the exact words in a prompt, on_enter tts or terminal spoken_message.
A rule stated as "never X" is implemented when a prompt forbids X or the structure makes X impossible. A rule about a tool's
required fields/enums/formats is implemented when the tool definition, its pre_process_code or the prompt provides them.
"evidence": ONE line quoted verbatim from the digest or generator (<= 240 characters; 'none' when missing).
"fix_hint": one concrete change (which node, which element, what to add or change); '' when implemented.
Do not mark a rule implemented because it is "probably" handled by the model's common sense: point at a line. Do not mark a
rule missing when a route/code/tool implements it under other words: search the digest for the values first.
Answer with JSON {"rules": [...]} for exactly the rule ids you were given, in the same order."""


# ----------------------------------------------------------------------------------------------- workflow digest
def _cond(c):
    if not isinstance(c, dict):
        return str(c)
    if "logic" in c and "conditions" in c:
        inner = [_cond(x) for x in c.get("conditions") or []]
        return "(" + (" %s " % c["logic"].upper()).join(inner) + ")"
    op = c.get("operator", "?")
    if op == "always":
        return "always"
    if op == "matches_intent":
        return "matches_intent \"%s\"" % c.get("description", "")
    if "variable" in c:
        return "%s %s %s" % (c["variable"], op, json.dumps(c.get("operand")) if "operand" in c else "")
    return json.dumps(c)


def _tool_text(t):
    f = t.get("function") or {}
    name = f.get("name", "?")
    L = ["description: " + " ".join(str(f.get("description", "")).split())]
    cfg = t.get("config") or {}
    cfg_bits = {k: v for k, v in cfg.items() if k in ("alwaysRunsAt", "maxRetries")}
    if cfg_bits:
        L.append("config: " + json.dumps(cfg_bits))
    if isinstance(cfg.get("alwaysRunsAt"), list) and cfg["alwaysRunsAt"]:
        L.append("LIFECYCLE TOOL: run by the engine at %s, never offered to the dialogue model" % ", ".join(map(str, cfg["alwaysRunsAt"])))
    params = (f.get("parameters") or {}).get("properties") or {}
    if "url" in params:
        L.append("url: %s %s" % ((params.get("method") or {}).get("default", ""), (params.get("url") or {}).get("default", "")))
    body = params.get("body") or {}
    req = body.get("required") or []
    for k, v in (body.get("properties") or {}).items():
        bits = []
        if "default" in v:
            bits.append("default %s" % json.dumps(v["default"]))
        if v.get("enum"):
            bits.append("enum " + json.dumps(v["enum"]))
        if v.get("description"):
            bits.append(" ".join(str(v["description"]).split()))
        L.append("  body.%s%s (%s): %s" % (k, "*" if k in req else "", v.get("type", ""), "; ".join(bits)))
    # non-api tools (code_exec, end_call) keep their simple params
    for k, v in params.items():
        if k in ("url", "method", "headers", "body"):
            continue
        if isinstance(v, dict) and "default" in v and k != "code":
            L.append("  %s: %s" % (k, json.dumps(v["default"])))
    for key in ("pre_process_code", "post_process_code"):
        if t.get(key):
            L.append(key + ":\n" + _indent(str(t[key]), 4))
    if t.get("response_mapping"):
        L.append("response_mapping: " + json.dumps(t["response_mapping"]))
    return name, "\n".join(L)


def _indent(s, n):
    pad = " " * n
    return "\n".join(pad + l for l in s.rstrip("\n").splitlines())


def workflow_digest(wf):
    """A compact, complete text of the workflow: prompts, tools (deduplicated), enums, transitions, code, terminals."""
    if "workflow" in wf and "nodes" not in wf:
        wf = wf["workflow"]
    nodes = wf.get("nodes") or {}
    tools, labels, counts = {}, {}, {}
    code_seen = {}

    def register(t):
        key = json.dumps(t, sort_keys=True)
        if key in labels:
            return labels[key]
        name, text = _tool_text(t)
        counts[name] = counts.get(name, 0) + 1
        label = name if counts[name] == 1 else "%s#%d" % (name, counts[name])
        labels[key] = label
        tools[label] = text
        return label

    body = []
    for name, n in nodes.items():
        nt = n.get("node_type", "?")
        flags = [k for k in ("passthrough", "on_enter_first_entry_only") if n.get(k)]
        body.append("NODE %s [%s]%s" % (name, nt, " (" + ", ".join(flags) + ")" if flags else ""))
        oe = n.get("on_enter") or {}
        if oe.get("type") == "tts":
            body.append("  on_enter tts: \"%s\"" % oe.get("text", ""))
        elif oe.get("type") == "llm" and oe.get("prompt"):
            body.append("  on_enter llm prompt:\n" + _indent(str(oe["prompt"]), 4))
        elif oe.get("type"):
            body.append("  on_enter: " + oe["type"])
        if n.get("task_message"):
            body.append("  task_message:\n" + _indent(n["task_message"], 4))
        tl = [register(t) for t in n.get("tools") or []]
        if tl:
            body.append("  tools: " + ", ".join(tl))
        for pa in n.get("pre_actions") or []:
            f = pa.get("function") or {}
            if f.get("name") == "code_exec":
                code = (((f.get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default", "")
                # the policy-as-code nodes share one 40 KB core and differ only in their last lines: print the shared
                # prefix once and only the tail afterwards (the full digest was 872 KB: E2BIG on Linux, 220k tokens)
                ref = None
                for rname, rcode in code_seen.items():
                    n_common = 0
                    for ch1, ch2 in zip(code, rcode):
                        if ch1 != ch2:
                            break
                        n_common += 1
                    if n_common >= 2000 and (ref is None or n_common > ref[1]):
                        ref = (rname, n_common)
                if ref:
                    cut = code.rfind("\n", 0, ref[1]) + 1
                    body.append("  code: the first %d characters are the same as node %s's code; then:\n%s" % (cut, ref[0], _indent(code[cut:], 4)))
                else:
                    code_seen[name] = code
                    body.append("  code:\n" + _indent(code, 4))
            else:
                body.append("  pre_action tool: " + register(pa))
        if n.get("response_mapping"):
            body.append("  response_mapping: " + json.dumps(n["response_mapping"]))
        for e in n.get("extraction_schema") or []:
            body.append("  extract %s (type %s): enum %s (min_confidence %s)\n%s" % (
                e.get("name"), e.get("type", "string"), json.dumps(e.get("enum_values")), e.get("min_confidence", ""), _indent(" ".join(str(e.get("description", "")).split()), 6)))
        if n.get("transitions"):
            body.append("  transitions (in order):")
            for i, t in enumerate(n["transitions"], 1):
                body.append("    %d. -> %s%s  if %s  [\"%s\"]" % (
                    i, t.get("target_node"), "  (tool-call transition transition_to_%s)" % t.get("target_node") if t.get("is_tool_call") else "",
                    _cond(t.get("condition")), t.get("description", "")))
        term = n.get("terminal")
        if term:
            f = term.get("function") or {}
            props = ((f.get("parameters") or {}).get("properties") or {})
            mode = (props.get("message_mode") or {}).get("default", "custom")
            if mode == "llm":
                body.append("  terminal: endedReason=%s, message_mode=llm, llm_prompt=\"%s\"" % (
                    f.get("name"), (props.get("llm_prompt") or {}).get("default", "")))
            elif mode == "none":
                body.append("  terminal: endedReason=%s, message_mode=none (hangs up without a farewell)" % f.get("name"))
            else:
                body.append("  terminal: endedReason=%s, spoken_message=\"%s\"" % (f.get("name"), (props.get("spoken_message") or {}).get("default", "")))
        body.append("")
    glob = [register(t) for t in wf.get("tools") or []]
    out = ["INITIAL NODE: %s" % wf.get("initial_node"), "", "SYSTEM PROMPT:", _indent(wf.get("system_prompt", ""), 2), ""]
    if glob:
        out.append("GLOBAL TOOLS (available in every node / run at end of call): " + ", ".join(glob))
    if wf.get("global_nodes"):
        out.append("GLOBAL NODES: " + json.dumps(wf["global_nodes"])[:3000])
    out.append("")
    out.append("TOOL DEFINITIONS (referenced by name from the nodes):")
    for label, text in tools.items():
        out.append("TOOL %s\n%s" % (label, _indent(text, 2)))
    out.append("")
    out.append("NODES (%d):" % len(nodes))
    out.extend(body)
    return "\n".join(out)


# ----------------------------------------------------------------------------------------------- audit
def _rule_block(r):
    s = "%s [%s] (%s): %s" % (r["id"], r.get("category", ""), r.get("source", ""), r["text"])
    if r.get("verbatim"):
        s += "\n   verbatim: " + " | ".join("\"%s\"" % v for v in r["verbatim"])
    if r.get("values"):
        s += "\n   values: " + json.dumps(r["values"], ensure_ascii=False)
    return s


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def verify_evidence(judged, sources_text):
    """Mark each judgement with evidence_found: does the quoted evidence occur verbatim (whitespace-insensitive) in the
    digest or the generator? Guards against invented evidence. Returns the number of unverified quotes."""
    S = _norm(sources_text)
    bad = 0
    for j in judged:
        if j.get("status") == "superseded":
            continue
        e = j.get("evidence")
        if not isinstance(e, str) or not e.strip() or e.strip().lower() == "none":
            j["evidence_found"] = False
            bad += 1
            continue
        ne = _norm(e)
        found = ne in S or ne.strip("\"'`") in S or ne[:60] in S
        j["evidence_found"] = found
        if not found:
            bad += 1
    return bad


async def _audit_batch(batch, system_prompt, model, log, sem, idx, nb):
    prompt = ("Audit these %d rules (ids %s to %s). Return one entry per id, same order.\n\nRULES:\n%s" % (
        len(batch), batch[0]["id"], batch[-1]["id"], "\n".join(_rule_block(r) for r in batch)))
    async with sem:
        obj, info = await ask_json_async(prompt, system_prompt, AUDIT_SCHEMA, "audit rules %s-%s (batch %d/%d)" % (
            batch[0]["id"], batch[-1]["id"], idx, nb), model=model, log=log)
    got = {str(x.get("id")): x for x in (obj.get("rules") if isinstance(obj, dict) else obj) or [] if isinstance(x, dict)}
    out = []
    for r in batch:
        x = got.get(r["id"])
        if not x or x.get("status") not in STATUSES:
            out.append({"id": r["id"], "status": "missing", "where": "", "evidence": "none",
                        "fix_hint": "(the auditor returned no judgement for this rule; re-run)"})
        else:
            out.append({"id": r["id"], "status": x["status"], "where": str(x.get("where", "")),
                        "evidence": str(x.get("evidence", ""))[:400], "fix_hint": str(x.get("fix_hint", ""))})
    return out, info


async def audit_async(rules_path, workflow_path, generator_path, out_path, model=None, batch_size=12, parallel=3, log=None):
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    t0 = time.time()
    model = model or model_for("audit")
    rules = json.load(open(rules_path))
    if isinstance(rules, dict):
        rules = rules.get("rules", [])
    wf = json.load(open(workflow_path))
    digest = workflow_digest(wf)
    gen = pathlib.Path(generator_path).read_text() if generator_path and pathlib.Path(generator_path).exists() else ""
    by_id = {r["id"]: r for r in rules}
    active = [r for r in rules if r.get("in_force", True)]
    superseded = [r for r in rules if not r.get("in_force", True)]
    log("audit: %d rules (%d in force) | workflow digest %d chars, generator %d chars | model %s | batches of %d, %d in parallel" % (
        len(rules), len(active), len(digest), len(gen), model, batch_size, parallel))
    system_prompt = PRIMER + "\n\n" + ("=" * 30 + " GENERATOR SOURCE (%s) " % pathlib.Path(generator_path).name + "=" * 30 + "\n" + gen + "\n\n" if gen else "") \
        + "=" * 30 + " WORKFLOW DIGEST (%s) " % pathlib.Path(workflow_path).name + "=" * 30 + "\n" + digest
    batches = [active[i:i + batch_size] for i in range(0, len(active), batch_size)]
    sem = asyncio.Semaphore(max(1, parallel))
    results = await asyncio.gather(*[_audit_batch(b, system_prompt, model, log, sem, i + 1, len(batches)) for i, b in enumerate(batches)])
    judged, cost, calls = [], 0.0, 0
    for out, info in results:
        judged.extend(out); cost = cost_sum(cost, info["cost_usd"]); calls += info["attempts"]
    for r in superseded:
        judged.append({"id": r["id"], "status": "superseded", "where": "superseded by %s" % r.get("superseded_by", ""), "evidence": "", "fix_hint": ""})
    order = {r["id"]: i for i, r in enumerate(rules)}
    judged.sort(key=lambda x: order.get(x["id"], 999))
    unverified = verify_evidence(judged, digest + "\n" + gen)
    summary = {s: 0 for s in STATUSES + ["superseded"]}
    for j in judged:
        summary[j["status"]] = summary.get(j["status"], 0) + 1
    summary["total"] = len(judged)
    summary["evidence_unverified"] = unverified
    # top fixes
    rank = {"contradicted": 0, "missing": 1, "partial": 2}
    gaps = sorted([j for j in judged if j["status"] in rank], key=lambda j: (rank[j["status"]], order.get(j["id"], 999)))
    top_fixes = []
    if gaps:
        gp = ("These rules of the brief are not (fully) implemented by the phone agent. Rank the 5 most important ones for passing "
              "simulated-customer test cases: a wrong close_call outcome/reason, a wrong date/amount/deadline, a forbidden disclosure, "
              "a missing or extra tool call, or a missed mandatory sentence fails a case; vaguer wording matters less. A contradicted "
              "rule usually outranks a missing one, which outranks a partial one, unless the partial one breaks many cases. "
              "For each, write the concrete fix: the node, the element (task_message line / transition / code / tool field / "
              "terminal message) and the text or logic to add or change. Return at most 5, most important first.\n\nGAPS:\n%s" % "\n\n".join(
                  "%s [%s]\n   rule: %s\n   where: %s\n   evidence: %s\n   fix_hint: %s" % (
                      j["id"], j["status"], _rule_block(by_id[j["id"]]), j["where"], j["evidence"], j["fix_hint"]) for j in gaps))
        obj, info = await ask_json_async(gp, PRIMER, FIXES_SCHEMA, "rank the %d gaps into the top 5 fixes" % len(gaps), model=model, log=log)
        cost = cost_sum(cost, info["cost_usd"]); calls += info["attempts"]
        for x in (obj.get("top_fixes") if isinstance(obj, dict) else obj) or []:
            if isinstance(x, dict) and str(x.get("id")) in by_id:
                j = next((j for j in judged if j["id"] == str(x["id"])), {})
                top_fixes.append({"id": str(x["id"]), "status": j.get("status", ""), "rule": by_id[str(x["id"])]["text"],
                                  "why": str(x.get("why", "")), "fix": str(x.get("fix", ""))})
        top_fixes = top_fixes[:5]
    meta = {"model": model, "seconds": round(time.time() - t0, 1), "cost_usd": cost_round(cost, 4), "calls": calls, "batches": len(batches),
            "rules": str(rules_path), "workflow": str(workflow_path), "generator": str(generator_path),
            "digest_chars": len(digest), "generator_chars": len(gen)}
    report = {"rules": judged, "summary": summary, "top_fixes": top_fixes, "meta": meta}
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    md = out.with_suffix(".md") if out.suffix == ".json" else pathlib.Path(str(out) + ".md")
    md.write_text(render_md(report, rules))
    print("audit: %s -> %s + %s | %d model call(s), %.0f s, %s | evidence not found verbatim: %d | top fixes: %s" % (
        ", ".join("%s %d" % (k, summary[k]) for k in STATUSES + ["superseded", "total"]), out, md.name, calls, meta["seconds"], cost_label(cost),
        unverified, ", ".join(f["id"] for f in top_fixes) or "none"), flush=True)
    return report


def audit(rules_path, workflow_path, generator_path, out_path, model=None, batch_size=12, parallel=3, log=None):
    return asyncio.run(audit_async(rules_path, workflow_path, generator_path, out_path, model=model, batch_size=batch_size,
                                   parallel=parallel, log=log))


# ----------------------------------------------------------------------------------------------- rendering
def render_md(report, rules):
    by_id = {r["id"]: r for r in rules}
    s, m = report["summary"], report.get("meta", {})
    L = ["# Coverage audit: %s" % pathlib.Path(m.get("workflow", "")).name, ""]
    L.append("Rules: `%s`. Generator: `%s`. Model %s, %.0f s, %s, %d call(s)." % (
        pathlib.Path(m.get("rules", "")).name, pathlib.Path(m.get("generator", "")).name, m.get("model"), m.get("seconds", 0), cost_label(m.get("cost_usd", 0)), m.get("calls", 0)))
    L.append("")
    L.append("| implemented | partial | missing | contradicted | superseded | total |")
    L.append("|---|---|---|---|---|---|")
    L.append("| %d | %d | %d | %d | %d | %d |" % tuple(s.get(k, 0) for k in ("implemented", "partial", "missing", "contradicted", "superseded", "total")))
    L.append("")
    if s.get("evidence_unverified"):
        L.append("%d evidence quote(s) were not found verbatim in the digest or the generator (marked *unverified* below)." % s["evidence_unverified"])
        L.append("")
    if report.get("top_fixes"):
        L.append("## Top fixes")
        L.append("")
        for i, f in enumerate(report["top_fixes"], 1):
            L.append("%d. **%s** (%s): %s" % (i, f["id"], f.get("status", ""), f.get("rule", "")))
            L.append("   - why: %s" % f.get("why", ""))
            L.append("   - fix: %s" % f.get("fix", ""))
        L.append("")
    for status in ("contradicted", "missing", "partial"):
        rs = [j for j in report["rules"] if j["status"] == status]
        if not rs:
            continue
        L.append("## %s (%d)" % (status, len(rs)))
        L.append("")
        for j in rs:
            r = by_id.get(j["id"], {})
            L.append("- **%s** (_%s_): %s" % (j["id"], r.get("source", ""), r.get("text", "")))
            if j.get("where"):
                L.append("  - where: %s" % j["where"])
            if j.get("evidence") and j["evidence"] != "none":
                L.append("  - evidence: `%s`" % j["evidence"].replace("`", "'"))
            if j.get("fix_hint"):
                L.append("  - fix: %s" % j["fix_hint"])
        L.append("")
    L.append("## All rules")
    L.append("")
    L.append("| id | status | where | evidence |")
    L.append("|---|---|---|---|")
    for j in report["rules"]:
        flag = " *unverified*" if j.get("evidence_found") is False else ""
        L.append("| %s | %s | %s | %s%s |" % (j["id"], j["status"], j.get("where", "").replace("|", "/"), (j.get("evidence") or "").replace("|", "/").replace("\n", " ")[:160], flag))
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit a workflow against a rule inventory with the selected model.")
    ap.add_argument("--rules", required=True)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--generator", default="", help="generator source (optional)")
    ap.add_argument("--out", required=True, help="output JSON path, e.g. out/<slot>.audit.json")
    ap.add_argument("--model", default=None, help="builder model (default $AUDIT_MODEL or selected provider default)")
    ap.add_argument("--batch", type=int, default=12, help="rules per model call")
    ap.add_argument("--parallel", type=int, default=3, help="model calls in flight at once")
    ap.add_argument("--digest-only", action="store_true", help="print the workflow digest and exit (no model call)")
    a = ap.parse_args(argv)
    for p in [a.rules, a.workflow] + ([a.generator] if a.generator else []):
        if not pathlib.Path(p).exists():
            sys.exit("not found: " + p)
    if a.digest_only:
        print(workflow_digest(json.load(open(a.workflow))))
        return
    audit(a.rules, a.workflow, a.generator, a.out, model=a.model, batch_size=a.batch, parallel=a.parallel)


if __name__ == "__main__":
    main()
