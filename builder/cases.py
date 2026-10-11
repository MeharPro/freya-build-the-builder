#!/usr/bin/env python3
"""Rule-branch practice cases for ANY brief, written by an independent model call (never by the building agent).

    python3 builder/cases.py --brief <brief.md> [<brief2.md>] --api <tool_api.json> --rules out/<slot>.rules.json --out out/<slot>.cases.json
    python3 builder/cases.py --check out/<slot>.cases.json --api <tool_api.json>        # re-run the deterministic checker
    python3 builder/cases.py --brief b.md --api api.json --rules r.json --scenarios hand.cases.json --out out/x.replay.json
    python3 builder/cases.py --compare out/x.replay.json hand.cases.json                 # expected-ledger agreement

Why: a building agent that writes its own tests encodes its own blind spots (CLAUDE.md, ττ-bench). Hidden briefs come
with no practice cases, so this script gives the build something to fail on: 12-20 cases, one per rule branch
(outcome/reason rows, identity failure paths, date classes, amount classes, special topics, multi-product mixes,
3-4 pairwise combinations). See builder/CASES.md.

How:
  1. Two model calls in parallel (one for the conversation-control branches, one for the promise/arithmetic branches),
     each with the brief(s), a digest of the tool API, the rule inventory, the fixed mock customers PUB-01..13 (the mock
     bank serves only those: every case reuses one through `mock_case`) and a weekday sheet. No case of any other bank
     is shown. Each call returns the brief's calendar (business weekdays, holidays) and cases whose dates are
     EXPRESSIONS (`addbd(today, 9)`, `next_bd(d('2026-10-18'))`, `week_monday(today) + days(11)`), never numbers the
     model worked out: all date arithmetic is evaluated here by builder/freyalib.py's CAL_HELPERS (exec'd) with the
     brief's calendar. Amounts may be expressions too (`ceil(0.4 * product('p1')['past_due'])`).
  2. A deterministic checker: schema, mock customer data copied from public-test-set.json (the mock answers with its
     own data), enums from the API file, product ids that exist, every promise date a business day, not before today
     and not after the case's stated deadline, callbacks later than `now`, holidays present in the brief, the weekday of
     every date written in a script. Failing cases go back to the model once (third call, only when needed), then are
     dropped.
  3. Output: <out> (the cases, `public-test-set.json` shape plus `mock_case`, `third_party`, `rule_ids`,
     `expected_confidence`), <out>.rationale.md (derivations, calendar ladders, coverage; the building agent does not
     read it), <out>.meta.json (calendar, outcome rows, checker report, model calls).

`--scenarios <file>` (evaluation of this script, not used by the build): take existing cases (mock_case/id, `now`,
title, script; NOT their expected ledgers or checks) and have the case-writer compute the expected ledger for each, so
it can be compared with a hand-verified set by `--compare`.

Needs OPENAI_API_KEY or Anthropic access. CASES_MODEL overrides the selected provider model.
Progress and every model call go to stderr ("model call: <model> | purpose: ..."); the one-line summary goes to stdout.
"""
import argparse, asyncio, datetime, json, math, os, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
from rules import api_digest, ask_json_async, read_briefs   # noqa: E402
from freyalib import CAL_HELPERS                            # noqa: E402

from model_provider import provider, model_for, cost_sum, cost_round, cost_label

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_NOW = "2026-10-14T11:00"
PUBLIC = ROOT / "public-test-set.json"
WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MO = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def log(s):
    print(s, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------------------------- inputs
def mock_customers():
    """The practice customers the mock bank serves, data only (no Brief A/B script, expectation or check)."""
    out = {}
    for c in json.load(open(PUBLIC)):
        out[c["id"]] = {"variables": c["variables"], "identity": c["identity"], "products": c["products"],
                        "faults": c.get("faults") or []}
    return out


def mock_table(mocks):
    L = []
    for cid, m in mocks.items():
        v = m["variables"]
        prods = []
        for i, p in enumerate(m["products"]):
            prods.append("p%d=%s" % (i + 1, json.dumps(p, separators=(",", ":"))))
        L.append("- %s: %s %s %s | identity %s | products %s%s" % (
            cid, v["title"], v["first_name"], v["last_name"], json.dumps(m["identity"]), "; ".join(prods),
            (" | FAULT: " + json.dumps(m["faults"])) if m["faults"] else ""))
    return "\n".join(L)


def weekday_sheet(start="2026-10-01", n=110):
    d0 = datetime.date.fromisoformat(start)
    rows = []
    for k in range(n):
        d = d0 + datetime.timedelta(days=k)
        rows.append("%s %s" % (d.isoformat(), WD[d.weekday()][:3]))
    return ", ".join(rows)


def inventory_text(rules_path):
    if not rules_path or not pathlib.Path(rules_path).exists():
        return ("(no rule inventory given: work from the brief alone. In rule_ids cite the brief's own numbering, e.g. "
                "'rule 13', 'section 7', 'section 12 table'; with several documents prefix the file or document name)")
    rules = json.load(open(rules_path))
    L = []
    for r in rules:
        if r.get("in_force") is False:
            continue
        L.append("%s [%s] (%s) %s%s%s" % (r["id"], r.get("category", ""), r.get("source", ""), r.get("text", ""),
                                         (" | verbatim: " + json.dumps(r["verbatim"])) if r.get("verbatim") else "",
                                         (" | values: " + json.dumps(r["values"], separators=(",", ":"))) if r.get("values") else ""))
    return "\n".join(L)


def api_enums(api_path):
    """{tool: {field: enum list}} and {tool: [fields]} from the API file."""
    api = json.load(open(api_path))
    enums, fields = {}, {}
    for p, v in (api.get("paths") or {}).items():
        op = v.get("post") or v.get("get") or next(iter(v.values()), {})
        body = ((op.get("requestBody") or {}).get("content") or {}).get("application/json", {}).get("schema", {})
        name = p.strip("/").split("/")[-1]
        fields[name] = list((body.get("properties") or {}).keys())
        enums[name] = {f: fs["enum"] for f, fs in (body.get("properties") or {}).items() if fs.get("enum")}
    return enums, fields


# ----------------------------------------------------------------------------------------------- calendar maths
class Cal:
    """The brief's calendar: freyalib CAL_HELPERS exec'd with its holidays and business weekdays."""

    def __init__(self, holidays, business_weekdays):
        self.holidays = sorted(set(str(h)[:10] for h in holidays))
        self.bwd = sorted(set(int(x) for x in business_weekdays))
        self.ns = {}
        exec(CAL_HELPERS(self.holidays, self.bwd), self.ns)

    def env(self, now, products):
        ns = self.ns
        nowdt = datetime.datetime.fromisoformat(now[:16])
        today = nowdt.date()

        def d(s):
            return datetime.date.fromisoformat(str(s)[:10])

        def days(n):
            return datetime.timedelta(days=int(n))

        def wd_index(name):
            name = str(name).strip().lower()
            for i, w in enumerate(WD):
                if w.lower().startswith(name[:3]):
                    return i
            raise ValueError("unknown weekday %r" % name)

        def week_monday(x):
            return x - datetime.timedelta(days=x.weekday())

        def prev_bd(x):
            g = 0
            while not ns["isbd"](x) and g < 4000:
                x -= datetime.timedelta(days=1); g += 1
            return x

        def subbd(x, n):
            c = 0; g = 0
            while c < n and g < 4000:
                x -= datetime.timedelta(days=1); g += 1
                if ns["isbd"](x):
                    c += 1
            return x

        def weekday_after(x, name):
            """first <weekday> strictly after x"""
            i = wd_index(name)
            k = (i - x.weekday()) % 7 or 7
            return x + datetime.timedelta(days=k)

        def weekday_on_or_after(x, name):
            i = wd_index(name)
            return x + datetime.timedelta(days=(i - x.weekday()) % 7)

        def weekday_in_week(monday, name):
            return week_monday(monday) + datetime.timedelta(days=wd_index(name))

        def product(pid):
            return products[pid]

        return {"__builtins__": {}, "today": today, "now_time": nowdt.strftime("%H:%M"), "d": d, "days": days,
                "isbd": ns["isbd"], "addbd": ns["addbd"], "next_bd": ns["next_bd"],
                "next_bd_after": lambda x: ns["next_bd"](x + datetime.timedelta(days=1)), "prev_bd": prev_bd,
                "subbd": subbd, "week_monday": week_monday, "lastbd_of_week": lambda m: ns["lastbd_of_week"](week_monday(m)),
                "weekday_after": weekday_after, "weekday_on_or_after": weekday_on_or_after,
                "weekday_in_week": weekday_in_week, "product": product, "ceil": math.ceil, "floor": math.floor,
                "round": round, "min": min, "max": max, "abs": abs, "int": int, "float": float}

    def ladder(self, now, n=14):
        """'2026-10-15 Thu +1' lines: the next n business days after today, with the non-business days in between."""
        today = datetime.date.fromisoformat(now[:10])
        L, c, x = [], 0, today
        L.append("%s %s today%s" % (today.isoformat(), WD[today.weekday()][:3], "" if self.ns["isbd"](today) else " (not a business day)"))
        while c < n:
            x += datetime.timedelta(days=1)
            if self.ns["isbd"](x):
                c += 1; L.append("%s %s +%d" % (x.isoformat(), WD[x.weekday()][:3], c))
            else:
                L.append("%s %s -- %s" % (x.isoformat(), WD[x.weekday()][:3], "holiday" if x.isoformat() in self.holidays else "not a business day"))
        return L


def evaluate(expr, env):
    if isinstance(expr, (int, float)) and not isinstance(expr, bool):
        return expr
    return eval(str(expr), env)  # noqa: S307  (restricted namespace, model-written arithmetic over dates)


def txt(x):
    return "%s %d %s %d" % (WD[x.weekday()], x.day, MO[x.month - 1], x.year)


def fmt_amount(x):
    s = "%.2f" % float(x)
    return s[:-3] if s.endswith(".00") else s


# ----------------------------------------------------------------------------------------------- the model calls
CASE_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "mock_case": {"type": "string", "description": "PUB-01 .. PUB-13"},
        "now": {"type": "string", "description": "YYYY-MM-DDTHH:MM, the call variable now"},
        "family": {"type": "string"},
        "level": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "title": {"type": "string"},
        "third_party": {"type": "boolean"},
        "rule_ids": {"type": "array", "items": {"type": "string"}},
        "script": {"type": "string"},
        "deadlines": {"type": "array", "items": {"type": "object", "properties": {
            "product_id": {"type": "string"}, "date_expr": {"type": "string"}}, "required": ["product_id", "date_expr"]}},
        "expected": {"type": "object", "properties": {
            "outcome": {"type": "string"},
            "reason": {"type": "string", "description": "empty string when the brief's table gives no reason"},
            "promises": {"type": "array", "items": {"type": "object", "properties": {
                "product_id": {"type": "string"}, "amount_expr": {"type": "string"}, "date_expr": {"type": "string"}},
                "required": ["product_id", "amount_expr", "date_expr"]}},
            "notes": {"type": "array", "items": {"type": "object", "properties": {
                "product_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["product_id", "reason"]}},
            "callbacks": {"type": "array", "items": {"type": "object", "properties": {
                "date_expr": {"type": "string"}, "time": {"type": "string"}}, "required": ["date_expr", "time"]}},
            "transfers": {"type": "array", "items": {"type": "object", "properties": {"queue": {"type": "string"}}, "required": ["queue"]}},
        }, "required": ["outcome", "reason", "promises", "notes", "callbacks", "transfers"]},
        "checks": {"type": "array", "items": {"type": "string"}},
        "derivation": {"type": "string"},
        "expected_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence_reason": {"type": "string"},
    },
    "required": ["id", "mock_case", "now", "family", "level", "title", "third_party", "rule_ids", "script", "deadlines",
                 "expected", "checks", "derivation", "expected_confidence", "confidence_reason"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "calendar": {"type": "object", "properties": {
            "business_weekdays": {"type": "array", "items": {"type": "integer"}, "description": "0=Monday .. 6=Sunday"},
            "holidays": {"type": "array", "items": {"type": "string"}, "description": "YYYY-MM-DD, exactly as the brief lists them"},
            "source": {"type": "string"}}, "required": ["business_weekdays", "holidays", "source"]},
        "multi_product": {"type": "boolean", "description": "true when the brief allows a customer more than one product"},
        "outcome_rows": {"type": "array", "items": {"type": "object", "properties": {
            "outcome": {"type": "string"}, "reason": {"type": "string"}}, "required": ["outcome", "reason"]},
            "description": "every outcome/reason pair of the brief's closing table in force (reason '' when none)"},
        "cases": {"type": "array", "items": CASE_ITEM},
    },
    "required": ["calendar", "multi_product", "outcome_rows", "cases"],
}

SYSTEM = """You are an independent test author for a bank's phone agent. You did not build the agent and you will never see it. From the bank's brief (and its tool API) you write practice cases: a script for a simulated customer, the bank ledger that must exist at the end of the call, and a few conversation checks. A judge model and the bank's ledger decide pass/fail, so every expected value must follow from the brief alone.

Read the brief(s) completely. When a brief is several documents (a mail, a policy extract, a memo, a code list), the rule in force is the latest dated decision, even when it does not say it replaces anything. Never use rules from any other bank or from memory.

THE MOCK BANK. It serves only the fixed practice customers listed in the prompt (PUB-01 .. PUB-13). Every case reuses one through `mock_case`: the mock answers identity checks with that customer's data, `get_account` returns that customer's products with product ids p1, p2, p3 in the listed order, and listed faults happen (e.g. the first create_promise fails). Name, title, identity, products and faults cannot be changed; only the script, the call time `now` and the expectations are yours. The persona already knows the right identity answers; the script says when to give a wrong one and which.
- One-product briefs: use PUB-01 .. PUB-10 only. Multi-product briefs: PUB-11 .. PUB-13 for multi-product mixes, and single-product customers too.
- `now` defaults to 2026-10-14T11:00 (a Wednesday). Use other dates only when a calendar edge needs it (a Friday or end-of-week call, a holiday inside the deadline window, an evening call near the callback window's end, a call on the day before a holiday). At most 4 cases per call with another `now`.

SCRIPTS. Second person, addressed to the simulated customer: what to say at each point and how to answer each likely question, so the call has exactly one correct ending. Leave the customer no choice that changes the ledger ("accept the first amount offered" is fine; "maybe pay later" is not). Give exact words for the line the test is about (the vague phrase, the weekday word, the refusal). Third-party cases: set third_party true; the script says who answers (a relative, a stranger) and what they say. A customer never volunteers an amount or a date unless the test needs it. To mention a specific calendar date in a script write a placeholder [[<date expression>]] (rendered as e.g. "Saturday 17 October 2026"), or say it in relative words when the relative word is the test ("next Friday"). Never write a weekday name next to a date yourself.

EXPECTED LEDGER. outcome and reason exactly as the brief's closing table names them in force (reason "" when the table gives none; the API enums are binding where they exist). promises: product_id, amount_expr, date_expr; notes only when the brief uses add_note (reason from the API enum); callbacks: date_expr and time "HH:MM"; transfers: queue from the API enum. Everything the brief says must or must not be recorded in that scenario, and nothing else.

DATES ARE EXPRESSIONS, NEVER YOUR ARITHMETIC. Every date (date_expr, deadlines, [[...]] placeholders) is a Python expression evaluated by a calendar engine with the brief's calendar (which you also return): names available
  today (the date of `now`), now_time ("HH:MM"), d('YYYY-MM-DD'), days(n) (timedelta),
  isbd(x), addbd(x, n) (the n-th business day after x, x not counted), subbd(x, n), next_bd(x) (x if a business day, else the next one), next_bd_after(x) (first business day strictly after x), prev_bd(x) (x or the business day before),
  week_monday(x), lastbd_of_week(x) (last business day of x's week), weekday_after(x, 'Friday') (first Friday strictly after x), weekday_on_or_after(x, 'Friday'), weekday_in_week(x, 'Friday') (the Friday of x's Monday-to-Sunday week), min, max.
Translate the brief's wording into these functions literally: "the 9th business day after today" -> addbd(today, 9); "next <weekday> means the one in the following calendar week" -> weekday_in_week(today + days(7), 'Friday'); a named weekend day or holiday moved to the next business day -> next_bd(d('2026-10-17')); "last business day of this week" -> lastbd_of_week(today). Write `deadlines` for every product of a case that has a promise (and for every product whose deadline the case is about): [{product_id, date_expr}].
Amounts: amount_expr is a number as text ("420") or an expression over product('p1') (the mock's product dict: past_due, minimum_payment, instalment_amount, days_late, ...), e.g. "product('p1')['minimum_payment']" or "ceil(0.4 * product('p1')['past_due'])". Use the expression whenever a rule computes the amount.

CHECKS. 2-4 short, observable statements a judge can verify from the transcript and tool calls (verbatim sentences the brief requires in that scenario, what must not be said before identity is verified, which tool must not be called, which proposal comes first). Never a check the brief does not require.

CONFIDENCE. expected_confidence: high = the brief fixes every ledger value for this script and the customer has no ledger-changing choice; medium = one value depends on reading an ambiguous sentence or on the persona following a delicate instruction; low = the brief can reasonably be read two ways for this scenario. confidence_reason names the rule and the doubt. derivation: the rule ids and the steps that give each expected value, in two to five lines. rule_ids: every inventory rule the case tests.

Also return: calendar (business weekdays 0=Monday..6=Sunday and every holiday date exactly as the brief lists it; empty list if none), multi_product, outcome_rows (every outcome/reason pair of the closing table in force). Output JSON only, matching the schema."""

GROUPS = {
    "control": ("conversation-control branches: the opening and the confirmation of who is on the line (unclear answers), "
                "every third-party ending (callback inside the window, a slot outside the window twice, wrong number, death, "
                "a relative offering to pay), every identity failure path (wrong answers up to the limit, refusal/deflection "
                "up to the limit, a swapped day and month if the API has that hint), and every special topic that ends the "
                "call without a promise or with a transfer (already paid, dispute, restructuring / payment plan, request "
                "for a human, hardship accepted and declined, does not want to talk, robot or scam question followed by a "
                "normal call). REQUIRED: at least one case for EVERY outcome/reason row of the closing table other than the "
                "plain promise row(s) (including service/tool-error rows: PUB-10's first create_promise fails; a brief that "
                "allows fewer retries than the fault needs ends in its error row). 9 to 12 cases."),
    "promise": ("promise and arithmetic branches: each date class (a weekend day, a holiday, a date after the deadline, "
                "a vague period, 'next <weekday>' / 'this <weekday>' as the brief defines them, a date before today), each "
                "amount class (below the floor, at the floor, the full amount too much, more than owed if the brief says "
                "what happens), the persuasion attempts per band (accept attempt 1, refuse every attempt), confirmation "
                "changes at the read-back, a failing promise service (PUB-10's fault) handled as the brief says, "
                "multi-product mixes when the brief allows several products (PUB-11..13: promise on some, refusal or "
                "hardship on others; notes if the brief uses them), and 3 or 4 pairwise combinations (hardship and still "
                "naming a date and amount, a correction at the read-back across a calendar edge, a transfer after a "
                "recorded promise, a calendar edge with another `now`). 7 to 9 cases."),
}


def base_prompt(briefs, api_path, rules_path):
    return ("BRIEF(S):\n%s\n\nTOOL API DIGEST:\n%s\n\nRULE INVENTORY (rules in force, made by another reader of the same "
            "brief; the brief wins where they differ):\n%s\n\nMOCK CUSTOMERS (the only customers the mock bank serves):\n%s\n\n"
            "WEEKDAY SHEET (for orientation only; use date expressions in the output):\n%s\n"
            % (read_briefs(briefs), api_digest(api_path), inventory_text(rules_path), mock_table(mock_customers()), weekday_sheet()))


async def generate(briefs, api_path, rules_path, model, prefix="GEN"):
    base = base_prompt(briefs, api_path, rules_path)
    tasks = []
    for k, (g, what) in enumerate(GROUPS.items()):
        p = (base + "\nTASK: write the cases for the %s.\nIds: %s-%s-01, %s-%s-02, ... Every case must test a different branch; "
             "prefer the branches where an agent is most likely to go wrong (limits, counters, calendar edges, precedence "
             "between rules)." % (what, prefix, g.upper()[:1], prefix, g.upper()[:1]))
        tasks.append(ask_json_async(p, SYSTEM, SCHEMA, "independent case writer: %s branches of %s" % (g, " ".join(pathlib.Path(b).name for b in briefs)),
                                    model=model, log=log))
    return await asyncio.gather(*tasks)


async def replay(briefs, api_path, rules_path, model, scenarios, batch=12):
    """Expected ledgers for given scripts (evaluation mode). The scenarios' own expected/checks are not shown."""
    base = base_prompt(briefs, api_path, rules_path)
    mocks = mock_customers()
    items = []
    for c in scenarios:
        mc = c.get("mock_case") or c["id"]
        if mc not in mocks:
            continue
        items.append({"id": c["id"], "mock_case": mc, "now": (c.get("variables") or {}).get("now") or DEFAULT_NOW,
                      "third_party": bool(c.get("third_party") or c.get("family") == "Third party"),
                      "title": c.get("title", ""), "script": c["script"]})
    chunks = [items[i:i + batch] for i in range(0, len(items), batch)]
    sem = asyncio.Semaphore(4)

    async def one(ch, k):
        async with sem:
            p = (base + "\nTASK: these scripts were written by someone else. For each one, keep id, mock_case, now, title, "
                 "third_party and script EXACTLY as given (copy them; the script may contain plain dates, keep them), and "
                 "write the expected ledger, deadlines, checks, derivation, rule_ids and confidence from the brief. "
                 "Family and level: your own label.\nSCENARIOS:\n%s" % json.dumps(ch, indent=1))
            return await ask_json_async(p, SYSTEM, SCHEMA, "independent case writer: expected ledgers for %d given scenarios (batch %d)" % (len(ch), k + 1),
                                        model=model, log=log)
    return await asyncio.gather(*[one(ch, k) for k, ch in enumerate(chunks)]), {c["id"]: c for c in items}


# ----------------------------------------------------------------------------------------------- checker
DATE_IN_TEXT = re.compile(r"\b(%s),?\s+(\d{1,2})(?:st|nd|rd|th)?\s+(%s)(?:\s+(\d{4}))?" % ("|".join(WD), "|".join(MO)))
PLACEHOLDER = re.compile(r"\[\[(.+?)\]\]")


def materialise(raw, cal, mocks, enums, slot, scenario=None):
    """One model case -> (case dict in public-test-set shape, rationale dict, errors, warnings)."""
    errs, warns = [], []
    mc = raw.get("mock_case", "")
    if mc not in mocks:
        return None, None, ["mock_case %r is not one of PUB-01..PUB-13" % mc], []
    m = mocks[mc]
    now = (scenario or {}).get("now") or raw.get("now") or DEFAULT_NOW
    try:
        nowdt = datetime.datetime.fromisoformat(now[:16])
        now = nowdt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return None, None, ["now %r is not YYYY-MM-DDTHH:MM" % now], []
    today = nowdt.date()
    products = {"p%d" % (i + 1): p for i, p in enumerate(m["products"])}
    env = cal.env(now, products)
    rat = {"exprs": []}

    def ev_date(expr, what):
        try:
            v = evaluate(expr, env)
            if isinstance(v, datetime.datetime):
                v = v.date()
            if not isinstance(v, datetime.date):
                raise ValueError("not a date: %r" % (v,))
            rat["exprs"].append("%s: %s = %s" % (what, expr, v.isoformat()))
            return v
        except Exception as e:
            errs.append("%s: cannot evaluate %r (%s)" % (what, expr, e)); return None

    # script: render [[expr]] placeholders, then check every 'Weekday D Month' against the calendar
    script = (scenario or {}).get("script") or raw.get("script", "")
    if not scenario:
        def rep(mo):
            e = mo.group(1).strip()
            try:
                v = evaluate(e, env)
                if isinstance(v, datetime.date):
                    rat["exprs"].append("script [[%s]] = %s" % (e, v.isoformat())); return txt(v)
                if isinstance(v, (int, float)):
                    return fmt_amount(v)
                return str(v)
            except Exception as ex:
                errs.append("script placeholder [[%s]]: %s" % (e, ex)); return mo.group(0)
        script = PLACEHOLDER.sub(rep, script)
        for mo in DATE_IN_TEXT.finditer(script):
            wd, day, mon, yr = mo.group(1), int(mo.group(2)), MO.index(mo.group(3)) + 1, int(mo.group(4) or today.year)
            try:
                x = datetime.date(yr, mon, day)
                if WD[x.weekday()] != wd:
                    errs.append("script says %r but %s is a %s" % (mo.group(0), x.isoformat(), WD[x.weekday()]))
            except ValueError:
                errs.append("script names an impossible date %r" % mo.group(0))
    if not script.strip():
        errs.append("empty script")

    exp = raw.get("expected") or {}
    outcome, reason = exp.get("outcome", ""), exp.get("reason") or None
    ce = enums.get("close_call", {})
    if ce.get("outcome") and outcome not in ce["outcome"]:
        errs.append("outcome %r not in the API enum %s" % (outcome, ce["outcome"]))
    if ce.get("reason") and reason is not None and reason not in ce["reason"]:
        errs.append("reason %r not in the API enum %s" % (reason, ce["reason"]))

    deadlines = {}
    for dl in raw.get("deadlines") or []:
        v = ev_date(dl.get("date_expr", ""), "deadline %s" % dl.get("product_id"))
        if v:
            deadlines[dl.get("product_id")] = v
            if not cal.ns["isbd"](v):
                warns.append("deadline of %s (%s) is not a business day" % (dl.get("product_id"), v))
    rat["deadlines"] = {k: v.isoformat() for k, v in deadlines.items()}

    promises = []
    seen = set()
    for pr in exp.get("promises") or []:
        pid = pr.get("product_id")
        if pid not in products:
            errs.append("promise on %r: the mock customer %s has only %s" % (pid, mc, ", ".join(products))); continue
        if pid in seen:
            warns.append("two promises on %s" % pid)
        seen.add(pid)
        try:
            amt = round(float(evaluate(pr.get("amount_expr", ""), env)), 2)
            rat["exprs"].append("amount %s: %s = %s" % (pid, pr.get("amount_expr"), fmt_amount(amt)))
        except Exception as e:
            errs.append("amount of %s: cannot evaluate %r (%s)" % (pid, pr.get("amount_expr"), e)); continue
        dt = ev_date(pr.get("date_expr", ""), "promise date %s" % pid)
        if dt is None:
            continue
        pd = float(products[pid].get("past_due") or 0)
        if amt <= 0:
            errs.append("promise amount %s on %s is not positive" % (amt, pid))
        if pd and amt > pd + 0.005:
            warns.append("promise amount %s on %s is above past_due %s" % (amt, pid, pd))
        if not cal.ns["isbd"](dt):
            errs.append("promise date %s (%s) is not a business day" % (dt, WD[dt.weekday()]))
        if dt < today:
            errs.append("promise date %s is before today %s" % (dt, today))
        if pid in deadlines and dt > deadlines[pid]:
            errs.append("promise date %s is after the deadline %s of %s" % (dt, deadlines[pid], pid))
        if pid not in deadlines:
            warns.append("no deadline given for %s: promise date not checked against it" % pid)
        promises.append({"product_id": pid, "amount": amt, "date": dt.isoformat()})

    notes = []
    ne = (enums.get("add_note") or {}).get("reason")
    for n in exp.get("notes") or []:
        if n.get("product_id") not in products:
            errs.append("note on unknown product %r" % n.get("product_id"))
        if ne and n.get("reason") not in ne:
            errs.append("note reason %r not in the API enum %s" % (n.get("reason"), ne))
        notes.append({"product_id": n.get("product_id"), "reason": n.get("reason")})

    callbacks = []
    for cb in exp.get("callbacks") or []:
        dt = ev_date(cb.get("date_expr", ""), "callback date")
        t = str(cb.get("time", ""))
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            errs.append("callback time %r is not HH:MM" % t)
        if dt is not None:
            if dt < today or (dt == today and t <= nowdt.strftime("%H:%M")):
                errs.append("callback %s %s is not later than now %s" % (dt, t, now))
            callbacks.append({"date": dt.isoformat(), "time": t})

    transfers = []
    qe = (enums.get("transfer_to_agent") or {}).get("queue")
    for tr in exp.get("transfers") or []:
        if qe and tr.get("queue") not in qe:
            errs.append("transfer queue %r not in the API enum %s" % (tr.get("queue"), qe))
        transfers.append({"queue": tr.get("queue")})

    if outcome == "not_reached" and (promises or notes):
        errs.append("not_reached with promises or notes")
    if not raw.get("checks"):
        warns.append("no checks")

    conf = raw.get("expected_confidence") if raw.get("expected_confidence") in ("high", "medium", "low") else "medium"
    if warns and conf == "high" and any("above past_due" in w or "deadline" in w for w in warns):
        conf = "medium"
    third = bool((scenario or {}).get("third_party", raw.get("third_party")))
    case = {"id": raw.get("id", ""), "mock_case": mc, "brief": slot, "family": raw.get("family", ""),
            "level": raw.get("level", "medium"), "title": (scenario or {}).get("title") or raw.get("title", ""),
            "variables": dict(m["variables"], now=now), "identity": m["identity"], "products": m["products"]}
    if m["faults"]:
        case["faults"] = m["faults"]
    if third:
        case["third_party"] = True
    case.update({"script": script,
                 "expected": {"outcome": outcome, "reason": reason, "promises": promises, "notes": notes,
                              "callbacks": callbacks, "transfers": transfers},
                 "checks": raw.get("checks") or [], "rule_ids": raw.get("rule_ids") or [], "expected_confidence": conf,
                 "generated_by": "builder/cases.py"})
    rat.update({"derivation": raw.get("derivation", ""), "confidence_reason": raw.get("confidence_reason", ""),
                "warnings": warns})
    return case, rat, errs, warns


def calendar_from(answers, brief_text):
    """Merge the calendars of the calls; keep holidays that appear in the brief; report disagreements."""
    notes = []
    hol, bwd = None, None
    for a in answers:
        c = a.get("calendar") or {}
        h = sorted(set(str(x)[:10] for x in c.get("holidays") or []))
        b = sorted(set(int(x) for x in c.get("business_weekdays") or [] if 0 <= int(x) <= 6))
        if hol is None:
            hol, bwd = h, b
        else:
            if h != hol:
                notes.append("calls disagree on holidays: %s vs %s (union kept)" % (hol, h)); hol = sorted(set(hol) | set(h))
            if b != bwd:
                notes.append("calls disagree on business weekdays: %s vs %s (first kept)" % (bwd, b))
    hol, bwd = hol or [], bwd or [0, 1, 2, 3, 4]
    kept = [h for h in hol if h in brief_text]
    if len(kept) != len(hol):
        notes.append("holidays not found in the brief and dropped: %s" % sorted(set(hol) - set(kept)))
    found = sorted(set(re.findall(r"\b20\d\d-\d\d-\d\d\b", brief_text)))
    return Cal(kept, bwd), notes, found


def coverage(cases, rows):
    got = {(c["expected"]["outcome"], c["expected"]["reason"] or "") for c in cases}
    out = []
    for r in rows:
        key = (r.get("outcome", ""), r.get("reason") or "")
        out.append((key, key in got))
    return out


# ----------------------------------------------------------------------------------------------- output
def write_outputs(out, cases, rats, cal, meta, rows, scenarios_mode=False):
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, indent=1) + "\n")
    stem = str(out)[:-5] if str(out).endswith(".json") else str(out)
    meta["calendar"] = {"holidays": cal.holidays, "business_weekdays": cal.bwd}
    pathlib.Path(stem + ".meta.json").write_text(json.dumps(meta, indent=1, default=str) + "\n")
    L = ["# Generated practice cases: rationale", "",
         "Written by `builder/cases.py` (independent case-writer call, %s; dates evaluated by freyalib CAL_HELPERS). "
         "The building agent reads only the cases file, never this rationale." % meta.get("model"), "",
         "## Calendar", "",
         "Business weekdays: %s. Holidays: %s." % (", ".join(WD[i] for i in cal.bwd), ", ".join(cal.holidays) or "none"), ""]
    for note in meta.get("calendar_notes") or []:
        L.append("- " + note)
    for now in sorted({c["variables"]["now"] for c in cases}):
        L += ["", "Business-day ladder from `now` = %s:" % now, "", "```"] + cal.ladder(now) + ["```"]
    if rows and not scenarios_mode:
        L += ["", "## Outcome rows covered", ""]
        for (o, r), ok in coverage(cases, rows):
            L.append("- %s `%s` / `%s`" % ("[x]" if ok else "[ ] NOT COVERED", o, r or "-"))
    L += ["", "## Cases", ""]
    for c in cases:
        r = rats.get(c["id"], {})
        e = c["expected"]
        L += ["### %s %s (%s, %s, now %s, confidence %s)" % (c["id"], c["title"], c["family"], c["mock_case"], c["variables"]["now"], c["expected_confidence"]), "",
              "- Rules: %s" % ", ".join(c.get("rule_ids") or []),
              "- Expected: `%s` / `%s`; promises %s; notes %s; callbacks %s; transfers %s" % (
                  e["outcome"], e["reason"], json.dumps(e["promises"]), json.dumps(e["notes"]), json.dumps(e["callbacks"]), json.dumps(e["transfers"])),
              "- Derivation: %s" % " ".join(str(r.get("derivation", "")).split()),
              "- Evaluated: %s" % ("; ".join(r.get("exprs", [])) or "-")]
        if r.get("confidence_reason"):
            L.append("- Confidence: %s" % " ".join(r["confidence_reason"].split()))
        if r.get("warnings"):
            L.append("- Checker warnings: %s" % "; ".join(r["warnings"]))
        L.append("")
    if meta.get("trimmed_to_20"):
        L += ["## Valid but trimmed (cap of 20 cases)", ""] + ["- " + t for t in meta["trimmed_to_20"]] + [""]
    if meta.get("dropped"):
        L += ["## Dropped by the checker", ""] + ["- %s: %s" % (k, "; ".join(v)) for k, v in meta["dropped"].items()] + [""]
    pathlib.Path(stem + ".rationale.md").write_text("\n".join(L) + "\n")


def check_file(path, api_path):
    """Re-run the deterministic checks on a written cases file (uses <stem>.meta.json for the calendar)."""
    cases = json.load(open(path))
    stem = path[:-5] if path.endswith(".json") else path
    meta = json.load(open(stem + ".meta.json")) if pathlib.Path(stem + ".meta.json").exists() else {}
    calm = meta.get("calendar") or {}
    cal = Cal(calm.get("holidays") or [], calm.get("business_weekdays") or [0, 1, 2, 3, 4])
    enums, _ = api_enums(api_path)
    mocks = mock_customers()
    bad = 0
    ids = set()
    for c in cases:
        errs = []
        if c["id"] in ids:
            errs.append("duplicate id")
        ids.add(c["id"])
        m = mocks.get(c.get("mock_case") or c.get("id"))
        if not m:
            errs.append("unknown mock_case")
        else:
            if c["products"] != m["products"] or c["identity"] != m["identity"]:
                errs.append("identity/products differ from the mock customer")
        for k in ("id", "brief", "family", "level", "title", "variables", "script", "expected", "checks"):
            if k not in c:
                errs.append("missing " + k)
        today = datetime.date.fromisoformat(c["variables"]["now"][:10])
        e = c["expected"]
        if (enums.get("close_call") or {}).get("outcome") and e["outcome"] not in enums["close_call"]["outcome"]:
            errs.append("outcome not in API enum")
        for p in e["promises"]:
            dt = datetime.date.fromisoformat(p["date"])
            if not cal.ns["isbd"](dt):
                errs.append("promise date %s not a business day" % p["date"])
            if dt < today:
                errs.append("promise date before today")
        for t in e["transfers"]:
            q = (enums.get("transfer_to_agent") or {}).get("queue")
            if q and t["queue"] not in q:
                errs.append("queue not in API enum")
        print(("OK  " if not errs else "BAD ") + c["id"] + ("" if not errs else " | " + "; ".join(errs)))
        bad += bool(errs)
    print("%d / %d cases pass the checker (calendar: %s, business weekdays %s)" % (len(cases) - bad, len(cases), cal.holidays, cal.bwd))
    return bad == 0


def map_rules(cases_path, rules_path):
    """Replace brief references in rule_ids ('rule 13', 'section 7') with the inventory ids citing them (in place)."""
    rules = [r for r in json.load(open(rules_path)) if r.get("in_force") is not False]
    cases = json.load(open(cases_path))
    n = 0
    for c in cases:
        out = []
        for ref in c.get("rule_ids") or []:
            if re.fullmatch(r"R\d+", ref):
                out.append(ref); continue
            m = re.search(r"(rule|section)s?\s*(\d+)", ref, re.I)
            hit = []
            if m:
                pat = re.compile(r"\b%s\s*%s\b" % (m.group(1).lower(), m.group(2)), re.I)
                hit = [r["id"] for r in rules if pat.search(r.get("source", ""))]
            out += hit or [ref]
            n += bool(hit)
        c["rule_ids"] = list(dict.fromkeys(out))
    pathlib.Path(cases_path).write_text(json.dumps(cases, indent=1) + "\n")
    print("rule ids: %d brief references mapped to inventory ids in %s" % (n, cases_path))


def compare(gen_path, ref_path):
    """Expected-ledger agreement per id between a replayed file and a reference (hand-written) file."""
    gen = {c["id"]: c for c in json.load(open(gen_path))}
    ref = {c["id"]: c for c in json.load(open(ref_path))}
    agree, rows = 0, []
    key = lambda e: (e["outcome"], e.get("reason"),
                     sorted((p["product_id"], round(float(p["amount"]), 2), p["date"]) for p in e["promises"]),
                     sorted((n.get("product_id"), n["reason"]) for n in e["notes"]),
                     sorted((c["date"], c["time"]) for c in e["callbacks"]),
                     sorted(t["queue"] for t in e["transfers"]))
    for cid, r in ref.items():
        if cid not in gen:
            rows.append((cid, "MISSING", "", "")); continue
        g = gen[cid]
        same = key(g["expected"]) == key(r["expected"])
        agree += same
        if not same:
            diffs = []
            names = ["outcome", "reason", "promises", "notes", "callbacks", "transfers"]
            for n, a, b in zip(names, key(g["expected"]), key(r["expected"])):
                if a != b:
                    diffs.append("%s gen=%s ref=%s" % (n, a, b))
            rows.append((cid, "DIFF", g.get("expected_confidence"), " | ".join(diffs)))
        else:
            rows.append((cid, "same", g.get("expected_confidence"), ""))
    for cid, st, conf, d in rows:
        print("%-10s %-7s %-6s %s" % (cid, st, conf or "", d))
    print("agreement: %d / %d" % (agree, len(ref)))
    return agree, rows


# ----------------------------------------------------------------------------------------------- main
async def run(briefs, api_path, rules_path, out, model=None, scenarios_path=None):
    t0 = time.time()
    model = model or model_for("cases")
    slot = pathlib.Path(briefs[-1]).stem
    brief_text = "\n".join(pathlib.Path(b).read_text() for b in briefs)
    enums, _ = api_enums(api_path)
    mocks = mock_customers()
    infos = []
    scen_by_id = {}
    if scenarios_path:
        res, scen_by_id = await replay(briefs, api_path, rules_path, model, json.load(open(scenarios_path)))
    else:
        res = await generate(briefs, api_path, rules_path, model)
    answers = [a for a, _ in res]
    infos += [i for _, i in res]
    cal, cal_notes, iso_in_brief = calendar_from(answers, brief_text)
    rows = next((a.get("outcome_rows") for a in answers if a.get("outcome_rows")), [])
    multi = any(a.get("multi_product") for a in answers)

    raws = [c for a in answers for c in a.get("cases") or []]
    # unique ids
    seen = set()
    for c in raws:
        base, k = c.get("id") or "GEN", 2
        while c["id"] in seen:
            c["id"] = "%s-%d" % (base, k); k += 1
        seen.add(c["id"])

    def build(raw_list):
        good, rats, bad = [], {}, {}
        for raw in raw_list:
            sc = scen_by_id.get(raw.get("id"))
            if scenarios_path and sc is None:
                continue
            if not multi and not scenarios_path and raw.get("mock_case") in ("PUB-11", "PUB-12", "PUB-13"):
                bad[raw.get("id", "?")] = ["multi-product mock customer for a one-product brief"]; continue
            case, rat, errs, _ = materialise(raw, cal, mocks, enums, slot, scenario=sc)
            if errs:
                bad[raw.get("id", "?")] = errs
            else:
                good.append(case); rats[case["id"]] = rat
        return good, rats, bad

    good, rats, bad = build(raws)
    first_findings = {}
    missing = [k for k, ok in coverage(good, rows) if not ok and k[0] != "promise"] if rows and not scenarios_path else []
    if (bad or missing) and not scenarios_path:
        # one repair call: the checker's findings for the failing cases, plus one new case per uncovered outcome row
        fix_in = [r for r in raws if r.get("id") in bad]
        first_findings = dict(bad)
        p = (base_prompt(briefs, api_path, rules_path) +
             "\nCALENDAR in use: business weekdays %s, holidays %s.\nTASK: (1) a deterministic checker rejected the cases "
             "below. Fix each one (keep its id and branch; correct the expressions, ids, enums or script). (2) Write one new "
             "case (ids GEN-X-01, GEN-X-02, ...) for each of these outcome/reason rows that no case reaches yet: %s (skip a row the fixed mock customers cannot reach, e.g. one that needs a fault no mock customer has). Return "
             "only these cases, with the same calendar, multi_product and outcome_rows.\nREJECTED CASES AND FINDINGS:\n%s"
             % (cal.bwd, cal.holidays, json.dumps([{"outcome": o, "reason": r} for o, r in missing]),
                json.dumps([{"case": r, "findings": bad[r["id"]]} for r in fix_in], indent=1)))
        try:
            ans, info = await ask_json_async(p, SYSTEM, SCHEMA, "independent case writer: repair %d rejected case(s), add %d uncovered outcome row(s)" % (len(fix_in), len(missing)), model=model, log=log)
            infos.append(info)
            g2, r2, bad2 = build(ans.get("cases") or [])
            have = {c["id"] for c in good}
            for c in g2:
                if c["id"] not in have:
                    good.append(c); rats[c["id"]] = r2[c["id"]]; bad.pop(c["id"], None)
            for k, v in bad2.items():
                if k in bad:
                    bad[k] = bad[k] + ["after repair: " + "; ".join(v)]
        except Exception as e:
            log("repair call failed: %r" % (e,))
    if not scenarios_path and len(good) > 20:
        # keep 20: the only case of an outcome row first, then everything but low confidence
        order = {"high": 0, "medium": 1, "low": 2}
        cnt = {}
        for c in good:
            k = (c["expected"]["outcome"], c["expected"]["reason"])
            cnt[k] = cnt.get(k, 0) + 1
        # round-robin over the writers (control / promise / repair) so neither group crowds out the other
        pos, seen_g = {}, {}
        for c in good:
            g = c["id"].rsplit("-", 1)[0]
            pos[c["id"]] = seen_g.get(g, 0); seen_g[g] = pos[c["id"]] + 1
        keep = sorted(good, key=lambda c: (cnt[(c["expected"]["outcome"], c["expected"]["reason"])] > 1,
                                           order[c["expected_confidence"]] > 1, pos[c["id"]]))[:20]
        ids = {c["id"] for c in keep}
        trimmed = ["%s %s" % (c["id"], c["title"]) for c in good if c["id"] not in ids]
        good = [c for c in good if c["id"] in ids]
    else:
        trimmed = []
    good.sort(key=lambda c: c["id"])
    meta = {"model": model, "seconds": round(time.time() - t0, 1), "cost_usd": cost_round(cost_sum(*(i["cost_usd"] for i in infos)), 3),
            "calls": len(infos), "briefs": briefs, "api": api_path, "rules": rules_path, "multi_product": multi,
            "outcome_rows": rows, "calendar_notes": cal_notes, "iso_dates_in_brief": iso_in_brief,
            "dropped": bad, "rejected_then_repaired": {k: v for k, v in first_findings.items() if k not in bad}, "trimmed_to_20": trimmed, "n_cases": len(good), "scenarios": scenarios_path}
    write_outputs(out, good, rats, cal, meta, rows, scenarios_mode=bool(scenarios_path))
    cov = coverage(good, rows) if rows else []
    conf = {k: sum(c["expected_confidence"] == k for c in good) for k in ("high", "medium", "low")}
    print("cases: %d -> %s (+ .rationale.md, .meta.json) | %d model call(s), %.0f s, %s | confidence %s | outcome rows covered %d/%d | dropped %d%s" % (
        len(good), out, len(infos), meta["seconds"], cost_label(meta["cost_usd"]), conf, sum(ok for _, ok in cov), len(cov), len(bad),
        (" | calendar notes: " + "; ".join(cal_notes)) if cal_notes else ""))
    if not scenarios_path and len(good) < 12:
        log("WARNING: only %d valid cases (target 12-20)" % len(good))
    return good


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--brief", nargs="+")
    ap.add_argument("--api")
    ap.add_argument("--rules")
    ap.add_argument("--out")
    ap.add_argument("--model")
    ap.add_argument("--scenarios", help="evaluation: compute expected ledgers for these cases' scripts")
    ap.add_argument("--check", help="re-run the deterministic checker on a cases file")
    ap.add_argument("--compare", nargs=2, metavar=("GENERATED", "REFERENCE"))
    ap.add_argument("--map-rules", help="map brief rule references in a cases file's rule_ids to the --rules inventory ids")
    a = ap.parse_args(argv)
    if a.map_rules:
        map_rules(a.map_rules, a.rules); return
    if a.compare:
        compare(*a.compare); return
    if a.check:
        sys.exit(0 if check_file(a.check, a.api or str(ROOT / "tools" / "openapi.json")) else 1)
    if not (a.brief and a.api and a.out):
        ap.error("--brief, --api and --out are required")
    asyncio.run(run(a.brief, a.api, a.rules, a.out, model=a.model, scenarios_path=a.scenarios))


if __name__ == "__main__":
    main()
