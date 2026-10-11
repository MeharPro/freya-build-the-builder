#!/usr/bin/env python3
"""Rule inventory v2: The selected model reads the brief(s) and the tool API file and lists every rule as structured JSON,
then the inventory is cross-checked (self-consistency, dated-decision resolution, chain-of-verification) and the
structured values are compiled into a spec a generator can consume.

    .venv/bin/python builder/rules.py briefs/brief-a.md --api tools/openapi.json --out out/brief-a.rules.json
    .venv/bin/python builder/rules.py briefs/brief-a.md briefs/brief-b.md --api tools/openapi.json --out out/brief-b.rules.json
    options: --samples 1|2|3 (default 3), --no-verify (skip T14/T15), --model

As a function:

    from rules import extract_rules
    rules = extract_rules(["briefs/brief-a.md"], "tools/openapi.json", "out/brief-a.rules.json")

Pipeline (see builder/AUDIT.md; techniques T13, T14, T15, T28 of docs/research/sota-techniques.md):
  1. T13 self-consistency: the extraction runs 3x in parallel with different document orders (forward, reverse,
     latest-dated first). One merge call (USC style) groups the three inventories: union; a rule found by only one
     sample gets confidence "low"; members that disagree on a value are listed in "alternatives".
  2. Deterministic self-check (every numbered rule cited, every ISO date and `backticked` token present) and one
     gap-fill call when something is missing.
  3. T14 dated decisions and T15 chain-of-verification, in parallel:
     - every topic with more than one candidate statement (overrides, same topic, same band/floor/window...) and every
       statement that is only a proposal or discussion becomes a multiple-choice block; one call says which candidate
       is in force for the calls, with the quoted deciding sentence (in_force, superseded_by, deciding_quote,
       effective_from). A decision that takes effect inside the plausible range of call dates keeps BOTH versions
       (the older one gets effective_until), so a generator can key code on `now`.
     - every rule with values gets a question "quote the sentence(s) that set <value>"; a fresh call that sees only the
       brief answers; numbers, dates, times and codes are compared deterministically and every quote must be found
       verbatim in the brief. Mismatches lower the rule to confidence "low".
  4. The values of the rules in force are compiled into out/<slot>.spec.json (schema in builder/spec_check.py) and
     validated; everything doubtful goes to out/<slot>.rules.conflicts.md, which the builder resolves first by
     re-reading the source sentence.

Output: <out> is a JSON list of rules
  {"id": "R01", "source": "brief-a.md rule 6", "category": "<see CATEGORIES>", "topic": "callback_window",
   "text": "...", "verbatim": [...], "values": {<partial spec>}, "overrides": "" | "R07", "in_force": true | false,
   "superseded_by": "R52", "doc": "...", "doc_date": "YYYY-MM-DD" | "", "status": "decided" | ..., "confidence":
   "high" | "medium" | "low", "samples": "ABC", ... optional: "alternatives", "deciding_quote", "effective_from",
   "effective_until", "not_policy", "verification"}
plus <out .md> (Markdown), <out .conflicts.md>, <out .meta.json> and <slot>.spec.json next to it.

Needs OPENAI_API_KEY or Anthropic access. RULES_MODEL overrides the selected provider model.
Progress and every model call go to stderr ("model call: <model> | purpose: ..."); the one-line summary goes to stdout.
"""
import argparse, asyncio, copy, datetime, json, os, pathlib, re, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import spec_check  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
from model_provider import provider, model_for, cost_sum, cost_round, cost_label

DEFAULT_MODEL = "claude-opus-5-5"
# extraction, merge and verification write long structured answers: output tokens dominate the wall time, and low effort
# halves the thinking without losing rules (measured on Brief D: 91-105 rules either way). The dated-decision call keeps
# the model's default effort. RULES_EFFORT overrides (low | medium | high | "" for the default).
FAST_EFFORT = os.environ.get("RULES_EFFORT", "low") or None
# Models of the extraction samples A, B, C (comma-separated; "" = the main model). Sample A sets the order of the merged
# inventory. Measured on Brief D: Sonnet for B and C was not cheaper (longer answers) and doubled the low-confidence
# rules (the samples agree less), so all three use the main model by default.
SAMPLE_MODELS = os.environ.get("RULES_SAMPLE_MODELS", "")
MAX_BUDGET_USD_PER_CALL = 6.0

CATEGORIES = ["opening", "third_party", "identity", "disclosure", "dates", "amounts", "persuasion", "hardship",
              "confirmation", "recording", "special", "multi_product", "closing", "wording", "other"]
STATUSES = ["decided", "proposal", "rejected", "discussion", "distractor", "unclear"]
SAMPLE_LABELS = "ABC"

EXTRACT_VALUES_SCHEMA = copy.deepcopy(spec_check.VALUES_SCHEMA)
EXTRACT_VALUES_SCHEMA["properties"].pop("verbatim")      # mandatory sentences live in the rule's own "verbatim" list

RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "R01, R02, ... in document order"},
                    "source": {"type": "string", "description": "e.g. 'brief-a.md rule 6', 'brief-a.md section 7 table row early', 'memo of <date> item 3', 'openapi.json /close_call'"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "topic": {"type": "string", "description": "snake_case name of the policy point, WITHOUT any number or value (e.g. 'callback_window', 'band_deadline', 'card_floor', 'closure_days'); an old statement and the later one that changes it get the SAME topic"},
                    "text": {"type": "string", "description": "the rule, one or two sentences, numbers/dates/enum values quoted exactly"},
                    "verbatim": {"type": "array", "items": {"type": "string"}, "description": "sentences the agent must say word for word, if any"},
                    "values": EXTRACT_VALUES_SCHEMA,
                    "overrides": {"type": "string", "description": "id of the earlier rule this one replaces, else empty string"},
                    "doc": {"type": "string", "description": "the document the statement is in, e.g. 'email of 6 Oct', 'policy extract 4.2', 'memo of 12 Oct', 'code list v3', 'brief-b.md'"},
                    "doc_date": {"type": "string", "description": "the document's date, or the effective date it states for this statement, as YYYY-MM-DD; '' when undated"},
                    "author_role": {"type": "string", "description": "role of the author of the document ('' when unknown)"},
                    "status": {"type": "string", "enum": STATUSES},
                    "status_words": {"type": "string", "description": "the words that show the status, quoted ('effective from Wednesday 14 October', 'are reviewing', 'proposal', ''), else ''"},
                },
                "required": ["id", "source", "category", "topic", "text", "verbatim", "values", "overrides", "doc_date", "status"],
            },
        }
    },
    "required": ["rules"],
}

SYSTEM_PROMPT = """You are a meticulous compliance analyst. You read a bank's specification for an automated outbound phone call
(a "brief": one or more Markdown documents) plus the bank's tool API (OpenAPI JSON) and you write the complete RULE INVENTORY:
every obligation, prohibition, value, threshold, mapping and mandatory sentence that a phone agent built from this brief must
follow. The inventory is later used to build and audit the agent, so completeness and exactness matter more than brevity.

OUTPUT: JSON {"rules": [...]} matching the schema you are given. Nothing else.

WHAT COUNTS AS A RULE (list ALL of them, in the documents' original order):
1. Every numbered rule of every document. One inventory rule per numbered rule by default. Split a numbered rule into two or
   more inventory rules ONLY when it contains clearly independent obligations (for example: a wording rule plus a closing
   outcome). Each part cites the same source number ("brief-a.md rule 3").
2. Every table: the table as a whole is a rule, and every row is in "values" (bands, outcome/reason mapping, note reasons,
   code lists, holidays). Quote every cell value exactly.
3. Every unnumbered sentence that constrains behaviour: definitions (business days, holidays, windows), "never" / "always" /
   "only" statements, notes under tables, statements that a tool is not used, what is known at the start of the call, how
   to address the customer, the language to speak.
4. Every sentence the agent must say word for word goes into "verbatim" (exact text, including punctuation), and the rule
   text says when it is said.
5. Tool API constraints that the brief does not state itself and that change what the agent must do: required fields,
   enum values, formats, "one per product", "always the last call". Source: "openapi.json /<path>". Do not list API
   facts the brief already states; put them in the brief rule's "values" instead. When the brief's policy is stricter
   than the service (e.g. the service allows more wrong answers), the brief's policy is the rule.
6. A brief made of several documents (a covering mail, a policy extract, a memo, a code list, an older version and a newer
   one): list the rules of every document. Real records rarely say "this supersedes"; a later dated document that decides
   something different on the same point replaces the earlier rule. When a later document changes, tightens, relaxes or
   withdraws an earlier rule, write the NEW rule in force with "overrides": "<id of the earlier rule>" and say in its text
   what changed and since when. The new rule's text and values must be SELF-CONTAINED: the complete rule now in force
   (what stays from the old rule plus what changed; for a table, the whole table as it now reads), because the old rule is
   no longer audited. A later rule that only ADDS to an earlier one without changing it is a new rule with
   "overrides": "" (the earlier rule stays in force). The earlier rule stays in the list with its original text.
7. Status: "decided" for anything the documents state or decide (policy text, numbered rules, tables, a memo's changes).
   Statements that only TALK about a rule without deciding it -- a proposal, "we are reviewing", "may be extended, see the
   memo", a rumour, a rejected option, a past practice mentioned in passing -- are listed ONLY when they touch a rule topic,
   with status proposal / discussion / rejected and the same topic as the rule they touch (they are resolved later).
   Text that brushes policy vocabulary but decides nothing for these calls (dashboards, social events, other teams) is not
   a rule; skip it.
8. The documents may be shown to you out of their original order. "Earlier" and "later" always mean the document dates,
   then the original position, never the order in which you read them. Use the original file names in "source".

FIELDS:
- "id": R01, R02, ... in order. Never reuse an id.
- "category": opening (first sentence, who is on the line, confirmation of identity of the person), third_party (someone
  else answers, callbacks), identity (security questions, wrong answers, declining), disclosure (what may or may not be said
  before/after verification, to whom), dates (business days, holidays, deadlines, how to read dates, weekday words),
  amounts (full amount, floor, accepted ranges), persuasion (attempts, what to propose, when to stop), hardship (illness,
  death, job loss, support transfer), confirmation (read-back, confirm question, changes at read-back), recording (tool
  call rules for recording a promise/note/callback, retries, "recorded" wording), special (already paid, dispute,
  restructuring, human, scam, robot, unanswerable questions, does not want to talk), multi_product (several products),
  closing (close_call outcomes/reasons, last tool call, thanks and goodbye), wording (how to address, language, forbidden
  words, mandatory sentences not tied to another category), other (call variables, API constraints, anything else).
- "text": the rule in one or two sentences. Quote numbers, dates, times, enum values and tool names exactly as in the
  document (keep `backticks` around identifiers). If the rule depends on another rule, name it ("see rule 30").
- "values": a PARTIAL SPEC holding only the keys this rule sets (the schema lists the keys; {} when nothing structured).
  Fill them from the documents' words only; never add a value the documents do not state, never a default.
  * calendar: business_weekdays ("Mon".."Sun") and holidays [{date: YYYY-MM-DD, name}] = closure days / bank holidays.
  * bands: one entry per lateness band, min_days / max_days inclusive (max_days null when open-ended); deadline_rule:
    "the n-th business day after the call date" -> {type: business_days_after, n, adjust: none};
    "n calendar days after the call date, if that is not a business day the last business day before it" ->
    {type: calendar_days_after, n, adjust: previous_business_day}; a fixed date -> {type: fixed, date}; anything else ->
    {type: other, text}; attempts = persuasion attempts in that band. A band that is "treated as" another band:
    same_as = that band's name (no deadline_rule needed).
  * floors: [{product_types: [API product types], rule: {type: field, field: <API product field>}}] or
    {type: multiple, factor, field, cap_to_full} or {type: percent, percent, field, round} or {type: other, text}.
  * attempt_ladder: one entry per persuasion attempt: attempt number, bands it applies to ([] = all), amount (full = the
    full amount; floor; in_play = the full amount, or the floor once the customer said the full amount is too much),
    date_rule (the date proposed, in the document's words), text (any mandatory preface).
  * callback: open / close as HH:MM (24 h), same_day (today allowed), later_than_now, days_ahead_business (how many
    business days after today are allowed), days_ahead_calendar (if counted in calendar days), text.
  * identity: one entry per security question, in the asking order: order 1.., field (API enum), hint_values (API hint
    enum values the brief handles), retry_rule (the brief's words on retries).
  * max_wrong_answers: the wrong answer at which the AGENT ends the check (the brief's policy number).
  * outcomes: [{outcome (API close_call outcome), reason (API enum value or the brief's code exactly as written; "" when
    none), when}] -- the whole outcome/code table in the table rule; a rule that names its own close lists that row.
  * note_reasons: [{reason (API add_note reason), when, text_must_contain}].
  * forbidden_words_before_verification: the words exactly as listed.
  * text: anything structured that fits no field.
  When a later document changes a structured value, the overriding rule's values hold the COMPLETE new structure (every
  band, every holiday including the new one, the whole outcome table as it now reads).
- "verbatim": [] when nothing must be said word for word.
- "overrides": "" unless this rule replaces an earlier listed rule.

KEEP IT COMPACT (the inventory is long and is written three times): "text" at most about 35 words; "values" hold only the
structured fields -- add a "text" inside values only for what the fields cannot hold, never a copy of the rule text;
"doc" at most 6 words; "author_role" and "status_words" only for statements that are not plain decided policy or that come
from a dated change document (a memo, a newer version), else "".

Be exhaustive: a brief of 47 numbered rules with three tables and a few definitions yields 50 to 65 inventory rules; a
raw-material pack (mail + policy + memo + code list) yields 60 to 80. Do not summarise several numbered rules into one.
Do not skip a rule because it looks obvious or repeats another one. Do not invent rules that are not in the documents."""

# ----------------------------------------------------------------------------------------------- Claude call
def _parse_json_text(text):
    """Find the first JSON object or list in a model answer (handles code fences and chatter)."""
    if text is None:
        raise ValueError("empty answer")
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON in answer")
    i = min(starts)
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(s[i:])
    return obj


async def ask_json_async(prompt, system_prompt, schema, purpose, model=None, max_budget_usd=MAX_BUDGET_USD_PER_CALL,
                         log=None, effort=None):
    """One Claude call, no tools, structured JSON out. Returns (obj, info). Retries once on invalid JSON.

    info = {"model", "cost_usd", "seconds", "turns", "attempts", "usage"}
    """
    if provider() == "openai":
        from model_provider import ask_json_openai
        return await ask_json_openai(prompt, system_prompt, schema, purpose, model or model_for("rules"),
                                     log or (lambda s: print(s, file=sys.stderr, flush=True)), effort)
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
    model = model or model_for("rules")
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    info = {"model": model, "cost_usd": 0.0, "seconds": 0.0, "turns": 0, "attempts": 0, "usage": {}}
    last_err = None
    # the SDK passes the system prompt on the CLI command line: a big one (the audit's generator + digest, ~90 KB)
    # fails with "[Errno 7] Argument list too long" (seen in the cloud rehearsal). The user message goes through stdin,
    # so a large context moves there under a <context> tag and the system prompt stays one line.
    if system_prompt and len(system_prompt) > 12000:
        prompt = "<context>\n" + system_prompt + "\n</context>\n\n" + prompt
        system_prompt = "Follow the instructions and context given in the <context> block of the user message exactly."
    for attempt in range(2):
        info["attempts"] = attempt + 1
        t0 = time.time()
        log("model call: %s | purpose: %s%s" % (model, purpose, " (retry after invalid JSON)" if attempt else ""))
        options = ClaudeAgentOptions(
            cwd=str(ROOT), model=model, tools=[], allowed_tools=[], permission_mode="dontAsk", max_turns=4,
            setting_sources=[], system_prompt=system_prompt, max_budget_usd=max_budget_usd,
            output_format={"type": "json_schema", "schema": schema}, effort=effort)
        p = prompt if not attempt else (prompt + "\n\nYour previous answer was not valid JSON for the schema (%s). "
                                                 "Answer again with valid JSON only." % last_err)
        text, structured, result = "", None, None
        async for m in query(prompt=p, options=options):
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, TextBlock):
                        text += b.text
            elif isinstance(m, ResultMessage):
                result = m
                structured = m.structured_output
                info["cost_usd"] += m.total_cost_usd or 0.0
                info["turns"] += m.num_turns or 0
                info["usage"] = m.usage or {}
        info["seconds"] += time.time() - t0
        if result is not None and result.is_error:
            last_err = "result error: %s %s" % (result.subtype, (result.errors or [result.result])[:1])
            log("model call failed: " + last_err)
            continue
        try:
            obj = structured if structured is not None else _parse_json_text(result.result if result and result.result else text)
            return obj, info
        except Exception as e:
            last_err = "%s: %s" % (type(e).__name__, e)
            log("invalid JSON: " + last_err)
    raise RuntimeError("Claude did not return valid JSON after 2 attempts: %s" % last_err)


def ask_json(*a, **kw):
    return asyncio.run(ask_json_async(*a, **kw))


# ----------------------------------------------------------------------------------------------- inputs
def api_digest(api_path):
    """A compact text of the tool API: path, summary, body fields with enums/formats/descriptions, required."""
    api = json.load(open(api_path))
    out = ["Tool API file: %s" % pathlib.Path(api_path).name]
    for p, v in (api.get("paths") or {}).items():
        op = v.get("post") or v.get("get") or next(iter(v.values()), {})
        out.append("- %s: %s" % (p, " ".join((op.get("summary") or op.get("description") or "").split())))
        body = ((op.get("requestBody") or {}).get("content") or {}).get("application/json", {}).get("schema", {})
        req = body.get("required") or []
        for f, fs in (body.get("properties") or {}).items():
            bits = [fs.get("type", "")]
            if fs.get("enum"):
                bits.append("enum " + json.dumps(fs["enum"]))
            if fs.get("format"):
                bits.append("format " + fs["format"])
            if fs.get("description"):
                bits.append(" ".join(fs["description"].split()))
            out.append("    %s%s: %s" % (f, "*" if f in req else "", "; ".join(b for b in bits if b)))
        resp = ((op.get("responses") or {}).get("200") or {}).get("content", {}).get("application/json", {}).get("schema", {})
        if resp:
            out.append("    response: " + json.dumps(resp)[:700])
    out.append("(* = required field)")
    return "\n".join(out)


def read_briefs(briefs):
    parts = []
    for b in briefs:
        p = pathlib.Path(b)
        parts.append("=" * 20 + " DOCUMENT FILE: %s " % p.name + "=" * 20 + "\n" + p.read_text())
    return "\n\n".join(parts)


# ----------------------------------------------------------------------------------------------- document orders (T13)
_MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                           "september", "october", "november", "december"])}
_HEADER_WORDS = re.compile(r"\b(date|dated|issued|effective|supplied|sent|version|updated|memo|re)\b", re.I)


def _dates_in(line):
    out = []
    for y, m, d in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", line):
        out.append("%s-%s-%s" % (y, m, d))
    for d, mon, y in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})\b", line):
        if mon.lower() in _MONTHS:
            out.append("%s-%02d-%02d" % (y, _MONTHS[mon.lower()], int(d)))
    for mon, d, y in re.findall(r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", line):
        if mon.lower() in _MONTHS:
            out.append("%s-%02d-%02d" % (y, _MONTHS[mon.lower()], int(d)))
    return out


def split_documents(briefs):
    """Cut every brief file into parts: on horizontal rules ('---') when there are any, else on '## ' headings.
    Each part gets its header date (a date on one of its first lines that also carries a word like Date/issued/effective)."""
    parts = []
    for fi, b in enumerate(briefs):
        p = pathlib.Path(b)
        text = p.read_text()
        chunks = [c for c in re.split(r"\n\s*-{3,}\s*\n", text) if c.strip()]
        if len(chunks) < 2:
            chunks = [c for c in re.split(r"\n(?=## )", text) if c.strip()]
        for k, c in enumerate(chunks):
            head = [l for l in c.splitlines() if l.strip() and not l.lstrip().startswith("|")][:8]
            ds = [d for l in head if _HEADER_WORDS.search(l) for d in _dates_in(l)]
            parts.append({"file": p.name, "fi": fi, "k": k + 1, "n": len(chunks), "pos": len(parts),
                          "text": c.strip("\n"), "date": max(ds) if ds else ""})
    return parts


def document_orders(parts):
    """Three orders of the parts: forward, reverse, latest-dated first (memo first)."""
    fwd = list(parts)
    rev = list(reversed(parts))
    dated = sorted([p for p in parts if p["date"]], key=lambda p: (p["date"], p["pos"]), reverse=True)
    if dated:
        latest = dated + [p for p in parts if not p["date"]]
    elif len({p["fi"] for p in parts}) > 1:     # undated files: the later file is the newer one
        latest = [p for fi in sorted({p["fi"] for p in parts}, reverse=True) for p in parts if p["fi"] == fi]
    else:                                         # one undated file: second half first
        h = len(parts) // 2
        latest = parts[h:] + parts[:h]
    return [("forward", fwd), ("reverse", rev), ("latest-dated first", latest)]


def render_parts(order, order_name):
    n = len(order)
    out = ["The documents are cut into %d part(s), shown here in %s order. 'position' is the original order. Earlier and "
           "later always mean the document dates, then the original position, never the order shown here." % (n, order_name)]
    for p in order:
        out.append("=" * 16 + " DOCUMENT FILE: %s | part %d of %d | position %d of %d%s " % (
            p["file"], p["k"], p["n"], p["pos"] + 1, n, (" | header date " + p["date"]) if p["date"] else "") + "=" * 16
            + "\n" + p["text"])
    return "\n\n".join(out)

def split_groups(parts, k):
    """k contiguous groups of parts with about the same amount of text (fewer when there are fewer parts)."""
    k = max(1, min(k, len(parts)))
    if k == 1:
        return [list(parts)]
    total = sum(len(p["text"]) for p in parts)
    groups, cur, acc = [], [], 0
    for i, p in enumerate(parts):
        cur.append(p)
        acc += len(p["text"])
        left_parts, left_groups = len(parts) - i - 1, k - len(groups) - 1
        if left_groups > 0 and (acc >= total * (len(groups) + 1) / k or left_parts == left_groups):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


# ----------------------------------------------------------------------------------------------- self-check
def numbered_rules(text):
    """Numbers of the numbered rules in a Markdown document (lines like '12. ...', not table rows)."""
    nums = []
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}(\d{1,3})\.\s+\S", line)
        if m and not line.lstrip().startswith("|"):
            nums.append(int(m.group(1)))
    return nums


def _flatten_text(obj, acc=None):
    """All strings of a JSON object joined with newlines (no JSON escaping, so quoted tokens match)."""
    acc = [] if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.append(str(k)); _flatten_text(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _flatten_text(v, acc)
    else:
        acc.append(str(obj))
    return acc


def cited_numbers(rule, fname):
    """Rule numbers that a rule's source cites (e.g. 'rule 6', 'rules 30 and 41', 'rules 3-5')."""
    src = rule.get("source", "")
    nums = set()
    for m in re.finditer(r"(?:rules?|items?|points?|paragraphs?|clauses?|nos?\.|#)\s*([\d,\s\-–and&]+)", src, re.I):
        chunk = m.group(1)
        for a, b in re.findall(r"(\d+)\s*[-–]\s*(\d+)", chunk):
            nums.update(range(int(a), int(b) + 1))
        for n in re.findall(r"\d+", re.sub(r"(\d+)\s*[-–]\s*(\d+)", " ", chunk)):
            nums.add(int(n))
    return nums


def example_tokens(text):
    """`backticked` tokens that occur ONLY in an 'Example' column of a Markdown table (sample values, not rules)."""
    ex, other = set(), set()
    header = None
    for line in text.splitlines():
        st = line.strip()
        if not st.startswith("|"):
            header = None
            other |= set(re.findall(r"`([^`\n]{2,40})`", line))
            continue
        cells = [c.strip() for c in st.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            other |= set(re.findall(r"`([^`\n]{2,40})`", line))
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        for i, c in enumerate(cells):
            toks = set(re.findall(r"`([^`\n]{2,40})`", c))
            (ex if i < len(header) and "example" in header[i] else other).update(toks)
    return ex - other


def self_check(rules, briefs):
    """Deterministic completeness check. Returns {"missing_numbers": {file: [n,...]}, "missing_tokens": [...]}"""
    dump = "\n".join(_flatten_text(rules)).lower()
    missing_numbers, missing_tokens = {}, []
    for b in briefs:
        text = pathlib.Path(b).read_text()
        fname = pathlib.Path(b).name
        nums = numbered_rules(text)
        cited = set()
        for r in rules:
            src = r.get("source", "")
            # a source cites this file when it names it, or when there is only one brief
            if fname in src or pathlib.Path(b).stem in src or len(briefs) == 1:
                cited |= cited_numbers(r, fname)
        miss = sorted(n for n in nums if n not in cited)
        if miss:
            missing_numbers[fname] = miss
        for tok in sorted(set(re.findall(r"\d{4}-\d{2}-\d{2}", text))):
            if tok not in dump:
                missing_tokens.append(tok)
        examples = example_tokens(text)
        for tok in sorted(set(re.findall(r"`([^`\n]{2,40})`", text)) - examples):
            t = tok.lower()
            if t not in dump and t.replace("`", "") not in dump:
                missing_tokens.append(tok)
    return {"missing_numbers": missing_numbers, "missing_tokens": sorted(set(missing_tokens))}


# ----------------------------------------------------------------------------------------------- normalise
_EXTRA = ("topic", "doc", "doc_date", "author_role", "status", "status_words", "confidence", "samples", "alternatives",
          "value_difference", "deciding_quote", "deciding_quote_found", "effective_from", "effective_until", "not_policy",
          "verification", "origin", "members", "value_difference_resolved", "stale_values")


def normalise(rules, keep_flags=False):
    """Validate shape, renumber ids in order, resolve overrides, mark in_force / superseded_by.
    keep_flags: keep in_force / superseded_by as they are (after T14) instead of recomputing them from overrides."""
    if isinstance(rules, dict):
        rules = rules.get("rules", [])
    if not isinstance(rules, list) or not rules:
        raise ValueError("inventory is not a non-empty list")
    clean, old_to_new = [], {}
    for i, r in enumerate(rules):
        if not isinstance(r, dict) or not r.get("text"):
            raise ValueError("rule %d has no text" % i)
        new_id = "R%02d" % (i + 1)
        old_id = str(r.get("id", new_id))
        if old_id in old_to_new:
            raise ValueError("duplicate rule id: " + old_id)
        old_to_new[old_id] = new_id
        cat = r.get("category") if r.get("category") in CATEGORIES else "other"
        verb = r.get("verbatim") or []
        if isinstance(verb, str):
            verb = [verb]
        vals = r.get("values") if isinstance(r.get("values"), dict) else {}
        vals = {k: v for k, v in vals.items() if v not in (None, "", [], {})}
        c = {"id": new_id, "source": str(r.get("source", "")), "category": cat, "text": str(r["text"]).strip(),
             "verbatim": [str(v) for v in verb], "values": vals, "overrides": str(r.get("overrides") or ""),
             "in_force": bool(r.get("in_force", True)) if keep_flags else True,
             "superseded_by": str(r.get("superseded_by") or "") if keep_flags else ""}
        for k in _EXTRA:
            if k in r and r[k] not in (None, ""):
                c[k] = r[k]
        c.setdefault("topic", "")
        c["status"] = c.get("status") if c.get("status") in STATUSES else "decided"
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(c.get("doc_date", ""))):
            c["doc_date"] = ""
        clean.append(c)
    by_id = {r["id"]: r for r in clean}
    replacements = {}
    for r in clean:
        if r["overrides"]:
            tgt = old_to_new.get(r["overrides"], r["overrides"])
            if tgt not in by_id:
                raise ValueError("unknown override: " + r["overrides"])
            if tgt == r["id"]:
                raise ValueError("rule overrides itself: " + r["id"])
            if tgt in replacements and not keep_flags:
                raise ValueError("multiple replacements for " + tgt + "; resolve their order explicitly")
            replacements[tgt] = r["id"]
            if tgt in by_id and tgt != r["id"]:
                r["overrides"] = tgt
                if not keep_flags:
                    by_id[tgt]["in_force"] = False
                    by_id[tgt]["superseded_by"] = r["id"]
            else:
                r["overrides"] = ""
        if keep_flags and r["superseded_by"]:
            r["superseded_by"] = old_to_new.get(r["superseded_by"], r["superseded_by"])
            if r["superseded_by"] not in by_id:
                r["superseded_by"] = ""
    for r in clean:
        visited = set()
        cursor = r
        while cursor.get("overrides"):
            if cursor["id"] in visited:
                raise ValueError("cyclic override chain")
            visited.add(cursor["id"])
            cursor = by_id[cursor["overrides"]]
    if not keep_flags:
        for r in clean:
            if r["status"] != "decided" and r["in_force"]:
                # a proposal / discussion is not a rule in force unless T14 decides otherwise
                r["in_force"] = False
                r["not_policy"] = True
    return clean


def require_numbered_coverage(check):
    if check.get("missing_numbers"):
        raise ValueError("Inventory omits numbered rules: %s" % check["missing_numbers"])


# ----------------------------------------------------------------------------------------------- atoms (values to compare)
_SKIP_NUM_KEYS = {"order", "attempt", "min_days"}   # min_days is often derived (previous max + 1); spec_check checks contiguity
_STR_ATOM_KEYS = {"date", "open", "close", "reason", "outcome", "field"}


def value_atoms(values):
    """The checkable atoms of a values object: numbers (not 0, not order/attempt), ISO dates, HH:MM, codes and fields."""
    nums, dates, strs = set(), set(), set()

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "identity":          # field names are checked against the API by spec_check; the order is a number
                    v = [{kk: vv for kk, vv in (q or {}).items() if kk != "field"} for q in v] if isinstance(v, list) else v
                walk(v, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, bool) or o is None:
            return
        elif isinstance(o, (int, float)):
            if key not in _SKIP_NUM_KEYS and o != 0:
                nums.add(_num(o))
        elif isinstance(o, str) and key in _STR_ATOM_KEYS and o.strip():
            s = o.strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                dates.add(s)
            elif re.fullmatch(r"\d{1,2}:\d{2}", s):
                dates.add(s.zfill(5))
            else:
                strs.add(s.lower())
    walk(values)
    return nums, dates, strs


def _num(x):
    try:
        f = float(x)
    except Exception:
        return str(x)
    return str(int(f)) if f == int(f) else ("%.4f" % f).rstrip("0").rstrip(".")


_NUM_WORDS = {w: str(i) for i, ws in enumerate([[], ["one", "first", "once"], ["two", "second", "twice", "both"],
               ["three", "third", "thrice"], ["four", "fourth"], ["five", "fifth"], ["six", "sixth"], ["seven", "seventh"],
               ["eight", "eighth"], ["nine", "ninth"], ["ten", "tenth"], ["eleven", "eleventh"], ["twelve", "twelfth"]]) for w in ws}


def text_atoms(text):
    """Numbers, ISO dates and HH:MM times in a free text (dates and times removed before numbers are read). Number words
    and ordinals count as numbers, and 'the next <unit>' counts as 1."""
    t = text or ""
    t = re.sub(r"\b(%s)\b" % "|".join(_NUM_WORDS), lambda m: " %s " % _NUM_WORDS[m.group(1).lower()], t, flags=re.I)
    t = re.sub(r"\bnext (business |calendar |working )?(day|week)", lambda m: " 1 " + m.group(0), t, flags=re.I)
    dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", t))
    t2 = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", t)
    times = {s.zfill(5) for s in re.findall(r"\b\d{1,2}:\d{2}\b", t2)}
    t3 = re.sub(r"\b\d{1,2}:\d{2}\b", " ", t2)
    nums = {_num(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t3)}
    return nums, dates | times


def _norm_text(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    s = re.sub(r"[*`|#>]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_found(quote, brief_norm):
    """A quote is found when (each piece of) it occurs in the normalised brief. Pieces: split on ellipses; >= 12 chars."""
    q = _norm_text(quote).strip(" .,;:'\"")
    if not q:
        return False
    pieces = [p.strip(" .,;:'\"") for p in re.split(r"\.\.\.|…|\[\.\.\.\]", q)]
    pieces = [p for p in pieces if len(p) >= 12] or [q]
    return all(p in brief_norm for p in pieces)


# ----------------------------------------------------------------------------------------------- T13 merge (USC)
MERGE_SCHEMA = {
    "type": "object",
    "properties": {"groups": {"type": "array", "items": {"type": "object", "properties": {
        "members": {"type": "array", "items": {"type": "string"}},
        "best": {"type": "string"},
        "values_differ": {"type": "boolean"},
        "difference": {"type": "string"}},
        "required": ["members", "best", "values_differ", "difference"]}}},
    "required": ["groups"],
}

MERGE_SYSTEM = """You merge independent rule inventories of the same bank brief, written by different analysts who read the
documents in different orders (universal self-consistency). You decide which entries state the SAME rule.

OUTPUT: JSON {"groups": [...]}. Each group: "members" (entry ids, at most one per inventory; inventories are the id
prefixes A, B, C), "best" (the member whose text and values are the most complete and exact), "values_differ" (true when
the members disagree on any number, date, time, code / enum value, field name, attempt count or mandatory wording),
"difference" (when values_differ: what differs, quoting each member's value with its id; else "").

- Same rule = same obligation from the same document (an old rule and the memo rule that changes it are DIFFERENT rules:
  separate groups). Two entries that only share a category are not the same rule.
- Every entry id appears in exactly one group. An entry that matches nothing is a group of its own.
- When one analyst split a rule in two and another kept it whole, group the whole entry with the part it matches best;
  the other part is its own group.
- Keep the groups in the documents' order (the order of inventory A where possible)."""


def _compact(r):
    s = "%s | %s | %s | topic %s | %s%s | %s" % (r["id"], r.get("source", ""), r.get("category", ""), r.get("topic", ""),
                                                 r.get("status", "decided"), (" | overrides " + r["overrides"]) if r.get("overrides") else "",
                                                 r.get("text", ""))
    if r.get("values"):
        s += " | values " + json.dumps(r["values"], ensure_ascii=False, separators=(",", ":"))
    if r.get("verbatim"):
        s += " | verbatim " + json.dumps(r["verbatim"], ensure_ascii=False)
    return s


def relabel(rules, label):
    """Prefix a sample's ids (R07 -> B07) and map its overrides."""
    m = {}
    out = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict) or not r.get("text"):
            continue
        nid = "%s%02d" % (label, len(out) + 1)
        m[str(r.get("id", ""))] = nid
        r = dict(r); r["id"] = nid
        out.append(r)
    for r in out:
        r["overrides"] = m.get(str(r.get("overrides") or ""), "")
    return out


def resolve_ref(ref, rules, before=None):
    """An 'overrides' written as a source ('brief-a.md rule 28') -> the id of the rule with that source. Exact source match
    first, then the same file and an overlapping rule number. Only rules listed before `before` (an index) qualify."""
    ref_l = (ref or "").strip().lower()
    if not ref_l:
        return ""
    pool = rules[:before] if before is not None else rules
    for r in pool:
        if r.get("source", "").strip().lower() == ref_l:
            return r["id"]
    nums = cited_numbers({"source": ref}, "")
    files = [w for w in re.findall(r"[\w.-]+\.md", ref_l)]
    if nums:
        for r in pool:
            src = r.get("source", "").lower()
            if (not files or any(f in src for f in files)) and nums & cited_numbers(r, ""):
                return r["id"]
    for r in pool:                                       # 'memo item 3' style: the longest source contained in the ref
        src = r.get("source", "").strip().lower()
        if len(src) >= 12 and (src in ref_l or ref_l in src):
            return r["id"]
    return ""


def relabel_groups(lists, label):
    """Join the rule lists of one sample's calls (one per group of parts, in order) and relabel (R07 -> B07).
    'overrides' is an id of the same call, or a source reference resolved against the whole sample."""
    out, ref = [], []
    for li, rules in enumerate(lists):
        m = {}
        start = len(out)
        for r in rules or []:
            if not isinstance(r, dict) or not r.get("text"):
                continue
            nid = "%s%02d" % (label, len(out) + 1)
            m[str(r.get("id", ""))] = nid
            r = dict(r); r["id"] = nid
            out.append(r)
        for r in out[start:]:
            o = str(r.get("overrides") or "")
            r["overrides"] = m.get(o, "")
            if o and not r["overrides"]:
                ref.append((r, o))
    for i, (r, o) in enumerate(ref):
        rid = resolve_ref(o, out)
        r["overrides"] = rid if rid != r["id"] else ""
    return out


def merge_samples(samples, groups):
    """Deterministic union from the merge call's groups. samples: {label: [rules]}. Returns merged rules (ids G###)."""
    by_id = {r["id"]: r for rs in samples.values() for r in rs}
    pos = {}
    for lab, rs in samples.items():
        for i, r in enumerate(rs):
            pos[r["id"]] = (lab, i)
    seen, clean = set(), []
    for g in groups or []:
        mem = [m for m in (g.get("members") or []) if m in by_id and m not in seen]
        if not mem:
            continue
        seen.update(mem)
        best = g.get("best") if g.get("best") in mem else sorted(mem)[0]
        clean.append({"members": mem, "best": best, "values_differ": bool(g.get("values_differ")),
                      "difference": str(g.get("difference") or "")})
    for i in by_id:
        if i not in seen:
            clean.append({"members": [i], "best": i, "values_differ": False, "difference": ""})
    # order: by the position of the inventory-A member; groups without one follow their predecessor in their own sample
    first = sorted(samples)[0]
    member_group = {m: gi for gi, g in enumerate(clean) for m in g["members"]}

    def key(gi):
        g = clean[gi]
        a = [pos[m][1] for m in g["members"] if pos[m][0] == first]
        if a:
            return (a[0], 0)
        lab, i = pos[g["members"][0]]
        rs = samples[lab]
        for j in range(i - 1, -1, -1):
            gj = member_group.get(rs[j]["id"])
            aj = [pos[m][1] for m in clean[gj]["members"] if pos[m][0] == first] if gj is not None else []
            if aj:
                return (aj[0], 1 + i - j)
        return (-1, i)
    order = sorted(range(len(clean)), key=key)
    gid = {gi: "G%03d" % (n + 1) for n, gi in enumerate(order)}
    merged = []
    n_samples = len(samples)
    for gi in order:
        g = clean[gi]
        b = by_id[g["best"]]
        r = copy.deepcopy(b)
        r["id"] = gid[gi]
        labs = sorted({pos[m][0] for m in g["members"]})
        r["samples"] = "".join(labs)
        r["members"] = g["members"]
        r["confidence"] = "high" if len(labs) >= 3 or len(labs) == n_samples else ("medium" if len(labs) == 2 else "low")
        ov = ""
        for m in [g["best"]] + [x for x in g["members"] if x != g["best"]]:
            o = by_id[m].get("overrides") or ""
            if o in member_group and member_group[o] != gi:
                ov = gid[member_group[o]]
                break
        r["overrides"] = ov
        # differing values: the merge call's judgement, or numbers/dates that conflict in both directions
        alts, auto = [], []
        bn, bd, _ = value_atoms(b.get("values") or {})
        for m in g["members"]:
            if m == g["best"]:
                continue
            o = by_id[m]
            on, od, _ = value_atoms(o.get("values") or {})
            if ((on - bn) and (bn - on)) or ((od - bd) and (bd - od)):
                auto.append("%s has %s where %s has %s" % (m, sorted((on - bn) | (od - bd)), g["best"], sorted((bn - on) | (bd - od))))
            if g["values_differ"] or auto:
                if json.dumps(o.get("values"), sort_keys=True) != json.dumps(b.get("values"), sort_keys=True) or o.get("verbatim") != b.get("verbatim"):
                    alts.append({"id": m, "text": o.get("text", ""), "values": o.get("values") or {}, "verbatim": o.get("verbatim") or []})
        if (g["values_differ"] or auto) and alts:
            r["alternatives"] = alts
            r["value_difference"] = "; ".join(x for x in [g["difference"]] + auto if x)
        merged.append(r)
    return merged


async def merge_call(samples, model, log):
    blocks = []
    for lab in sorted(samples):
        blocks.append("INVENTORY %s (%d entries; id | source | category | topic | status | text | values | verbatim):\n%s" % (
            lab, len(samples[lab]), "\n".join(_compact(r) for r in samples[lab])))
    prompt = ("Merge these %d inventories of the same brief into groups of entries that state the same rule.\n\n%s\n\n"
              "Answer with the JSON only." % (len(samples), "\n\n".join(blocks)))
    return await ask_json_async(prompt, MERGE_SYSTEM, MERGE_SCHEMA, "merge %d sampled inventories (self-consistency union, flag "
                                "minority rules and differing values)" % len(samples), model=model, log=log, effort=FAST_EFFORT)

# ----------------------------------------------------------------------------------------------- T14 dated decisions
DECIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "call_date_range": {"type": "object", "properties": {"earliest": {"type": "string"}, "latest": {"type": "string"},
                                                             "basis": {"type": "string"}}, "required": ["earliest", "latest", "basis"]},
        "blocks": {"type": "array", "items": {"type": "object", "properties": {
            "block": {"type": "string"},
            "decisions": {"type": "array", "items": {"type": "object", "properties": {
                "rule": {"type": "string"},
                "status": {"type": "string", "enum": ["in_force", "superseded", "not_policy"]},
                "superseded_by": {"type": "string"},
                "effective_from": {"type": "string"},
                "deciding_quote": {"type": "string"}},
                "required": ["rule", "status", "superseded_by", "effective_from", "deciding_quote"]}},
            "reason": {"type": "string"}},
            "required": ["block", "decisions", "reason"]}},
    },
    "required": ["call_date_range", "blocks"],
}

DECIDE_SYSTEM = """You resolve which statement of a bank's documents is IN FORCE for the phone calls the documents prepare.
You get the documents and numbered blocks; each block lists candidate statements about one topic with their document,
date, author role and status words. For each candidate say:
- "in_force": it applies to the calls (several candidates of a block can be in force together when they complement each
  other: different parts of the same topic, or an addition that changes nothing else);
- "superseded": a later DECIDED statement changes the same point; "superseded_by" = that candidate's id;
- "not_policy": a proposal, a rejected option, discussion, a rumour, a past practice, an announcement that something will
  be decided later, or a distractor; it decides nothing.
Rules of evidence: the most recent dated decision wins, whether or not it says "supersedes"; proposals and discussion
decide nothing; if the latest discussion never decided, the last decided rule stays in force; a document that says another
document wins on conflicts (e.g. "where this mail and the policy disagree, the policy wins") is a decision too.
"deciding_quote": copy, character for character, the one sentence (or table row) of the documents that decides the
candidate's status (for in_force: the sentence that sets it; for superseded: the sentence of the later document that
changes it; for not_policy: the words that show it is not decided). "effective_from": YYYY-MM-DD when the documents give
a date from which the candidate applies (a memo's effective date), else "".
"call_date_range": the plausible range of dates of the calls (YYYY-MM-DD; go-live, the example `now`, campaign dates;
"" when the documents give nothing) and the basis in a few words."""


def decision_blocks(rules, max_size=8):
    """Topics with more than one candidate statement, and single statements that are not decided policy."""
    ids = [r["id"] for r in rules]
    parent = {i: i for i in ids}
    size = {i: 1 for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b, limit=None):
        ra, rb = find(a), find(b)
        if ra == rb or (limit and size[ra] + size[rb] > limit):
            return
        parent[rb] = ra
        size[ra] += size[rb]
    by_id = {r["id"]: r for r in rules}
    for r in rules:                                     # strong links: overrides, same topic
        if r.get("overrides") in by_id:
            union(r["id"], r["overrides"])
    topics = {}
    for r in rules:
        t = re.sub(r"[^a-z0-9]+", "_", (r.get("topic") or "").lower()).strip("_")
        if t:
            topics.setdefault(t, []).append(r["id"])
    for t, members in topics.items():
        for m in members[1:]:
            union(members[0], m, limit=max_size)
    ent = {}                                            # weak links: the same structured entity
    for r in rules:
        v = r.get("values") or {}
        keys = set()
        if v.get("callback"):
            keys.add(("callback",))
        if v.get("max_wrong_answers") is not None:
            keys.add(("max_wrong",))
        if (v.get("calendar") or {}).get("holidays"):
            keys.add(("holidays",))
        for b in v.get("bands") or []:
            keys.add(("band", str(b.get("name", "")).strip().lower()[:12]))
        for f in v.get("floors") or []:
            for pt in f.get("product_types") or []:
                keys.add(("floor", pt))
        for a in v.get("attempt_ladder") or []:
            keys.add(("attempt", a.get("attempt")))
        for k in keys:
            ent.setdefault(k, []).append(r["id"])
    for k, members in ent.items():
        for m in members[1:]:
            union(members[0], m, limit=max_size)
    comps = {}
    for i in ids:
        comps.setdefault(find(i), []).append(i)
    blocks = []
    for members in comps.values():
        if len(members) > 1 or by_id[members[0]].get("status", "decided") != "decided":
            blocks.append(sorted(members, key=ids.index))
    blocks.sort(key=lambda m: ids.index(m[0]))
    return blocks


def _candidate_line(r):
    s = "  [%s] document: %s | date: %s | author: %s | status: %s%s | source: %s%s\n      %s" % (
        r["id"], r.get("doc", "") or "?", r.get("doc_date", "") or "undated", r.get("author_role", "") or "?",
        r.get("status", "decided"), (" (\"%s\")" % r["status_words"]) if r.get("status_words") else "", r.get("source", ""),
        (" | overrides " + r["overrides"]) if r.get("overrides") else "", r.get("text", ""))
    if r.get("values"):
        s += "\n      values: " + json.dumps(r["values"], ensure_ascii=False, separators=(",", ":"))
    return s


async def decide_call(rules, blocks, docs, model, log):
    by_id = {r["id"]: r for r in rules}
    txt = []
    for bi, members in enumerate(blocks):
        topic = by_id[members[0]].get("topic") or by_id[members[0]].get("category")
        txt.append("BLOCK T%d -- topic: %s\n%s" % (bi + 1, topic, "\n".join(_candidate_line(by_id[m]) for m in members)))
    prompt = ("DOCUMENTS (original order):\n\n%s\n\nBLOCKS:\n\n%s\n\nFor every block and every candidate in it: which is in "
              "force for the calls? Answer with the JSON only." % (docs, "\n\n".join(txt)))
    return await ask_json_async(prompt, DECIDE_SYSTEM, DECIDE_SCHEMA, "resolve %d dated-decision block(s) (which candidate "
                                "is in force, deciding quote, effective date)" % len(blocks), model=model, log=log)


def _iso_or_empty(s):
    s = str(s or "").strip()
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else ""


def apply_decisions(rules, blocks, ans, brief_norm):
    """Apply the T14 answer deterministically. Returns (call_date_range, log of decisions for the conflicts file)."""
    by_id = {r["id"]: r for r in rules}
    rng = ans.get("call_date_range") or {}
    rng = {"earliest": _iso_or_empty(rng.get("earliest")), "latest": _iso_or_empty(rng.get("latest")),
           "basis": str(rng.get("basis") or "")}
    notes = []
    block_of = {}
    for bi, members in enumerate(blocks):
        for m in members:
            block_of[m] = bi
    for b in ans.get("blocks") or []:
        m = re.search(r"\d+", str(b.get("block", "")))
        bi = int(m.group()) - 1 if m else -1
        if not 0 <= bi < len(blocks):
            continue
        members = blocks[bi]
        entry = {"block": "T%d" % (bi + 1), "topic": by_id[members[0]].get("topic", ""), "reason": b.get("reason", ""), "decisions": []}
        for d in b.get("decisions") or []:
            rid = d.get("rule")
            if rid not in by_id or rid not in members:
                continue
            r = by_id[rid]
            st = d.get("status")
            q = str(d.get("deciding_quote") or "").strip()
            if q:
                r["deciding_quote"] = q
                r["deciding_quote_found"] = quote_found(q, brief_norm)
            ef = _iso_or_empty(d.get("effective_from"))
            if ef:
                r["effective_from"] = ef
            if st == "in_force":
                r["in_force"], r["superseded_by"] = True, ""
                r.pop("not_policy", None)
            elif st == "superseded":
                sb = d.get("superseded_by") if d.get("superseded_by") in by_id and d.get("superseded_by") != rid else ""
                r["in_force"], r["superseded_by"] = False, sb
                r.pop("not_policy", None)
                if sb and not by_id[sb].get("overrides"):
                    by_id[sb]["overrides"] = rid
            elif st == "not_policy":
                r["in_force"], r["superseded_by"], r["not_policy"] = False, "", True
            entry["decisions"].append({"rule": rid, "status": st, "superseded_by": r.get("superseded_by", ""),
                                       "effective_from": ef, "quote": q, "quote_found": r.get("deciding_quote_found")})
        # T14 risk: a decision that takes effect inside the range of call dates keeps both versions
        for d in entry["decisions"]:
            r = by_id[d["rule"]]
            sb = r.get("superseded_by")
            if r["in_force"] or not sb:
                continue
            ef = by_id[sb].get("effective_from", "")
            if ef and rng["earliest"] and rng["earliest"] < ef and (not rng["latest"] or ef <= rng["latest"]):
                r["in_force"] = True
                r["effective_until"] = ef
                d["kept_until"] = ef
        if members and not any(by_id[m]["in_force"] or by_id.get(by_id[m].get("superseded_by"), {}).get("in_force")
                               for m in members) and not all(by_id[m].get("not_policy") for m in members):
            entry["warning"] = "no candidate of this block is in force"
        notes.append(entry)
    return rng, notes

def stale_values(rules):
    """A value that a superseded rule had, that the rule replacing it names in its text but no longer has in its values,
    is replaced. Where another rule in force still carries it, that rule is stale: flag it (confidence low,
    stale_values) and leave it to the builder; outcome rows with a stale reason are left out of the spec."""
    by_id = {r["id"]: r for r in rules}
    found = []
    for old in rules:
        new = by_id.get(old.get("superseded_by") or "")
        if old["in_force"] or not new:
            continue
        on, od, os_ = value_atoms(old.get("values") or {})
        nn, nd, ns = value_atoms(new.get("values") or {})
        ntext = " ".join([new.get("text", ""), new.get("deciding_quote", ""), old.get("deciding_quote", "")])
        tn, td = text_atoms(ntext)
        tl = " %s " % re.sub(r"[^a-z0-9_]+", " ", ntext.lower())
        replaced = {a for a in on - nn if a in tn} | {a for a in od - nd if a in td} | \
                   {a for a in os_ - ns if " %s " % re.sub(r"[^a-z0-9_]+", " ", a) in tl}
        if not replaced:
            continue
        for r in rules:
            if not r["in_force"] or r is new or r.get("effective_until"):
                continue
            rn, rd, rs = value_atoms(r.get("values") or {})
            hit = replaced & (rn | rd | rs)
            if hit and not any(x["rule"] == r["id"] and set(x["values"]) >= hit for x in found):
                r["confidence"] = "low"
                r["stale_values"] = sorted(set(r.get("stale_values", [])) | hit)
                found.append({"rule": r["id"], "values": sorted(hit), "old": old["id"], "new": new["id"]})
    return found


# ----------------------------------------------------------------------------------------------- T15 chain-of-verification
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
        "q": {"type": "string"},
        "quotes": {"type": "array", "items": {"type": "object", "properties": {"quote": {"type": "string"}, "in_force": {"type": "boolean"}},
                                               "required": ["quote", "in_force"]}},
        "value_in_force": {"type": "string"},
        "earlier_value": {"type": "string"},
        "effective_from": {"type": "string"},
        "not_found": {"type": "boolean"}},
        "required": ["q", "quotes", "value_in_force", "earlier_value", "effective_from", "not_found"]}}},
    "required": ["answers"],
}

VERIFY_SYSTEM = """You answer questions about a bank's documents (a brief for an automated phone call, sometimes several
documents: mail, policy, memo, code list) and its tool API, using ONLY those documents. For every question:
- "quotes": the exact sentence(s) or table row(s) that set the value, copied character for character from the documents
  (you may quote part of a sentence; never paraphrase, never join pieces with ellipses). Mark each quote "in_force": false
  when a later document changed it or it only proposes/discusses.
- "value_in_force": the value(s) that apply to the calls, complete, with every number as digits (5, not "fifth";
  2, not "twice"), dates as YYYY-MM-DD, times as HH:MM, codes, enum values and field names exactly as written.
- "earlier_value" and "effective_from" (YYYY-MM-DD) when a later document changed the value; else "".
- "not_found": true when the documents do not set it.
Answer every question; do not skip any."""


def verification_questions(rules):
    qs = []
    for r in rules:
        if not (r["in_force"] or r.get("effective_until")):
            continue
        v = r.get("values") or {}
        keys = [k for k in v if k in spec_check.KEY_QUESTIONS]
        n, d, s = value_atoms(v)
        if not keys or not (n or d or s):
            continue
        what = "; ".join(spec_check.KEY_QUESTIONS[k] for k in keys)
        names = [b.get("name") for b in v.get("bands") or [] if b.get("name")]
        pts = sorted({pt for f in v.get("floors") or [] for pt in f.get("product_types") or []})
        extra = (" (bands: %s)" % ", ".join(names) if names else "") + (" (product types: %s)" % ", ".join(pts) if pts else "")
        sizes = ["%d %s" % (len(v[k]), k) for k in keys if isinstance(v[k], list) and len(v[k]) > 2]
        if sizes:
            extra += " -- give ALL of them (%s)" % ", ".join(sizes)
        when = " -- the version that applies before %s" % r["effective_until"] if r.get("effective_until") else ""
        qs.append({"q": "V%02d" % (len(qs) + 1), "rule": r["id"],
                   "text": "V%02d [%s | topic %s]: %s%s%s" % (len(qs) + 1, r.get("source", ""), r.get("topic", ""), what, extra, when)})
    return qs


async def verify_calls(qs, docs, api, model, log, per_call=30):
    """A fresh context per call: only the documents, the API and the questions (never the inventory)."""
    chunks = [qs[i:i + per_call] for i in range(0, len(qs), per_call)]
    jobs = []
    for ci, ch in enumerate(chunks):
        prompt = ("DOCUMENTS:\n\n%s\n\n%s\n\nQUESTIONS:\n%s\n\nAnswer every question with the JSON only." % (
            docs, api, "\n".join(q["text"] for q in ch)))
        jobs.append(ask_json_async(prompt, VERIFY_SYSTEM, VERIFY_SCHEMA, "chain-of-verification: quote the sentences that set "
                                   "%d value(s) (fresh context, brief only)%s" % (len(ch), " [%d/%d]" % (ci + 1, len(chunks)) if len(chunks) > 1 else ""),
                                   model=model, log=log, effort=FAST_EFFORT))
    res = await asyncio.gather(*jobs, return_exceptions=True)
    answers, infos = [], []
    for x in res:
        if isinstance(x, Exception):
            log("verification call failed: %s" % x)
            continue
        obj, info = x
        infos.append(info)
        answers += (obj or {}).get("answers") or []
    return answers, infos


def apply_verification(rules, qs, answers, brief_norm):
    by_id = {r["id"]: r for r in rules}
    ans = {str(a.get("q", "")).strip(): a for a in answers}
    out = []
    for q in qs:
        r = by_id[q["rule"]]
        a = ans.get(q["q"])
        if not a:
            r["verification"] = {"q": q["q"], "status": "no_answer"}
            out.append((r["id"], r["verification"]))
            continue
        quotes = [x for x in a.get("quotes") or [] if str(x.get("quote") or "").strip()]
        found = [quote_found(x["quote"], brief_norm) for x in quotes]
        # compared with the verifier's own statement of the value only: a quote can still carry a value a later
        # document replaced ("the hardship code from the list (X in v3)")
        older = bool(r.get("effective_until"))
        pool = " ".join([a.get("earlier_value") or "", a.get("value_in_force") or ""]) if older else (a.get("value_in_force") or "")
        pn, pd = text_atoms(pool)
        pl = _norm_text(pool)
        rn, rd, rs = value_atoms(r.get("values") or {})
        missing = sorted(rn - pn) + sorted(rd - pd) + sorted(s for s in rs if _norm_text(s) not in pl)
        status = "ok"
        if a.get("not_found"):
            status = "not_found"
        elif missing:
            status = "mismatch"
        elif quotes and not any(found):
            status = "quote_not_found"
        r["verification"] = {"q": q["q"], "status": status, "missing": missing, "verifier_value": a.get("value_in_force", ""),
                             "earlier_value": a.get("earlier_value", ""), "effective_from": a.get("effective_from", ""),
                             "quotes": [{"quote": x["quote"], "in_force": x.get("in_force", True), "found": f} for x, f in zip(quotes, found)]}
        if status != "ok":
            r["confidence"] = "low"
        elif r.get("alternatives"):
            r["value_difference_resolved"] = True     # the sampled values differed; the chosen one is verified
        out.append((r["id"], r["verification"]))
    return out

# ----------------------------------------------------------------------------------------------- T28 spec compile
def _band_key(name):
    s = re.sub(r"\bband\b", " ", str(name or "").lower())
    s = re.split(r"[-–—(:,]", s)[0]
    return re.sub(r"\s+", " ", s).strip()


def compile_spec(rules, api_name, at=None):
    """Merge the partial specs of the rules that apply at date `at` (None = the latest calls) into one spec.
    API-sourced rules go first so the brief's own rules win. Returns (spec, sources, conflicts, notes)."""
    def applies(r):
        if not r["in_force"]:
            return False
        ef, eu = r.get("effective_from", ""), r.get("effective_until", "")
        if at is None:
            return not eu
        return not (ef and at < ef) and not (eu and at >= eu)
    stem = pathlib.Path(api_name).name.lower()
    rs = [r for r in rules if applies(r)]
    rs = [r for r in rs if r.get("source", "").lower().startswith(stem)] + [r for r in rs if not r.get("source", "").lower().startswith(stem)]
    spec, sources, conflicts, notes = {}, {}, [], []

    def src(key, rid):
        sources.setdefault(key, [])
        if rid not in sources[key]:
            sources[key].append(rid)

    def setf(obj, k, v, where, rid, owners):
        if v is None or v == "" or v == [] or v == {}:
            return
        if k in obj and obj[k] != v and owners.get(where + "." + k) not in (None, rid):
            conflicts.append("%s.%s: %s (%s) -> %s (%s)" % (where, k, json.dumps(obj[k], ensure_ascii=False),
                                                           owners.get(where + "." + k), json.dumps(v, ensure_ascii=False), rid))
        obj[k] = copy.deepcopy(v)
        owners[where + "." + k] = rid
    owners = {}
    bands, floors, ladder, idn, outs, notes_r, verb, forb = [], {}, {}, {}, {}, {}, [], []
    for r in rs:
        v, rid = r.get("values") or {}, r["id"]
        if v.get("calendar"):
            cal = spec.setdefault("calendar", {})
            c = v["calendar"]
            setf(cal, "business_weekdays", c.get("business_weekdays"), "calendar", rid, owners)
            hol = {h["date"]: h for h in cal.get("holidays", [])}
            for h in c.get("holidays") or []:
                h = h if isinstance(h, dict) else {"date": str(h)}
                if h.get("date") and h["date"] not in hol:
                    hol[h["date"]] = {"date": h["date"], "name": h.get("name", "")}
            if hol:
                cal["holidays"] = sorted(hol.values(), key=lambda h: h["date"])
            if c.get("text"):
                cal["text"] = (cal.get("text", "") + " " + c["text"]).strip()
            src("calendar", rid)
        for b in v.get("bands") or []:
            k = _band_key(b.get("name"))
            tgt = next((x for x in bands if (k and _band_key(x.get("name")) == k) or
                        (b.get("min_days") is not None and x.get("min_days") == b.get("min_days") and x.get("max_days") == b.get("max_days"))), None)
            if tgt is None:
                tgt = {}
                bands.append(tgt)
            for f in ("name", "min_days", "max_days", "deadline_rule", "attempts", "same_as", "text"):
                if f in b and not (f == "name" and tgt.get("name")):
                    if f == "max_days" and b[f] is None:
                        tgt.setdefault("max_days", None)
                        continue
                    setf(tgt, f, b[f], "bands[%s]" % (tgt.get("name") or b.get("name")), rid, owners)
            src("bands", rid)
        for f in v.get("floors") or []:
            for pt in f.get("product_types") or []:
                if pt in floors and floors[pt][0] != f.get("rule") and floors[pt][1] != rid:
                    conflicts.append("floors[%s]: %s (%s) -> %s (%s)" % (pt, json.dumps(floors[pt][0]), floors[pt][1], json.dumps(f.get("rule")), rid))
                floors[pt] = (copy.deepcopy(f.get("rule") or {}), rid)
            src("floors", rid)
        for a in v.get("attempt_ladder") or []:
            k = (a.get("attempt"), tuple(sorted(str(x).lower() for x in a.get("bands") or [])))
            ladder[k] = copy.deepcopy(a)
            src("attempt_ladder", rid)
        if v.get("callback"):
            cb = spec.setdefault("callback", {})
            for k2, x in v["callback"].items():
                setf(cb, k2, x, "callback", rid, owners)
            src("callback", rid)
        for q in v.get("identity") or []:
            if q.get("field"):
                idn[q["field"]] = {**idn.get(q["field"], {}), **{k2: x for k2, x in q.items() if x not in (None, "", [])}}
                src("identity", rid)
        if v.get("max_wrong_answers") is not None:
            setf(spec, "max_wrong_answers", v["max_wrong_answers"], "spec", rid, owners)
            src("max_wrong_answers", rid)
        for o in v.get("outcomes") or []:
            if str(o.get("reason") or "").lower() in [x.lower() for x in r.get("stale_values", [])]:
                continue
            k = (o.get("outcome", ""), o.get("reason", "") or "")
            if k not in outs:
                outs[k] = {"outcome": k[0], "reason": k[1], "when": o.get("when", "")}
            elif o.get("when") and o["when"] not in outs[k]["when"] and len(outs[k]["when"]) < 300:
                outs[k]["when"] = (outs[k]["when"] + "; " + o["when"]).strip("; ")
            src("outcomes", rid)
        for n in v.get("note_reasons") or []:
            if n.get("reason"):
                notes_r[n["reason"]] = {**notes_r.get(n["reason"], {}), **{k2: x for k2, x in n.items() if x}}
                src("note_reasons", rid)
        for s in r.get("verbatim") or []:
            if s and s not in [x["text"] for x in verb]:
                verb.append({"text": s, "when": "%s: %s" % (rid, r["text"][:160])})
                src("verbatim", rid)
        for w in v.get("forbidden_words_before_verification") or []:
            if w and w.lower() not in [x.lower() for x in forb]:
                forb.append(w)
                src("forbidden_words_before_verification", rid)
        if v.get("text"):
            notes.append("%s: %s" % (rid, v["text"]))
    if bands:
        spec["bands"] = sorted(bands, key=lambda b: (b.get("min_days") is None, b.get("min_days") or 0))
    if floors:
        grouped = {}
        for pt, (rule, rid) in floors.items():
            grouped.setdefault(json.dumps(rule, sort_keys=True), {"product_types": [], "rule": rule})["product_types"].append(pt)
        spec["floors"] = list(grouped.values())
    if ladder:
        spec["attempt_ladder"] = [ladder[k] for k in sorted(ladder, key=lambda k: (k[0] or 0, k[1]))]
    if idn:
        spec["identity"] = sorted(idn.values(), key=lambda q: q.get("order") or 99)
    if outs:
        spec["outcomes"] = list(outs.values())
    if notes_r:
        spec["note_reasons"] = list(notes_r.values())
    if verb:
        spec["verbatim"] = verb
    if forb:
        spec["forbidden_words_before_verification"] = forb
    return spec, sources, conflicts, notes


def build_spec_doc(rules, api_path, call_range):
    spec, sources, conflicts, notes = compile_spec(rules, api_path)
    doc = {"schema": spec_check.SCHEMA_ID, "call_date_range": call_range or {"earliest": "", "latest": "", "basis": ""},
           "spec": spec, "sources": sources, "notes": notes, "merge_conflicts": conflicts}
    cuts = sorted({r["effective_until"] for r in rules if r["in_force"] and r.get("effective_until")})
    if cuts:
        bounds = [""] + cuts + [""]
        tl = []
        for a, b in zip(bounds, bounds[1:]):
            s, _, c2, _ = compile_spec(rules, api_path, at=a or "0000-00-00")
            tl.append({"from": a, "until": b, "spec": s})
            conflicts += [x for x in c2 if x not in conflicts]
        doc["timeline"] = tl
    return doc

# ----------------------------------------------------------------------------------------------- rendering
def _flags(r):
    f = []
    if not r["in_force"]:
        f.append("**[not policy]**" if r.get("not_policy") else "**[superseded by %s]**" % (r["superseded_by"] or "?"))
    if r.get("effective_from"):
        f.append("[from %s]" % r["effective_from"])
    if r.get("effective_until"):
        f.append("**[in force until %s, then %s]**" % (r["effective_until"], r.get("superseded_by") or "?"))
    if r.get("stale_values"):
        f.append("**[stale value(s) %s]**" % r["stale_values"])
    if r.get("confidence") and r["confidence"] != "high":
        f.append("[confidence %s%s]" % (r["confidence"], (", samples " + r["samples"]) if r.get("samples") else ""))
    ver = (r.get("verification") or {}).get("status")
    if ver:
        f.append("[verified]" if ver == "ok" else "**[verification: %s]**" % ver)
    return (" " + " ".join(f)) if f else ""


def render_md(rules, briefs, api_path, meta=None):
    L = ["# Rule inventory: %s" % ", ".join(pathlib.Path(b).name for b in briefs), ""]
    L.append("Tool API: `%s`. %d rules (%d in force, %d superseded or not policy, %d low confidence)." % (
        pathlib.Path(api_path).name, len(rules), sum(r["in_force"] for r in rules), sum(not r["in_force"] for r in rules),
        sum(r.get("confidence") == "low" for r in rules)))
    if meta:
        L.append("Model %s, %.0f s, %s, %d call(s); samples %s; spec `%s`; conflicts `%s`." % (
            meta.get("model"), meta.get("seconds", 0), cost_label(meta.get("cost_usd", 0)), meta.get("calls", 0), meta.get("samples"),
            meta.get("spec", ""), meta.get("conflicts", "")))
        chk = meta.get("self_check") or {}
        if chk.get("missing_numbers") or chk.get("missing_tokens"):
            L.append("Self-check: missing numbered rules %s; missing tokens %s." % (chk.get("missing_numbers"), chk.get("missing_tokens")))
        else:
            L.append("Self-check: every numbered rule is cited; every date and backticked token of the brief appears in the inventory.")
    L.append("")
    for cat in CATEGORIES:
        rs = [r for r in rules if r["category"] == cat]
        if not rs:
            continue
        L.append("## %s (%d)" % (cat, len(rs)))
        L.append("")
        for r in rs:
            ov = " (overrides %s)" % r["overrides"] if r["overrides"] else ""
            L.append("- **%s**%s%s — _%s_: %s" % (r["id"], _flags(r), ov, r["source"], r["text"]))
            for v in r["verbatim"]:
                L.append("  - verbatim: \"%s\"" % v)
            if r["values"]:
                L.append("  - values: `%s`" % json.dumps(r["values"], ensure_ascii=False))
            if r.get("deciding_quote"):
                L.append("  - deciding quote%s: \"%s\"" % ("" if r.get("deciding_quote_found") else " (NOT found verbatim)", r["deciding_quote"]))
        L.append("")
    return "\n".join(L)


def render_conflicts(rules, briefs, merge_info, decisions, verifs, verbatim_missing, spec_doc, spec_problems, stale=()):
    by_id = {r["id"]: r for r in rules}
    L = ["# Rule inventory: conflicts and doubts (%s)" % ", ".join(pathlib.Path(b).name for b in briefs), "",
         "Resolve these FIRST, before writing the generator: re-read the quoted source sentence in the brief, decide, and "
         "use the value the brief sets (never a value from another brief). Anything not listed here was found by every "
         "extraction sample and, where it carries a value, verified against a quote of the brief.", ""]
    n = 0
    if stale:
        L += ["## Values a later rule replaced that another rule in force still carries", "",
              "The rule named \"new\" replaced the value; the rule below still has it. Use the new value (outcome rows with a "
              "stale reason are left out of spec.json).", ""]
        for x in stale:
            r = by_id[x["rule"]]
            L.append("- **%s** (_%s_) still has %s, replaced by %s (old rule %s): %s" % (x["rule"], r["source"], x["values"], x["new"], x["old"], r["text"]))
        L.append(""); n += len(stale)
    low = [r for r in rules if r.get("confidence") == "low" and r["in_force"] and not r.get("verification") and not r.get("stale_values")]
    if low:
        L += ["## Rules found by only one extraction sample (confidence low)", ""]
        for r in low:
            L.append("- **%s** (_%s_, samples %s): %s" % (r["id"], r["source"], r.get("samples", "?"), r["text"]))
        L.append(""); n += len(low)
    diff = [r for r in rules if r.get("alternatives") and r["in_force"]]
    if diff:
        L += ["## Values that differ between the extraction samples", ""]
        for r in diff:
            res = " -- chosen value verified against the brief" if r.get("value_difference_resolved") else ""
            L.append("- **%s** (_%s_): %s%s" % (r["id"], r["source"], r.get("value_difference", ""), res))
            L.append("  - chosen: `%s`" % json.dumps(r["values"], ensure_ascii=False))
            for a in r["alternatives"]:
                L.append("  - %s: `%s`%s" % (a["id"], json.dumps(a["values"], ensure_ascii=False),
                                              (" verbatim %s" % a["verbatim"]) if a.get("verbatim") != r["verbatim"] else ""))
        L.append(""); n += sum(1 for r in diff if not r.get("value_difference_resolved"))
    bad = [(rid, v) for rid, v in verifs if v.get("status") != "ok" and (by_id[rid]["in_force"])]
    if bad:
        L += ["## Values a fresh reader could not confirm (chain-of-verification)", ""]
        for rid, v in bad:
            r = by_id[rid]
            L.append("- **%s** (_%s_) **%s**: %s" % (rid, r["source"], v.get("status"), r["text"]))
            L.append("  - inventory values: `%s`" % json.dumps(r["values"], ensure_ascii=False))
            if v.get("missing"):
                L.append("  - not in the verifier's answer: %s" % v["missing"])
            if v.get("verifier_value"):
                L.append("  - verifier (in force): %s" % v["verifier_value"])
            if v.get("earlier_value"):
                L.append("  - verifier (earlier): %s (changed from %s)" % (v["earlier_value"], v.get("effective_from") or "?"))
            for q in v.get("quotes") or []:
                L.append("  - quote%s%s: \"%s\"" % ("" if q.get("in_force", True) else " (not in force)", "" if q.get("found") else " (NOT found verbatim)", q["quote"]))
        L.append(""); n += len(bad)
    if decisions:
        L += ["## Dated decisions (which statement is in force)", ""]
        for d in decisions:
            L.append("- **%s** topic `%s`%s: %s" % (d["block"], d["topic"], (" **WARNING: %s**" % d["warning"]) if d.get("warning") else "", d.get("reason", "")))
            for x in d["decisions"]:
                L.append("  - %s: %s%s%s%s%s" % (x["rule"], x["status"], (" by " + x["superseded_by"]) if x.get("superseded_by") else "",
                                                 (" from " + x["effective_from"]) if x.get("effective_from") else "",
                                                 (" -- BOTH VERSIONS KEPT, old one until %s: key the code on `now`" % x["kept_until"]) if x.get("kept_until") else "",
                                                 (" -- \"%s\"%s" % (x["quote"], "" if x.get("quote_found") else " (NOT found verbatim)")) if x.get("quote") else ""))
            if d.get("warning") or any(x.get("quote") and not x.get("quote_found") for x in d["decisions"]) or any(x.get("kept_until") for x in d["decisions"]):
                n += 1
        L.append("")
    if verbatim_missing:
        L += ["## Mandatory sentences not found verbatim in the brief", ""]
        for rid, s in verbatim_missing:
            L.append("- **%s**: \"%s\"" % (rid, s))
        L.append(""); n += len(verbatim_missing)
    if spec_problems or spec_doc.get("merge_conflicts"):
        L += ["## Structured spec (`spec.json`) problems", ""]
        for lvl, m in spec_problems:
            L.append("- %s: %s" % (lvl, m))
        for c in spec_doc.get("merge_conflicts") or []:
            L.append("- two rules in force set different values: %s (the later one is used)" % c)
        L.append(""); n += len(spec_problems) + len(spec_doc.get("merge_conflicts") or [])
    if n == 0 and not decisions:
        L.append("Nothing to resolve.")
    return "\n".join(L), n


# ----------------------------------------------------------------------------------------------- main
async def extract_rules_async(briefs, api_path, out_path, model=None, log=None, samples=3, verify=True, split=2):
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    t0 = time.time()
    model = model or model_for("rules")
    docs = read_briefs(briefs)
    brief_norm = _norm_text(docs + "\n" + pathlib.Path(api_path).read_text())
    api = api_digest(api_path)
    cost, calls, stages = 0.0, 0, {}

    def account(info, stage):
        nonlocal cost, calls
        cost = cost_sum(cost, info["cost_usd"]); calls += info["attempts"]
        st = stages.setdefault(stage, {"seconds": 0.0, "cost_usd": 0.0, "calls": 0})
        st["cost_usd"] = cost_sum(st["cost_usd"], info["cost_usd"]); st["calls"] += info["attempts"]

    # 1. T13: extraction samples in parallel, different document orders
    parts = split_documents(briefs)
    orders = document_orders(parts)[:max(1, min(3, samples))]
    log("documents: %d part(s) in %d file(s); dated parts: %s" % (len(parts), len(briefs),
        ", ".join("%s part %d %s" % (p["file"], p["k"], p["date"]) for p in parts if p["date"]) or "none"))
    t1 = time.time()

    groups = split_groups(parts, split)
    if len(groups) > 1:
        log("each sample is written by %d parallel calls, one per group of parts: %s" % (len(groups), " | ".join(
            ",".join(str(p["pos"] + 1) for p in g) for g in groups)))

    async def one(label, oname, order, group, gi):
        only = ""
        if len(groups) > 1:
            only = ("\n\nLIST RULES ONLY FROM THE PARTS AT POSITION(S) %s. The other parts are shown for context: use them to "
                    "understand definitions and dates, and to name in \"overrides\" an earlier rule that one of your rules "
                    "replaces -- when that earlier rule is in a part you do not list, write its source as the other analyst "
                    "would (e.g. \"brief-a.md rule 28\", \"<file> <document> section 4.1 table\") instead of an id. Do not list "
                    "rules of the other parts; another analyst lists them." % ", ".join(str(p["pos"] + 1) for p in group))
        prompt = ("Write the complete rule inventory for the brief below.\n\nBRIEF DOCUMENT(S):\n\n%s\n\n%s%s\n\n"
                  "Reminder: every numbered rule, every table row, every definition and every mandatory sentence, in the "
                  "documents' ORIGINAL order (by position). Use the file names above in \"source\" (e.g. \"%s rule 12\"). "
                  "Answer with the JSON only." % (render_parts(order, oname), api, only, pathlib.Path(briefs[-1]).name))
        obj, info = await ask_json_async(prompt, SYSTEM_PROMPT, RULE_SCHEMA, "extract the rule inventory from %s, sample %s "
                                         "(documents in %s order)%s" % (", ".join(pathlib.Path(b).name for b in briefs), label, oname,
                                         (", parts %s" % ",".join(str(p["pos"] + 1) for p in group)) if len(groups) > 1 else ""),
                                         model=sample_model.get(label) or model, log=log, effort=FAST_EFFORT)
        return label, gi, obj, info
    sm = [x.strip() for x in SAMPLE_MODELS.split(",")]
    sample_model = {SAMPLE_LABELS[i]: (sm[i] if i < len(sm) else "") for i in range(3)}
    jobs = [one(SAMPLE_LABELS[i], on, o, g, gi) for i, (on, o) in enumerate(orders) for gi, g in enumerate(groups)]
    res = await asyncio.gather(*jobs, return_exceptions=True)
    got = {}
    for x in res:
        if isinstance(x, Exception):
            log("extraction call failed: %s: %s" % (type(x).__name__, x))
            continue
        label, gi, obj, info = x
        account(info, "extract")
        got.setdefault(label, {})[gi] = (obj.get("rules", []) if isinstance(obj, dict) else obj, info)
    samp = {}
    for label in sorted(got):
        if len(got[label]) < len(groups):
            log("sample %s incomplete (%d of %d calls); dropped" % (label, len(got[label]), len(groups)))
            continue
        rs = relabel_groups([got[label][gi][0] for gi in range(len(groups))], label)
        if rs:
            samp[label] = rs
            log("sample %s: %d rules (%s)" % (label, len(rs), ", ".join("%.0f s %s" % (got[label][gi][1]["seconds"], cost_label(got[label][gi][1]["cost_usd"]))
                                                                    for gi in range(len(groups)))))
    stages.setdefault("extract", {})["seconds"] = time.time() - t1
    if not samp:
        raise RuntimeError("every extraction sample failed")
    merge_note = {"samples": {k: len(v) for k, v in samp.items()}}
    if len(samp) == 1:
        merged = next(iter(samp.values()))
        for r in merged:
            r["confidence"], r["samples"] = "medium", next(iter(samp))
    else:
        t1 = time.time()
        try:
            obj, info = await merge_call(samp, model, log)
            account(info, "merge")
            merged = merge_samples(samp, obj.get("groups", []))
        except Exception as e:            # merge failed: fall back to the first sample, every rule medium
            log("merge failed (%s); using sample %s alone" % (e, sorted(samp)[0]))
            merged = samp[sorted(samp)[0]]
            for r in merged:
                r["confidence"], r["samples"] = "medium", sorted(samp)[0]
        stages["merge"]["seconds"] = time.time() - t1
    rules = normalise(merged)
    log("merged inventory: %d rules (%d high, %d medium, %d low confidence; %d with differing sampled values)" % (
        len(rules), *[sum(r.get("confidence") == c for r in rules) for c in ("high", "medium", "low")],
        sum(1 for r in rules if r.get("alternatives"))))

    # 2. deterministic self-check and one gap-fill
    chk = self_check(rules, briefs)
    log("self-check: missing numbered rules %s, missing tokens %s" % (chk["missing_numbers"] or "none", chk["missing_tokens"] or "none"))
    if chk["missing_numbers"] or chk["missing_tokens"]:
        t1 = time.time()
        gaps = []
        for f, nums in chk["missing_numbers"].items():
            gaps.append("%s: numbered rules %s" % (f, ", ".join(map(str, nums))))
        if chk["missing_tokens"]:
            gaps.append("these values/tokens from the brief appear nowhere in the inventory: %s" % ", ".join(chk["missing_tokens"]))
        existing = "\n".join("%s | %s | %s" % (r["id"], r["source"], r["text"]) for r in rules)
        gp = ("The inventory below was extracted from the brief but is incomplete.\n\nMISSING:\n- %s\n\n"
              "EXISTING INVENTORY (id | source | text):\n%s\n\nBRIEF DOCUMENT(S):\n\n%s\n\n%s\n\n"
              "Return ONLY the rules that must be ADDED to cover the missing items (same schema, ids starting at R%02d). "
              "If a missing token belongs in an existing rule's values, return that rule again with the same id and the completed values; "
              "it will replace the existing one. Do not return rules that are already complete."
              % ("\n- ".join(gaps), existing, docs, api, len(rules) + 1))
        try:
            obj2, info2 = await ask_json_async(gp, SYSTEM_PROMPT, RULE_SCHEMA, "gap-fill the rule inventory (%s)" % "; ".join(gaps)[:160],
                                               model=model, log=log)
            account(info2, "gap-fill")
            added = obj2.get("rules", []) if isinstance(obj2, dict) else obj2
            by_id = {r["id"]: r for r in rules}
            n_rep = n_add = 0
            for r in added or []:
                if not isinstance(r, dict) or not r.get("text"):
                    continue
                rid = str(r.get("id", ""))
                if rid in by_id:
                    by_id[rid].update({k: r[k] for k in ("source", "category", "text", "verbatim", "values", "overrides") if k in r})
                    n_rep += 1
                else:
                    r = dict(r); r["confidence"], r["origin"] = "medium", "gap-fill"
                    rules.append(r); n_add += 1
            rules = normalise(rules)
            chk = self_check(rules, briefs)
            log("gap-fill: %d added, %d replaced -> %d rules | self-check: missing numbered rules %s, missing tokens %s" % (
                n_add, n_rep, len(rules), chk["missing_numbers"] or "none", chk["missing_tokens"] or "none"))
        except Exception as e:
            log("gap-fill failed: %s" % e)
        stages.setdefault("gap-fill", {})["seconds"] = time.time() - t1

    require_numbered_coverage(chk)
    # 3. T14 dated decisions and T15 chain-of-verification, in parallel
    decisions, verifs, call_range = [], [], {"earliest": "", "latest": "", "basis": ""}
    if verify:
        t1 = time.time()
        blocks = decision_blocks(rules)
        qs = verification_questions(rules)
        log("dated-decision blocks: %d | verification questions: %d" % (len(blocks), len(qs)))
        jobs = [decide_call(rules, blocks, docs, model, log) if blocks else asyncio.sleep(0, result=None),
                verify_calls(qs, docs, api, model, log) if qs else asyncio.sleep(0, result=([], []))]
        dres, vres = await asyncio.gather(*jobs, return_exceptions=True)
        if isinstance(dres, Exception):
            log("dated-decision call failed: %s" % dres)
        elif dres:
            obj, info = dres
            account(info, "decide")
            call_range, decisions = apply_decisions(rules, blocks, obj or {}, brief_norm)
            log("dated decisions: call dates %s..%s; %s" % (call_range["earliest"] or "?", call_range["latest"] or "?", "; ".join(
                "%s %s" % (d["block"], ",".join("%s=%s" % (x["rule"], x["status"]) for x in d["decisions"])) for d in decisions)[:600]))
        if isinstance(vres, Exception):
            log("verification failed: %s" % vres)
        else:
            answers, infos = vres
            for info in infos:
                account(info, "verify")
            verifs = apply_verification(rules, qs, answers, brief_norm)
            log("verification: %d checked, %d ok, %s" % (len(verifs), sum(v["status"] == "ok" for _, v in verifs), ", ".join(
                "%s %s" % (rid, v["status"]) for rid, v in verifs if v["status"] != "ok") or "no mismatch"))
        stages.setdefault("verify+decide", {})["seconds"] = time.time() - t1
    stale = stale_values(rules)
    if stale:
        log("stale values (replaced by a later rule, still in another rule in force): %s" % "; ".join(
            "%s %s (replaced %s -> %s)" % (x["rule"], x["values"], x["old"], x["new"]) for x in stale))
    verbatim_missing = [(r["id"], s) for r in rules if r["in_force"] for s in r["verbatim"] if not quote_found(s, brief_norm)]

    # 4. T28 spec, conflicts, outputs
    out = pathlib.Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    base = str(out)[:-len(".rules.json")] if str(out).endswith(".rules.json") else str(out.with_suffix(""))
    spec_path, conf_path, meta_path = pathlib.Path(base + ".spec.json"), pathlib.Path(base + ".rules.conflicts.md"), pathlib.Path(base + ".rules.meta.json")
    spec_doc = build_spec_doc(rules, api_path, call_range)
    spec_problems = spec_check.check(spec_doc, json.load(open(api_path)))
    spec_path.write_text(json.dumps(spec_doc, indent=1, ensure_ascii=False) + "\n")
    conf_md, n_conf = render_conflicts(rules, briefs, merge_note, decisions, verifs, verbatim_missing, spec_doc, spec_problems, stale)
    conf_path.write_text(conf_md + "\n")
    meta = {"model": model, "sample_models": {k: v or model for k, v in sample_model.items() if k in got}, "seconds": time.time() - t0, "cost_usd": cost, "calls": calls, "self_check": chk,
            "samples": merge_note["samples"], "stages": stages, "briefs": [str(b) for b in briefs], "api": str(api_path),
            "spec": spec_path.name, "conflicts": conf_path.name, "n_conflicts": n_conf, "call_date_range": call_range,
            "n_rules": len(rules), "n_in_force": sum(r["in_force"] for r in rules),
            "n_low": sum(r.get("confidence") == "low" for r in rules),
            "n_low_in_force": sum(r.get("confidence") == "low" and r["in_force"] for r in rules),
            "verification": {s: sum(v["status"] == s for _, v in verifs) for s in sorted({v["status"] for _, v in verifs})},
            "decision_blocks": len(decisions), "spec_errors": sum(1 for l, _ in spec_problems if l == "ERROR"),
            "spec_warnings": sum(1 for l, _ in spec_problems if l == "WARN")}
    out.write_text(json.dumps(rules, indent=1, ensure_ascii=False) + "\n")
    md = out.with_suffix(".md") if out.suffix == ".json" else pathlib.Path(str(out) + ".md")
    md.write_text(render_md(rules, briefs, api_path, meta))
    meta_path.write_text(json.dumps(meta, indent=1) + "\n")
    cats = {}
    for r in rules:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    print("rules: %d (%d in force, %d low confidence) -> %s + %s + %s + %s | %d conflict item(s), spec %d error(s) %d warning(s) | "
          "%d model call(s), %.0f s, %s | samples %s | verification %s | self-check: %s" % (
              len(rules), meta["n_in_force"], meta["n_low"], out, md.name, spec_path.name, conf_path.name, n_conf,
              meta["spec_errors"], meta["spec_warnings"], calls, meta["seconds"], cost_label(cost), merge_note["samples"],
              meta["verification"] or "skipped",
              "ok" if not (chk["missing_numbers"] or chk["missing_tokens"]) else "gaps %s %s" % (chk["missing_numbers"], chk["missing_tokens"])),
          flush=True)
    return rules


def extract_rules(briefs, api_path, out_path, model=None, log=None, samples=3, verify=True, split=2):
    return asyncio.run(extract_rules_async(briefs, api_path, out_path, model=model, log=log, samples=samples, verify=verify, split=split))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract the rule inventory of a brief with the selected model (rules v2).")
    ap.add_argument("briefs", nargs="+", help="brief Markdown file(s), earlier briefs first")
    ap.add_argument("--api", required=True, help="tool API file (OpenAPI JSON)")
    ap.add_argument("--out", required=True, help="output JSON path, e.g. out/<slot>.rules.json")
    ap.add_argument("--model", default=None, help="builder model (default $RULES_MODEL or selected provider default)")
    ap.add_argument("--samples", type=int, default=3, help="extraction samples in parallel (1-3, default 3)")
    ap.add_argument("--split", type=int, default=2, help="parallel calls per sample, each listing the rules of one group of "
                    "parts (default 2; 1 = one call per sample)")
    ap.add_argument("--no-verify", action="store_true", help="skip the dated-decision and verification calls")
    a = ap.parse_args(argv)
    for p in a.briefs + [a.api]:
        if not pathlib.Path(p).exists():
            sys.exit("not found: " + p)
    extract_rules(a.briefs, a.api, a.out, model=a.model, samples=a.samples, verify=not a.no_verify, split=a.split)


if __name__ == "__main__":
    main()
