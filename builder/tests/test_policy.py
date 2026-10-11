"""Tests of builder/policy.py (T1 offer guard, T2 counters in code, T3 state_line, T22 code-built read-back).

Every test execs the generated code-node source exactly as the platform runs a code node: one namespace holding
`vars`, the snippet mutates vars. A call is simulated as a sequence of events (the node the routing would enter),
with the extraction variables set the way the extractor would set them before each event. Dates are around
weekends, a bank holiday and both deadlines; amounts around the floor and the full amount. Example values are the
kit's practice calendar (now = Wednesday 14 October 2026); the module itself holds none of them.

    python3 builder/tests/test_policy.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import freyalib as fl  # noqa: E402
import policy as pol  # noqa: E402

HOL = ["2026-10-26", "2026-11-11"]
TODAY = "2026-10-14"

TEXTS = {
    "_allow_defaults": True,
    # the former library defaults (Brief A wording) that the older tests assert on; a real generator passes the brief's own
    "too_much_floor": "I understand. The lowest amount I can accept is [floor], the [floor_name]. The rest stays overdue.",
    "paid": "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise for your [words].",
    "hardship": "I am sorry to hear that. Would you like me to connect you with our customer support team?",
    "notalk_first": "I understand. This will only take a moment.",
    "wrap_change": "A recorded promise cannot be changed on this call, but you can change it in the mobile app.",
    "human_first": "Before I transfer you, is there anything I can help you with myself?","after_recorded": "You will receive a text message confirming this promise.",
         "wrap_change": "You can change it in the mobile app."}

BODY = r'''
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
monday = today - datetime.timedelta(days=today.weekday())
a1 = lastbd_of_week(monday)
if a1 is None or a1 <= today:
    a1 = lastbd_of_week(monday + datetime.timedelta(days=7))
spec = json.loads(str(vars.get('test_products')))
for i, p in enumerate(spec):
    late = int(p['days_late']) > 7
    dl = addbd(today, 7 if late else 12)
    rungs = [('full_or_floor', a1)] + ([('floor', dl)] if late else [])
    register_product(vars, 'p' + str(i + 1), p['words'], p['full'], p['floor'], 'minimum payment', dl, rungs)
statement = 'STATEMENT'
'''


def mk(multi=False, notes=False):
    return pol.Policy(HOL, texts=TEXTS, multi=multi, notes=notes,
                      note_reasons={"refused": "refused", "hardship": "hardship", "dispute": "dispute",
                                    "paid": "paid", "service_error": "service_error"} if notes else None)


def run(src, V):
    exec(src, {"vars": V})
    return V


def start(products, multi=False, notes=False):
    import json
    P = mk(multi, notes)
    V = {"today_iso": TODAY, "now": TODAY + "T11:00", "test_products": json.dumps(products)}
    run(P.prepare_code(BODY, "statement"), V)
    assert V.get("prepare_state") == "ok", V.get("prepare_state")
    return P, V


def ev(P, V, event, **ext):
    for k, v in ext.items():
        V[k] = v
    run(P.event_code(event), V)
    assert V.get("policy_state") == "ok", (event, V.get("policy_state"))
    for k, neutral in pol.CLEAR_ENUMS.items():
        assert V[k] == neutral, (k, V[k])
    return V


CARD = {"words": "credit card ending 4821", "full": 420, "floor": 126, "days_late": 6}      # early: 1 attempt
LOAN = {"words": "personal loan", "full": 2100, "floor": 700, "days_late": 28}               # late: 2 attempts
CAR = {"words": "car loan", "full": 75, "floor": 25, "days_late": 3}

TESTS = []


def test(f):
    TESTS.append(f)
    return f


@test
def prepare_and_statement():
    P, V = start([CARD])
    assert V["say_next"] == "STATEMENT" and V["route"] == "negotiate"
    assert V["deadline_p1"] == "2026-11-02", V["deadline_p1"]           # 12 business days, 26 Oct holiday skipped
    assert V["offer_question"] == "Can you pay 420 today?", V["offer_question"]
    assert V["state_line"].startswith("Product: credit card ending 4821"), V["state_line"]


@test
def early_refusals_exhaust():
    P, V = start([CARD])
    ev(P, V, "refuse")
    assert V["say_next"] == "Can you pay 420 on Friday 16 October?", V["say_next"]
    assert V["attempts_used_p1"] == "1"
    assert "420 on today" not in V["state_line"] and "420 on 2026-10-14" in V["state_line"], V["state_line"]
    ev(P, V, "refuse")
    assert V["route"] == "fin" and V["final_route"] == "refused", (V["route"], V.get("final_route"))


@test
def too_much_then_ladder_switches_to_floor():          # EXT-A-18
    P, V = start([LOAN])
    ev(P, V, "too_much")
    assert "700" in V["say_next"] and "rest stays overdue" in V["say_next"], V["say_next"]
    assert V["prop_amount"] == "700.0" and V["prop_date"] == TODAY and V["offered_floor_p1"] == "yes"
    ev(P, V, "refuse")
    assert V["say_next"] == "Can you pay 700 on Friday 16 October?", V["say_next"]        # attempt 1 = floor
    ev(P, V, "refuse")
    assert V["say_next"] == "Can you pay 700 on Friday 23 October?", V["say_next"]        # attempt 2 = floor, deadline
    ev(P, V, "accept", stance="accept")
    assert V["route"] == "confirm" and V["ok_amount"] == "700.0" and V["ok_date"] == "2026-10-23"
    assert V["readback_line"] == "To confirm: personal loan, 700, on Friday 23 October. Do you confirm?", V["readback_line"]


@test
def floor_offered_once_only():
    P, V = start([LOAN])
    ev(P, V, "too_much")
    ev(P, V, "too_much")                                   # too much again: a flat refusal, no second floor offer
    assert V["attempts_used_p1"] == "1" and V["say_next"] == "Can you pay 700 on Friday 16 October?", V["say_next"]
    assert "do not offer it again" in V["state_line"]


@test
def weekend_offer():
    P, V = start([CARD])
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-17", offer_amount="")
    assert V["offer_verdict"] == "weekend_or_holiday", V["offer_verdict"]
    assert V["say_next"] == ("Saturday 17 October is not a business day. The next business day is Monday 19 October. "
                             "Can you pay 420 on Monday 19 October?"), V["say_next"]
    ev(P, V, "accept", stance="accept")
    assert V["route"] == "confirm" and V["ok_date"] == "2026-10-19"


@test
def holiday_offer():                                       # PUB-07
    P, V = start([CARD])
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-26")
    assert V["offer_verdict"] == "weekend_or_holiday" and V["prop_date"] == "2026-10-27", V["prop_date"]


@test
def after_deadline_offer():                                # PUB-04
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-11-06")
    assert V["offer_verdict"] == "after_deadline" and V["prop_date"] == "2026-10-23"
    assert V["say_next"].startswith("The latest date I can record is Friday 23 October."), V["say_next"]
    ev(P, V, "refuse")                                     # refusing the deadline is a flat refusal
    assert V["attempts_used_p1"] == "1" and V["prop_date"] == "2026-10-16"


@test
def before_today_offer():
    P, V = start([CARD])
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-12", offer_when="12 October", offer_amount="420")
    assert V["offer_verdict"] == "before_today" and V["prop_date"] == TODAY


@test
def floor_boundaries():
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="exact", offer_amount="700", offer_date="2026-10-22")       # = floor: ok
    assert V["offer_verdict"] == "ok" and V["route"] == "confirm" and V["ok_amount"] == "700.0"
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="exact", offer_amount="699.99", offer_date="2026-10-22")
    assert V["offer_verdict"] == "below_floor" and V["prop_amount"] == "700.0" and V["prop_date"] == "2026-10-22"
    assert V["say_next"].startswith("I cannot record 699.99."), V["say_next"]
    ev(P, V, "offer", offer_kind="exact", offer_amount="500")  # another named amount is not a refusal
    assert V["offer_verdict"] == "below_floor" and V["attempts_used_p1"] == "0", V["attempts_used_p1"]
    assert V["say_next"] == "I cannot record 500." and V["prop_amount"] == "700.0", V["say_next"]
    ev(P, V, "refuse")  # a plain no to the floor is the refusal that spends an attempt
    assert V["attempts_used_p1"] == "1", V["attempts_used_p1"]
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="exact", offer_amount="2100", offer_date="2026-10-16")       # = full: ok
    assert V["offer_verdict"] == "ok"
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="exact", offer_amount="2500")
    assert V["offer_verdict"] == "above_full" and V["prop_amount"] == "2100.0"


@test
def date_and_amount_problems_together():
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="exact", offer_amount="100", offer_date="2026-10-18")
    assert V["offer_verdict"] == "weekend_or_holiday" and V["prop_amount"] == "700.0" and V["prop_date"] == "2026-10-19"
    assert "Sunday 18 October" in V["say_next"] and "I cannot record 100" in V["say_next"], V["say_next"]


@test
def amount_only_keeps_date_on_the_table():
    P, V = start([LOAN])
    ev(P, V, "refuse")                                      # attempt 1: 2100 on Fri 16
    ev(P, V, "offer", offer_kind="exact", offer_amount="1000", offer_date="")
    assert V["route"] == "confirm" and V["ok_date"] == "2026-10-16" and V["ok_amount"] == "1000.0"


@test
def vague_then_deadline():
    P, V = start([CARD])
    ev(P, V, "offer", offer_kind="vague", offer_date="2026-10-19")
    assert V["say_next"] == "Which exact day would that be?" and V["route"] == "negotiate"
    ev(P, V, "offer", offer_kind="vague")
    assert V["prop_date"] == "2026-11-02" and V["say_next"].startswith("The latest date I can record is Monday 2 November."), V["say_next"]


@test
def hardship_with_named_offer():                            # EXT-A-28
    P, V = start([LOAN])
    ev(P, V, "hardship", offer_kind="exact", offer_amount="700", offer_date="2026-10-22")
    assert V["route"] == "hardship" and V["hs_offer"] == "yes" and V["say_next"].startswith("I am sorry")
    assert V["offer_date"] == pol.CLEAR_VALUES["offer_date"] and V["offer_kind"] == "none"   # schema-valid clear
    ev(P, V, "hs_decline", hs_answer="support_no")
    assert V["route"] == "confirm" and V["ok_amount"] == "700.0" and V["ok_date"] == "2026-10-22", (V["route"], V.get("ok_date"))


@test
def hardship_without_offer():                               # PUB-05
    P, V = start([LOAN])
    ev(P, V, "hardship")
    ev(P, V, "hs_decline")
    assert V["route"] == "fin" and V["final_route"] == "hardship"


@test
def hardship_refusal_is_no_persuasion():
    P, V = start([LOAN])
    ev(P, V, "hardship")
    ev(P, V, "too_much")
    assert V["route"] == "fin" and V["final_route"] == "hardship" and V["attempts_used_p1"] == "0"


@test
def confirm_change_reads_back_again():                     # EXT-A-34
    P, V = start([CARD])
    ev(P, V, "refuse")
    ev(P, V, "accept", stance="accept")
    assert V["readback_line"] == "To confirm: credit card ending 4821, 420, on Friday 16 October. Do you confirm?"
    ev(P, V, "change", confirm="change", offer_amount="250")
    assert V["route"] == "confirm" and V["readback_line"] == "To confirm: credit card ending 4821, 250, on Friday 16 October. Do you confirm?", V["readback_line"]
    ev(P, V, "change", confirm="change", offer_date="2026-10-24")      # a Saturday at the read-back
    assert V["route"] == "negotiate" and V["prop_date"] == "2026-10-27", V["prop_date"]   # Mon 26 is a holiday


@test
def confirm_no_is_a_refusal():
    P, V = start([LOAN])
    ev(P, V, "accept", stance="accept")                    # 2100 today
    ev(P, V, "confirm_no", confirm="no")
    assert V["route"] == "negotiate" and V["say_next"] == "Can you pay 2100 on Friday 16 October?", V["say_next"]


@test
def record_retry_then_ok():                                # PUB-10
    P, V = start([CARD])
    ev(P, V, "accept", stance="accept")
    ev(P, V, "confirm_yes", confirm="yes")
    assert V["route"] == "record" and V["rec_pid"] == "p1" and V["rec_amount"] == "420.0" and V["rec_date"] == TODAY
    V["rec_ok"] = "False"
    ev(P, V, "rec_after")
    assert V["route"] == "record"
    V["rec_ok"] = "True"
    ev(P, V, "rec_after")
    assert V["route"] == "wrapup" and V["outcome"] == "promise" and V["reason"] == ""
    assert V["wrap_line"] == ("Your promise is recorded. You will receive a text message confirming this promise. "
                              "Is there anything else I can help you with?"), V["wrap_line"]


@test
def record_fails_twice():
    P, V = start([CARD])
    ev(P, V, "accept", stance="accept")
    ev(P, V, "confirm_yes")
    for _ in range(2):
        V["rec_ok"] = "pending"                            # HTTP 500: nothing mapped
        ev(P, V, "rec_after")
    assert V["route"] == "fin" and V["final_route"] == "service_error", (V["route"], V.get("final_route"))


@test
def wrapup_events():                                       # EXT-A-31, EXT-A-35
    P, V = start([CARD])
    ev(P, V, "accept", stance="accept")
    ev(P, V, "confirm_yes")
    V["rec_ok"] = "true"
    ev(P, V, "rec_after")
    ev(P, V, "wrap_change", wrap="change")
    assert V["route"] == "wrapup" and V["wrap_line"].startswith("You can change it in the mobile app."), V["wrap_line"]
    ev(P, V, "wrap_human", wrap="human")
    assert V["route"] == "wrapup" and V["wrap_line"].startswith("Before I transfer you")
    ev(P, V, "wrap_human", wrap="human")
    assert V["route"] == "xfer_general"
    ev(P, V, "finalize")
    assert V["final_route"] == "promise"


@test
def human_and_notalk_counters():
    P, V = start([CARD])
    ev(P, V, "human", topic="human")
    assert V["route"] == "negotiate" and V["say_next"].startswith("Before I transfer you")
    ev(P, V, "human", topic="human")
    assert V["route"] == "xfer_general"
    P, V = start([CARD])
    ev(P, V, "notalk", topic="no_talk")
    assert V["route"] == "negotiate" and V["say_next"].endswith("Can you pay 420 today?"), V["say_next"]
    ev(P, V, "notalk", topic="no_talk")
    assert V["route"] == "fin" and V["final_route"] == "refused"


@test
def paid_and_dispute_single():
    P, V = start([CARD])
    ev(P, V, "paid", topic="already_paid")
    assert V["route"] == "fin" and V["final_route"] == "paid"
    P, V = start([CARD])
    ev(P, V, "dispute", topic="dispute")
    assert V["final_route"] == "dispute"


@test
def multi_accept_all_today():
    P, V = start([CARD, LOAN, CAR], multi=True, notes=True)
    assert V["stage"] == "all" and V["offer_question"] == "Can you pay all of them today?"
    ev(P, V, "accept", stance="accept")
    assert V["route"] == "confirm" and V["readback_line"].count("today") == 3, V["readback_line"]


@test
def multi_one_date_after_a_deadline():                     # PUB-13
    P, V = start([CARD, LOAN], multi=True, notes=True)
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-30", offer_for="all")
    assert V["route"] == "confirm"
    assert V["agreed_p1"].startswith("420.0|2026-10-30") and V["agreed_p2"].startswith("2100.0|2026-10-23|dl"), (V["agreed_p1"], V["agreed_p2"])
    assert "latest date I can record for it" in V["readback_line"], V["readback_line"]


@test
def multi_one_by_one_with_notes():                         # PUB-12
    P, V = start([CARD, LOAN, CAR], multi=True, notes=True)
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-15", offer_for="first")
    assert V["state_p1"] == "agreed" and V["cur_pid"] == "p2" and V["attempts_used_p2"] == "1", V["say_next"]
    assert V["say_next"].endswith("For your personal loan, can you pay 2100 on Friday 16 October?"), V["say_next"]
    ev(P, V, "refuse")
    assert V["say_next"] == "For your personal loan, can you pay 700 on Friday 23 October?", V["say_next"]
    ev(P, V, "refuse")
    assert V["state_p2"] == "refused" and V["cur_pid"] == "p3" and V["say_next"].startswith("I understand."), V["say_next"]
    ev(P, V, "refuse")
    assert V["state_p3"] == "refused" and V["route"] == "confirm", V["route"]
    assert V["readback_line"].endswith("To confirm: credit card ending 4821, 420, on Thursday 15 October. Do you confirm?"), V["readback_line"]
    ev(P, V, "confirm_yes", confirm="yes")
    V["rec_ok"] = "true"
    ev(P, V, "rec_after")
    assert V["route"] == "note" and V["note_pid"] == "p2" and V["note_reason"] == "refused"
    V["note_ok"] = "true"
    ev(P, V, "note_after")
    assert V["route"] == "note" and V["note_pid"] == "p3"
    V["note_ok"] = "true"
    ev(P, V, "note_after")
    assert V["route"] == "wrapup" and V["outcome"] == "promise"


@test
def multi_refuse_all_today_goes_one_by_one():
    P, V = start([CARD, LOAN], multi=True, notes=True)
    ev(P, V, "refuse")
    assert V["stage"] == "one" and V["cur_pid"] == "p1"
    assert V["say_next"].startswith("Let us go through them one by one.") and V["say_next"].endswith("can you pay 420 on Friday 16 October?"), V["say_next"]


@test
def multi_one_date_for_all_after_one_by_one_started():     # PUB-11
    P, V = start([CARD, LOAN, CAR], multi=True, notes=True)
    ev(P, V, "refuse")
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-16", offer_for="all")
    assert V["route"] == "confirm" and all(V["agreed_" + p].startswith(x) for p, x in
                                           (("p1", "420.0|2026-10-16"), ("p2", "2100.0|2026-10-16"), ("p3", "75.0|2026-10-16"))), V["readback_line"]


@test
def multi_no_promise_closing_order():
    P, V = start([CARD, LOAN], multi=True, notes=True)
    ev(P, V, "paid", topic="already_paid", offer_for="first")
    assert V["state_p1"] == "paid" and V["cur_pid"] == "p2"
    ev(P, V, "dispute", topic="dispute")
    assert V["route"] == "note"
    for _ in range(2):
        V["note_ok"] = "true"
        ev(P, V, "note_after")
    assert V["route"] == "fin" and V["final_route"] == "dispute", V.get("final_route")


@test
def every_event_survives_empty_vars():
    P = mk(True, True)
    for name, e in pol.EVENT_NODES.items():
        V = {}
        exec(P.event_code(e), {"vars": V})
        assert "route" in V and "state_line" in V, (name, V)


@test
def node_sources_are_platform_safe():
    P = mk(True, True)
    nodes = {}
    P.add_event_nodes(nodes)
    for n in nodes.values():
        src = n["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        assert "{{" not in src and "}}" not in src
        compile(src, n["name"], "exec")
        assert n["transitions"][-1]["condition"]["operator"] == "always"


def main():
    fails = 0
    for t in TESTS:
        try:
            t()
            print("ok   " + t.__name__)
        except Exception as e:
            fails += 1
            print("FAIL %s: %r" % (t.__name__, e))
    print("%d/%d policy tests pass" % (len(TESTS) - fails, len(TESTS)))
    return 1 if fails else 0


@test
def test_aside_prefix():
    """A side question in a turn that goes through code is answered first, in the line the route speaks."""
    import json
    P = pol.Policy(HOL, texts=TEXTS, asides={"robot": {"when": "asks whether they talk to a robot", "say": "I am the bank's digital assistant."}})
    V = {"today_iso": TODAY, "now": TODAY + "T11:00", "test_products": json.dumps([CARD])}
    run(P.prepare_code(BODY, "statement"), V)
    assert V.get("prepare_state") == "ok", V.get("prepare_state")
    V["stance"] = "accept"; V["aside"] = "robot"
    run(P.event_code("accept"), V)
    assert V.get("policy_state") == "ok", V.get("policy_state")
    key = {"confirm": "readback_line", "wrapup": "wrap_line"}.get(V.get("route"), "say_next")
    assert V[key].startswith("I am the bank's digital assistant."), (V.get("route"), V[key])
    assert V.get("aside") == "none"
    V["stance"] = "refuse"; V["aside"] = "none"
    run(P.event_code("refuse"), V)
    assert not V["say_next"].startswith("I am the bank"), V["say_next"]
    n = P.confirm_node("t", "c", "d", "a")
    assert any(e["name"] == "aside" for e in n["extraction_schema"]), n["extraction_schema"]


@test
def explicit_confirmation_has_a_safe_fallback_route():
    """The whole-read-back yes can reach recording even if the main confirm enum is missed."""
    P, V = start([CARD])
    n = P.confirm_node("Confirm the offered amount and date.", "read-back answer", "date", "amount")
    fields = {e["name"]: e for e in n["extraction_schema"]}
    assert "Yes, I confirm" in fields["confirm"]["description"]
    assert fields["confirm_affirmative"]["enum_values"] == ["none", "yes"], fields["confirm_affirmative"]
    routes = n["transitions"]
    assert [r["target_node"] for r in routes[:3]] == ["change_offer", "confirm_no", "rec_next"], routes
    yes_conditions = routes[2]["condition"]["conditions"]
    assert {c["variable"] for c in yes_conditions} == {"confirm", "confirm_affirmative"}, yes_conditions
    assert all(c["operator"] == "equals" and c["operand"] == "yes" for c in yes_conditions)
    task = n["task_message"]
    assert "rec_next transition immediately" in task and "Do not say the payment is recorded" in task
    assert "successful create_promise result" in task

    ev(P, V, "accept", stance="accept")
    ev(P, V, "confirm_yes", confirm="other", confirm_affirmative="yes")
    assert V["route"] == "record" and V["rec_pid"] == "p1", V
    assert V.get("recorded_pids", "") == ""


@test
def partial_confirmation_never_records_every_product():
    """A named subset takes the change route before either affirmative signal."""
    P, V = start([CARD, LOAN], multi=True)
    n = P.confirm_node("Confirm both offers.", "read-back answer", "date", "amount")
    routes = n["transitions"]
    yes_index = next(i for i, r in enumerate(routes) if r["target_node"] == "rec_next")
    for ordinal in P.P["ordinals"]:
        partial_index = next(i for i, r in enumerate(routes)
                             if r["target_node"] == "change_offer"
                             and r["condition"]["conditions"][0].get("variable") == "offer_for"
                             and r["condition"]["conditions"][0].get("operand") == ordinal)
        assert partial_index < yes_index
    fields = {e["name"]: e for e in n["extraction_schema"]}
    assert "Agreement to only some products is none" in fields["confirm_affirmative"]["description"]


@test
def test_offer_when_resolved_in_code():
    """'tomorrow' and friends resolve against the CALL's today, not the real clock; a past extracted date is vague."""
    import json, datetime
    P, V = start([CARD])
    src = P.core()
    G = {"vars": V}
    exec(src + "\nout = {}\nfor w in ['tomorrow', 'next friday', 'this saturday', 'friday', 'the 23rd', 'the sixth of november', 'end of the month', 'day after tomorrow', 'in two weeks', 'November 6th', 'Monday the 26th', 'monday the twenty-sixth', 'next friday the 23rd', 'on friday 30', 'the twenty', 'on the thirty', 'the twenty third', '', 'monday the 26th', 'friday the 16th']:\n    d, k = resolve_when(vars, w)\n    out[w] = (d.isoformat() if d else None, k)\n", G)
    out = G["out"]
    assert out["tomorrow"] == ("2026-10-15", "exact"), out
    assert out["day after tomorrow"] == ("2026-10-16", "exact"), out
    assert out["next friday"] == ("2026-10-23", "exact"), out        # Wed 14 Oct: the Friday of the following week
    assert out["this saturday"] == ("2026-10-17", "exact"), out
    assert out["friday"] == ("2026-10-16", "exact"), out
    assert out["the 23rd"] == ("2026-10-23", "exact"), out
    assert out["the sixth of november"] == ("2026-11-06", "exact"), out
    assert out["November 6th"] == ("2026-11-06", "exact"), out
    assert out["in two weeks"] == ("2026-10-28", "exact"), out
    # a day of the month said with a weekday is that day, never the weekday's next occurrence (Freya PUB-07 talkative:
    # 'Monday the twenty-sixth' was read back as Monday 19 October)
    assert out["Monday the 26th"] == ("2026-10-26", "exact"), out
    assert out["monday the twenty-sixth"] == ("2026-10-26", "exact"), out
    assert out["next friday the 23rd"] == ("2026-10-23", "exact"), out
    assert out["on friday 30"] == ("2026-10-30", "exact"), out
    # a day cut off after its tens word is not a day (Freya talkative PUB-04: 'on the twenty' recorded as the 20th)
    assert out["the twenty"] == (None, "vague"), out
    assert out["on the thirty"] == (None, "vague"), out
    assert out["the twenty third"] == ("2026-10-23", "exact"), out
    P2, V2 = start([CARD])
    ev(P2, V2, "offer", offer_kind="exact", offer_date="2026-10-20", offer_when="the twenty", offer_amount="")
    assert V2.get("offer_verdict") == "cutoff", (V2.get("offer_verdict"), V2.get("say_next"))
    assert out["end of the month"] == (None, "vague"), out
    assert out[""] == (None, "none"), out
    assert out["monday the 26th"] == ("2026-10-26", "exact"), out      # the number wins over the weekday (PUB-07)
    assert out["monday the twenty-sixth"] == ("2026-10-26", "exact"), out
    assert out["friday the 16th"] == ("2026-10-16", "exact"), out
    # the offer event: the extraction said 2026-10-11 (real clock) but the words say tomorrow -> 15 Oct is checked
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-11", offer_when="tomorrow", offer_amount="420")
    assert V.get("offer_verdict") == "ok", (V.get("offer_verdict"), V.get("say_next"))
    assert "15 October" in (V.get("readback_line") or V.get("say_next") or ""), (V.get("route"), V.get("readback_line"), V.get("say_next"))
    # a past date with no words is treated as vague (ask once for the exact day), never 'has already passed'
    P, V = start([CARD])
    ev(P, V, "offer", offer_kind="exact", offer_date="2026-10-11", offer_when="", offer_amount="420")
    assert V.get("offer_verdict") == "vague", (V.get("offer_verdict"), V.get("say_next"))


@test
def this_week_date_semantics():
    """Current-week words preserve the named week, even when the day has passed."""
    P, V = start([CARD])  # Wednesday 14 October
    G = {"vars": V}
    exec(P.core() + "\nout = [resolve_when(vars, x) for x in ('this Monday', 'this Wednesday', 'next Monday')]\n", G)
    got = [(d.isoformat() if d else None, kind) for d, kind in G["out"]]
    assert got == [("2026-10-12", "exact"), ("2026-10-14", "exact"), ("2026-10-19", "exact")], got
    ev(P, V, "offer", offer_kind="exact", offer_when="this Monday", offer_date="2026-10-19")
    assert V["offer_verdict"] == "before_today" and V["prop_date"] == TODAY, V["say_next"]
    # The other supported brief mode says both "this" and "next" mean the first day strictly after now.
    P2 = pol.Policy(HOL, texts=TEXTS, weekday_rule="first_after")
    V2 = {"today_iso": "2026-10-16", "now": "2026-10-16T11:00"}  # Friday
    G2 = {"vars": V2}
    exec(P2.core() + "\nout = [resolve_when(vars, x) for x in ('this Friday', 'next Friday')]\n", G2)
    got2 = [(d.isoformat() if d else None, kind) for d, kind in G2["out"]]
    assert got2 == [("2026-10-23", "exact"), ("2026-10-23", "exact")], got2


@test
def once_only_spoken_state():
    P, V = start([LOAN])
    ev(P, V, "too_much")
    assert "already been spoken once" in V["state_line"] and "Current offer, ask exactly" not in V["state_line"], V["state_line"]
    ev(P, V, "offer", offer_kind="exact", offer_amount="200", offer_amount_present="yes")
    assert V["say_next"] == "I cannot record 200." and "ask exactly" not in V["state_line"], V["state_line"]
    P2, V2 = start([LOAN])
    ev(P2, V2, "hardship")
    assert "already spoken once" in V2["state_line"] and "do not repeat" in V2["state_line"], V2["state_line"]
    assert "do not repeat it in dialogue" in P.negotiate_node("t", [], [])["task_message"]
    assert "do not repeat it in dialogue" in P.hardship_node("t", "h", "k", "d", "a")["task_message"]


@test
def amount_references_use_current_product():
    """A named minimum/full amount is resolved from the selected product, including after read-back."""
    P, V = start([LOAN])
    ev(P, V, "offer", offer_kind="none", offer_ref="floor", offer_amount_present="no")
    assert V["route"] == "confirm" and V["ok_amount"] == "700.0" and V["offer_ref"] == "none", V
    ev(P, V, "change", confirm="change", offer_ref="full", offer_amount_present="no")
    assert V["route"] == "confirm" and V["ok_amount"] == "2100.0", V["readback_line"]
    P2, V2 = start([CARD, LOAN], multi=True)
    ev(P2, V2, "offer", offer_kind="none", offer_for="second", offer_ref="floor", offer_amount_present="no")
    assert V2["state_p2"] == "agreed" and V2["agreed_p2"].startswith("700.0|") and V2["state_p1"] == "open", V2
    P4, V4 = start([CARD, LOAN], multi=True)
    ev(P4, V4, "offer", offer_kind="none", offer_for="none", offer_ref="floor", offer_amount_present="no")
    assert V4["route"] == "negotiate" and V4["stage"] == "one", V4
    assert V4["state_p1"] == V4["state_p2"] == "open", V4
    P3, V3 = start([LOAN])
    ev(P3, V3, "offer", offer_kind="exact", offer_ref="floor", offer_amount="0", offer_amount_present="yes")
    assert V3["offer_verdict"] == "below_floor" and V3["prop_amount"] == "700.0", V3["say_next"]


@test
def amount_reference_after_hardship_and_with_too_much():
    P, V = start([LOAN])
    ev(P, V, "hardship", offer_kind="none", offer_ref="floor", offer_amount_present="no")
    assert V["hs_offer"] == "yes" and V["hs_ref"] == "floor", V
    ev(P, V, "hs_decline")
    assert V["route"] == "confirm" and V["ok_amount"] == "700.0", V["readback_line"]
    P2, V2 = start([LOAN])
    ev(P2, V2, "offer", offer_kind="exact", stance="too_much", offer_ref="floor",
       offer_amount_present="no", offer_when="Friday 16 October")
    assert V2["route"] == "confirm" and V2["ok_amount"] == "700.0", V2
    assert "rest stays overdue" in V2["readback_line"], V2["readback_line"]


@test
def reference_extraction_routes_to_guard():
    names = {e["name"] for e in pol.Policy.offer_extraction("d", "a", "k")}
    assert "offer_ref" in names and "offer_amount_present" in names
    transitions = pol.Policy.offer_guard_transitions()
    assert "offer_ref" in str(transitions[0]) and "floor" in str(transitions[0]), transitions
    P = mk()
    assert any(e["name"] == "offer_ref" for e in P.confirm_node("t", "c", "d", "a")["extraction_schema"])
    hs = P.hardship_node("t", "h", "k", "d", "a")
    assert any(e["name"] == "offer_ref" for e in hs["extraction_schema"])
    assert "offer_ref" in str(hs["transitions"]), hs["transitions"]


@test
def cut_off_days_complete_once_without_spending_vague_retry():
    P, V = start([CARD, LOAN], multi=True)
    ev(P, V, "offer", offer_kind="exact", offer_for="all", offer_when="thirty", offer_date="2026-10-30")
    assert V["offer_verdict"] == "cutoff" and V["vague_all"] == "no" and V["pending_when"] == "thirty", V
    ev(P, V, "offer", offer_kind="vague", offer_for="none", offer_when="October", offer_date="2026-10-30")
    assert V["route"] == "confirm" and V["agreed_p1"].startswith("420.0|2026-10-30"), V
    assert V["agreed_p2"].startswith("2100.0|2026-10-23"), V["agreed_p2"]
    assert V["when_prev"] == "thirty" and V["pending_when"] == "", V
    P2, V2 = start([CARD])
    ev(P2, V2, "offer", offer_kind="exact", offer_when="Monday the twenty", offer_date="2026-10-19")
    assert V2["offer_verdict"] == "cutoff" and V2["vague_asked_p1"] == "no", V2
    ev(P2, V2, "offer", offer_kind="exact", offer_when="sixth", offer_date="2026-10-06")
    assert V2["offer_verdict"] == "weekend_or_holiday" and V2["prop_date"] == "2026-10-27", V2["say_next"]


@test
def cardinal_days_and_day_sized_amounts():
    P, V = start([LOAN])
    G = {"vars": V}
    exec(P.core() + "\nout=[resolve_when(vars,w) for w in ('thirty October','October twenty six','Friday twenty three')]\n", G)
    got = [(d.isoformat() if d else None, k) for d, k in G["out"]]
    assert got == [("2026-10-30", "exact"), ("2026-10-26", "exact"), ("2026-10-23", "exact")], got
    ev(P, V, "offer", offer_kind="exact", offer_amount="20", offer_when="Friday twenty")
    assert V["offer_verdict"] == "cutoff" and V["offered_floor_p1"] == "no", V
    ev(P, V, "offer", offer_kind="exact", offer_amount="3", offer_when="Three")
    assert V["route"] == "confirm" and V["ok_date"] == "2026-10-23" and V["ok_amount"] == "2100.0", V
    P2, V2 = start([LOAN])
    ev(P2, V2, "offer", offer_kind="exact", offer_amount="20")
    assert V2["offer_verdict"] == "cutoff_amount" and V2["offered_floor_p1"] == "no", V2
    ev(P2, V2, "offer", offer_kind="exact", offer_amount="20")
    assert V2["offer_verdict"] == "below_floor" and V2["offered_floor_p1"] == "yes", V2


@test
def right_now_requires_a_positive_payment_offer():
    P, V = start([CARD])
    G = {"vars": V}
    exec(P.core() + "\nout=[resolve_when(vars,w) for w in ('too much for me right now','I can pay right now','I cannot pay right now','I can not pay right now','pay it now')]\n", G)
    got = [(d.isoformat() if d else None, k) for d, k in G["out"]]
    assert got == [(None, "none"), (TODAY, "exact"), (None, "none"), (None, "none"), (TODAY, "exact")], got


if __name__ == "__main__":
    sys.exit(main())
