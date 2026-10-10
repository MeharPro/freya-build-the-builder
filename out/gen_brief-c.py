"""Brief C (Nordvik Savings Bank) generator on builder/freyalib. Writes out/brief-c.workflow.json.

Structure from out/gen_brief-a_v2.py (conversation-first opening, one ask node per identity question, prepare code,
negotiate, fin/end pairs); every rule, value, date and sentence below comes from tests/synthetic/brief-c.md.
`# Rn` = rule number in the brief; `# R-cal` = section 7 calendar text."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")
BANK = "Nordvik Savings Bank"
# R-cal: business days Monday to Saturday, except the Nordvik holidays; Sundays and holidays never
HOLIDAYS = ["2026-10-16", "2026-11-02", "2026-11-21", "2026-12-08", "2026-12-24", "2026-12-25", "2026-12-26", "2026-12-31"]
BWD = [0, 1, 2, 3, 4, 5]
WEEKDAY_RULE = "first_after"  # R22: "this <weekday>" and "next <weekday>" both = the first such weekday after today
BYE = "Thank you for your time. Goodbye from Nordvik Savings Bank."  # R48
BYE_T = "Thank you for your time, {{title}} {{last_name}}. Goodbye from Nordvik Savings Bank."  # R17 + R48

nodes = {}

# ---------------------------------------------------------------- terminals (R47 table)
FINS = {
    "paid": ("paid", "self_reported", "Thank you for letting me know. The bank will check for the payment within two business days and will not call you again before then. " + BYE_T),  # R40
    "declined_offer": ("no_promise", "declined_offer", "I understand. " + BYE_T),  # R32, R42, R46
    "financial_distress": ("no_promise", "financial_distress", "I understand. The care team will contact you within three business days. " + BYE_T),  # R33
    "system_fault": ("no_promise", "system_fault", "I am sorry, the promise could not be saved because of a technical problem. " + BYE_T),  # R38
    "exhausted": ("not_verified", "exhausted", "I am sorry, the security check could not be completed. A colleague can complete the check if you call the number on the back of your card or on your latest statement. " + BYE),  # R15
    "withheld": ("not_verified", "withheld", "I understand. The bank cannot discuss anything until the security check is complete. " + BYE),  # R16, R46
    "scheduled": ("not_reached", "scheduled", "Thank you, we will call back then. " + BYE),  # R6
    "no_slot": ("not_reached", "no_slot", "I understand, I will not book a callback. " + BYE),  # R7
    "wrong_party": ("not_reached", "wrong_party", "I apologise for the disturbance. " + BYE),  # R8
    "estate": ("not_reached", "estate", "Please accept my condolences. " + BYE),  # R9: ask nothing further
    "unconfirmed": ("not_reached", "unconfirmed", "I am sorry, I could not confirm who I am speaking with. " + BYE),  # R3
}
for key, (outcome, reason, farewell) in FINS.items():
    fl.end_pair(key, outcome, reason, farewell, nodes)
# R34 on the hardship path: when the customer asked for a reduction, the farewell answers it ("cannot offer any
# reduction"). Two terminals routed on the extraction: a template variable set to '' is spoken as the literal placeholder.
nodes["fin_financial_distress"]["transitions"] = [
    fl.eq("asked_reduction", "yes", "end_financial_distress_reduction", "the customer asked for a reduction"),
    fl.always("end_financial_distress")]
nodes["end_financial_distress_reduction"] = fl.end_node(
    "end_financial_distress_reduction", "no_promise_financial_distress",
    "I understand. I cannot offer any reduction, and the figures are those on the account. The care team will contact you within three business days. " + BYE_T)

# R47: promise reason full if the recorded amount equals the overdue amount, otherwise partial; R39 sentence
nodes["fin_promise"] = fl.code_node("fin_promise", fl.promise_reason_code(), [fl.always("end_promise")])
nodes["end_promise"] = fl.end_node("end_promise", "promise",
                                   "I have noted your promise. A confirmation will be sent to your registered email address. " + BYE_T)
# R47: "If a transfer takes place after a promise was recorded, the promise decides"
TRANSFERS = {
    "plan_review": "Thank you. A colleague from the plan review team will take over now. " + BYE_T,  # R42
    "agent_request": "A colleague will take over now. " + BYE,  # R43 (before or after the check)
    "care_team": "Thank you. A colleague from the care team will take over now. " + BYE_T,  # R33
    "contested": "A colleague will take over now. " + BYE_T,  # R41
}
for reason, farewell in TRANSFERS.items():
    nodes["fin_" + reason] = fl.code_node("fin_" + reason, fl.promise_or_code("transferred", reason), [fl.always("end_" + reason)])
    nodes["end_" + reason] = fl.end_node("end_" + reason, "transferred_" + reason, farewell)

# ---------------------------------------------------------------- setup: dates
# R19: deadline = Nth business day after today (today not counted): green 9, amber 4. R31: attempt 1 = next business day.
DATES = r'''
vars['green_deadline'] = addbd(today, 9).isoformat()
vars['amber_deadline'] = addbd(today, 4).isoformat()
vars['attempt1_date'] = addbd(today, 1).isoformat()
'''
# R6: callback today or the next two business days, 09:00-18:00 inclusive, later than now
CALLBACK = {"open": "09:00", "close": "18:00", "same_day": True, "days_ahead": 2}
SETUP = fl.SETUP_CODE(HOLIDAYS, BWD, callback_rule=CALLBACK, extra=DATES, weekday_rule=WEEKDAY_RULE)

# R18 product words, R19 bands, R26 floors
PREPARE_BODY = fl.products_from_vars() + r'''
import math
p = prods[0] if prods else {}
if not isinstance(p, dict):
    p = {}
ptype = str(p.get('type') or '')
vars['product_id'] = str(p.get('product_id') or 'p1')
past_due = float(p.get('past_due') or 0)
if ptype == 'credit_card':
    words = 'credit card ending in ' + str(p.get('card_last4') or '')
    floor_raw = float(math.ceil(round(past_due * 0.4, 2) - 1e-9))  # R26: 40% rounded up to the next whole unit IS the floor
    floor_name = '40 percent of the overdue amount, rounded up'
elif ptype == 'car_loan':
    words = 'car loan'
    floor_raw = float(p.get('instalment_amount') or past_due)
    floor_name = 'the instalment amount'
else:
    words = 'personal loan' if ptype == 'personal_loan' else (ptype.replace('_', ' ') or 'loan')
    floor_raw = float(p.get('instalment_amount') or past_due)
    floor_name = 'the instalment amount'
floor = float(math.ceil(floor_raw - 1e-9))  # R26: state a rounded floor in whole units (a loan instalment is the floor itself)
if floor > past_due:
    floor = past_due
days_late = int(float(p.get('days_late') or 0))
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
if days_late <= 10:
    band = 'green'; attempts = 2; deadline = datetime.date.fromisoformat(str(vars.get('green_deadline')))
else:
    band = 'amber'; attempts = 1; deadline = datetime.date.fromisoformat(str(vars.get('amber_deadline')))
a1 = datetime.date.fromisoformat(str(vars.get('attempt1_date')))
if a1 > deadline:
    a1 = deadline
vars['product_words'] = words
vars['past_due_fmt'] = fmt(past_due)
vars['past_due_num'] = str(past_due)
vars['floor_fmt'] = fmt(floor)
vars['floor_min_fmt'] = fmt(floor_raw)
vars['floor_name'] = floor_name
vars['days_late_txt'] = str(days_late)
vars['band'] = band
vars['attempts_n'] = str(attempts)
vars['deadline_iso'] = deadline.isoformat()
vars['deadline_text'] = txt_short(deadline)
vars['attempt1_iso'] = a1.isoformat()
vars['attempt1_text'] = txt_short(a1)
if attempts >= 2:
    vars['attempt2_line'] = 'Attempt 2: propose the floor ' + fmt(floor) + ' on the deadline, ' + txt_short(deadline) + ' (' + deadline.isoformat() + '). After attempt 2 is refused, stop.'
else:
    vars['attempt2_line'] = 'There is NO attempt 2 for this customer. After attempt 1 is refused, stop.'
vars['calendar_text'] = calendar_text(today, deadline, 10)
'''
PREPARE_FALLBACKS = {"product_words": "account", "past_due_fmt": "the overdue amount", "past_due_num": "0"}
for k in ["floor_fmt", "floor_min_fmt", "floor_name", "days_late_txt", "band", "attempts_n", "deadline_iso", "deadline_text",
          "attempt1_iso", "attempt1_text", "attempt2_line", "calendar_text"]:
    PREPARE_FALLBACKS[k] = ""
PREPARE = fl.CAL_HELPERS(HOLIDAYS, BWD, WEEKDAY_RULE) + fl.guarded(PREPARE_BODY, "prepare_state", PREPARE_FALLBACKS)

# ---------------------------------------------------------------- opening (R1-R4)
OPENING_LINE = "Good day, this is the virtual assistant of Nordvik Savings Bank, and this call is recorded."  # R1 verbatim
ASK_NAME = "Am I speaking with {{first_name}} {{last_name}}?"  # R2
WHO_VALUES = ["customer", "someone_else", "wrong_number", "deceased", "refuses", "wants_agent", "unclear"]
WHO_DESC = ("Who answered, judged ONLY from the person's latest message. "
            "customer = ONLY 'yes', 'speaking', 'that's me', or they say the customer's own name ({{first_name}} {{last_name}}). "
            "someone_else = another person answered (a relative, partner, colleague), or says the customer is not here / not available, or offers to take a message. "
            "wrong_number = says this number does not belong to that person / they do not know them. "
            "deceased = says the customer has died / passed away. "
            "refuses = says they do not want to talk or wants to end the call. "
            "wants_agent = asks to speak to a person, a human, an agent. "
            "unclear = anything else: 'hello', 'go ahead', 'who's calling?', 'what is this about?', 'is this a robot?', 'is this a scam?', any question, silence.")
ROUTES = [
    ("customer", "ask_phone", "the customer confirmed who they are"),
    ("deceased", "fin_estate", "the customer has died"),
    ("wrong_number", "fin_wrong_party", "wrong number"),
    ("someone_else", "third_party", "someone else answered"),
    ("refuses", "fin_withheld", "does not want to talk (R46, before the check)"),
    ("wants_agent", "xfer_agent", "asks for a person (R43)"),
]
nodes["opening"] = fl.conv(
    "opening",
    # the chat route answers the first customer line with the dialogue model instead of the tts: repeat the line here
    "If you have not spoken yet in this call, your message is exactly: \"" + OPENING_LINE + " " + ASK_NAME + "\" (word for word, nothing before it). "
    "Otherwise you have just introduced yourself and asked whether you are speaking with {{first_name}} {{last_name}}. Do not call any tool in this turn. Do not say why you are calling.",
    on_enter={"type": "tts", "text": OPENING_LINE + " " + ASK_NAME},
    extraction=[fl.ext("who1", WHO_VALUES, WHO_DESC)], first_only=True)
INITIAL = fl.conversation_first("opening", SETUP, "who1", ROUTES, "opening_retry", nodes)

nodes["opening_retry"] = fl.conv(
    "opening_retry",
    "You called {{first_name}} {{last_name}} and asked whether you are speaking with them, but the answer did not confirm it. "
    "No tool call is allowed in this turn. Do not say why you are calling. Do not use the words overdue, arrears, collections, payment or debt, and do not name any product.\n"
    "If the person asked a question, answer it briefly first: "
    "a robot, an AI or a machine -> say exactly \"I am an automated assistant of Nordvik Savings Bank, and this conversation is recorded.\"; "
    "a scam -> they may hang up and call the number on the back of their card or on their latest statement to confirm the call; "
    "who is calling -> the virtual assistant of Nordvik Savings Bank; what it is about -> you can discuss it only with {{first_name}} {{last_name}} personally.\n"
    "Then ask exactly: \"" + ASK_NAME + "\" This is the second and last time you ask.",
    extraction=[fl.ext("who2", WHO_VALUES, WHO_DESC)],
    transitions=[fl.eq("who2", v, t, d) for v, t, d in ROUTES] + [fl.always("fin_unconfirmed")])  # R3

# ---------------------------------------------------------------- third party (R5-R10)
cb_tool = fl.api_tool(
    API, "schedule_callback",
    description="Book a callback for the customer. CALL it as soon as the person names a day and time inside the allowed window.",
    field_descriptions={"date": "Callback date as YYYY-MM-DD. Must be one of the allowed days.",
                        "time": "Callback time as HH:MM, 24 hour, from 09:00 to 18:00 inclusive, later than now."},
    post=fl.ok_post("Callback booked.", "The booking failed. Try schedule_callback once more with the same values."))

nodes["third_party"] = fl.conv(
    "third_party",
    "You called for {{first_name}} {{last_name}} but someone else is on the line.\n"
    "STRICT: Say only that you are calling from Nordvik Savings Bank on a private matter that you can discuss with the customer personally. "
    "Never say what the matter is, not even in general terms. Never use the words overdue, arrears, collections, payment or debt, never name a product or an amount. "
    "If they ask what it is about, offer to pay, or offer to take a message, repeat that you can discuss it only with the customer. Never ask them a security question and arrange nothing with them except a callback.\n"
    "Your only job: ask when {{first_name}} {{last_name}} can be reached, then book a callback.\n"
    "Now: {{today_text}}, {{now_time}}.\n{{callback_text}}\n"
    "- If they give a day and time inside the window, call schedule_callback with date YYYY-MM-DD and time HH:MM. 'Tomorrow morning around eleven' means tomorrow at 11:00. If they give only a day, ask for a time; if only a vague time like 'morning', propose a precise time such as 10:00 and ask if it suits.\n"
    "- If the day or time is outside the window, state the window (today after now, or the next two business days, from 09:00 to 18:00) and ask once for another slot.\n"
    "- If the second slot is also outside the window, or they cannot say when, book nothing: call transition_to_fin_no_slot.\n"
    "- If they ask whether you are a robot: say exactly \"I am an automated assistant of Nordvik Savings Bank, and this conversation is recorded.\"\n"
    "After every tool result, speak or call the next tool.",
    tools=[cb_tool],
    extraction=[fl.ext("tp_status", ["none", "wrong_number", "deceased"],
                       "From the person's latest message: wrong_number if they say this number does not belong to the customer or they do not know the customer; deceased if they say the customer has died; otherwise none.")],
    transitions=[
        fl.ok_true("schedule_callback", "fin_scheduled", "callback booked"),
        fl.eq("tp_status", "deceased", "fin_estate", "customer died"),
        fl.eq("tp_status", "wrong_number", "fin_wrong_party", "wrong number"),
        fl.intent_tool("fin_no_slot",
                       "No callback can be booked: the person gave a second slot outside the allowed window, or cannot say when the customer is reachable.",
                       "No callback can be booked inside the allowed window"),
    ])

# ---------------------------------------------------------------- identity (R11-R16)
Q_PHONE = "What are the last four digits of the mobile number registered with the bank?"
Q_DOB = "What is your date of birth?"
SWAP = "Day and month look swapped. This is NOT a wrong answer. Ask the customer to repeat the date of birth with the month said as a word, for example 14 March 1988."  # R14
LIMIT = ("Two wrong answers: the check has ended. Do not ask again and reveal no amount, product or reason for the call. "
         "Tell the customer a colleague can complete the check if they call the number on the back of their card or on their latest statement.")  # R13, R15
# R13 limit 2 is stricter than the service's three (API summary): fallback route on the service counter, in case a
# hook cannot write vars. 3 - 2 = 1 left means two wrong answers.
SERVICE_LEFT_AT_LIMIT = "1"
WRONG = "Wrong answer. Tell the customer it does not match our records and ask the same question again: {question}"


def verify_tool(field, question, desc, answer_desc, verified_text):
    return fl.api_tool(API, "verify_identity", baked={"field": field}, description=desc,
                       field_descriptions={"answer": answer_desc},
                       post=fl.verify_count_post(question, 2, {"day_month_swapped": SWAP}, LIMIT,
                                                 free_hints={"day_month_swapped": 1},  # R14: one free retry per call
                                                 all_verified_text="Both security questions passed. Identity is verified.",
                                                 verified_text=verified_text, wrong_text=WRONG))


transfer_general = fl.api_tool(API, "transfer_to_agent", baked={"queue": "general"},
                               description="Transfer the call to a person. CALL it at once whenever the customer asks for a person, a human or an agent. Do not ask whether you can help first.")  # R43

ID_COMMON = ("Rules for this step:\n"
             "- Until both questions pass, do not use the words overdue, arrears, collections, payment or debt, and name no product or amount.\n"
             "- If the customer refuses to answer, or asks what the call is about instead of answering: say once that the bank cannot discuss anything until the security check is complete, and ask the question again.\n"
             "- If the customer asks for a person: call transfer_to_agent at once.\n"
             "- After every tool result, speak to the customer or call the next tool. Follow what_to_do_next.")
REFUSAL_DESC = ("From the customer's LATEST message only: refused if they refuse to answer the security question, or ask what the call is about (or how much they owe) instead of answering it; "
                "end_call if they say they do not want to talk or want to end the call; none if they give an answer or say anything else.")

nodes["ask_phone"] = fl.conv(
    "ask_phone",
    "The person confirmed they are {{first_name}} {{last_name}}. Check identity with two security questions, one at a time. Ask the first now: \"" + Q_PHONE + "\"\n"
    "When they give four digits, call verify_identity with answer = the four digits only. Do not ask the date of birth before this question has passed.\n" + ID_COMMON,
    tools=[verify_tool("phone_last4", Q_PHONE, "Check the last four digits of the registered mobile number. CALL it every time the customer gives four digits.",
                       "Exactly four digits.", "Correct. Now ask the second security question: " + Q_DOB), transfer_general],
    extraction=[fl.ext("refusal_phone", ["none", "refused", "end_call"], REFUSAL_DESC)],
    transitions=[
        fl.eq("id_route", "exhausted", "fin_exhausted", "two wrong answers"),
        fl.tr("fin_exhausted", "two wrong answers (service counter, no swapped hint so far)",
              fl.and_group(fl.cond("verify_identity_response.data.wrong_answers_left", "equals", SERVICE_LEFT_AT_LIMIT),
                           fl.cond("hint_day_month_swapped", "is_not_set"))),
        fl.is_true("verify_identity_response.data.verified", "ask_dob", "phone digits correct"),
        fl.transferred("fin_agent_request", "transferred"),
        fl.eq("refusal_phone", "end_call", "fin_withheld", "wants to end the call"),
        fl.eq("refusal_phone", "refused", "count_decline_phone", "customer refused"),
    ])

nodes["ask_dob"] = fl.conv(
    "ask_dob",
    "The mobile digits were correct. Ask the second security question now: \"" + Q_DOB + "\"\n"
    "Call verify_identity with the date as YYYY-MM-DD. If the customer gives the date ONLY in numbers (for example 3/7/85), do not call the tool: ask them to say the month as a word, then call it. "
    "If they give only part of the date, ask for the rest before calling the tool.\n" + ID_COMMON,
    tools=[verify_tool("date_of_birth", Q_DOB, "Check the date of birth. CALL it every time the customer gives a full date of birth with the month as a word.",
                       "The date of birth as YYYY-MM-DD.", "Both security questions passed. Identity is verified."), transfer_general],
    extraction=[fl.ext("refusal_dob", ["none", "refused", "end_call"], REFUSAL_DESC)],
    transitions=[
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.eq("id_route", "exhausted", "fin_exhausted", "two wrong answers"),
        fl.tr("fin_exhausted", "two wrong answers (service counter, no swapped hint so far)",
              fl.and_group(fl.cond("verify_identity_response.data.wrong_answers_left", "equals", SERVICE_LEFT_AT_LIMIT),
                           fl.cond("hint_day_month_swapped", "is_not_set"))),
        fl.transferred("fin_agent_request", "transferred"),
        fl.eq("refusal_dob", "end_call", "fin_withheld", "wants to end the call"),
        fl.eq("refusal_dob", "refused", "count_decline_dob", "customer refused"),
    ])

for stage in ["phone", "dob"]:  # R16: the second refusal or deflection closes withheld
    code = fl.counter_code("decline_count", 2, "decline_route", reset={"refusal_dob": "none", "refusal_phone": "none"})
    nodes[f"count_decline_{stage}"] = fl.code_node(f"count_decline_{stage}", code, [
        fl.eq("decline_route", "close", "fin_withheld", "second refusal"), fl.always(f"ask_{stage}")])

# ---------------------------------------------------------------- account (R17)
nodes["load_account"] = fl.api_node(
    "load_account", fl.api_tool(API, "get_account", description="Get the overdue product.", retries=2),
    [fl.always("prepare")], mapping=[{"path": "data.products", "variable": "products"}])
nodes["prepare"] = fl.code_node("prepare", PREPARE, [fl.always("negotiate")])


def promise_tool():  # R35-R38
    return fl.api_tool(API, "create_promise", baked={"product_id": "{{product_id}}"},
                       description="Record the payment promise. CALL it only after you read back amount, date and product, asked \"Shall I record this?\" and the customer clearly said yes.",
                       field_descriptions={"amount": "The agreed amount, a number like 420.5.",
                                           "date": "The agreed payment date as YYYY-MM-DD."},
                       pre=fl.promise_state_pre("past_due_num"),
                       post=fl.promise_state_post(3, "The promise is recorded.",
                                                  "NOT recorded. Do not say it is recorded. Call create_promise again with exactly the same values.",
                                                  "NOT recorded after three attempts. Tell the customer the promise could not be saved."))


PROMISE_TR = [
    fl.eq("promise_route", "recorded", "fin_promise", "promise recorded"),
    fl.ok_true("create_promise", "fin_promise", "promise recorded"),
    fl.eq("promise_route", "fault", "fin_system_fault", "three failed promise calls"),
    fl.count_gt("create_promise_failure_count", 2, "fin_system_fault", "three failed promise calls"),
]

FACTS = ("ACCOUNT\n- Product: {{product_words}}.\n- Full overdue amount: {{past_due_fmt}}. Days overdue: {{days_late_txt}}.\n"
         "- Floor, the smallest amount the bank records: {{floor_fmt}} ({{floor_name}}). Accept any amount from {{floor_min_fmt}} up to {{past_due_fmt}}.\n"
         "DATES\n- Today: {{today_text}} ({{today_iso}}).\n- Deadline, the latest date you may record: {{deadline_text}} ({{deadline_iso}}). The deadline itself is valid.\n"
         "- A promise date must be a business day (Monday to Saturday, not a Nordvik holiday) from today up to the deadline. Saturdays are business days.\n"
         "- Attempt 1 date: {{attempt1_text}} ({{attempt1_iso}}).\n- Persuasion attempts allowed: {{attempts_n}}. {{attempt2_line}}\n"
         "WEEKDAY WORDS (\"this X\" and \"next X\" both mean the first X after today)\n{{weekday_table}}\nCALENDAR (look every date up here)\n{{calendar_text}}\n")

NEGOTIATE = (
    "The customer is verified. You stated the overdue amount and asked \"Are you able to settle the full overdue amount today?\". Now agree a payment.\n\n"
    "HOW TO AGREE THE PAYMENT\n"
    "1. You propose every figure. NEVER ask what they can pay or how much they can afford. If they say 'you tell me', propose a figure yourself. Ask for the full overdue amount first.\n"
    "2. Yes to paying today = the full amount, today.\n"
    "3. A date or an amount the customer proposes is never a refusal. Check it:\n"
    "   - Date: look it up in the CALENDAR. 'allowed' -> accept it. A Sunday or a Nordvik holiday not after the deadline -> say it is not a business day and propose the next business day shown. "
    "After the deadline -> say the latest date the bank can record is {{deadline_text}}, and propose it; if they decline it, it is a flat refusal.\n"
    "   - A vague period ('next week', 'the week after next', 'after payday', 'end of the month') -> ask once for the exact day. If no exact day follows, it is a non-answer and uses one persuasion attempt.\n"
    "   - Amount from the floor up to the full amount, both included -> accept it. Above the full amount -> record the full amount {{past_due_fmt}} and say so. "
    "Below the floor -> say the smallest amount the bank can record is {{floor_fmt}} and propose it once; if they do not accept, it is a flat refusal.\n"
    "4. If they say the full amount is too much: propose the floor {{floor_fmt}}, once, and say the remainder stays overdue and the account stays in arrears until it is cleared. If they decline the floor, it is a flat refusal.\n"
    "5. A flat refusal (a no to paying today with no date and no amount, a non-answer, or declining your proposal) uses one persuasion attempt:\n"
    "   - Attempt 1: propose paying on {{attempt1_text}} - the full amount {{past_due_fmt}}, or the floor {{floor_fmt}} if they already said the full amount is too much.\n"
    "   - {{attempt2_line}}\n"
    "   - When the allowed attempts are used up, stop: call transition_to_fin_declined_offer. Never repeat a proposal they declined.\n"
    "6. When amount and date are agreed, read back the amount, the date and the product: \"<amount> on <weekday day month> for your {{product_words}}. Shall I record this?\" "
    "Call create_promise only after a clear yes, with amount as a number and date as YYYY-MM-DD. If they change the amount or date, check it again and read back again.\n"
    "7. After create_promise: if it failed, call it again with the same values (up to two more times). Never say the promise is noted unless the result has ok true.\n"
    "8. One promise per call. A recorded promise is not changed or cancelled: if asked, the payments line can change it.\n\n"
    "OTHER\n"
    "- Never offer or agree to a discount, waiver, fee reversal, instalment plan or a date after the deadline. If asked, say you cannot offer any reduction and the figures are those on the account.\n"
    "- If they ask for a person: call transfer_to_agent at once.\n"
    "- If they say they do not want to talk or want to end the call: call transition_to_fin_declined_offer at once.\n"
    "- If they ask something these facts do not answer, say you do not have that information and that the payments team can answer it.\n"
    "- After every tool result, speak to the customer or call the next tool.\n\n" + FACTS)

TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a bereavement, job loss or a similar hardship (this wins over all others). "
              "already_paid = says they have ALREADY paid this overdue amount (not 'I will pay'). "
              "dispute = says it is not their debt, they never had this product, or it was closed or settled in the past. "
              "new_plan = asks for a new payment plan, lower instalments or spreading the amount over several months (just saying the amount is too much is NOT new_plan). "
              "none = anything else.")

nodes["negotiate"] = fl.conv(
    "negotiate", NEGOTIATE,
    on_enter={"type": "tts", "text": "Thank you, {{title}} {{last_name}}. I am calling from the payments team of Nordvik Savings Bank about an overdue amount on your {{product_words}}. "
                                     "The overdue amount is {{past_due_fmt}}, and it is {{days_late_txt}} days overdue. Are you able to settle the full overdue amount today?"},  # R18, R29
    first_only=True,
    tools=[promise_tool(), transfer_general],
    extraction=[fl.ext("topic", ["none", "hardship", "already_paid", "dispute", "new_plan"], TOPIC_DESC)],
    transitions=PROMISE_TR + [
        fl.transferred("fin_agent_request", "transferred to a person"),
        fl.eq("topic", "hardship", "hardship", "hardship"),
        fl.eq("topic", "already_paid", "fin_paid", "already paid"),
        fl.eq("topic", "dispute", "xfer_contested", "contested"),
        fl.eq("topic", "new_plan", "plan_offer", "wants a new plan"),
        fl.intent_tool("fin_declined_offer",
                       "The customer finally declined: all persuasion attempts are used up, or they do not want to talk.",
                       "The customer finally declined to make any promise"),
    ])

# R33
nodes["hardship"] = fl.conv(
    "hardship",
    "The customer mentioned a hardship. You already said: \"I am sorry to hear that. I will not ask you for a payment today.\" and asked whether you may connect them with the care team now. "
    "Make NO persuasion attempt and propose no amount and no date. If they did not answer the question, ask it again once.\n"
    "Never offer a discount, waiver, fee reversal or plan. If they ask for one, say you cannot offer any reduction and the figures are those on the account.\n"
    "If they ask for a person: call transfer_to_agent at once.\n"
    "If the customer themselves names a date and an amount, check them with the facts below, read back and ask \"Shall I record this?\", and call create_promise after a clear yes.\n"
    "After every tool result, speak to the customer or call the next tool.\n\n" + FACTS,
    on_enter={"type": "tts", "text": "I am sorry to hear that. I will not ask you for a payment today. The bank's care team can review your situation. May I connect you with them now?"},
    first_only=True,
    tools=[promise_tool(), transfer_general],
    extraction=[fl.ext("care_choice", ["none", "accept", "decline"],
                       "Answer to the offer to connect with the care team, from the customer's LATEST message: accept if they want to be connected, decline if they say no or do not want it, none otherwise."),
                fl.ext("asked_reduction", ["no", "yes"],
                       "yes if the customer has asked, at any point in the call, for a discount, a waiver, a fee reversal, a reduction or an instalment plan; otherwise no.")],
    transitions=PROMISE_TR + [
        fl.transferred("fin_agent_request", "transferred to a person (R43)"),
        fl.eq("care_choice", "accept", "xfer_care", "accepts the care team"),
        fl.eq("care_choice", "decline", "fin_financial_distress", "declines the care team"),
    ])

# R42
nodes["plan_offer"] = fl.conv(
    "plan_offer",
    "The customer asked for a new payment plan or lower instalments. You said the plan review team handles these requests and asked whether you may connect them now. "
    "Do not describe or invent any plan, and propose no amount or date. If they did not answer the question, ask it again once. "
    "The only tool here is transfer_to_agent: call it at once if they ask for a person.",
    tools=[transfer_general],
    on_enter={"type": "tts", "text": "I cannot describe or arrange a payment plan myself. The plan review team handles these requests. May I connect you with them now?"},
    first_only=True,
    extraction=[fl.ext("plan_choice", ["none", "accept", "decline"],
                       "Answer to the offer to connect with the plan review team, from the customer's LATEST message: accept if they want to be connected, decline if they say no, none otherwise.")],
    transitions=[
        fl.transferred("fin_agent_request", "transferred to a person (R43)"),
        fl.eq("plan_choice", "accept", "xfer_plan", "accepts the plan review team"),
        fl.eq("plan_choice", "decline", "fin_declined_offer", "declines the transfer"),
    ])

for name, q, fin, line in [
        ("xfer_plan", "restructuring", "fin_plan_review", "I will connect you with the plan review team now."),  # R42
        ("xfer_care", "support", "fin_care_team", "I will connect you with the care team now."),  # R33
        ("xfer_contested", "general", "fin_contested", "I understand. A colleague will look into it. I will connect you now."),  # R41
        ("xfer_agent", "general", "fin_agent_request", "I will connect you with a colleague now.")]:  # R43
    nodes[name] = fl.api_node(name, fl.api_tool(API, "transfer_to_agent", baked={"queue": q}, description="Transfer.", retries=1),
                              [fl.always(fin)], on_enter={"type": "tts", "text": line})

# ---------------------------------------------------------------- close_call lifecycle (R47)
close_call = fl.close_call_tool(
    API,
    outcome_desc="promise: a promise was recorded. paid: says already paid. transferred: handed to a person. no_promise: verified, no promise. not_verified: identity not passed. not_reached: the customer was not reached.",
    reason_desc="promise: full|partial. paid: self_reported. transferred: plan_review|agent_request|care_team|contested. no_promise: declined_offer|financial_distress|system_fault. "
                "not_verified: exhausted|withheld. not_reached: scheduled|no_slot|wrong_party|estate|unconfirmed.")

SYSTEM = ("You are the virtual assistant of Nordvik Savings Bank on an outbound phone call to {{first_name}} {{last_name}}. Speak English. Keep every turn to one or two short sentences. "
          "After the security check, address the customer as {{title}} {{last_name}}.\n"
          "Always:\n"
          "- Until the security check is complete, never use the words overdue, arrears, collections, payment or debt, and never name a product, to anyone. The word collections is never used.\n"
          "- If asked whether you are a robot, an AI or a machine: say exactly \"I am an automated assistant of Nordvik Savings Bank, and this conversation is recorded.\" and carry on. Never claim to be a person.\n"
          "- If asked whether this is a scam: say they may hang up and call the number on the back of their card or on their latest statement to confirm the call, then continue.\n"
          "- Never invent a figure, a date or a reason. If you do not have the information, say so and that the payments team can answer it.\n"
          "- Never offer a discount, waiver, fee reversal, instalment plan or any term you were not given.\n"
          "- Do not say goodbye or end the call yourself: the call is closed for you.\n"
          "- Call at most one tool per message. When a rule says to call a tool, call it: saying it is not enough.\n"
          "- After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. Follow what_to_do_next in a tool result.\n"
          "- Say amounts as plain numbers, for example 420.50, and dates as weekday, day and month, for example Thursday 15 October.")

wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call], None)  # never ship test_variables

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-c.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "->", out)
