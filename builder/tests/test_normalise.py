"""Table test of freyalib.normalise_pre (T21): speech -> what the tool API expects.

Each case execs the generated pre_process_code exactly as the platform runs a pre hook: `config` is the
substituted request (url, method, headers, body) and `vars` the call variables; the hook edits config['body'] in
place. Every case also runs twice (idempotence: a normalised value passes through unchanged) and once more with
separate globals/locals dicts (exec semantics of an unknown sandbox).

    python3 builder/tests/test_normalise.py
"""
import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import freyalib as fl  # noqa: E402

NOW = "2026-10-14T11:00"          # a Wednesday
UNCHANGED = object()

# (field kind, spoken value, expected value; UNCHANGED = must pass through as is)
DIGITS = [
    ("4471", "4471"),
    ("four four seven one", "4471"),
    ("forty-four seventy-one", "4471"),
    ("forty four seventy one", "4471"),
    ("463... 51", "46351"),
    ("463 then 51", "46351"),
    ("four six three ... five one", "46351"),
    ("double four seven one", "4471"),
    ("oh five one two", "0512"),
    ("zero five one two", "0512"),
    ("44-71", "4471"),
    ("4 4 7 1", "4471"),
    ("It's 4471.", "4471"),
    ("the last four digits are 4471", "4471"),
    ("4471, no sorry, 4472", "4472"),
    ("four four seven one, I mean four four seven two", "4472"),
    ("triple five two", "5552"),
    ("nine oh two one oh", "90210"),
    ("forty four hundred seventy one", "4471"),
    ("hundred", UNCHANGED),                           # doubt -> unchanged
    ("I don't remember", UNCHANGED),
    ("SW1A 1AA", UNCHANGED),
    ("", UNCHANGED),
]

DOB = [
    ("1988-03-14", "1988-03-14"),
    ("fourteenth of March 1988", "1988-03-14"),
    ("the fourteenth of March nineteen eighty-eight", "1988-03-14"),
    ("14 March 88", "1988-03-14"),
    ("14th March 1988", "1988-03-14"),
    ("March 14, 1988", "1988-03-14"),
    ("March fourteen nineteen eighty-eight", "1988-03-14"),
    ("March the twenty-first, nineteen ninety", "1990-03-21"),
    ("14/03/1988", "1988-03-14"),
    ("14.03.1988", "1988-03-14"),
    ("14-03-88", "1988-03-14"),
    ("03/14/1988", "1988-03-14"),         # impossible as dmy, valid swapped
    ("05/04/1990", "1990-04-05"),         # ambiguous: read in the brief's order (dmy)
    ("14031988", "1988-03-14"),
    ("2 Feb 05", "2005-02-02"),
    ("first of January two thousand and five", "2005-01-01"),
    ("12 Dec twenty oh one", "2001-12-12"),
    ("fourteen three nineteen eighty eight", "1988-03-14"),
    ("14 March 1988, no wait, 15 March 1988", "1988-03-15"),
    ("31 February 1988", UNCHANGED),
    ("a long time ago", UNCHANGED),
    ("1988/3/4", "1988-03-04"),
]

DOB_MDY = [
    ("05/04/1990", "1990-05-04"),
    ("14/03/1988", "1988-03-14"),         # impossible as mdy, valid swapped
    ("March 14 1988", "1988-03-14"),
]

DATE = [
    ("2026-10-20", "2026-10-20"),
    ("the twentieth of October", "2026-10-20"),
    ("20 October 2026", "2026-10-20"),
    ("October 20th", "2026-10-20"),
    ("5 January", "2027-01-05"),           # year-less, already past this year -> next year
    ("Friday the 16th of October", "2026-10-16"),
    ("20/10/26", "2026-10-20"),
    ("tomorrow", UNCHANGED),               # no resolver table passed
    ("next Friday", UNCHANGED),
]

DATE_REL = [
    ("tomorrow", "2026-10-15"),
    ("next Friday", "2026-10-16"),
    ("this Friday", "2026-10-16"),
    ("on Friday", "2026-10-16"),
    ("day after tomorrow", "2026-10-16"),
    ("the 20th of October", "2026-10-20"),
    ("sometime next week", UNCHANGED),
]

AMOUNT = [
    (420.5, 420.5),
    (300, 300.0),
    ("420", 420.0),
    ("four hundred and twenty point five", 420.5),
    ("twelve fifty", 1250.0),
    ("1,250.00", 1250.0),
    ("$1,250", 1250.0),
    ("1250 dollars", 1250.0),
    ("two thousand five hundred", 2500.0),
    ("a hundred and fifty", 150.0),
    ("three hundred dollars and fifty cents", 300.5),
    ("four hundred, no, four fifty", 450.0),
    ("one thousand two hundred and thirty four", 1234.0),
    ("2.5k", 2500.0),
    ("fifty", 50.0),
    ("point five", 0.5),
    ("as much as I can", UNCHANGED),
    ("1.250,00", UNCHANGED),
]

TIME = [
    ("14:30", "14:30"),
    ("9:05", "09:05"),
    ("eleven in the morning", "11:00"),
    ("half past two", "14:30"),
    ("11am", "11:00"),
    ("11 a.m.", "11:00"),
    ("3pm", "15:00"),
    ("quarter to four", "15:45"),
    ("quarter past ten", "10:15"),
    ("ten thirty", "10:30"),
    ("two o'clock", "14:00"),
    ("noon", "12:00"),
    ("nine fifteen in the morning", "09:15"),
    ("4.30 pm", "16:30"),
    ("whenever suits you", UNCHANGED),
]


def run(code, body, variables, split_scope=False):
    config = {"url": "https://bank.example/v1/tool", "method": "POST",
              "headers": {"Content-Type": "application/json"}, "body": body}
    g = {"config": config, "vars": variables}
    if split_scope:
        exec(code, {"__builtins__": __builtins__}, g)
    else:
        exec(code, g)
    return config["body"]


def check(code, field, value, expected, variables, extra_body=None, label=""):
    errs = []
    want = value if expected is UNCHANGED else expected
    for split in (False, True):
        body = dict(extra_body or {})
        body[field] = copy.deepcopy(value)
        out = run(code, body, dict(variables), split)[field]
        if out != want or type(out) is not type(want):
            errs.append("%s %r -> %r (want %r)%s" % (label, value, out, want, " [split scope]" if split else ""))
            break
        again = run(code, {**(extra_body or {}), field: copy.deepcopy(out)}, dict(variables), split)[field]
        if again != out:
            errs.append("%s not idempotent: %r -> %r -> %r" % (label, value, out, again))
            break
    return errs


def main():
    v = {"now": NOW, "customer_id": "c_1"}
    rel_vars = dict(v)
    exec(fl.relative_days_code("now", "relative_days"), {"vars": rel_vars})

    suites = [
        ("digits", fl.normalise_pre({"answer": "digits"}), "answer", DIGITS, v, None),
        ("answer/phone", fl.normalise_pre(["answer"]), "answer", DIGITS[:19], v, {"field": "phone_last4"}),
        ("dob", fl.normalise_pre({"answer": "dob"}, date_order="dmy"), "answer", DOB, v, None),
        ("answer/dob", fl.normalise_pre(["answer"]), "answer", DOB, v, {"field": "date_of_birth"}),
        ("dob mdy", fl.normalise_pre({"answer": "dob"}, date_order="mdy"), "answer", DOB_MDY, v, None),
        ("date", fl.normalise_pre(["date"]), "date", DATE, v, None),
        ("date rel", fl.normalise_pre(["date"], relative_var="relative_days"), "date", DATE_REL, rel_vars, None),
        ("amount", fl.normalise_pre(["amount"]), "amount", AMOUNT, v, None),
        ("time", fl.normalise_pre(["time"]), "time", TIME, v, None),
    ]
    errors, n = [], 0
    for label, code, field, table, variables, extra in suites:
        assert "{{" not in code and "}}" not in code
        compile(code, label, "exec")
        for value, expected in table:
            n += 1
            errors += check(code, field, value, expected, variables, extra, label)

    # two-digit year without `now` is a doubt: left as is
    n += 1
    errors += check(fl.normalise_pre({"answer": "dob"}), "answer", "14 March 88", UNCHANGED, {}, None, "no-now")
    # several fields at once, other fields untouched, a non-dict body and a missing field never raise
    n += 1
    code = fl.normalise_pre({"amount": "amount", "date": "date"})
    body = run(code, {"customer_id": "c_1", "product_id": "p1", "amount": "twelve fifty", "date": "20 October"}, dict(v))
    if body != {"customer_id": "c_1", "product_id": "p1", "amount": 1250.0, "date": "2026-10-20"}:
        errors.append("multi-field body: %r" % body)
    n += 1
    for weird in ("raw string body", None, 42):
        config = {"url": "u", "method": "POST", "headers": {}, "body": weird}
        exec(code, {"config": config, "vars": {}})
    exec(code, {"config": {"body": {"customer_id": "c_1"}}, "vars": {}})
    # helpers
    n += 1
    e = fl.digit_extraction("phone_last4", 4, "Last four digits of the phone number")
    if e != {"name": "phone_last4", "type": "string", "description": "Last four digits of the phone number",
             "validation_pattern": "^[0-9]{4}$", "max_retries": 2, "min_confidence": 0.5}:
        errors.append("digit_extraction: %r" % e)
    n += 1
    if "all 4 digits" not in fl.latest_value_note(4) or "LAST value" not in fl.latest_value_note(4):
        errors.append("latest_value_note: %r" % fl.latest_value_note(4))
    n += 1
    tool = fl.api_tool(fl.load_api(str(pathlib.Path(__file__).resolve().parents[2] / "tools/openapi.json")),
                       "create_promise", baked={"product_id": "p1"},
                       pre=fl.normalise_pre({"amount": "amount", "date": "date"}) + fl.promise_pre())
    wf = fl.assemble("n", {"n": fl.conv("n", "t", tools=[tool], transitions=[fl.always("e")]),
                           "e": fl.end_node("e", "e", "Bye.")}, "s", strict=False)
    try:
        fl.check(wf)
    except ValueError as ex:
        errors.append("check() rejects a tool carrying the hook: %s" % ex)

    for e in errors:
        print("FAIL " + e)
    print("%d/%d normalisation cases pass" % (n - len(errors), n))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
