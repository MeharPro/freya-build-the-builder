"""Generator for tests/synthetic/brief-d.md (Kestrel Bank, autumn arrears campaign; raw material pack: email,
CP-7 section 4 excerpt, the 12 October memo overriding parts of both, dialler code list v3) on builder/freyalib.py
+ builder/multiproduct.py. Writes out/brief-d.workflow.json.

Rule in force = memo over CP-7 over the email (the email says CP-7 wins, "unless a later memo says otherwise"):
  memo 1: Band S latest date = 5th business day (not 7th)        memo 2: Band S = 2 attempts (final-offer repeat gone)
  memo 3: card floor = min(2 x minimum_payment, past_due)         memo 4: Founders' Day 2026-10-30 is a closure day
  memo 5: hardship-declined close code HSHP (not HARD)            memo 6: callbacks 09:00 to 18:00 included
Every value below is taken from brief-d.md; `# R..` names the brief item / section it implements."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402
import multiproduct as mp  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")
# R CP-7 4.3 closure days + memo 4 (Founders' Day, Friday 30 October 2026). Monday 26 October is a normal day.
HOLIDAYS = ["2026-10-30", "2026-11-20", "2026-12-24", "2026-12-25", "2026-12-28", "2026-12-31"]

nodes = {}

# ---------------------------------------------------------------- terminals (code list v3 + memo 5)
# key: (outcome, reason code, farewell). Every close carries a code, promise and paid included (email "Closing").
BYE = "Thank you for your time, {{title}} {{last_name}}. Goodbye."
FINS = {
    "promise": ("promise", "PRM", BYE),          # 1; the verbatim email sentence is said once by `wrapup`
    "paid": ("paid", "AP", "Payments made today show on our side on the next business day. " + BYE),       # 2 + verbatim sentence
    "transferred_restructuring": ("transferred", "TRS", "I am transferring you to our restructuring team now. Thank you, {{title}} {{last_name}}. Goodbye."),
    "transferred_human": ("transferred", "TRH", "I am transferring you to a colleague now. Thank you, {{title}} {{last_name}}. Goodbye."),
    "transferred_support": ("transferred", "TSP", "I am transferring you to our customer care team now. Thank you, {{title}} {{last_name}}. Goodbye."),
    "refused": ("no_promise", "RF", "I understand. " + BYE),                                                 # 6
    "hardship": ("no_promise", "HSHP", "I understand. Take care. " + BYE),                                   # 7, memo 5
    "dispute": ("no_promise", "DSP", "Thank you for telling me. " + BYE),                                    # 8
    "service_error": ("no_promise", "SVC", "I am sorry, our system could not complete this because of a technical problem. " + BYE),  # 9
    "svc_identity": ("not_verified", "SVC", "I am sorry, our security check is not working at the moment, so I cannot continue. Thank you, goodbye."),  # 10
    "failed": ("not_verified", "IDF", "For security I cannot continue by phone. You can use the Kestrel mobile app or visit a branch. Thank you, goodbye."),  # 11
    "declined": ("not_verified", "IDD", "I understand. Without the security questions I cannot discuss anything. Thank you, goodbye."),  # 12
    "callback": ("not_reached", "CBK", "Thank you, we will call back then. Goodbye."),                       # 13
    "no_callback": ("not_reached", "NCB", "Thank you for your help. Goodbye."),                              # 14
    "wrong_number": ("not_reached", "WN", "I apologise for the inconvenience. Thank you, goodbye."),                     # 15
    "deceased": ("not_reached", "DEC", "Please accept my condolences. Thank you, goodbye."),                            # 16 + verbatim
    "unclear": ("not_reached", "UNC", "I am sorry, I could not confirm who I am speaking with. Thank you, goodbye."),   # 17
}
for key, (outcome, reason, farewell) in FINS.items():
    fl.end_pair(key, outcome, reason, farewell, nodes, outcome_var="close_outcome", reason_var="close_code")  # not `reason`: add_note has a model-filled `reason`

# ---------------------------------------------------------------- setup: dates (all from `now`)
# R 4.1 Band F latest date: calendar day 21 days after the call date; not a business day -> the last business day
#   before it. Band S (memo 1): the 5th business day after the call date (day 0 = call date).
# R 4.8 attempt 1: the next business day after the call date.
# R 4.6 vague period: last business day of the current week; on that day, the next business day after it.
# R 4.7 weekday words: "next X" = first X after the call date (same week allowed; on X itself, 7 days later);
#   "this X" and a bare "X" = the same day = the first X from today on (today when the call is on X).
SETUP_EXTRA = r'''
vars['close_outcome'] = 'not_reached'
vars['close_code'] = 'UNC'
vars['attempt1_date'] = addbd(today, 1).isoformat()
vars['f_deadline'] = prev_bd(today + datetime.timedelta(days=21)).isoformat()
vars['s_deadline'] = addbd(today, 5).isoformat()
monday = today - datetime.timedelta(days=today.weekday())
vg = lastbd_of_week(monday)
if vg is None or vg <= today:
    vg = addbd(today, 1)
vars['vague_iso'] = vg.isoformat()
vars['vague_text'] = txt_short(vg)
tab = []
for i in range(7):
    k = (i - today.weekday()) % 7
    this_d = today + datetime.timedelta(days=k)
    next_d = today + datetime.timedelta(days=(k if k > 0 else 7))
    tab.append('"' + WD[i] + '" or "this ' + WD[i] + '" = ' + txt(this_d) + ' (' + this_d.isoformat() + '); "next ' + WD[i] + '" = ' + txt(next_d) + ' (' + next_d.isoformat() + ')')
vars['weekday_table'] = '\n'.join(tab)
'''
# R79 (memo effective date): the memo applies "from the first call on Wednesday 14 October", the campaign's go-live;
# no campaign call happens before it, so its values are applied unconditionally (not gated on `now`).
# R 4.4 + memo 6: today later than now, or the next two business days, 09:00 to 18:00 both included.
SETUP = fl.SETUP_CODE(HOLIDAYS, callback_rule={"open": "09:00", "close": "18:00", "same_day": True, "days_ahead": 2},
                      extra=SETUP_EXTRA,
                      fallbacks={"close_outcome": "not_reached", "close_code": "UNC", "attempt1_date": "", "f_deadline": "", "s_deadline": "", "vague_iso": "", "vague_text": ""})

# ---------------------------------------------------------------- prepare: per-product facts
# R 4.1 bands per product (F 1-10: 1 attempt; S 11+: 2 attempts per memo 2; over 45 -> S).
# R 4.2 + memo 3 floors: card = 2 x minimum_payment capped at past_due; loans = instalment_amount.
# R email "Stating the arrears": "arrears team", "overdue payment", per product: words, overdue amount, days overdue;
#   the first ask is verbatim ("Are you able to clear the overdue amount today?" / "... all of these today?").
PREPARE = mp.prepare_code(
    HOLIDAYS,
    api=API, pid_field="product_id", amount_field="past_due", days_late_field="days_late", type_field="type",
    extra_code="vars['acct_route'] = 'ok' if prods else 'fail'\nvars['close_outcome'] = 'no_promise'\nvars['close_code'] = 'RF'\n",
    statement_fallback="Thank you. I am calling from the arrears team about an overdue payment. Are you able to clear the overdue amount today?",
    bands=[{"name": "F", "max_days_late": 10, "attempts": 1, "deadline_var": "f_deadline"},
           {"name": "S", "max_days_late": None, "attempts": 2, "deadline_var": "s_deadline"}],
    floor_rules=[{"types": ["credit_card"], "expr": "min(2 * float(p.get('minimum_payment') or 0), amount)", "name": "twice the minimum payment"},
                 {"types": None, "field": "instalment_amount", "name": "instalment"}],
    wording=[{"types": ["credit_card"], "template": "credit card ending {card_last4}"},
             {"types": None, "template": "{type_words}"}],
    unknown_type_words="account",
    statement={
        "one": "Thank you, {title} {last_name}. I am calling from the arrears team about an overdue payment. Your {words} has an overdue amount of {past_due}, and it is {days_late} days overdue. Are you able to clear the overdue amount today?",
        "many_head": "Thank you, {title} {last_name}. I am calling from the arrears team about overdue payments on {n} of your products. ",
        "many_item": "Your {words} has an overdue amount of {past_due}, {days_late} days overdue. ",
        "many_tail": "Are you able to clear all of these today?",
    },
    line_template=("{pid} = your {words}: full overdue amount {past_due}, {days_late} days overdue (band {band}). "
                   "Floor (smallest amount that can be recorded) {floor} ({floor_name}). "
                   "Latest date {deadline_text} ({deadline_iso}). "
                   "Attempt 1: propose the amount in play ({past_due}, or the floor {floor} once the customer said the full amount is too much) on {a1_text} ({a1_iso}). "),
    attempt2_template=("Attempt 2: propose the floor {floor} on the latest date {deadline_text} ({deadline_iso}). "
                       "Persuasion attempts for this product: {attempts}. After attempt 2 is refused, stop: this product is refused (2 attempts)."),
    one_attempt_template="NO attempt 2. Persuasion attempts for this product: 1. After attempt 1 is refused, stop: this product is refused (1 attempt).",
    attempt1_var="attempt1_date",
    closed_day_move="before",            # R 4.6: closed day -> nearest business day BEFORE the named day
    calendar_extra_days=10)

# ---------------------------------------------------------------- opening (email "Opening")
WHO_VALUES = ["customer", "someone_else", "wrong_number", "deceased", "refuses", "unclear"]
WHO_DESC = ("Who answered, judged ONLY from the person's latest message. "
            "customer = they confirm: 'yes', 'speaking', 'that's me', or they say their own name ({{first_name}} / {{last_name}}). "
            "someone_else = another person answered (a relative, partner, flatmate, colleague), says the customer is not here or not available, or offers to take a message. "
            "wrong_number = says this number does not belong to that person / they do not know them. "
            "deceased = says the customer has died / passed away. "
            "refuses = says they do not want to talk / not interested. "
            "unclear = anything else: 'hello', 'go ahead', 'who's asking', 'what is this about?', any question, silence.")
ASK_NAME = "Am I speaking with {{first_name}} {{last_name}}?"
OPENING_ROUTES = [
    ("customer", "ask_phone", "the customer confirmed who they are"),
    ("deceased", "fin_deceased", "the customer has died"),
    ("wrong_number", "fin_wrong_number", "wrong number"),
    ("someone_else", "third_party", "someone else answered"),
]
nodes["opening"] = fl.opening_conv(   # chat route: the dialogue model speaks the first line, so the task repeats it
    "opening", "This is the digital assistant of Kestrel Bank. Please note that this call is recorded. " + ASK_NAME,
    "you have just introduced yourself and asked: \"" + ASK_NAME + "\" Do not call any tool in this turn. Do not say why you are calling.",
    [fl.ext("who1", WHO_VALUES, WHO_DESC)])
INITIAL = fl.conversation_first("opening", SETUP, "who1", OPENING_ROUTES, "opening_retry", nodes)

NEVER_SAY = ("NEVER say, before identity is confirmed: arrears, overdue, late, collections, debt, payment, instalment, or the name of any product "
             "(credit card, loan, car loan). Not even when asked what the call is about.")
nodes["opening_retry"] = fl.conv(
    "opening_retry",
    "You asked whether you are speaking with {{first_name}} {{last_name}}, but the answer did not confirm it. This is your second and LAST ask. "
    "No tool call is allowed in this turn. " + NEVER_SAY + "\n"
    "If the person asked a question, answer it first in one sentence: who is this -> you are the digital assistant of Kestrel Bank; "
    "a robot or an AI -> say exactly \"I am Kestrel Bank's digital assistant.\"; a scam -> they are welcome to hang up and call the number on the back of their card or on their statement; "
    "what it is about -> you can only discuss that with {{first_name}} {{last_name}}. "
    "If they said they do not want to talk, say this will only take a moment. "
    "Then ask exactly: \"" + ASK_NAME + "\"",
    extraction=[fl.ext("who2", WHO_VALUES, WHO_DESC)],
    transitions=[
        fl.eq("who2", "customer", "ask_phone", "the customer confirmed who they are"),
        fl.eq("who2", "deceased", "fin_deceased", "the customer has died"),
        fl.eq("who2", "wrong_number", "fin_wrong_number", "wrong number"),
        fl.eq("who2", "someone_else", "third_party", "someone else answered"),
        fl.eq("who2", "refuses", "fin_declined", "does not want to talk, a second time, before identity"),
        fl.always("fin_unclear"),
    ])

# ---------------------------------------------------------------- third party (email "Someone else answers")
cb_tool = fl.api_tool(
    API, "schedule_callback",
    description="Book a callback for the customer. CALL it as soon as the person names (or accepts) a day and time inside the allowed window.",
    field_descriptions={"date": "Callback date as YYYY-MM-DD. Must be one of the allowed days.",
                        "time": "Callback time as HH:MM, 24 hour, from 09:00 up to and including 18:00."},
    post=fl.ok_post("Callback booked.", "The booking failed. Call schedule_callback once more with the same values."))

nodes["third_party"] = fl.conv(
    "third_party",
    "You called for {{title}} {{last_name}} ({{first_name}}) but someone else is on the line.\n"
    "Say that this is a personal banking matter that you can only discuss with {{title}} {{last_name}}, and ask when they can be reached. Nothing more.\n"
    "STRICT: " + NEVER_SAY + " Never mention any account, amount or the reason for the call. Ask no security question. "
    "If they offer to pay, to answer questions, or to help, decline politely (you can only discuss it with {{title}} {{last_name}}) and ask again when they can be reached.\n"
    "Now: {{today_text}}, {{now_time}}.\n{{callback_text}}\n"
    "- A day and time inside the window -> call schedule_callback with date YYYY-MM-DD and time HH:MM. 'Tomorrow morning around eleven' = tomorrow at 11:00. "
    "Only a day -> ask for a time. Only a vague time like 'morning' -> propose a precise time such as 11:00 and ask if it suits.\n"
    "- Outside the window -> propose ONCE the nearest slot inside the window (a precise day and HH:MM). If they accept, book it.\n"
    "- If they do not accept that slot, or cannot say when: book nothing, call transition_to_fin_no_callback.\n"
    "After every tool result, speak or call the next tool.",
    tools=[cb_tool],
    extraction=[fl.ext("tp_status", ["none", "wrong_number", "deceased"],
                       "From the person's latest message: wrong_number if they say this number does not belong to the customer or they do not know the customer; deceased if they say the customer has died; otherwise none.")],
    transitions=[
        fl.ok_true("schedule_callback", "fin_callback", "callback booked"),
        fl.eq("tp_status", "deceased", "fin_deceased", "customer died"),
        fl.eq("tp_status", "wrong_number", "fin_wrong_number", "wrong number"),
        fl.intent_tool("fin_no_callback",
                       "No callback can be booked: the person turned down the one slot proposed inside the window, or cannot say when the customer is reachable.",
                       "No callback can be booked inside the allowed window"),
    ])

# ---------------------------------------------------------------- identity (email "Identity")
# R: phone_last4 first, then date_of_birth; the SECOND wrong answer on either question ends the check (the service
# allows three: stop at wrong_answers_left 1, or 0); a day_month_swapped hint is not a wrong answer.
HINTS = {"day_month_swapped": "Day and month look swapped. This is NOT a wrong answer. Ask the customer to repeat the date of birth with the month as a word, for example 14 March 1988."}
STOP_LEFT = ("1", "0")
MAX_WRONG = "Second wrong answer: the security check has FAILED. Do not ask anything else and do not say what the call is about."
ID_OK = "Both answers are correct. Identity verified."
WRONG = "Wrong answer (this was the first). Tell the customer it does not match our records and ask again: {question}"

transfer_general = fl.api_tool(API, "transfer_to_agent", baked={"queue": "general"},
                               description="Transfer the call to a person. CALL it straight away when the customer asks for a person, a human or an agent.")

ID_COMMON = ("Rules for this step:\n"
             "- " + NEVER_SAY + " If asked what the call is about or how much they owe, say you can explain once the security questions are done.\n"
             "- If they say they do not want to talk: say once that this will only take a moment, and ask the question again.\n"
             "- If the customer does not want to answer, or asks what the call is about instead of answering: explain that the questions are there to protect their account and that nothing can be discussed without them, and ask the question again.\n"
             "- If the customer asks for a person: call transfer_to_agent straight away, no 'can I help you first'.\n"
             "- Robot or AI -> \"I am Kestrel Bank's digital assistant.\" Scam -> they are welcome to hang up and call the number on the back of their card or on their statement. Then ask the question again.\n"
             "- After every tool result, speak to the customer or call the next tool. Follow what_to_do_next.")
REFUSAL_DESC = ("From the customer's LATEST message only: refused if they decline to answer the security question, say they do not want to talk, "
                "or ask what the call is about instead of answering. none if they give an answer or say anything else.")
WRONG_LEFT = "verify_identity_response.data.wrong_answers_left"
FAILED = fl.tr("fin_failed", "second wrong answer", *[fl.cond(WRONG_LEFT, "equals", v) for v in STOP_LEFT])
ID_SVC = fl.count_gt("verify_identity_failure_count", 1, "fin_svc_identity", "the identity service failed repeatedly")

nodes["ask_phone"] = fl.conv(
    "ask_phone",
    "The person confirmed they are {{first_name}} {{last_name}}. From now on address them as {{title}} {{last_name}}. "
    "Before anything else you must check identity with two security questions, one at a time. Ask the first now: the last four digits of their phone number.\n"
    "When they give four digits, call verify_identity with answer = the four digits only.\n" + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "phone_last4"},
                       description="Check the last four digits of the phone number. CALL it every time the customer gives four digits.",
                       field_descriptions={"answer": "Exactly four digits."},
                       post=fl.verify_post("What are the last four digits of your phone number?", HINTS, MAX_WRONG,
                                           all_verified_text=ID_OK, verified_text="Correct. Now ask for the date of birth.",
                                           wrong_text=WRONG, stop_left=STOP_LEFT)), transfer_general],
    extraction=[fl.ext("refusal_phone", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        FAILED,
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.is_true("verify_identity_response.data.verified", "ask_dob", "phone digits correct"),
        fl.transferred("fin_transferred_human", "transferred"),
        ID_SVC,
        fl.eq("refusal_phone", "refused", "count_decline_phone", "customer declined"),
    ])

nodes["ask_dob"] = fl.conv(
    "ask_dob",
    "The phone digits were correct. Now ask the second security question: their date of birth.\n"
    "When they give it, call verify_identity with answer = the date as YYYY-MM-DD, however they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03-05). "
    "If they give only part of the date, ask for the rest before calling the tool.\n" + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "date_of_birth"},
                       description="Check the date of birth. CALL it every time the customer gives a full date of birth.",
                       field_descriptions={"answer": "The date of birth as YYYY-MM-DD."},
                       post=fl.verify_post("What is your date of birth?", HINTS, MAX_WRONG, all_verified_text=ID_OK,
                                           wrong_text=WRONG, stop_left=STOP_LEFT)), transfer_general],
    extraction=[fl.ext("refusal_dob", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        FAILED,
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.transferred("fin_transferred_human", "transferred"),
        ID_SVC,
        fl.eq("refusal_dob", "refused", "count_decline_dob", "customer declined"),
    ])

# R: explain once; a second decline (or asking again what it is about) closes IDD.
for stage in ["phone", "dob"]:
    code = fl.counter_code("decline_count", 2, "decline_route", reset={"refusal_phone": "none", "refusal_dob": "none"})
    nodes[f"count_decline_{stage}"] = fl.code_node(f"count_decline_{stage}", code, [
        fl.eq("decline_route", "close", "fin_declined", "second decline"), fl.always(f"ask_{stage}")])

# ---------------------------------------------------------------- account
nodes["load_account"] = fl.api_node(
    "load_account", fl.api_tool(API, "get_account", description="Get the products in arrears.", retries=2),
    [fl.always("prepare")], mapping=[{"path": "data.products", "variable": "products"}])
nodes["prepare"] = fl.code_node("prepare", PREPARE, [
    fl.eq("acct_route", "fail", "fin_service_error", "get_account returned no products (service failed)"),
    fl.always("negotiate")])

# ---------------------------------------------------------------- promise + note tools
NOTE_ENUM = mp.note_reasons(API)
# R "Read-back and recording": up to three tries in total for the same promise, then a service_error note.
PROMISE_PRE = mp.promise_pre_code(cap_to_deadline=True, cap_to_amount=True, api=API,
                                  snap_closed="before", holidays=HOLIDAYS)
PROMISE_POST = mp.promise_post_code(max_fails=3, fail_reason="service_error", api=API)
NOTE_PRE = mp.note_pre_code(api=API)
NOTE_POST = mp.note_post_code(api=API)

# R code list "Note reasons": what the text must contain, per reason.
NOTE_TEXT = ("Required. What the note must contain: refused -> the number of persuasion attempts made and the last offer (amount and date), "
             "e.g. '2 attempts; last offer 440 on 2026-10-21'; hardship -> the circumstance in the customer's own words; "
             "dispute -> what is disputed; paid -> the channel and the day the customer says they paid; "
             "service_error -> the words 'create_promise' and the number of tries, e.g. 'create_promise failed after 3 tries'.")


def promise_tool():
    return fl.api_tool(API, "create_promise",
                       description="Record ONE product's payment promise. CALL it once per agreed product, in PRODUCTS order, only after the read-back and a clear yes to 'Shall I record that?'.",
                       field_descriptions={"product_id": "The product id exactly as in PRODUCTS, for example p1.",
                                           "amount": "The agreed amount for this product, a number like 420.5.",
                                           "date": "The agreed payment date for this product as YYYY-MM-DD."},
                       pre=PROMISE_PRE, post=PROMISE_POST)


def note_tool():
    return fl.api_tool(API, "add_note",
                       description="Record why ONE product ends the call without a promise. CALL it once for every product without a recorded promise. Never after a transfer.",
                       field_descriptions={"product_id": "The product id exactly as in PRODUCTS, for example p2.",
                                           "reason": "Why this product has no promise. One of: " + ", ".join(NOTE_ENUM) + ".",
                                           "text": NOTE_TEXT},
                       required=["product_id", "reason", "text"],
                       pre=NOTE_PRE, post=NOTE_POST)


TRANSFERRED = fl.transferred("fin_transferred_human", "transferred to a person")
ALL_DONE = mp.all_done_tr("finalize", "every product has a recorded promise or a note")

FACTS = ("PRODUCTS (in get_account order)\n{{products_text}}\n"
         "DATES\n- Today: {{today_text}} ({{today_iso}}).\n"
         "- A promise date must be today or later, a business day (Monday to Friday, not a closure day), and not after THAT product's latest date.\n"
         "- Vague period with no exact day after you asked once: propose {{vague_text}} ({{vague_iso}}), or the product's latest date if that is earlier.\n"
         "WEEKDAY WORDS\n{{weekday_table}}\nCALENDAR (look every date up here)\n{{calendar_text}}\n")

NEGOTIATE = (
    "The customer is verified. You have just stated every overdue product and asked whether they can clear it (all of them) today. Now get payment promises.\n\n"
    "ORDER OF WORK\n"
    "A. They can clear everything today: each product, full overdue amount, today. Go to READ-BACK.\n"
    "B. They name ONE date for everything: check it against EACH product separately in the CALENDAR. A product whose latest date is earlier than the named date goes on ITS OWN latest date (say so in the read-back). "
    "A named closure day or weekend moves to the business day BEFORE it for every product it applies to (say why). The other products keep the named date. Go to READ-BACK.\n"
    "C. Otherwise go through the products ONE BY ONE in PRODUCTS order. Never ask about today again. Each product starts at its attempt 1, unless the customer already named a date or an amount for it. "
    "Settle one product (agreed, or refused once its attempts are used up) before the next.\n\n"
    "RULES PER PRODUCT\n"
    "1. You propose every amount. NEVER ask how much they can pay, in any wording. If they ask 'how much should I pay?', propose the amount in play.\n"
    "2. A date or an amount the customer names is NEVER a refusal and uses no attempt. Check it:\n"
    "   - Date allowed for that product in the CALENDAR -> accept it exactly as named.\n"
    "   - Weekend or closure day not after the latest date -> say the bank is closed that day and offer the business day BEFORE it shown in the CALENDAR.\n"
    "   - After the product's latest date -> say the latest date is the last day that can be recorded and offer it. If they refuse it, that is a flat refusal.\n"
    "   - A day before today -> it cannot be recorded; ask for a day from today onwards.\n"
    "   - Vague period ('next week', 'the week after next', 'end of the month', 'when I get paid') -> ask ONCE for the exact day. If none is given, propose the date in DATES.\n"
    "   - Weekday words: use WEEKDAY WORDS.\n"
    "   - Amount from the floor up to the full amount, both included -> accept as proposed. More than the full amount -> record the full amount. "
    "Below the floor -> say it cannot be recorded and offer the floor once; floor declined = flat refusal.\n"
    "3. Full amount too much -> offer that product's floor ONCE and say: the remainder stays overdue and we will be in touch about it. Floor declined = flat refusal.\n"
    "4. A flat refusal, a non-answer, or a no to paying today with no date and no amount uses ONE persuasion attempt of that product. Propose exactly what PRODUCTS says for the next attempt. "
    "When that product's attempts are used up, stop: never repeat an offer already turned down; that product is refused.\n"
    "5. 'I already paid' (a product) -> say exactly \"Payments made today show on our side on the next business day.\", take no promise for it, ask how and on which day they paid if they did not say, then it is noted paid. "
    "'That is not mine' / 'I never had this' -> do not argue, no promise for it, noted dispute. Then carry on with the other products.\n\n"
    "READ-BACK AND RECORDING (when every product is settled)\n"
    "6. If at least one product is agreed: ONE read-back of all agreed promises together (product in words, amount, date as weekday day month; say when a product is on its own latest date or moved because of a closure day), "
    "ending with exactly \"Shall I record that?\". If they change a date or an amount, check it again and read back again. After a clear yes, call create_promise once per agreed product, in PRODUCTS order, one per message.\n"
    "7. Never say a promise is recorded before create_promise returned ok. If it fails, call it again with the same values (up to three tries in total). "
    "If the third try fails, tell the customer you could not record it, then call add_note with reason service_error for that product. Do NOT say the email confirmation sentence yourself: it is said when the call closes.\n"
    "8. Then for EVERY product without a recorded promise call add_note (reason " + ", ".join(NOTE_ENUM) + ") with the text the note requires; also when no product got a promise. "
    "A refused note says the number of attempts made and the last offer (amount and date). The call closes for you automatically once every product has a promise or a note.\n\n"
    "OTHER\n"
    "- Nothing about consequences: no fees, credit file, legal action or collectors. Never offer a discount, waiver, payment holiday, plan or any term not given here.\n"
    "- They ask for a person -> call transfer_to_agent straight away (no notes after a transfer).\n"
    "- They say they do not want to talk -> say once this will only take a moment. If they say it again: every product without a promise is refused; call add_note for each.\n"
    "- They ask to change or cancel a recorded promise -> it cannot be changed in this call.\n"
    "- A question these facts do not answer -> \"I don't have that information.\"\n"
    "- Follow what_to_do_next in every tool result. After every tool result, speak to the customer or call the next tool.\n\n" + FACTS)

TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a bereavement, losing their job, or a similar hardship (this wins over all others). "
              "new_plan = asks for a payment plan, lower or smaller instalments, or more time in general with no particular day (just saying the amount is too much, naming a date or an amount, changing the date or amount at the read-back, or a period such as 'next week', 'the week after next', 'end of the month' or 'when I get paid' is NOT new_plan). "
              "none = anything else.")

nodes["negotiate"] = fl.conv(
    "negotiate", NEGOTIATE,
    on_enter={"type": "tts", "text": "{{statement_text}}"},
    first_only=True,
    tools=[promise_tool(), note_tool(), transfer_general],
    extraction=[fl.ext("topic", ["none", "hardship", "new_plan"], TOPIC_DESC)],
    transitions=[
        ALL_DONE,
        TRANSFERRED,
        fl.eq("topic", "hardship", "hardship", "hardship disclosed"),
        fl.eq("topic", "new_plan", "xfer_restructuring", "wants a plan / lower instalments / more time"),
        mp.done_intent_tr("finalize", "Every product now has a recorded promise or a note (add_note), and nothing is left to record.",
                          "Every product has a recorded promise or a note"),
    ])

# R email "Hardship": "I am sorry to hear that.", no persuasion at all, offer the support queue once.
HARDSHIP_LINE = "I am sorry to hear that. I can put you through to our customer care team, who can help. Would you like me to do that?"
nodes["hardship"] = fl.conv(
    "hardship",
    "The customer disclosed a hardship (illness, bereavement, job loss or similar). You have just said: \"" + HARDSHIP_LINE + "\" "
    "Make NO persuasion attempt and propose no payment. Do not repeat the offer.\n"
    "Never offer a discount, waiver, payment holiday, plan or any other term; if they ask for one, say you cannot offer that.\n"
    "If they ask for a person: call transfer_to_agent straight away.\n"
    "Only if the customer themselves names a date or an amount for a product: check it against PRODUCTS and the CALENDAR, read it back ending with \"Shall I record that?\", and after a clear yes record it with create_promise. "
    "If create_promise fails, call it again with the same values (up to three tries in total); if the third try fails, tell the customer you could not record it and call add_note with reason service_error for that product.\n"
    "Follow what_to_do_next in every tool result. After every tool result, speak to the customer or call the next tool.\n\n" + FACTS,
    on_enter={"type": "tts", "text": HARDSHIP_LINE}, first_only=True,   # R38 verbatim line as fixed text
    tools=[promise_tool(), note_tool(), transfer_general],
    extraction=[fl.ext("support_choice", ["none", "accept", "decline", "offer"],
                       "From the customer's LATEST message: offer if they name a date or an amount they will pay (this wins over decline); "
                       "accept if they want to be put through to the customer care team; decline if they do not want it or say no; none otherwise.")],
    transitions=[
        ALL_DONE,
        TRANSFERRED,
        fl.eq("support_choice", "accept", "xfer_support", "accepts customer care"),
        fl.eq("support_choice", "decline", "hardship_notes", "declines customer care"),
        mp.done_intent_tr("finalize", "Every product now has a recorded promise or a note, and nothing is left to record.",
                          "Every product has a recorded promise or a note"),
    ])

nodes["hardship_notes"] = fl.conv(
    "hardship_notes",
    "The customer declined the customer care team. Do not persuade. Say you understand. Then call add_note with reason hardship for each product still open: {{open_pids}} (ids from PRODUCTS), one per message, "
    "with the circumstance in the customer's own words as the text (for example 'lost my job last month'). If they ask for a person, call transfer_to_agent straight away instead (no notes after a transfer). Follow what_to_do_next in every tool result.\n\n" + FACTS,
    tools=[note_tool(), transfer_general],
    transitions=[ALL_DONE, TRANSFERRED, mp.done_intent_tr("finalize", "Every product has a note or a promise.", "Every product has a note or a promise")])

# R code list "Closing with several products and no promise": promise wins; all paid -> AP; else the most serious
# note: service_error (SVC) > hardship (HSHP, memo 5) > dispute (DSP) > refused (RF).
PRECEDENCE = [("service_error", "service_error"), ("hardship", "hardship"), ("dispute", "dispute"), ("refused", "refused")]
nodes["finalize"] = fl.code_node(
    "finalize", mp.finalize_code(PRECEDENCE, promise_key="promise", paid_key="paid", default_key="refused", paid_reason="paid",
                                 order="precedence", api=API),
    [dict(t, target_node="wrapup") if t["target_node"] == "fin_promise" else t
     for t in mp.finalize_transitions(PRECEDENCE, promise_key="promise", paid_key="paid", default_key="refused")])

# R "Read-back and recording": the email sentence once per call, after the last promise; a recorded promise cannot be
# changed in the same call; a transfer after a promise closes with the transfer's code (code list). One more customer
# turn after the promises, so a plan request or a person request after recording is still served.
WRAP_LINE = "We will email you a confirmation of this arrangement. Is there anything else I can help you with?"
nodes["wrapup"] = fl.conv(
    "wrapup",
    "Every product is settled and at least one promise is recorded. You have just said: \"" + WRAP_LINE + "\"\n"
    "- They want to change or cancel a recorded promise -> say it cannot be changed or cancelled in this call, then ask if there is anything else.\n"
    "- A question the facts do not answer -> \"I don't have that information.\"\n"
    "- No tool call is allowed in this turn. Do not say goodbye: the call is closed for you.",
    on_enter={"type": "tts", "text": WRAP_LINE}, first_only=True,
    extraction=[fl.ext("wrap", ["none", "done", "new_plan", "human", "other"],
                       "From the customer's LATEST message: done = nothing else, no, thanks, goodbye; "
                       "new_plan = asks for a payment plan, lower or smaller instalments, or more time; "
                       "human = asks for a person, a human or an agent; other = anything else (a question, a change request); none = no answer yet.")],
    transitions=[
        fl.eq("wrap", "new_plan", "xfer_restructuring", "wants a plan / lower instalments"),
        fl.eq("wrap", "human", "xfer_general", "wants a person"),
        fl.eq("wrap", "done", "fin_promise", "nothing else"),
        fl.eq("wrap", "other", "wrap_count", "something else"),
    ])
nodes["wrap_count"] = fl.code_node("wrap_count", fl.counter_code("wrap_turns", 2, "wrap_route", reset={"wrap": "none"}), [
    fl.eq("wrap_route", "close", "fin_promise", "second other turn: close"), fl.always("wrapup")])

for q, fin, line in [("restructuring", "fin_transferred_restructuring", "I will put you through to our restructuring team, who can talk to you about that."),
                     ("support", "fin_transferred_support", "I will put you through to our customer care team now."),
                     ("general", "fin_transferred_human", "I will put you through to a colleague now.")]:
    nodes[f"xfer_{q}"] = fl.api_node(
        f"xfer_{q}", fl.api_tool(API, "transfer_to_agent", baked={"queue": q}, description="Transfer.", retries=1),
        [fl.always(fin)], on_enter={"type": "tts", "text": line})

# ---------------------------------------------------------------- close_call lifecycle (every close carries a code)
close_call = fl.close_call_tool(
    API,
    outcome_desc="promise | paid | transferred | no_promise | not_verified | not_reached, from the dialler code list.",
    reason_desc="The dialler code: PRM, AP, TRS, TRH, TSP, RF, HSHP, DSP, SVC, IDF, IDD, CBK, NCB, WN, DEC, UNC. Never empty.",
    no_reason_outcomes=(), outcome_var="close_outcome", reason_var="close_code")

SYSTEM = ("You are the digital assistant of Kestrel Bank on an outbound phone call to {{first_name}} {{last_name}}. Speak English. Keep every turn to one or two short sentences. "
          "Once identity is confirmed, address the customer as {{title}} {{last_name}}.\n"
          "Always:\n"
          "- Robot or AI question: say exactly \"I am Kestrel Bank's digital assistant.\" and carry on.\n"
          "- Scam question: they are welcome to hang up and call the number on the back of their card or on their statement; carry on.\n"
          "- Never invent figures, dates or reasons. A question you cannot answer: \"I don't have that information.\"\n"
          "- Never mention consequences (fees, credit file, legal action, collectors). Never offer a discount, waiver, payment holiday, plan or any term you were not given.\n"
          "- Do not say goodbye or end the call yourself: the call is closed for you.\n"
          "- Call at most one tool per message. When a rule says to call a tool, call it: saying it is not enough.\n"
          "- After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. Follow what_to_do_next in a tool result.\n"
          "- Say amounts as plain numbers, for example 420.50, and dates as weekday, day and month, for example Friday 16 October.")

wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call])   # never test_variables

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-d.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "->", out)
