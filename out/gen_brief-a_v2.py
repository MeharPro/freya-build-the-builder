"""Brief A generator, v2 shape: out/gen_brief-a_lib.py with the INITIAL node changed. Writes out/brief-a_v2.workflow.json.

Why this exists: the chat route (POST /api/v2/chat/message, used by builder/smoke.py and builder/sim.py) SKIPS a first
code node, while simulations run it, so the v1 agent (initial node = the `setup` code node) behaved differently in our
local tests than in the scored runs. Here the call starts in the `opening` conversation node, which has one always
transition to `setup`; `setup` runs right after the customer's first turn as a passthrough code node and routes on
`who1` exactly as `opening` did before (fl.conversation_first, see builder/FREYALIB.md "Initial node").
Everything else is identical to gen_brief-a_lib.py; out/compare_brief-a_v2.py proves it."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")
HOLIDAYS = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]  # from the brief, section 7

nodes = {}

# ---------------------------------------------------------------- terminals
# key: (outcome, reason, farewell)
FINS = {
    "promise": ("promise", "", "Your payment promise is recorded. You will receive a text message confirming this promise. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "paid": ("paid", "", "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise today. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "transferred_restructuring": ("transferred", "restructuring", "Thank you, {{title}} {{last_name}}. A colleague will take over now. Goodbye."),
    "transferred_human": ("transferred", "human", "Thank you, {{title}} {{last_name}}. A colleague will take over now. Goodbye."),
    "transferred_support": ("transferred", "support", "Thank you, {{title}} {{last_name}}. A colleague from customer support will take over now. Goodbye."),
    "refused": ("no_promise", "refused", "I understand. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "hardship": ("no_promise", "hardship", "I understand. Thank you for your time, {{title}} {{last_name}}, and take care. Goodbye."),
    "dispute": ("no_promise", "dispute", "Thank you for telling me. I will not take a payment promise today. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "service_error": ("no_promise", "service_error", "I am sorry, I could not record your promise because of a technical problem. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "failed": ("not_verified", "failed", "I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile app or visit a branch. Thank you, goodbye."),
    "declined": ("not_verified", "declined", "I understand. Without the security questions I cannot continue. Thank you for your time, goodbye."),
    "callback": ("not_reached", "callback", "Thank you, we will call back then. Goodbye."),
    "no_callback": ("not_reached", "no_callback", "Thank you for your help. Goodbye."),
    "wrong_number": ("not_reached", "wrong_number", "I apologise for the inconvenience. Thank you, goodbye."),
    "deceased": ("not_reached", "deceased", "I am sorry for your loss. Goodbye."),
    "unclear": ("not_reached", "unclear", "I am sorry, I could not confirm who I am speaking with. Thank you, goodbye."),
}
for key, (outcome, reason, farewell) in FINS.items():
    fl.end_pair(key, outcome, reason, farewell, nodes)

# ---------------------------------------------------------------- setup: dates
# Brief A: attempt 1 is the last business day of this week (else of next week); the early band may record up to
# 12 business days ahead, the late band up to 7. Callbacks: today up to 19:00 or the next business day 10:00-19:00.
ATTEMPT_DATES = r'''
monday = today - datetime.timedelta(days=today.weekday())
a1 = lastbd_of_week(monday)
if a1 is None or a1 <= today:
    a1 = lastbd_of_week(monday + datetime.timedelta(days=7))
vars['attempt1_date'] = a1.isoformat()
vars['early_deadline'] = addbd(today, 12).isoformat()
vars['late_deadline'] = addbd(today, 7).isoformat()
'''
SETUP = fl.SETUP_CODE(HOLIDAYS, callback_rule={"open": "10:00", "close": "19:00", "same_day": True, "days_ahead": 1},
                      extra=ATTEMPT_DATES)

# Brief A: one product; early band (<= 7 days late) = 1 persuasion attempt, late band = 2; the floor is the minimum
# payment of a credit card or the instalment of a loan.
PREPARE_BODY = fl.products_from_vars() + r'''
p = prods[0] if prods else {}
if not isinstance(p, dict):
    p = {}
ptype = str(p.get('type') or '')
vars['product_id'] = str(p.get('product_id') or 'p1')
if ptype == 'credit_card':
    words = 'credit card ending ' + str(p.get('card_last4') or '')
    floor = p.get('minimum_payment')
    floor_name = 'minimum payment'
else:
    words = ptype.replace('_', ' ') if ptype else 'loan'
    floor = p.get('instalment_amount')
    floor_name = 'monthly instalment'
past_due = float(p.get('past_due') or 0)
try:
    floor = float(floor)
except Exception:
    floor = past_due
days_late = int(float(p.get('days_late') or 0))
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
if days_late <= 7:
    band = 'early'; attempts = 1; deadline = datetime.date.fromisoformat(str(vars.get('early_deadline')))
else:
    band = 'late'; attempts = 2; deadline = datetime.date.fromisoformat(str(vars.get('late_deadline')))
a1 = datetime.date.fromisoformat(str(vars.get('attempt1_date')))
if a1 > deadline:
    a1 = deadline
vars['product_words'] = words
vars['past_due_fmt'] = fmt(past_due)
vars['floor_fmt'] = fmt(floor)
vars['floor_name'] = floor_name
vars['days_late_txt'] = str(days_late)
vars['band'] = band
vars['attempts_n'] = str(attempts)
vars['deadline_iso'] = deadline.isoformat()
vars['deadline_text'] = txt_short(deadline)
vars['attempt1_iso'] = a1.isoformat()
vars['attempt1_text'] = txt_short(a1)
if attempts >= 2:
    vars['attempt2_line'] = 'Attempt 2: propose the floor amount ' + fmt(floor) + ' on the deadline, ' + txt_short(deadline) + ' (' + deadline.isoformat() + ').'
else:
    vars['attempt2_line'] = 'There is NO attempt 2 for this customer. After attempt 1 is refused, stop.'
vars['calendar_text'] = calendar_text(today, deadline, 10)
'''
PREPARE_FALLBACKS = {"product_words": "account", "past_due_fmt": "the past-due amount"}
for k in ["floor_fmt", "floor_name", "days_late_txt", "band", "attempts_n", "deadline_iso", "deadline_text",
          "attempt1_iso", "attempt1_text", "attempt2_line", "calendar_text"]:
    PREPARE_FALLBACKS[k] = ""
PREPARE = fl.CAL_HELPERS(HOLIDAYS) + fl.guarded(PREPARE_BODY, "prepare_state", PREPARE_FALLBACKS)

# `setup` is created by fl.conversation_first below, right after `opening`

# ---------------------------------------------------------------- opening
WHO_VALUES = ["customer", "someone_else", "wrong_number", "deceased", "refuses", "unclear"]
WHO_DESC = ("Who answered, judged ONLY from the person's latest message. "
            "customer = they confirm they are {{title}} {{last_name}}: 'yes', 'that's me', 'speaking', or they say the customer's own name ({{first_name}} / {{last_name}}). "
            "someone_else = another person answered (a relative, partner, colleague), or says the customer is not here / not available, or offers to take a message. "
            "wrong_number = says this number does not belong to that person / they do not know them. "
            "deceased = says the customer has died / passed away. "
            "refuses = says they do not want to talk / not interested. "
            "unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', a question, silence.")

OPENING_ROUTES = [  # routed in `setup` on who1; anything else -> opening_retry
    ("customer", "ask_dob", "the customer confirmed who they are"),
    ("deceased", "fin_deceased", "the customer has died"),
    ("wrong_number", "fin_wrong_number", "wrong number"),
    ("someone_else", "third_party", "someone else answered"),
]
nodes["opening"] = fl.conv(
    "opening",
    "You have just introduced yourself and asked whether you are speaking with {{title}} {{last_name}}. Do not call any tool in this turn. Do not say why you are calling.",
    on_enter={"type": "tts", "text": "Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with {{title}} {{last_name}}?"},
    extraction=[fl.ext("who1", WHO_VALUES, WHO_DESC)], first_only=True)
INITIAL = fl.conversation_first("opening", SETUP, "who1", OPENING_ROUTES, "opening_retry", nodes)

nodes["opening_retry"] = fl.conv(
    "opening_retry",
    "You called {{title}} {{last_name}} and asked whether you are speaking with them, but the answer did not confirm it. "
    "No tool call is allowed in this turn. Do not say why you are calling, and do not mention any account, product, debt, payment or collections.\n"
    "If the person asked a question, answer it briefly first: who you are -> you are Freya Bank's digital assistant; a robot or AI -> you are Freya Bank's digital assistant; "
    "a scam -> they can verify this call by phoning Freya Bank's customer service number; what it is about -> you can only discuss that with {{title}} {{last_name}}. "
    "If they said they do not want to talk, say you only need a moment. "
    "Then ask exactly: \"Am I speaking with {{title}} {{last_name}}?\"",
    extraction=[fl.ext("who2", WHO_VALUES, WHO_DESC)],
    transitions=[
        fl.eq("who2", "customer", "ask_dob", "the customer confirmed who they are"),
        fl.eq("who2", "deceased", "fin_deceased", "the customer has died"),
        fl.eq("who2", "wrong_number", "fin_wrong_number", "wrong number"),
        fl.eq("who2", "someone_else", "third_party", "someone else answered"),
        fl.eq("who2", "refuses", "fin_declined", "refuses again"),
        fl.always("fin_unclear"),
    ])

# ---------------------------------------------------------------- third party
cb_tool = fl.api_tool(
    API, "schedule_callback",
    description="Book a callback for the customer. CALL it as soon as the person names a day and time inside the allowed window.",
    field_descriptions={"date": "Callback date as YYYY-MM-DD. Must be one of the allowed days.",
                        "time": "Callback time as HH:MM, 24 hour, between 10:00 and 19:00."},
    post=fl.ok_post("Callback booked.", "The booking failed. Try schedule_callback once more with the same values."))

nodes["third_party"] = fl.conv(
    "third_party",
    "You called for {{title}} {{last_name}} ({{first_name}}) but someone else is on the line.\n"
    "STRICT: Never say why you are calling. Never mention the bank account, a product, a debt, an amount, a payment or collections, even if they ask or offer to pay or help. "
    "If they ask what it is about, say you can only discuss it with {{title}} {{last_name}} personally. Do not ask them any security question.\n"
    "Your only job: ask when {{title}} {{last_name}} can be reached, then book a callback.\n"
    "Now: {{today_text}}, {{now_time}}.\n{{callback_text}}\n"
    "- If they give a day and time inside the window, call schedule_callback with date YYYY-MM-DD and time HH:MM. 'Tomorrow morning around eleven' means tomorrow at 11:00. If they give only a day, ask for a time; if only a vague time like 'morning', propose a precise time such as 11:00 and ask if it suits.\n"
    "- If the day or time is outside the window, say you can only call back today or on the next business day between 10:00 and 19:00, and ask once for another time.\n"
    "- If the second answer is also outside the window, or they cannot say when, do not book: call transition_to_fin_no_callback.\n"
    "After every tool result, speak or call the next tool.",
    tools=[cb_tool],
    extraction=[fl.ext("tp_status", ["none", "wrong_number", "deceased"],
                       "From the person's latest message: wrong_number if they say this number does not belong to the customer or they do not know the customer; deceased if they say the customer has died; otherwise none.")],
    transitions=[
        fl.ok_true("schedule_callback", "fin_callback", "callback booked"),
        fl.eq("tp_status", "deceased", "fin_deceased", "customer died"),
        fl.eq("tp_status", "wrong_number", "fin_wrong_number", "wrong number"),
        fl.intent_tool("fin_no_callback",
                       "No callback can be booked: the person gave a second time outside the allowed window, or cannot say when the customer is reachable.",
                       "No callback can be booked inside the allowed window"),
    ])

# ---------------------------------------------------------------- identity
HINTS = {"day_month_swapped": "Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for example 14 March 1988."}
MAX_WRONG = "Three wrong answers. The check has ended. Say nothing about the account."
ALL_VERIFIED = "Both answers are correct. Identity verified."  # the brief's two questions (freyalib's default is generic)

transfer_general = fl.api_tool(API, "transfer_to_agent", baked={"queue": "general"},
                               description="Transfer the call to a human colleague. CALL it only when the customer insists on a human after you asked once whether you can help.")

ID_COMMON = ("Rules for this step:\n"
             "- Do not mention the reason for the call, collections, a debt, a payment, a product or an amount. If asked what the call is about or how much they owe, say you can explain right after the security questions.\n"
             "- If the customer refuses to answer, or asks what the call is about instead of answering: explain that these questions protect their account, and ask the question again.\n"
             "- If the customer asks for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"
             "- After every tool result, speak to the customer or call the next tool. Follow what_to_do_next.")

REFUSAL_DESC = ("From the customer's LATEST message only: refused if they refuse to answer the security question, say they do not want to talk, "
                "or ask what the call is about instead of answering it. none if they give an answer or say anything else.")

nodes["ask_dob"] = fl.conv(
    "ask_dob",
    "The person confirmed they are {{title}} {{last_name}}. You must check identity with two security questions, one at a time. Now ask the first: their date of birth.\n"
    "When they give it, call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03-05). "
    "If they give only part of the date, ask for the rest before calling the tool.\n" + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "date_of_birth"},
                       description="Check the date of birth. CALL it every time the customer gives a full date of birth.",
                       field_descriptions={"answer": "The date of birth as YYYY-MM-DD."},
                       post=fl.verify_post("What is your date of birth?", HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED)), transfer_general],
    extraction=[fl.ext("refusal_dob", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        fl.eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        fl.is_true("verify_identity_response.data.verified", "ask_phone", "date of birth correct"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_dob", "refused", "count_decline_dob", "customer refused"),
    ])

nodes["ask_phone"] = fl.conv(
    "ask_phone",
    "The date of birth was correct. Now ask the second security question: the last four digits of the phone number on file.\n"
    "When they give four digits, call verify_identity with answer = the four digits only.\n" + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "phone_last4"},
                       description="Check the last four digits of the phone number. CALL it every time the customer gives four digits.",
                       field_descriptions={"answer": "Exactly four digits."},
                       post=fl.verify_post("What are the last four digits of the phone number on file?", HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED)), transfer_general],
    extraction=[fl.ext("refusal_phone", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_phone", "refused", "count_decline_phone", "customer refused"),
    ])

for stage in ["dob", "phone"]:
    code = fl.counter_code("decline_count", 2, "decline_route", reset={"refusal_dob": "none", "refusal_phone": "none"})
    nodes[f"count_decline_{stage}"] = fl.code_node(f"count_decline_{stage}", code, [
        fl.eq("decline_route", "close", "fin_declined", "second refusal"), fl.always(f"ask_{stage}")])

# ---------------------------------------------------------------- account
nodes["load_account"] = fl.api_node(
    "load_account", fl.api_tool(API, "get_account", description="Get the late products.", retries=2),
    [fl.always("prepare")], mapping=[{"path": "data.products", "variable": "products"}])
nodes["prepare"] = fl.code_node("prepare", PREPARE, [fl.always("negotiate")])


def promise_tool():
    return fl.api_tool(API, "create_promise", baked={"product_id": "{{product_id}}"},
                       description="Record the payment promise. CALL it only after you read back product, amount and date and the customer clearly said yes.",
                       field_descriptions={"amount": "The agreed amount, a number like 420.5.",
                                           "date": "The agreed payment date as YYYY-MM-DD."},
                       post=fl.promise_post(), pre=fl.promise_pre())


PROMISE_TR = [
    fl.ok_true("create_promise", "fin_promise", "promise recorded"),
    fl.tool_failed_twice("create_promise", "fin_service_error", "create_promise failed twice"),
]

FACTS = ("ACCOUNT\n- Product: {{product_words}}.\n- Full past-due amount: {{past_due_fmt}}. Days late: {{days_late_txt}}.\n"
         "- Floor, the lowest amount you may accept: {{floor_fmt}} (the {{floor_name}}).\n"
         "DATES\n- Today: {{today_text}} ({{today_iso}}).\n- Deadline, the latest date you may record: {{deadline_text}} ({{deadline_iso}}).\n"
         "- A promise date must be a business day (Monday to Friday, not a bank holiday) from today up to the deadline.\n"
         "- Attempt 1 date: {{attempt1_text}} ({{attempt1_iso}}).\n- Persuasion attempts allowed: {{attempts_n}}. {{attempt2_line}}\n"
         "WEEKDAY WORDS\n{{weekday_table}}\nCALENDAR (look every date up here)\n{{calendar_text}}\n")

NEGOTIATE = (
    "The customer is verified. You told them about the late payment and asked \"Can you make this payment today?\". Now get a payment promise.\n\n"
    "HOW TO GET THE PROMISE\n"
    "1. You propose every amount. NEVER ask how much they can pay. If they ask you to choose, propose an amount yourself. Start with the full past-due amount.\n"
    "2. Yes to paying today = the full amount, today.\n"
    "3. A date or an amount the customer proposes is never a refusal. Check it:\n"
    "   - Date: look it up in the CALENDAR. 'allowed' -> accept it. Weekend or bank holiday not after the deadline -> say that day is not possible and offer the next business day shown. "
    "After the deadline (for example a salary date later) -> say the latest date you can record is {{deadline_text}} and offer it; if they refuse that, it is a flat refusal.\n"
    "   - A vague period ('next week', 'the week after next', 'end of the month', 'when my salary comes') -> ask once for the exact day. If they still give none, propose the deadline {{deadline_text}}.\n"
    "   - 'next <weekday>' and 'this <weekday>': use WEEKDAY WORDS.\n"
    "   - Amount from the floor up to the full amount, both included -> accept it. Below the floor -> say it cannot be recorded and offer the floor {{floor_fmt}} once; if they do not accept, it is a flat refusal.\n"
    "4. If they say the full amount is too much: offer the floor {{floor_fmt}} once, and say the rest stays overdue. If they refuse the floor, it is a flat refusal.\n"
    "5. A flat refusal (a no with no date and no amount, a non-answer, or refusing your offer) uses one persuasion attempt:\n"
    "   - Attempt 1: propose paying on {{attempt1_text}} - the full amount, or the floor {{floor_fmt}} if they already said the full amount is too much.\n"
    "   - {{attempt2_line}}\n"
    "   - When the allowed attempts are used up and they refuse again, stop: call transition_to_fin_refused. Never repeat an offer they already refused.\n"
    "6. When amount and date are agreed, read back: \"{{product_words}}, <amount>, on <weekday day month>. Do you confirm?\" Call create_promise only after a clear yes, with amount as a number and date as YYYY-MM-DD. "
    "If they change the date or amount, check it again and read back again.\n"
    "7. After create_promise: if it failed, call create_promise once more with the same values. Never say the promise is recorded unless the result has ok true.\n\n"
    "OTHER\n"
    "- Never offer a discount, waiver, payment plan or any other term.\n"
    "- If they ask for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"
    "- If they say twice that they do not want to talk: call transition_to_fin_refused.\n"
    "- If they ask to change or cancel a promise: they can do it in the mobile app.\n"
    "- If they ask something these facts do not answer, say you do not have that information.\n"
    "- After every tool result, speak to the customer or call the next tool.\n\n" + FACTS)

TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a death in the family, or losing their job (this wins over all others). "
              "already_paid = says they have ALREADY paid this past-due amount (not 'I will pay'). "
              "dispute = says the debt or product is not theirs, they never had it, or it was closed or paid off in the past. "
              "new_plan = explicitly asks for a new payment plan, lower or smaller instalments, or restructuring (just saying the amount is too much is NOT new_plan). "
              "none = anything else.")

neg_tr = PROMISE_TR + [
    fl.transferred("fin_transferred_human", "transferred to a human"),
    fl.eq("topic", "hardship", "hardship", "hardship"),
    fl.eq("topic", "already_paid", "fin_paid", "already paid"),
    fl.eq("topic", "dispute", "fin_dispute", "dispute"),
    fl.eq("topic", "new_plan", "xfer_restructuring", "wants a new plan"),
    fl.intent_tool("fin_refused",
                   "The customer finally refused: all persuasion attempts are used up, or they said twice they do not want to talk.",
                   "The customer finally refused to make any promise"),
]
nodes["negotiate"] = fl.conv(
    "negotiate", NEGOTIATE,
    on_enter={"type": "tts", "text": "Thank you, {{title}} {{last_name}}. I am calling from the collections team about a late payment on your {{product_words}}. The past-due amount is {{past_due_fmt}}, and it is {{days_late_txt}} days late. Can you make this payment today?"},
    first_only=True,
    tools=[promise_tool(), transfer_general],
    extraction=[fl.ext("topic", ["none", "hardship", "already_paid", "dispute", "new_plan"], TOPIC_DESC)],
    transitions=neg_tr)

nodes["hardship"] = fl.conv(
    "hardship",
    "The customer mentioned a hardship (illness, a death in the family, or job loss). Do NOT try to persuade them and do not propose any payment.\n"
    "On your first turn here: say one short sentence of sympathy, then offer to connect them with the customer support team. Offer it only once.\n"
    "Never offer a discount, waiver, payment plan or any other term. If they ask for one, say you cannot offer that.\n"
    "If the customer themselves names a date or an amount to pay, handle it with the rules below and record it with create_promise after a clear yes to the read-back.\n"
    "After every tool result, speak to the customer or call the next tool.\n\n" + FACTS,
    tools=[promise_tool()],
    extraction=[fl.ext("support_choice", ["none", "accept", "decline"],
                       "Answer to the offer to connect with the customer support team, from the customer's LATEST message: accept if they want to be connected, decline if they do not want it or say no, none otherwise or if the offer has not been made yet.")],
    transitions=PROMISE_TR + [
        fl.eq("support_choice", "accept", "xfer_support", "accepts support"),
        fl.eq("support_choice", "decline", "fin_hardship", "declines support"),
    ])

for q, fin, line in [("restructuring", "fin_transferred_restructuring", "I cannot set up a new plan myself, but I will transfer you to the team that can help with that."),
                     ("support", "fin_transferred_support", "I will connect you with our customer support team now.")]:
    nodes[f"xfer_{q}"] = fl.api_node(
        f"xfer_{q}", fl.api_tool(API, "transfer_to_agent", baked={"queue": q}, description="Transfer.", retries=1),
        [fl.always(fin)], on_enter={"type": "tts", "text": line})

# ---------------------------------------------------------------- close_call lifecycle
close_call = fl.close_call_tool(
    API,
    outcome_desc="promise: a promise was recorded. paid: says already paid. transferred: handed to a person. no_promise: verified, no promise. not_verified: identity not passed. not_reached: the customer was not reached.",
    reason_desc="transferred: restructuring|human|support. no_promise: refused|hardship|dispute|service_error. not_verified: failed|declined. not_reached: callback|no_callback|wrong_number|deceased|unclear. Empty for promise and paid.",
    no_reason_outcomes=("promise", "paid"))

SYSTEM = ("You are Freya Bank's digital assistant on an outbound phone call to {{title}} {{last_name}}. Speak English. Keep every turn to one or two short sentences. Address the customer as {{title}} {{last_name}}.\n"
          "Always:\n"
          "- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue.\n"
          "- If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue.\n"
          "- Never invent figures, dates or reasons. If you do not have the information, say so.\n"
          "- Never offer a discount, waiver, payment plan or any term you were not given.\n"
          "- Do not say goodbye or end the call yourself: the call is closed for you.\n"
          "- Call at most one tool per message. When a rule says to call a tool, call it: saying it is not enough.\n"
          "- After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. Follow what_to_do_next in a tool result.\n"
          "- Say amounts as plain numbers, for example 420.50, and dates as weekday, day and month, for example Friday 16 October.")

wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call],
                 {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"})

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-a_v2.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "->", out)
