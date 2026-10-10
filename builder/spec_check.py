#!/usr/bin/env python3
"""Structured spec of a brief (rules v2, technique T28): the schema and a deterministic validator.

    python3 builder/spec_check.py out/<slot>.spec.json --api <tool_api.json>      # prints problems, exit 1 on ERROR

The spec is compiled by builder/rules.py from the `values` of the rules in force (each rule's `values` is a PARTIAL spec
with the same keys). A generator can read `out/<slot>.spec.json` and pass the values into its code instead of retyping
them. Nothing here holds a default from any brief: every value comes from the brief that was read, and every enum is
checked against the tool API file that was given. Anything a brief says that does not fit a field goes into the `text`
fallback of the nearest object (or into `notes`), and the generator then writes code for it from the text.

Spec keys (all optional; a brief that does not mention a topic leaves the key out):

  calendar          {business_weekdays: ["Mon".."Sun"], holidays: [{date: YYYY-MM-DD, name}], text}
                    holidays = every closure/holiday date in force (non-business days that are weekdays).
  bands             [{name, min_days, max_days (int, or null when open-ended), deadline_rule, attempts, same_as, text}]
                    same_as = name of another band whose deadline and attempts apply ("treat it as band X")
                    by the product's lateness (days_late); deadline_rule = {type, n, adjust, date, text}
                    type:   business_days_after (the n-th business day after the call date)
                            calendar_days_after (n calendar days after the call date)
                            fixed (a fixed date: `date`) | other (only `text`)
                    adjust: none | previous_business_day | next_business_day (when the computed day is not a business day)
  floors            [{product_types: [api product types], rule: {type, field, percent, factor, round, cap_to_full, text}}]
                    type: field (the product's own `field`) | percent (`percent` % of `field`) |
                          multiple (`factor` x `field`) | other (only `text`); cap_to_full: never more than the full amount
  attempt_ladder    [{attempt: 1.., bands: [band names, [] = all], amount: full|floor|in_play, date_rule: text, text}]
                    what the agent proposes on each persuasion attempt
  callback          {open: HH:MM, close: HH:MM, same_day: bool, later_than_now: bool, days_ahead_business: int,
                     days_ahead_calendar: int, text}
  identity          [{order: 1.., field: api verify_identity field, hint_values: [api hint enum], retry_rule: text}]
  max_wrong_answers int: the wrong answer that ends the check (the brief's policy, even when the service allows more)
  outcomes          [{outcome: api close_call outcome, reason: api reason (or the brief's code), when: text}]
  note_reasons      [{reason: api add_note reason, when: text, text_must_contain: text}]
  verbatim          [{text: exact sentence, when: text}]
  forbidden_words_before_verification  [words]
  text              free-text fallback for a rule that fits no field

`out/<slot>.spec.json` = {"schema": "rules-v2/spec-1", "call_date_range": {earliest, latest, basis},
                          "spec": {...in force for the latest calls...}, "timeline": [{"from", "until", "spec"}] (only when
                          a decision takes effect inside the range of call dates: the generator keys code on `now`),
                          "sources": {key: [rule ids]}, "notes": [free text]}
"""
import argparse, datetime, json, pathlib, re, sys

SCHEMA_ID = "rules-v2/spec-1"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEADLINE_TYPES = ["business_days_after", "calendar_days_after", "fixed", "other"]
ADJUST = ["none", "previous_business_day", "next_business_day"]
FLOOR_TYPES = ["field", "percent", "multiple", "other"]
LADDER_AMOUNTS = ["full", "floor", "in_play"]

_S = {"type": "string"}
_I = {"type": "integer"}
_B = {"type": "boolean"}
_N = {"type": "number"}
_SL = {"type": "array", "items": _S}

# JSON schema of a partial spec: what one rule's `values` may hold (used in the extraction call's output schema).
VALUES_SCHEMA = {
    "type": "object",
    "description": "PARTIAL SPEC: only the keys this rule sets; {} when the rule sets no structured value",
    "properties": {
        "calendar": {"type": "object", "properties": {
            "business_weekdays": {"type": "array", "items": {"type": "string", "enum": WEEKDAYS}},
            "holidays": {"type": "array", "items": {"type": "object", "properties": {"date": _S, "name": _S}, "required": ["date"]}},
            "text": _S}},
        "bands": {"type": "array", "items": {"type": "object", "properties": {
            "name": _S, "min_days": _I, "max_days": {"type": ["integer", "null"]},
            "deadline_rule": {"type": "object", "properties": {
                "type": {"type": "string", "enum": DEADLINE_TYPES}, "n": _I,
                "adjust": {"type": "string", "enum": ADJUST}, "date": _S, "text": _S}},
            "attempts": _I, "same_as": _S, "text": _S}}},
        "floors": {"type": "array", "items": {"type": "object", "properties": {
            "product_types": _SL,
            "rule": {"type": "object", "properties": {
                "type": {"type": "string", "enum": FLOOR_TYPES}, "field": _S, "percent": _N, "factor": _N,
                "round": _S, "cap_to_full": _B, "text": _S}}}}},
        "attempt_ladder": {"type": "array", "items": {"type": "object", "properties": {
            "attempt": _I, "bands": _SL, "amount": {"type": "string", "enum": LADDER_AMOUNTS}, "date_rule": _S, "text": _S}}},
        "callback": {"type": "object", "properties": {
            "open": _S, "close": _S, "same_day": _B, "later_than_now": _B, "days_ahead_business": _I,
            "days_ahead_calendar": _I, "text": _S}},
        "identity": {"type": "array", "items": {"type": "object", "properties": {
            "order": _I, "field": _S, "hint_values": _SL, "retry_rule": _S}}},
        "max_wrong_answers": _I,
        "outcomes": {"type": "array", "items": {"type": "object", "properties": {"outcome": _S, "reason": _S, "when": _S}}},
        "note_reasons": {"type": "array", "items": {"type": "object", "properties": {"reason": _S, "when": _S, "text_must_contain": _S}}},
        "verbatim": {"type": "array", "items": {"type": "object", "properties": {"text": _S, "when": _S}}},
        "forbidden_words_before_verification": _SL,
        "text": _S,
    },
}
SPEC_KEYS = list(VALUES_SCHEMA["properties"])

# Short descriptions of each key, used to ask a verifier for a value without showing it (T15).
KEY_QUESTIONS = {
    "calendar": "which weekdays are business days and which dates are closure days / holidays",
    "bands": "the lateness bands: days_late range, the deadline / latest promise date rule, the number of persuasion attempts",
    "floors": "the floor (smallest promise amount) per product type, how it is computed and any cap",
    "attempt_ladder": "what the agent proposes on each persuasion attempt (amount and date) and in which bands",
    "callback": "the callback window: which days, the earliest and latest time",
    "identity": "the security questions, their order, and what to do on a hint or a retry",
    "max_wrong_answers": "how many wrong answers end the identity check (the agent's policy)",
    "outcomes": "the close_call outcome and reason/code for each situation",
    "note_reasons": "the add_note reason for each product situation and what the note text must contain",
    "verbatim": "the sentence(s) the agent must say word for word",
    "forbidden_words_before_verification": "the words that must not be said before identity is verified",
}


# ----------------------------------------------------------------------------------------------- API enums
def _body(api, tool):
    for p, v in (api.get("paths") or {}).items():
        if p.rstrip("/").split("/")[-1] == tool:
            op = v.get("post") or v.get("get") or next(iter(v.values()), {})
            return (((op.get("requestBody") or {}).get("content") or {}).get("application/json", {}).get("schema", {}), op)
    return {}, {}


def _resp(op):
    return ((op.get("responses") or {}).get("200") or {}).get("content", {}).get("application/json", {}).get("schema", {})


def api_enums(api):
    """Enums of the tool API that the spec refers to. A missing enum is None (no check)."""
    out = {}
    b, _ = _body(api, "close_call")
    props = b.get("properties") or {}
    out["outcome"] = (props.get("outcome") or {}).get("enum")
    out["close_reason"] = (props.get("reason") or {}).get("enum")
    b, _ = _body(api, "add_note")
    out["note_reason"] = ((b.get("properties") or {}).get("reason") or {}).get("enum")
    b, op = _body(api, "verify_identity")
    out["identity_field"] = ((b.get("properties") or {}).get("field") or {}).get("enum")
    out["hint"] = ((_resp(op).get("properties") or {}).get("hint") or {}).get("enum")
    b, _ = _body(api, "transfer_to_agent")
    out["queue"] = ((b.get("properties") or {}).get("queue") or {}).get("enum")
    _, op = _body(api, "get_account")
    prod = {}
    for k, v in (_resp(op).get("properties") or {}).items():
        if v.get("type") == "array" and isinstance(v.get("items"), dict):
            prod = v["items"].get("properties") or {}
            break
    out["product_type"] = (prod.get("type") or {}).get("enum")
    out["product_fields"] = sorted(prod) or None
    return out


# ----------------------------------------------------------------------------------------------- validation
def _iso(s):
    try:
        return datetime.date.fromisoformat(str(s)) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s)) else None
    except ValueError:
        return None


def _hhmm(s):
    m = re.fullmatch(r"(\d{2}):(\d{2})", str(s or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m and int(m.group(1)) < 24 and int(m.group(2)) < 60 else None


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_spec(spec, en, where="spec"):
    """Problems of one spec object: list of (level, message), level ERROR or WARN."""
    P = []
    err = lambda m: P.append(("ERROR", "%s: %s" % (where, m)))
    warn = lambda m: P.append(("WARN", "%s: %s" % (where, m)))
    if not isinstance(spec, dict):
        return [("ERROR", "%s is not an object" % where)]
    for k in spec:
        if k not in SPEC_KEYS:
            warn("unknown key %r (not in the schema)" % k)

    cal = spec.get("calendar")
    if cal is not None:
        bw = cal.get("business_weekdays") or []
        if not bw:
            warn("calendar.business_weekdays is empty")
        for d in bw:
            if d not in WEEKDAYS:
                err("calendar.business_weekdays: %r is not one of %s" % (d, WEEKDAYS))
        seen = set()
        for h in cal.get("holidays") or []:
            d = _iso(h.get("date") if isinstance(h, dict) else h)
            if not d:
                err("calendar.holidays: %r is not an ISO date YYYY-MM-DD" % (h,))
                continue
            if d in seen:
                warn("calendar.holidays: %s listed twice" % d)
            seen.add(d)
            if bw and WEEKDAYS[d.weekday()] not in bw:
                warn("calendar.holidays: %s is a %s, not a business weekday anyway" % (d, WEEKDAYS[d.weekday()]))

    bands = spec.get("bands")
    names = set()
    if bands is not None:
        if not isinstance(bands, list) or not bands:
            err("bands is empty")
            bands = []
        rows = []
        for i, b in enumerate(bands):
            w = "bands[%d] %s" % (i, b.get("name", ""))
            names.add(str(b.get("name", "")).strip().lower())
            lo, hi = b.get("min_days"), b.get("max_days")
            if not _is_int(lo):
                err("%s: min_days %r is not an integer" % (w, lo))
            if hi is not None and not _is_int(hi):
                err("%s: max_days %r is not an integer or null" % (w, hi))
            if _is_int(lo) and _is_int(hi) and lo > hi:
                err("%s: min_days %d > max_days %d" % (w, lo, hi))
            if _is_int(lo):
                rows.append((lo, hi, w))
            dr = b.get("deadline_rule")
            if b.get("same_as"):
                if str(b["same_as"]).strip().lower() not in {str(x.get("name", "")).strip().lower() for x in bands if x is not b}:
                    err("%s: same_as %r is not another band's name" % (w, b["same_as"]))
            elif not isinstance(dr, dict):
                err("%s: no deadline_rule" % w)
            else:
                t = dr.get("type")
                if t not in DEADLINE_TYPES:
                    err("%s: deadline_rule.type %r not in %s" % (w, t, DEADLINE_TYPES))
                if t in ("business_days_after", "calendar_days_after") and not (_is_int(dr.get("n")) and dr["n"] >= 0):
                    err("%s: deadline_rule.n %r must be a non-negative integer for %s" % (w, dr.get("n"), t))
                if t == "fixed" and not _iso(dr.get("date")) and not dr.get("text"):
                    err("%s: fixed deadline without an ISO date or text" % w)
                if t == "other" and not dr.get("text"):
                    err("%s: deadline_rule type other without text" % w)
                if dr.get("adjust", "none") not in ADJUST:
                    err("%s: deadline_rule.adjust %r not in %s" % (w, dr.get("adjust"), ADJUST))
            a = b.get("attempts")
            if a is not None and not (_is_int(a) and a >= 0):
                err("%s: attempts %r is not a non-negative integer" % (w, a))
        rows.sort(key=lambda r: r[0])
        for (lo1, hi1, w1), (lo2, hi2, w2) in zip(rows, rows[1:]):
            if hi1 is None:
                err("%s is open-ended but %s starts after it" % (w1, w2))
            elif lo2 != hi1 + 1:
                err("bands not contiguous: %s ends at %d, %s starts at %d" % (w1, hi1, w2, lo2))

    floors = spec.get("floors")
    if floors is not None:
        covered = set()
        for i, f in enumerate(floors or []):
            w = "floors[%d]" % i
            pts = f.get("product_types") or []
            if not pts:
                err("%s: no product_types" % w)
            for pt in pts:
                if en.get("product_type") and pt not in en["product_type"]:
                    err("%s: product type %r not in the API enum %s" % (w, pt, en["product_type"]))
                if pt in covered:
                    warn("%s: product type %r has two floors" % (w, pt))
                covered.add(pt)
            r = f.get("rule") or {}
            t = r.get("type")
            if t not in FLOOR_TYPES:
                err("%s: rule.type %r not in %s" % (w, t, FLOOR_TYPES))
            if t in ("field", "percent", "multiple"):
                if not r.get("field"):
                    err("%s: rule.type %s needs a field" % (w, t))
                elif en.get("product_fields") and r["field"] not in en["product_fields"]:
                    err("%s: field %r is not a get_account product field %s" % (w, r["field"], en["product_fields"]))
            if t == "percent" and not (isinstance(r.get("percent"), (int, float)) and 0 < r["percent"] <= 100):
                err("%s: percent %r must be in (0, 100]" % (w, r.get("percent")))
            if t == "multiple" and not (isinstance(r.get("factor"), (int, float)) and r["factor"] > 0):
                err("%s: multiple needs a positive factor, got %r" % (w, r.get("factor")))
            if t == "other" and not r.get("text"):
                err("%s: rule type other without text" % w)
        for pt in en.get("product_type") or []:
            if covered and pt not in covered:
                warn("floors: API product type %r has no floor" % pt)

    lad = spec.get("attempt_ladder")
    if lad is not None:
        nums = []
        for i, s in enumerate(lad or []):
            w = "attempt_ladder[%d]" % i
            if not (_is_int(s.get("attempt")) and s["attempt"] >= 1):
                err("%s: attempt %r is not an integer >= 1" % (w, s.get("attempt")))
            else:
                nums.append(s["attempt"])
            if s.get("amount") not in LADDER_AMOUNTS:
                err("%s: amount %r not in %s" % (w, s.get("amount"), LADDER_AMOUNTS))
            for bn in s.get("bands") or []:
                if names and str(bn).strip().lower() not in names:
                    err("%s: band %r is not a band name %s" % (w, bn, sorted(names)))
            if not (s.get("date_rule") or s.get("text")):
                warn("%s: no date_rule" % w)
        if nums and sorted(set(nums)) != list(range(1, max(nums) + 1)):
            err("attempt_ladder: attempts %s are not 1..n" % sorted(set(nums)))
        for b in bands or []:
            a = b.get("attempts")
            if _is_int(a) and nums and a > max(nums):
                err("band %s allows %d attempts but the ladder stops at %d" % (b.get("name"), a, max(nums)))

    cb = spec.get("callback")
    if cb is not None:
        o, c = _hhmm(cb.get("open")), _hhmm(cb.get("close"))
        if cb.get("open") is not None and o is None:
            err("callback.open %r is not HH:MM" % cb.get("open"))
        if cb.get("close") is not None and c is None:
            err("callback.close %r is not HH:MM" % cb.get("close"))
        if o is not None and c is not None and o >= c:
            err("callback.open %s is not before close %s" % (cb["open"], cb["close"]))
        for k in ("days_ahead_business", "days_ahead_calendar"):
            if cb.get(k) is not None and not (_is_int(cb[k]) and cb[k] >= 0):
                err("callback.%s %r is not a non-negative integer" % (k, cb[k]))
        if not cb.get("same_day") and not cb.get("days_ahead_business") and not cb.get("days_ahead_calendar") and not cb.get("text"):
            err("callback allows no day at all")

    idn = spec.get("identity")
    if idn is not None:
        orders = []
        for i, q in enumerate(idn or []):
            w = "identity[%d]" % i
            if en.get("identity_field") and q.get("field") not in en["identity_field"]:
                err("%s: field %r not in the API enum %s" % (w, q.get("field"), en["identity_field"]))
            if _is_int(q.get("order")):
                orders.append(q["order"])
            else:
                err("%s: order %r is not an integer" % (w, q.get("order")))
            for h in q.get("hint_values") or []:
                if en.get("hint") and h not in en["hint"]:
                    err("%s: hint %r not in the API enum %s" % (w, h, en["hint"]))
        if orders and sorted(orders) != list(range(1, len(orders) + 1)):
            err("identity: orders %s are not 1..n" % sorted(orders))
        fields = [q.get("field") for q in idn or []]
        if len(set(fields)) != len(fields):
            warn("identity: a field is asked twice %s" % fields)

    mw = spec.get("max_wrong_answers")
    if mw is not None and not (_is_int(mw) and mw >= 1):
        err("max_wrong_answers %r is not an integer >= 1" % mw)

    outs = spec.get("outcomes")
    if outs is not None:
        seen = set()
        for i, o in enumerate(outs or []):
            w = "outcomes[%d]" % i
            if en.get("outcome") and o.get("outcome") not in en["outcome"]:
                err("%s: outcome %r not in the API enum %s" % (w, o.get("outcome"), en["outcome"]))
            r = o.get("reason") or ""
            if r and en.get("close_reason") and r not in en["close_reason"]:
                err("%s: reason %r not in the API enum %s" % (w, r, en["close_reason"]))
            key = (o.get("outcome"), r)
            if key in seen:
                warn("%s: outcome/reason %s/%s listed twice" % (w, key[0], key[1] or "-"))
            seen.add(key)
        nowhen = [i for i, o in enumerate(outs or []) if not o.get("when")]
        if nowhen:
            warn("outcomes%s: no 'when'" % nowhen)
        used = {o.get("outcome") for o in outs or []}
        for oc in en.get("outcome") or []:
            if outs and oc not in used:
                warn("outcomes: API outcome %r is never used" % oc)

    for i, n in enumerate(spec.get("note_reasons") or []):
        if en.get("note_reason") and n.get("reason") not in en["note_reason"]:
            err("note_reasons[%d]: reason %r not in the API enum %s" % (i, n.get("reason"), en["note_reason"]))

    for i, v in enumerate(spec.get("verbatim") or []):
        t = v.get("text") if isinstance(v, dict) else v
        if not (isinstance(t, str) and t.strip()):
            err("verbatim[%d] has no text" % i)
    fw = spec.get("forbidden_words_before_verification")
    if fw is not None and not all(isinstance(w, str) and w.strip() for w in fw):
        err("forbidden_words_before_verification has an empty or non-string entry")
    return P


def check(doc, api):
    """Problems of a spec document (out/<slot>.spec.json) against an API dict."""
    en = api_enums(api)
    if not isinstance(doc, dict):
        return [("ERROR", "spec document is not an object")]
    spec = doc.get("spec", doc)
    P = validate_spec(spec, en, "spec")
    for i, t in enumerate(doc.get("timeline") or []):
        for k in ("from", "until"):
            if t.get(k) and not _iso(t[k]):
                P.append(("ERROR", "timeline[%d].%s %r is not an ISO date" % (i, k, t[k])))
        P += validate_spec(t.get("spec") or {}, en, "timeline[%d] (%s..%s)" % (i, t.get("from") or "", t.get("until") or ""))
    rng = doc.get("call_date_range") or {}
    for k in ("earliest", "latest"):
        if rng.get(k) and not _iso(rng[k]):
            P.append(("ERROR", "call_date_range.%s %r is not an ISO date" % (k, rng[k])))
    return P


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a structured spec (out/<slot>.spec.json) against the tool API.")
    ap.add_argument("spec")
    ap.add_argument("--api", required=True)
    a = ap.parse_args(argv)
    doc = json.load(open(a.spec))
    P = check(doc, json.load(open(a.api)))
    for lvl, m in P:
        print("%s: %s" % (lvl, m))
    n_err = sum(1 for l, _ in P if l == "ERROR")
    print("spec_check: %d error(s), %d warning(s) | %s" % (n_err, len(P) - n_err, a.spec))
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
