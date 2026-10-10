"""Independent re-derivation of the extended cases: python3 tests/cases/verify_cases.py .
Own calendar code; per case the path through Brief A/B rules is re-stated and recomputed."""
import json, sys, datetime as dt
R = sys.argv[1]
HOL = {"2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"}
D = lambda s: dt.date.fromisoformat(s[:10])
def biz(d): return d.weekday() < 5 and d.isoformat() not in HOL
def nth_biz(d, n):
    k = 0
    while k < n:
        d += dt.timedelta(days=1); k += biz(d)
    return d
def next_biz_on_or_after(d):
    while not biz(d): d += dt.timedelta(days=1)
    return d
def deadline(today, days_late): return nth_biz(today, 12 if days_late <= 7 else 7)
def last_biz_of_week(d):
    fri = d + dt.timedelta(days=4 - d.weekday())
    while not biz(fri): fri -= dt.timedelta(days=1)
    return fri
def attempt1(today):
    l = last_biz_of_week(today)
    return last_biz_of_week(today + dt.timedelta(days=7 - today.weekday())) if l == today else l
def weekday_this(today, wd): return today + dt.timedelta(days=wd - today.weekday())
def weekday_next(today, wd): return weekday_this(today, wd) + dt.timedelta(days=7)
def floor(p): return p.get("minimum_payment", p.get("instalment_amount"))
def resolve(today, p, named):
    """rules 19, 20, 23: a named date -> the date to record (customer accepts the offer)"""
    dl = deadline(today, p["days_late"])
    if named > dl: return dl
    if named < today: return None
    return next_biz_on_or_after(named)

PUB = {c["id"]: c for c in json.load(open(R + "/public-test-set.json"))}
# Re-stated path per case: product index -> (amount rule, date rule). Written from the scripts, not from 'expected'.
FULL, FLOOR = "full", "floor"
PATH = {
 "EXT-A-02": [(FULL, "today")], "EXT-A-03": [(FULL, ("named", "2026-10-22"))], "EXT-A-09": [(FULL, "today")],
 "EXT-A-10": [(FULL, ("named", "2026-10-21"))], "EXT-A-11": [(FULL, "tomorrow")], "EXT-A-15": [(200.0, "today")],
 "EXT-A-16": [(FLOOR, ("this", 4))], "EXT-A-18": [(FLOOR, "deadline")], "EXT-A-19": [(FULL, ("named", "2026-10-17"))],
 "EXT-A-20": [(FULL, ("next", 4))], "EXT-A-21": [(FULL, "deadline")], "EXT-A-22": [(FULL, ("named", "2026-10-20"))],
 "EXT-A-23": [(FULL, ("named", "2026-10-26"))], "EXT-A-24": [(FULL, "attempt1")], "EXT-A-28": [(700.0, ("named", "2026-10-22"))],
 "EXT-A-31": [(FULL, "today")], "EXT-A-34": [(250.0, ("this", 4))], "EXT-A-35": [(FULL, "tomorrow")], "EXT-A-36": [(FLOOR, "today")],
 "EXT-A-37": [(FULL, "attempt1")], "EXT-A-38": [(FULL, ("this", 4))], "EXT-A-41": [(FULL, ("named", "2026-11-06"))], "EXT-A-42": [(FULL, "deadline")],
 "EXT-B-02": [None, None, (FULL, "today")], "EXT-B-06": [(FULL, "today"), None],
 "EXT-B-07": [(FULL, ("named", "2026-11-06"))] * 3, "EXT-B-08": [(FULL, ("this", 4))],
 "EXT-B-09": [(FULL, "today"), (FULL, "today"), (FULL, ("named", "2026-10-26"))],
 "EXT-B-14": [(FULL, "today"), (FULL, ("named", "2026-10-26"))],
}
CB = {"EXT-A-04": ("today", "16:00"), "EXT-A-08": ("next", "19:00"), "EXT-A-39": ("today", "19:00"), "EXT-A-40": ("next", "10:00")}
CB_REJECT = {"EXT-A-05": [("today", "21:00"), ("2026-10-17", "09:00")], "EXT-A-40": [("today", "20:00")]}
REASONS = {"promise": {None}, "paid": {None}, "transferred": {"restructuring", "human", "support"}, "no_promise": {"refused", "hardship", "dispute", "service_error"},
           "not_verified": {"failed", "declined"}, "not_reached": {"callback", "no_callback", "wrong_number", "deceased", "unclear"}}
QUEUE = {"restructuring": "restructuring", "human": "general", "support": "support"}
errs = []
def cb_ok(now, date, time):
    t = dt.datetime.fromisoformat(now); d = D(date); hh = dt.time.fromisoformat(time)
    return d in (t.date(), nth_biz(t.date(), 1)) and dt.time(10) <= hh <= dt.time(19) and dt.datetime.combine(d, hh) > t
for f in ("brief-a", "brief-b"):
    cases = json.load(open(f"{R}/tests/cases/{f}-extended.cases.json"))
    ids = [c["id"] for c in cases]; assert len(set(ids)) == len(ids)
    for c in cases:
        m, e, cid = PUB[c["mock_case"]], c["expected"], c["id"]
        def bad(x): errs.append(f"{cid}: {x}")
        for k in ("identity", "products"):
            if c[k] != m[k]: bad(k + " differs from mock")
        if c.get("faults") != m.get("faults"): bad("faults differ from mock")
        if {k: v for k, v in c["variables"].items() if k != "now"} != {k: v for k, v in m["variables"].items() if k != "now"}: bad("variables differ")
        if e["reason"] not in REASONS[e["outcome"]]: bad("outcome/reason pair not in table")
        if e["outcome"] == "transferred" and [t["queue"] for t in e["transfers"]] != [QUEUE[e["reason"]]]: bad("transfer queue")
        if e["outcome"] != "transferred" and e["transfers"]: bad("transfer without transferred outcome")
        if (e["outcome"] == "promise") != bool(e["promises"]) and e["outcome"] != "transferred": bad("promise outcome vs promises")
        if (e["reason"] == "callback") != bool(e["callbacks"]): bad("callback vs callbacks")
        if c["brief"] == "A" and e["notes"]: bad("Brief A never uses add_note")
        today = D(c["variables"]["now"]); prods = c["products"]
        # promises recomputed
        want = []
        for i, step in enumerate(PATH.get(cid, [])):
            if step is None: continue
            p = prods[i]; amt, rule = step
            a = p["past_due"] if amt == FULL else floor(p) if amt == FLOOR else amt
            if not floor(p) <= a <= p["past_due"]: bad(f"amount {a} outside floor..full")
            if rule == "today": d = today
            elif rule == "tomorrow": d = resolve(today, p, nth_biz(today, 1) if False else today + dt.timedelta(days=1))
            elif rule == "deadline": d = deadline(today, p["days_late"])
            elif rule == "attempt1": d = attempt1(today)
            elif rule[0] == "named": d = resolve(today, p, D(rule[1]))
            elif rule[0] == "this": d = resolve(today, p, weekday_this(today, rule[1]))
            elif rule[0] == "next": d = resolve(today, p, weekday_next(today, rule[1]))
            want.append({"product_id": "p%d" % (i + 1), "amount": a, "date": d.isoformat()})
        if cid not in PATH and e["promises"]: bad("promise without a re-stated path")
        if sorted(map(json.dumps, want)) != sorted(map(json.dumps, e["promises"])): bad(f"promises {e['promises']} != recomputed {want}")
        for p in e["promises"]:
            pr = prods[int(p["product_id"][1:]) - 1]; d = D(p["date"])
            if not (biz(d) and today <= d <= deadline(today, pr["days_late"])): bad(f"promise date {d} breaks rule 19")
        for cb in e["callbacks"]:
            if not cb_ok(c["variables"]["now"], cb["date"], cb["time"]): bad(f"callback {cb} outside rule 6")
        if cid in CB:
            day, tm = CB[cid]; t = dt.datetime.fromisoformat(c["variables"]["now"]).date()
            d = t if day == "today" else nth_biz(t, 1)
            if e["callbacks"] != [{"date": d.isoformat(), "time": tm}]: bad(f"callback recomputed {d} {tm}")
        for day, tm in CB_REJECT.get(cid, []):
            t = dt.datetime.fromisoformat(c["variables"]["now"]).date(); d = t.isoformat() if day == "today" else day
            if cb_ok(c["variables"]["now"], d, tm): bad(f"customer's {d} {tm} would be valid, case assumes it is not")
        # Brief B notes: every product without a promise has a note, unless the call was transferred
        if c["brief"] == "B":
            promised = {p["product_id"] for p in e["promises"]}
            noted = {n["product_id"] for n in e["notes"]}
            if e["outcome"] == "transferred":
                if e["notes"]: bad("notes on a transfer")
            else:
                need = {"p%d" % (i + 1) for i in range(len(prods))} - promised
                if noted != need: bad(f"notes for {sorted(noted)}, need {sorted(need)}")
                if not e["promises"]:
                    rs = [n["reason"] for n in sorted(e["notes"], key=lambda n: n["product_id"])]
                    exp_o = ("paid", None) if all(r == "paid" for r in rs) else ("no_promise", next(r for r in rs if r != "paid"))
                    if (e["outcome"], e["reason"]) != exp_o: bad(f"closing {exp_o} expected")
        print("ok " if not [x for x in errs if x.startswith(cid + ":")] else "BAD", cid, c["variables"]["now"], e["outcome"], e["reason"], [(p["product_id"], p["amount"], p["date"]) for p in e["promises"]], e["callbacks"] or "")
print("\n".join(errs) or "no discrepancies")
# ladders for the rationale
for now in ("2026-10-14", "2026-10-16", "2026-10-23", "2026-11-10"):
    t = D(now); print(now, t.strftime("%a"), "ladder:", ", ".join(f"{k}={nth_biz(t,k).strftime('%a %d %b')}" for k in range(1, 13)), "| attempt1:", attempt1(t))
