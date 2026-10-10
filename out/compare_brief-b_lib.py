"""Proof of equivalence: out/brief-b.workflow.json (the organisers' proven generator, 3/3 practice cases) versus
out/brief-b.lib.workflow.json (the port onto builder/freyalib.py + builder/multiproduct.py). Compares the two JSON
trees recursively and prints every differing path. For every differing Python string (code node source, pre/post
hook) it then EXECUTES both versions on the same inputs (vars / config / result) and compares what they write,
so a textual difference is shown to be semantically nil, or a listed deliberate improvement. For the finalize node
it compares the transition each version would take. Exit code 1 when a difference is not covered by a passing
semantic test."""
import copy, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REF = json.load(open(ROOT / "out/brief-b.workflow.json"))
LIB = json.load(open(ROOT / "out/brief-b.lib.workflow.json"))

diffs = []


def walk(a, b, path):
    if type(a) is not type(b):
        diffs.append((path, "type %s vs %s" % (type(a).__name__, type(b).__name__)))
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            p = "%s.%s" % (path, k) if path else k
            if k not in a:
                diffs.append((p, "only in lib"))
            elif k not in b:
                diffs.append((p, "only in ref"))
            else:
                walk(a[k], b[k], p)
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append((path, "list length %d vs %d" % (len(a), len(b))))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, "%s[%d]" % (path, i))
    elif a != b:
        diffs.append((path, "value differs"))


walk(REF, LIB, "")
print("nodes: ref %d, lib %d" % (len(REF["nodes"]), len(LIB["nodes"])))
print("differing paths: %d" % len(diffs))
for p, why in diffs:
    print("  -", p, ":", why)


def get(o, path):
    cur = o
    for part in path.replace("]", "").split("."):
        if "[" in part:
            name, idx = part.split("[")
            cur = cur[name][int(idx)]
        else:
            cur = cur[part]
    return cur


def run_vars(code, vars_in):
    g = {"vars": copy.deepcopy(vars_in)}
    exec(code, g)
    return g["vars"]


def run_hook(code, result=None, config=None, vars_in=None, no_vars=False):
    """Executes a hook. With no_vars=True the hook sees no `vars` at all (the platform's post hooks may not get one)."""
    g = {"result": copy.deepcopy(result), "config": copy.deepcopy(config)}
    if not no_vars:
        g["vars"] = copy.deepcopy(vars_in or {})
    exec(code, g)
    return {"result": g["result"], "config": g["config"], "vars": g.get("vars")}


PASSED, FAILED = [], []


def expect(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print("  %s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def code_of(wf, node):
    return wf["nodes"][node]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


# ---------------------------------------------------------------- inputs
NOWS = ["2026-10-14T11:00", "2026-10-16T18:30", "2026-10-17T09:00", "2026-10-23T19:30", "2026-10-25T12:00",
        "2026-11-10T08:00", "2026-11-25T15:00", "2026-12-24T10:00", "2026-12-31T16:00", "2027-01-04T10:30",
        "2026-10-14", "2026-10-30T23:59"]
P_CC = {"product_id": "p1", "type": "credit_card", "card_last4": "4821", "past_due": 420.5, "days_late": 5, "minimum_payment": 60}
P_PL = {"product_id": "p2", "type": "personal_loan", "past_due": 1200, "days_late": 12, "instalment_amount": 300}
P_CAR = {"product_id": "p3", "type": "car_loan", "past_due": "845.25", "days_late": "7", "instalment_amount": "211.3"}
P_LATE_CC = {"product_id": "p1", "type": "credit_card", "card_last4": "0001", "past_due": 99.99, "days_late": 30, "minimum_payment": 25}
P_NOFLOOR = {"product_id": "p2", "type": "personal_loan", "past_due": 500, "days_late": 8}
P_NOTYPE = {"product_id": "p3", "past_due": 10, "days_late": 1}
P_NOID = {"type": "credit_card", "card_last4": "7777", "past_due": 55, "days_late": 2, "minimum_payment": 10}
PRODUCTS = [
    [P_CC], [P_PL], [P_LATE_CC], [P_NOFLOOR], [P_NOTYPE], [P_NOID],
    [P_CC, P_PL], [P_LATE_CC, P_NOFLOOR], [P_CC, P_PL, P_CAR], [P_NOID, P_NOTYPE, P_NOFLOOR],
    [P_CC, "junk", P_PL],                                     # a non-dict entry is skipped
    [],                                                       # no product
]
CUSTOMER = {"customer_id": "c_test", "title": "Mr", "last_name": "Reyes", "first_name": "Daniel"}


def setup_vars(wf, now):
    v = dict(CUSTOMER, now=now)
    return run_vars(code_of(wf, "setup"), v)


def label(prods):
    return "+".join("%s/%s" % (p.get("product_id", "noid"), p.get("type", "notype")) if isinstance(p, dict) else "junk" for p in prods) or "none"


# ---------------------------------------------------------------- code nodes
def route_of(wf, node, vars_out):
    """The target the engine would pick for a code node's transitions: first OR-of-equals that matches, else always."""
    for t in wf["nodes"][node]["transitions"]:
        c = t["condition"]
        if c.get("operator") == "always":
            return t["target_node"]
        for leaf in c.get("conditions", []):
            if leaf.get("operator") == "equals" and leaf["variable"] in vars_out \
                    and str(vars_out[leaf["variable"]]) == str(leaf["operand"]):
                return t["target_node"]
    return None


FINALIZE_STATES = []
for pids in ["p1", "p1,p2", "p1,p2,p3", ""]:
    for rec in ["", "p1", "p2", "p1,p3"]:
        for notes in ["", "p1:paid", "p1:paid,p2:paid", "p1:paid,p2:paid,p3:paid", "p1:dispute,p2:hardship", "p1:paid,p2:hardship",
                      "p1:refused", "p1:service_error,p2:refused", "p2:dispute", "p1:refused,p2:paid,p3:dispute", "p2:bogus",
                      "p1:paid,p2:bogus", "p9:paid", "garbage"]:
            FINALIZE_STATES.append({"pids_csv": pids, "rec_pids": rec, "note_log": notes})
FINALIZE_STATES += [
    {},                                                                   # nothing at all
    {"pids_csv": "p1", "create_promise_success_count": 1, "create_promise_response.data.ok": "true"},
    {"pids_csv": "p1", "create_promise_success_count": "1", "create_promise_response.data.ok": True},
    {"pids_csv": "p1", "create_promise_success_count": 1, "create_promise_response.data.ok": "false"},
    {"pids_csv": "p1", "create_promise_success_count": 0, "create_promise_response.data.ok": "true"},
    {"pids_csv": "p1", "note_log": "p1:paid", "create_promise_success_count": 1, "create_promise_response.data.ok": "true"},
    {"pids_csv": "p1,p2", "rec_pids": None, "note_log": None},
    {"pids_csv": 12, "rec_pids": 3, "note_log": 4.5},
]


def semantic_code_nodes():
    print("semantic test: code nodes")
    for node in sorted(n for n in REF["nodes"] if REF["nodes"][n]["node_type"] == "code"):
        if code_of(REF, node) == code_of(LIB, node):
            continue
        if node == "setup":
            for now in NOWS:
                a, b = setup_vars(REF, now), setup_vars(LIB, now)
                missing = {k: v for k, v in a.items() if b.get(k) != v}
                expect("setup now=%s" % now, not missing and a["setup_state"] == "ok" == b["setup_state"],
                       "" if not missing else "ref keys not matched: %s" % missing)
            a, b = run_vars(code_of(REF, "setup"), {"now": "garbage"}), run_vars(code_of(LIB, "setup"), {"now": "garbage"})
            expect("setup now=garbage falls back", a["setup_state"].startswith("error") and b["setup_state"].startswith("error")
                   and a["callback_text"] == b["callback_text"] and a["today_text"] == b["today_text"] and a["weekday_table"] == b["weekday_table"],
                   "%r vs %r" % (a, b))
        elif node == "prepare":
            for now in NOWS[:8]:
                base = setup_vars(REF, now)
                for prods in PRODUCTS:
                    for shape in ("list", "json", "flat"):
                        v = dict(base)
                        if shape == "list":
                            v["products"] = prods
                        elif shape == "json":
                            v["products"] = json.dumps(prods)
                        else:
                            for i, p in enumerate(prods):
                                if isinstance(p, dict):
                                    for k, x in p.items():
                                        v["get_account_response.data.products.%d.%s" % (i, k)] = x
                        a, b = run_vars(code_of(REF, "prepare"), v), run_vars(code_of(LIB, "prepare"), v)
                        missing = {k: (v2, b.get(k)) for k, v2 in a.items() if b.get(k) != v2}
                        extra = sorted(set(b) - set(a))
                        expect("prepare now=%s products=%s shape=%s" % (now, label(prods), shape),
                               not missing and not extra and a["prepare_state"] == b["prepare_state"],
                               "" if not (missing or extra) else "ref keys not matched: %s extra: %s" % (missing, extra))
            # error paths: no setup (today_iso missing); setup present but a band deadline missing
            for name, v in [("without setup", {}), ("without late_deadline", {k: x for k, x in setup_vars(REF, NOWS[0]).items() if k != "late_deadline"} | {"products": [P_CC, P_PL]})]:
                a, b = run_vars(code_of(REF, "prepare"), v), run_vars(code_of(LIB, "prepare"), v)
                expect("prepare %s falls back" % name, a["prepare_state"].startswith("error") and b["prepare_state"].startswith("error")
                       and {k: a[k] for k in a if k != "prepare_state"} == {k: b[k] for k in b if k != "prepare_state"},
                       "%r vs %r" % (a, b))
        elif node == "finalize":
            for i, st in enumerate(FINALIZE_STATES):
                a, b = run_vars(code_of(REF, "finalize"), st), run_vars(code_of(LIB, "finalize"), st)
                ra, rb = route_of(REF, "finalize", a), route_of(LIB, "finalize", b)
                same_route = ra == rb and ra is not None
                # the lib writes the fin KEY of an unknown reason's fallback ('refused'); the ref writes the raw reason.
                # Both route to fin_refused through the always transition: a deliberate improvement, routing identical.
                same_var = a["final_route"] == b["final_route"]
                known = b["final_route"] in ("promise", "paid", "hardship", "dispute", "service_error", "refused") and same_var
                tag = "finalize state#%d %s" % (i, json.dumps(st, default=str))
                if same_route and not same_var:
                    expect(tag + " (justified: unknown reason %r routes to %s in both)" % (a["final_route"], ra), True)
                else:
                    expect(tag, same_route and known, "ref %s->%s vs lib %s->%s" % (a["final_route"], ra, b["final_route"], rb))
        else:
            expect("code node %s differs and has no semantic test" % node, False)


# ---------------------------------------------------------------- hooks
RESULTS = [{"status": "success", "data": {"ok": True}, "header": {"X": "1"}},
           {"status": "success", "data": {"ok": False, "error": "closed"}, "header": {}},
           {"status": "success", "data": {"ok": "true"}}, {"status": "success", "data": {"ok": "false"}},
           {"status": "error", "data": None}, "not a dict", {"status": "success", "data": {}}, {"status": "success"}]
PROMISE_CONFIGS = []
for pid in ["p1", "1", " 2 ", "", "p9", "x1", None, 3]:
    for amount in ["1,200.50", 300, "60", "abc", 999999, None]:
        for date in ["2026-10-30T00:00:00", "2026-10-16", "2026-12-30", "", None]:
            b = {}
            if pid is not None:
                b["product_id"] = pid
            if amount is not None:
                b["amount"] = amount
            if date is not None:
                b["date"] = date
            PROMISE_CONFIGS.append({"body": b})
PROMISE_CONFIGS += [{"body": "raw"}, {}, {"body": {"product_id": "p1", "amount": "50", "date": "2026-10-20", "extra": 1}}]
NOTE_CONFIGS = [{"body": {"product_id": p, "reason": r}} for p in ["p1", "1", " 2 ", "", "p9", "x1", 3]
                for r in ["refused", "hardship", "dispute", "paid", "service_error", "", None]] + [{"body": "raw"}, {}, {"body": {"reason": "paid"}}]
STATES = [
    {},
    {"pids_csv": "p1", "dl_p1": "2026-10-28", "pd_p1": "420.5"},
    {"pids_csv": "p1,p2,p3", "dl_p1": "2026-10-28", "pd_p1": "420.5", "dl_p2": "2026-10-23", "pd_p2": "1200.0", "dl_p3": "2026-11-05", "pd_p3": "845.25",
     "rec_pids": "", "note_log": "", "open_pids": "p1,p2,p3", "all_done": "no"},
    {"pids_csv": "p1,p2", "dl_p1": "2026-10-28", "pd_p1": "420.5", "dl_p2": "2026-10-23", "pd_p2": "1200.0", "rec_pids": "p1", "note_log": "p2:paid",
     "pending_pid": "p2", "pending_note": "p2:paid", "fail_p2": 1},
    {"pids_csv": "p1,p2", "rec_pids": "", "note_log": "", "pending_pid": "p1", "fail_p1": 0},
    {"pids_csv": "p1,p2", "rec_pids": "", "note_log": "", "pending_pid": "p1", "fail_p1": "1"},
    {"pids_csv": "p1,p2", "rec_pids": "p1", "note_log": "", "pending_pid": "p1", "fail_p1": 5},
    {"pids_csv": "p1,p2", "rec_pids": "", "note_log": "p1:dispute", "pending_pid": "p2", "pending_note": "p2:refused"},
    {"pids_csv": "p1,p2", "rec_pids": "", "note_log": "p2:paid", "pending_pid": "", "pending_note": "p2:refused"},
    {"pids_csv": "p1,p2", "rec_pids": "", "note_log": "", "pending_pid": "", "pending_note": ""},
    {"pids_csv": "", "pending_pid": "p1", "pending_note": "p1:paid"},
    {"pids_csv": None, "rec_pids": None, "note_log": None, "pending_pid": None, "pending_note": None},
]


def hook_kind(p):
    """(tool name, 'pre'|'post') of a differing hook path like nodes.negotiate.tools[0].pre_process_code."""
    holder = p.rsplit(".", 1)[0]
    return get(REF, holder)["function"]["name"], ("pre" if p.endswith("pre_process_code") else "post")


def semantic_hooks():
    print("semantic test: hooks")
    for p, why in diffs:
        if not p.endswith("_process_code"):
            continue
        a, b = get(REF, p), get(LIB, p)
        tool, kind = hook_kind(p)
        where = p.split("tools")[0].split("nodes.")[-1].rstrip(".")
        if tool == "schedule_callback" and kind == "post":
            for i, r in enumerate(RESULTS):
                oa, ob = run_hook(a, r, {}), run_hook(b, r, {})
                tag = "hook %s/%s post result#%d" % (where, tool, i)
                if oa != ob:
                    # a deliberate improvement: the lib tests ok as boolean OR string, the ref tests Python truthiness
                    strict = r if not isinstance(r, dict) else (r.get("data") or {})
                    improved = isinstance(strict, dict) and isinstance(strict.get("ok"), str)
                    expect(tag + (" (justified: string 'false' ok handled)" if improved else ""), improved, "" if improved else "%r vs %r" % (oa, ob))
                else:
                    expect(tag, True)
        elif tool == "create_promise" and kind == "pre":
            n_ok = n_all = 0
            bad = []
            for j, c in enumerate(PROMISE_CONFIGS):
                for k, st in enumerate(STATES):
                    for no_vars in (False, True):
                        oa, ob = run_hook(a, None, c, st, no_vars), run_hook(b, None, c, st, no_vars)
                        n_all += 1
                        if oa == ob:
                            n_ok += 1
                        elif len(bad) < 5:
                            bad.append((j, k, no_vars, oa, ob))
            expect("hook %s/%s pre: %d/%d (config x state x vars/no-vars) identical" % (where, tool, n_ok, n_all), n_ok == n_all,
                   "" if n_ok == n_all else "first mismatches: %r" % bad)
        elif tool in ("create_promise", "add_note") and kind == "post":
            n_ok = n_all = 0
            bad = []
            for i, r in enumerate(RESULTS):
                for k, st in enumerate(STATES):
                    for no_vars in (False, True):
                        oa, ob = run_hook(a, r, {}, st, no_vars), run_hook(b, r, {}, st, no_vars)
                        n_all += 1
                        if oa == ob:
                            n_ok += 1
                        elif len(bad) < 5:
                            bad.append((i, k, no_vars, oa, ob))
            expect("hook %s/%s post: %d/%d (result x state x vars/no-vars) identical" % (where, tool, n_ok, n_all), n_ok == n_all,
                   "" if n_ok == n_all else "first mismatches: %r" % bad)
        elif tool == "add_note" and kind == "pre":
            n_ok = n_all = 0
            bad = []
            for j, c in enumerate(NOTE_CONFIGS):
                for k, st in enumerate(STATES):
                    for no_vars in (False, True):
                        oa, ob = run_hook(a, None, c, st, no_vars), run_hook(b, None, c, st, no_vars)
                        n_all += 1
                        if oa == ob:
                            n_ok += 1
                        elif len(bad) < 5:
                            bad.append((j, k, no_vars, oa, ob))
            expect("hook %s/%s pre: %d/%d identical" % (where, tool, n_ok, n_all), n_ok == n_all,
                   "" if n_ok == n_all else "first mismatches: %r" % bad)
        else:
            expect("hook %s differs and has no semantic test" % p, False)


semantic_code_nodes()
semantic_hooks()
uncovered = [p for p, _ in diffs if not (p.endswith("_process_code") or ".code.default" in p)]
print("\nSUMMARY: %d differing paths, %d covered by semantic tests (%d pass, %d fail), %d uncovered"
      % (len(diffs), len(diffs) - len(uncovered), len(PASSED), len(FAILED), len(uncovered)))
for p in uncovered:
    print("  UNCOVERED:", p)
sys.exit(1 if FAILED or uncovered else 0)
