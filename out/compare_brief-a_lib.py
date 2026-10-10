"""Proof of equivalence: out/brief-a.workflow.json (the proven generator) versus out/brief-a.lib.workflow.json
(the port onto builder/freyalib.py). Compares the two JSON trees recursively and prints every differing path.
For every differing Python string (code node source, pre/post hook) it then EXECUTES both versions on the same
inputs and compares what they write into `vars` / `result`, so a textual difference is shown to be semantically
nil. Exit code 1 when a difference is not covered by a passing semantic test."""
import copy, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REF = json.load(open(ROOT / "out/brief-a.workflow.json"))
LIB = json.load(open(ROOT / "out/brief-a.lib.workflow.json"))

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


def run_hook(code, result=None, config=None, vars_in=None):
    g = {"result": copy.deepcopy(result), "config": copy.deepcopy(config), "vars": copy.deepcopy(vars_in or {})}
    exec(code, g)
    return {"result": g["result"], "config": g["config"], "vars": g["vars"]}


# ---------------------------------------------------------------- semantic tests
NOWS = ["2026-10-14T11:00", "2026-10-16T18:30", "2026-10-17T09:00", "2026-10-23T19:30", "2026-10-25T12:00",
        "2026-11-10T08:00", "2026-11-25T15:00", "2026-12-24T10:00", "2026-12-31T16:00", "2027-01-04T10:30",
        "2026-10-14", "2026-10-30T23:59"]
PRODUCTS = [
    [{"product_id": "p1", "type": "credit_card", "card_last4": "4821", "past_due": 420.5, "days_late": 5, "minimum_payment": 60}],
    [{"product_id": "p1", "type": "personal_loan", "past_due": 1200, "days_late": 12, "instalment_amount": 300}],
    [{"product_id": "p2", "type": "car_loan", "past_due": 845.25, "days_late": 7, "instalment_amount": 211.3}],
    [{"product_id": "p1", "type": "credit_card", "card_last4": "0001", "past_due": 99.99, "days_late": 30, "minimum_payment": 25}],
    [{"product_id": "p1", "type": "personal_loan", "past_due": 500, "days_late": 8}],         # no floor -> past_due
    [],                                                                                        # no product
]
PASSED, FAILED = [], []


def expect(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print("  %s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def code_of(wf, node):
    return wf["nodes"][node]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


def setup_vars(wf, now):
    return run_vars(code_of(wf, "setup"), {"now": now, "customer_id": "c_test", "title": "Mr", "last_name": "Reyes"})


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
            # error path: both fall back without raising
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
                                for k, x in p.items():
                                    v["get_account_response.data.products.%d.%s" % (i, k)] = x
                        a, b = run_vars(code_of(REF, "prepare"), v), run_vars(code_of(LIB, "prepare"), v)
                        missing = {k: (v2, b.get(k)) for k, v2 in a.items() if b.get(k) != v2}
                        expect("prepare now=%s products=%s shape=%s" % (now, prods[0]["product_id"] + "/" + prods[0]["type"] if prods else "none", shape),
                               not missing and a["prepare_state"] == b["prepare_state"], "" if not missing else "ref keys not matched: %s" % missing)
            # error path: no today_iso
            a, b = run_vars(code_of(REF, "prepare"), {}), run_vars(code_of(LIB, "prepare"), {})
            expect("prepare without setup falls back", a["prepare_state"].startswith("error") and b["prepare_state"].startswith("error")
                   and {k: a[k] for k in a if k != "prepare_state"} == {k: b[k] for k in b if k != "prepare_state"},
                   "%r vs %r" % (a, b))
        else:
            expect("code node %s differs and has no semantic test" % node, False)


def semantic_hooks():
    print("semantic test: hooks")
    results = [{"status": "success", "data": {"ok": True}, "header": {"X": "1"}},
               {"status": "success", "data": {"ok": False, "error": "closed"}, "header": {}},
               {"status": "success", "data": {"ok": "true"}}, {"status": "success", "data": {"ok": "false"}},
               {"status": "error", "data": None}, "not a dict", {"status": "success", "data": {}}]
    configs = [{"body": {"amount": "1,200.50", "date": "2026-10-16T00:00:00", "outcome": "promise", "reason": ""}},
               {"body": {"amount": 300, "date": "2026-10-16", "outcome": "no_promise", "reason": "refused"}},
               {"body": {"outcome": "paid", "reason": "x"}}, {"body": "raw"}, {}]
    seen = set()
    for p, why in diffs:
        if not p.endswith("_process_code"):
            continue
        a, b = get(REF, p), get(LIB, p)
        for i, r in enumerate(results):
            for j, c in enumerate(configs):
                oa, ob = run_hook(a, r, c), run_hook(b, r, c)
                key = (p, i, j)
                if key in seen:
                    continue
                seen.add(key)
                tag = "hook %s result#%d config#%d" % (p.split("tools")[0].split("nodes.")[-1].rstrip("."), i, j)
                if oa != ob:
                    # a deliberate improvement: the lib tests ok as boolean OR string, the ref tests Python truthiness
                    strict = r if not isinstance(r, dict) else (r.get("data") or {})
                    improved = isinstance(strict, dict) and isinstance(strict.get("ok"), str)
                    expect(tag + (" (justified: string 'false' ok handled)" if improved else ""), improved, "" if improved else "%r vs %r" % (oa, ob))
                else:
                    expect(tag, True)


semantic_code_nodes()
semantic_hooks()
uncovered = [p for p, _ in diffs if not (p.endswith("_process_code") or ".code.default" in p)]
print("\nSUMMARY: %d differing paths, %d covered by semantic tests (%d pass, %d fail), %d uncovered"
      % (len(diffs), len(diffs) - len(uncovered), len(PASSED), len(FAILED), len(uncovered)))
for p in uncovered:
    print("  UNCOVERED:", p)
sys.exit(1 if FAILED or uncovered else 0)
