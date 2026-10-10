"""Tests of freyalib.gated_digits_identity / digits_from_spec (the opt-in digits gate in front of the identity tool).

The route code is exec'd the way the platform runs a code node (one namespace holding `vars`), and the transitions
are walked with a small evaluator of the deterministic conditions (equals, not_equals, is_set, always; OR of leaves
and AND groups), so each scenario follows the path a call would take. No platform call.

    python3 builder/tests/test_gated_identity.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402

API = fl.load_api(ROOT / "tools" / "openapi.json")
API_E = fl.load_api(ROOT / "tests" / "synthetic" / "brief-e.openapi.json")


def leaf(c, V):
    if "logic" in c:
        f = all if c["logic"] == "and" else any
        return f(leaf(x, V) for x in c["conditions"])
    op, v = c["operator"], V.get(c.get("variable"))
    if op == "always":
        return True
    if op == "is_set":
        return v not in (None, "")
    if op == "is_not_set":
        return v in (None, "")
    if op == "equals":
        return v is not None and str(v) == str(c["operand"])
    if op == "not_equals":
        return v is None or str(v) != str(c["operand"])
    raise AssertionError("operator %s not expected here" % op)


def route(node, V):
    for t in node["transitions"]:
        if leaf(t["condition"], V):
            return t["target_node"]
    return None


def run_code(node, V):
    code = node["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
    exec(compile(code, node["name"], "exec"), {"vars": V})


def build(**kw):
    args = dict(api=API, stage="phone", field_value="phone_last4", n_digits=4,
                ask_task="Ask for the last four digits of the phone number on file.",
                answer_desc="The last four digits of the phone number on file.",
                on_verified="ask_next", on_all_verified="load_account", on_exhausted="fin_failed",
                wrong_line="That does not match our records. What are the last four digits of the phone number on file?",
                unreadable_line="Sorry, I could not read that. What are the last four digits of the phone number on file?",
                extraction=[fl.ext("refusal_phone", ["none", "refused", "question"], "refusal")],
                transitions=[fl.eq("refusal_phone", "refused", "count_decline", "refused")])
    args.update(kw)
    return fl.gated_digits_identity(**args)


def after_check(nodes, V, response):
    """check_phone ran with `response` (data): apply the node-level mapping, then run route_phone and route it."""
    for m in nodes["check_phone"]["response_mapping"]:
        k = m["path"].split(".", 1)[1]
        if k in response:
            V[m["variable"]] = str(response[k]).lower() if isinstance(response[k], bool) else str(response[k])
    assert route(nodes["check_phone"], V) == "route_phone"
    run_code(nodes["route_phone"], V)
    return route(nodes["route_phone"], V)


def test_digits_from_spec():
    assert fl.digits_from_spec(API, "phone_last4") == 4
    assert fl.digits_from_spec(API, "date_of_birth") is None
    assert fl.digits_from_spec(API_E, "company_number") == 8      # "exactly eight digits", not the "seven-digit" sentence
    assert fl.digits_from_spec(API_E, "founded_year") == 4


def test_shape():
    nodes = build()
    assert set(nodes) == {"ask_phone", "ask_phone_wrong", "ask_phone_unread", "check_phone", "route_phone"}
    for k in ("ask_phone", "ask_phone_wrong", "ask_phone_unread"):
        n = nodes[k]
        assert n["node_type"] == "conversation" and n["tools"] == []
        e = n["extraction_schema"][0]
        assert e["name"] == "phone_digits" and e["validation_pattern"] == "^[0-9]{4}$"
        assert n["transitions"][0]["target_node"] == "check_phone"          # the gate comes first
        assert n["transitions"][1]["target_node"] == "count_decline"        # then the brief's own routes
    assert nodes["ask_phone_wrong"]["on_enter"]["type"] == "tts" and "does not match" in nodes["ask_phone_wrong"]["on_enter"]["text"]
    body = nodes["check_phone"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
    assert body["field"]["default"] == "phone_last4" and body["answer"]["default"] == "{{phone_digits}}"
    assert "description" not in body["answer"]                              # baked: the model never fills it
    assert nodes["check_phone"]["node_type"] == "api_request" and nodes["route_phone"]["node_type"] == "code"


def test_gate_holds_partial_and_sentinel():
    nodes = build()
    ask = nodes["ask_phone"]
    assert route(ask, {}) is None                                           # nothing extracted ('44', a cut-off line)
    assert route(ask, {"phone_digits": "0000"}) is None                     # the cleared sentinel is not an answer
    assert route(ask, {"phone_digits": "4471"}) == "check_phone"
    assert route(ask, {"refusal_phone": "refused"}) == "count_decline"


def test_paths():
    nodes = build()
    V = {"phone_digits": "4471"}
    assert after_check(nodes, V, {"ok": True, "verified": True, "all_verified": True, "wrong_answers_left": 3}) == "load_account"
    assert V["phone_digits"] == "0000"                                      # cleared: the same answer is not sent again
    assert route(nodes["ask_phone"], V) is None
    V = {"phone_digits": "4471"}
    assert after_check(nodes, V, {"ok": True, "verified": True, "all_verified": False, "wrong_answers_left": 3}) == "ask_next"
    V = {"phone_digits": "1234"}
    assert after_check(nodes, V, {"ok": True, "verified": False, "all_verified": False, "wrong_answers_left": 2}) == "ask_phone_wrong"
    V["phone_digits"] = "4471"                                              # the customer tries again: the gate opens again
    assert route(nodes["ask_phone_wrong"], V) == "check_phone"
    V = {"phone_digits": "9999"}
    assert after_check(nodes, V, {"ok": True, "verified": False, "all_verified": False, "wrong_answers_left": 0}) == "fin_failed"
    V = {"phone_digits": "4471"}
    assert after_check(nodes, V, {"ok": False, "error": "unreadable"}) == "ask_phone_unread"


def test_stricter_brief_and_extra_routes():
    nodes = build(stop_left=("1", "0"), extra_routes=[fl.eq("id_route", "exhausted", "fin_failed", "the brief's own counter")])
    V = {"phone_digits": "1234"}
    assert after_check(nodes, V, {"ok": True, "verified": False, "wrong_answers_left": 1}) == "fin_failed"
    V = {"phone_digits": "4471", "id_route": "exhausted"}
    assert after_check(nodes, V, {"ok": True, "verified": True, "all_verified": True}) == "fin_failed"


def test_other_length_and_workflow_check():
    nodes = build(api=API_E, stage="company", field_value="company_number", n_digits=fl.digits_from_spec(API_E, "company_number"),
                  extraction=None, transitions=None)
    assert nodes["ask_company"]["extraction_schema"][0]["validation_pattern"] == "^[0-9]{8}$"
    V = {"company_digits": "01234567"}
    run_code(nodes["route_company"], V)
    assert V["company_digits"] == "00000000"
    # assembled with the targets it names: no structural error, every code hook compiles, no '{{' in code, no null
    n2 = build()
    for t, line in (("ask_next", "Next."), ("load_account", "Loaded."), ("fin_failed", "Bye."), ("count_decline", "Bye.")):
        n2[t] = fl.end_node(t, t, line)
    first = fl.opening_conv("opening", "Hello.", "Greet.", [fl.ext("who1", ["customer", "other"], "who")], max_turns=5)
    first["transitions"] = [fl.always("ask_phone")]
    n2["opening"] = first
    wf = fl.assemble("opening", n2, "You are a bank's assistant.", strict=False)
    fl.check(wf)
    assert "null" not in json.dumps(wf)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok", t.__name__)
    print("%d tests passed" % len(tests))
