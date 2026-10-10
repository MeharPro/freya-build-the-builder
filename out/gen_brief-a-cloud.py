"""Generator for slot `brief-a-cloud`: Brief A (briefs/brief-a.md) on builder/freyalib. Writes out/brief-a-cloud.workflow.json.

Written by following .claude/skills/build-phone-agent/SKILL.md; out/gen_brief-a_v2.py was the structural reference.
Every brief value lives here (rule numbers `R<n>` refer to the numbered rules of briefs/brief-a.md).
Deviations from the reference are marked `DEV:` and listed in out/brief-a-cloud.REPORT.md.

Usage: python3 out/gen_brief-a-cloud.py [tools/openapi.json] [out/brief-a-cloud.workflow.json]"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")

# ---------------------------------------------------------------- brief values (section 7, rules 6, 11-12, 18, 25)
HOLIDAYS = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]   # section 7
CALLBACK = {"open": "10:00", "close": "19:00", "same_day": True, "days_ahead": 1}  # R6
EARLY_MAX_DAYS = 7                                                                  # R18 band table
EARLY_BD, EARLY_ATTEMPTS = 12, 1
LATE_BD, LATE_ATTEMPTS = 7, 2
MAX_DECLINES = 2                                                                    # R15, R45 (second refusal closes)
BANK = "Freya Bank"

nodes = {}

# ---------------------------------------------------------------- terminals: one per row of the closing table (R46, R47)
BYE = " Thank you for your time, {{title}} {{last_name}}. Goodbye."
FINS = {
    # key: (outcome, reason, farewell)
    "promise": ("promise", "", "You will receive a text message confirming this promise." + BYE),            # R38 verbatim
    "paid": ("paid", "", "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise today." + BYE),  # R39
    "transferred_restructuring": ("transferred", "restructuring", "Thank you, {{title}} {{last_name}}. A colleague will take over now. Goodbye."),  # R41
    "transferred_human": ("transferred", "human", "Thank you, {{title}} {{last_name}}. A colleague will take over now. Goodbye."),  # R42
    "transferred_support": ("transferred", "support", "Thank you, {{title}} {{last_name}}. A colleague from customer support will take over now. Goodbye."),  # R32
    "refused": ("no_promise", "refused", "I understand." + BYE),                                              # R31, R45
    "hardship": ("no_promise", "hardship", "I understand, and I hope things get better soon." + BYE),         # R32
    "dispute": ("no_promise", "dispute", "Thank you for telling me. I will not take a payment promise today." + BYE),  # R40
    "service_error": ("no_promise", "service_error", "I am sorry, I could not record your promise because of a technical problem." + BYE),  # R37
    "failed": ("not_verified", "failed", "I am sorry, I could not verify your identity, so I cannot continue. Please use the " + BANK + " mobile app or visit a branch. Thank you, goodbye."),  # R14
    "declined": ("not_verified", "declined", "I understand. Without the security questions I cannot continue. Thank you for your time, goodbye."),  # R15
    "callback": ("not_reached", "callback", "Thank you, we will call back then. Goodbye."),                    # R6
    "no_callback": ("not_reached", "no_callback", "Thank you for your help. Goodbye."),                       # R7
    "wrong_number": ("not_reached", "wrong_number", "I apologise for the inconvenience. Thank you, goodbye."),  # R8
    # DEV: the reference farewell has no thank-you; R47 asks every call to thank and say goodbye. R9 sentence verbatim.
    "deceased": ("not_reached", "deceased", "I am sorry for your loss. Thank you, goodbye."),                  # R9
    "unclear": ("not_reached", "unclear", "I am sorry, I could not confirm who I am speaking with. Thank you, goodbye."),  # R3
}
for key, (outcome, reason, farewell) in FINS.items():
    fl.end_pair(key, outcome, reason, farewell, nodes)

# ---------------------------------------------------------------- setup code: dates (R6, R18, R30)
DATES_EXTRA = r'''
monday = today - datetime.timedelta(days=today.weekday())
a1 = lastbd_of_week(monday)
if a1 is None or a1 <= today:
    a1 = lastbd_of_week(monday + datetime.timedelta(days=7))
vars['attempt1_date'] = a1.isoformat()
vars['early_deadline'] = addbd(today, __EARLY_BD__).isoformat()
vars['late_deadline'] = addbd(today, __LATE_BD__).isoformat()
'''.replace("__EARLY_BD__", str(EARLY_BD)).replace("__LATE_BD__", str(LATE_BD))
SETUP = fl.SETUP_CODE(HOLIDAYS, callback_rule=CALLBACK, extra=DATES_EXTRA)

# ---------------------------------------------------------------- prepare code: product facts (R17, R18, R25, R30)
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
    floor_name = 'instalment amount'
past_due = float(p.get('past_due') or 0)
try:
    floor = float(floor)
except Exception:
    floor = past_due
days_late = int(float(p.get('days_late') or 0))
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
if days_late <= __EARLY_MAX__:
    band = 'early'; attempts = __EARLY_ATT__; deadline = datetime.date.fromisoformat(str(vars.get('early_deadline')))
else:
    band = 'late'; attempts = __LATE_ATT__; deadline = datetime.date.fromisoformat(str(vars.get('late_deadline')))
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
'''.replace("__EARLY_MAX__", str(EARLY_MAX_DAYS)).replace("__EARLY_ATT__", str(EARLY_ATTEMPTS)).replace("__LATE_ATT__", str(LATE_ATTEMPTS))
PREPARE_FALLBACKS = {"product_words": "account", "past_due_fmt": "the past-due amount"}
for k in ["floor_fmt", "floor_name", "days_late_txt", "band", "attempts_n", "deadline_iso", "deadline_text",
          "attempt1_iso", "attempt1_text", "attempt2_line", "calendar_text"]:
    PREPARE_FALLBACKS[k] = ""
PREPARE = fl.CAL_HELPERS(HOLIDAYS) + fl.guarded(PREPARE_BODY, "prepare_state", PREPARE_FALLBACKS)

# ---------------------------------------------------------------- opening (R1-R4, R8, R9, R45) -> setup (code) -> routes
WHO_VALUES = ["customer", "someone_else", "wrong_number", "deceased", "refuses", "unclear"]
WHO_DESC = ("Who answered, judged ONLY from the person's latest message. "
            "customer = they confirm they are {{title}} {{last_name}}: 'yes', 'that's me', 'speaking', or they say the customer's own name ({{first_name}} / {{last_name}}). "
            "someone_else = another person answered (a relative, partner, colleague), or says the customer is not here / not available, or offers to take a message. "
            "wrong_number = says this number does not belong to that person / they do not know them. "
            "deceased = says the customer has died / passed away. "
            "refuses = says they do not want to talk / not interested. "
            "unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', 'is this a robot?', 'is this a scam?', a question, silence.")

OPENING_ROUTES = [
    ("customer", "ask_dob", "the customer confirmed who they are"),
    ("deceased", "fin_deceased", "the customer has died"),
    ("wrong_number", "fin_wrong_number", "wrong number"),
    ("someone_else", "third_party", "someone else answered"),
]
# R1: digital assistant, calling from the bank, call recorded; no word about collections/debt/payment/product. R2: the ask.
# DEV: wording follows R1 more literally ("a digital assistant calling from ... This call is recorded").
nodes["opening"] = fl.conv(
    "opening",
    "You have just introduced yourself and asked whether you are speaking with {{title}} {{last_name}}. Do not call any tool in this turn. Do not say why you are calling.",
    on_enter={"type": "tts", "text": "Hello, I am a digital assistant calling from " + BANK + ". This call is recorded. Am I speaking with {{title}} {{last_name}}?"},
    extraction=[fl.ext("who1", WHO_VALUES, WHO_DESC)], first_only=True)
INITIAL = fl.conversation_first("opening", SETUP, "who1", OPENING_ROUTES, "opening_retry", nodes)

# R3: second ask after answering the customer's question (R4, R43); still unclear -> not_reached/unclear.
# R45: a second "I do not want to talk" before verification -> not_verified/declined.
nodes["opening_retry"] = fl.conv(
    "opening_retry",
    "You called {{title}} {{last_name}} and asked whether you are speaking with them, but the answer did not confirm it. "
    "No tool call is allowed in this turn. Do not say why you are calling, and do not mention any account, product, debt, payment or collections.\n"
    "If the person asked a question, answer it briefly first: who you are -> you are " + BANK + "'s digital assistant; a robot or AI -> you are " + BANK + "'s digital assistant; "
    "a scam -> they can verify this call by phoning " + BANK + "'s customer service number; what it is about -> you can only discuss that with {{title}} {{last_name}}. "
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

# ---------------------------------------------------------------- third party (R5-R10)
cb_tool = fl.api_tool(
    API, "schedule_callback",
    description="Book a callback for the customer. CALL it as soon as the person names a day and time inside the allowed window.",
    field_descriptions={"date": "Callback date as YYYY-MM-DD. Must be one of the allowed days.",
                        "time": "Callback time as HH:MM, 24 hour, between %s and %s." % (CALLBACK["open"], CALLBACK["close"])},
    post=fl.ok_post("Callback booked.", "The booking failed. Try schedule_callback once more with the same values."))

nodes["third_party"] = fl.conv(
    "third_party",
    "You called for {{title}} {{last_name}} ({{first_name}}) but someone else is on the line.\n"
    "STRICT: Never say why you are calling. Never mention the bank account, a product, a debt, an amount, a payment or collections, even if they ask or offer to pay or help. "
    "If they ask what it is about, say you can only discuss it with {{title}} {{last_name}} personally. Do not ask them any security question and do not accept answers to them.\n"
    "Your only job: ask when {{title}} {{last_name}} can be reached, then book a callback.\n"
    "Now: {{today_text}}, {{now_time}}.\n{{callback_text}}\n"
    "- If they give a day and time inside the window, call schedule_callback with date YYYY-MM-DD and time HH:MM. 'Tomorrow morning around eleven' means tomorrow at 11:00. If they give only a day, ask for a time; if only a vague time like 'morning', propose a precise time such as 11:00 and ask if it suits.\n"
    "- If the day or time is outside the window, say you can only call back today or on the next business day between " + CALLBACK["open"] + " and " + CALLBACK["close"] + ", and ask once for another time.\n"
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

# ---------------------------------------------------------------- identity (R11-R15, R42)
HINTS = {"day_month_swapped": "Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for example 14 March 1988."}  # R13
MAX_WRONG = "Three wrong answers. The check has ended. Say nothing about the account."  # R12, R14
ALL_VERIFIED = "Both answers are correct. Identity verified."
WRONG = "Wrong answer. Tell the customer it does not match our records and ask again: {question}"

transfer_general = fl.api_tool(API, "transfer_to_agent", baked={"queue": "general"},
                               description="Transfer the call to a human colleague. CALL it only when the customer insists on a human after you asked once whether you can help.")

ID_COMMON = ("Rules for this step:\n"
             "- Do not mention the reason for the call, collections, a debt, a payment, a product or an amount. If asked what the call is about or how much they owe, say you can explain right after the security questions.\n"
             "- If the customer refuses to answer, or asks what the call is about instead of answering: explain that these questions protect their account, and ask the question again.\n"
             "- If the customer asks for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"
             "- After every tool result, speak to the customer or call the next tool. Follow what_to_do_next.")

REFUSAL_DESC = ("From the customer's LATEST message only: refused if they refuse to answer the security question, say they do not want to talk, "
                "or ask what the call is about instead of answering it. none if they give an answer or say anything else.")


def verify_tool(field, question, desc, answer_desc):
    return fl.api_tool(API, "verify_identity", baked={"field": field}, description=desc,
                       field_descriptions={"answer": answer_desc},
                       post=fl.verify_post(question, HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED, wrong_text=WRONG))


nodes["ask_dob"] = fl.conv(
    "ask_dob",
    "The person confirmed they are {{title}} {{last_name}}. You must check identity with two security questions, one at a time. Now ask the first: their date of birth.\n"
    "When they give it, call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03-05). "
    "If they give only part of the date, ask for the rest before calling the tool.\n" + ID_COMMON,
    tools=[verify_tool("date_of_birth", "What is your date of birth?",
                       "Check the date of birth. CALL it every time the customer gives a full date of birth.",
                       "The date of birth as YYYY-MM-DD."), transfer_general],
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
    tools=[verify_tool("phone_last4", "What are the last four digits of the phone number on file?",
                       "Check the last four digits of the phone number. CALL it every time the customer gives four digits.",
                       "Exactly four digits."), transfer_general],
    extraction=[fl.ext("refusal_phone", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_phone", "refused", "count_decline_phone", "customer refused"),
    ])

# R15: one counter across both questions; the second refusal closes as not_verified/declined.
for stage in ["dob", "phone"]:
    code = fl.counter_code("decline_count", MAX_DECLINES, "decline_route", reset={"refusal_dob": "none", "refusal_phone": "none"})
    nodes[f"count_decline_{stage}"] = fl.code_node(f"count_decline_{stage}", code, [
        fl.eq("decline_route", "close", "fin_declined", "second refusal"), fl.always(f"ask_{stage}")])

# ---------------------------------------------------------------- account (R16)
nodes["load_account"] = fl.api_node(
    "load_account", fl.api_tool(API, "get_account", description="Get the late products.", retries=2),
    [fl.always("prepare")], mapping=[{"path": "data.products", "variable": "products"}])
nodes["prepare"] = fl.code_node("prepare", PREPARE, [fl.always("negotiate")])


def promise_tool():
    # R34, R37: only after a clear yes; "recorded" only on ok true; one retry.
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
    "1. You propose every amount. NEVER ask how much they can pay. If they ask you to choose, propose an amount yourself. Start with the full past-due amount.\n"  # R24
    "2. Yes to paying today = the full amount, today.\n"
    "3. A date or an amount the customer proposes is never a refusal. Check it:\n"  # R29
    "   - Date: look it up in the CALENDAR. 'allowed' -> accept it. Weekend or bank holiday not after the deadline -> say that day is not possible and offer the next business day shown. "  # R19, R20
    "After the deadline (for example a salary date later) -> say the latest date you can record is {{deadline_text}} and offer it; if they refuse that, it is a flat refusal.\n"  # R23
    "   - A vague period ('next week', 'the week after next', 'end of the month', 'when my salary comes') -> ask once for the exact day. If they still give none, propose the deadline {{deadline_text}}.\n"  # R21
    "   - 'next <weekday>' and 'this <weekday>': use WEEKDAY WORDS.\n"  # R22
    "   - Amount from the floor up to the full amount, both included -> accept it. Below the floor -> say it cannot be recorded and offer the floor {{floor_fmt}} once; if they do not accept, it is a flat refusal.\n"  # R27
    "4. If they say the full amount is too much: offer the floor {{floor_fmt}} once, and say the rest stays overdue. If they refuse the floor, it is a flat refusal.\n"  # R26
    "5. A flat refusal (a no with no date and no amount, a non-answer, or refusing your offer) uses one persuasion attempt:\n"  # R30
    "   - Attempt 1: propose paying on {{attempt1_text}} - the full amount, or the floor {{floor_fmt}} if they already said the full amount is too much.\n"
    "   - {{attempt2_line}}\n"
    "   - When the allowed attempts are used up and they refuse again, stop: call transition_to_fin_refused. Never repeat an offer they already refused.\n"  # R31
    "6. When amount and date are agreed, read back: \"{{product_words}}, <amount>, on <weekday day month>. Do you confirm?\" Call create_promise only after a clear yes, with amount as a number and date as YYYY-MM-DD. "  # R34
    "If they change the date or amount, check it again and read back again.\n"  # R35
    "7. After create_promise: if it failed, call create_promise once more with the same values. Never say the promise is recorded unless the result has ok true.\n\n"  # R37
    "OTHER\n"
    "- Never offer a discount, waiver, payment plan or any other term.\n"  # R33
    "- If they ask for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"  # R42
    "- If they say twice that they do not want to talk: call transition_to_fin_refused.\n"  # R45
    "- If they ask to change or cancel a promise: they can do it in the mobile app.\n"  # R36
    "- If they ask something these facts do not answer, say you do not have that information.\n"  # R44
    "- After every tool result, speak to the customer or call the next tool.\n\n" + FACTS)

TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a death in the family, or losing their job (this wins over all others). "
              "already_paid = says they have ALREADY paid this past-due amount (not 'I will pay'). "
              "dispute = says the debt or product is not theirs, they never had it, or it was closed or paid off in the past. "
              "new_plan = explicitly asks for a new payment plan, lower or smaller instalments, or restructuring (just saying the amount is too much is NOT new_plan). "
              "none = anything else.")

nodes["negotiate"] = fl.conv(
    "negotiate", NEGOTIATE,
    # R17 statement + R28 first ask, in fixed text
    on_enter={"type": "tts", "text": "Thank you, {{title}} {{last_name}}. I am calling from the collections team about a late payment on your {{product_words}}. The past-due amount is {{past_due_fmt}}, and it is {{days_late_txt}} days late. Can you make this payment today?"},
    first_only=True,
    tools=[promise_tool(), transfer_general],
    extraction=[fl.ext("topic", ["none", "hardship", "already_paid", "dispute", "new_plan"], TOPIC_DESC)],
    transitions=PROMISE_TR + [
        fl.transferred("fin_transferred_human", "transferred to a human"),
        fl.eq("topic", "hardship", "hardship", "hardship"),           # R32 first: before R30 and R41
        fl.eq("topic", "already_paid", "fin_paid", "already paid"),   # R39
        fl.eq("topic", "dispute", "fin_dispute", "dispute"),          # R40
        fl.eq("topic", "new_plan", "xfer_restructuring", "wants a new plan"),  # R41
        fl.intent_tool("fin_refused",
                       "The customer finally refused: all persuasion attempts are used up, or they said twice they do not want to talk.",
                       "The customer finally refused to make any promise"),
    ])

# R32: sympathy, no persuasion, offer support once; accept -> transfer support; decline -> no_promise/hardship;
# a date/amount named by the customer is still recorded.
# DEV: the hardship node also carries transfer_to_agent(general) + a transferred route, so R42 (human, "applies
# before and after verification") works here too; the reference has no human exit from hardship (audit gap R52).
nodes["hardship"] = fl.conv(
    "hardship",
    "The customer mentioned a hardship (illness, a death in the family, or job loss). Do NOT try to persuade them and do not propose any payment.\n"
    "On your first turn here: say one short sentence of sympathy, then offer to connect them with the customer support team. Offer it only once.\n"
    "Never offer a discount, waiver, payment plan or any other term. If they ask for one, say you cannot offer that.\n"
    "If they ask for a human colleague instead: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"
    "If the customer themselves names a date or an amount to pay, handle it with the rules below and record it with create_promise after a clear yes to the read-back.\n"
    "After every tool result, speak to the customer or call the next tool.\n\n" + FACTS,
    tools=[promise_tool(), transfer_general],
    extraction=[fl.ext("support_choice", ["none", "accept", "decline"],
                       "Answer to the offer to connect with the customer support team, from the customer's LATEST message: accept if they want to be connected, decline if they do not want it or say no, none otherwise or if the offer has not been made yet.")],
    transitions=PROMISE_TR + [
        fl.transferred("fin_transferred_human", "transferred to a human"),
        fl.eq("support_choice", "accept", "xfer_support", "accepts support"),
        fl.eq("support_choice", "decline", "fin_hardship", "declines support"),
    ])

for q, fin, line in [("restructuring", "fin_transferred_restructuring", "I cannot set up a new plan myself, but I will transfer you to the team that can help with that."),
                     ("support", "fin_transferred_support", "I will connect you with our customer support team now.")]:
    nodes[f"xfer_{q}"] = fl.api_node(
        f"xfer_{q}", fl.api_tool(API, "transfer_to_agent", baked={"queue": q}, description="Transfer.", retries=1),
        [fl.always(fin)], on_enter={"type": "tts", "text": line})

# ---------------------------------------------------------------- close_call lifecycle (R46)
close_call = fl.close_call_tool(
    API,
    outcome_desc="promise: a promise was recorded. paid: says already paid. transferred: handed to a person. no_promise: verified, no promise. not_verified: identity not passed. not_reached: the customer was not reached.",
    reason_desc="transferred: restructuring|human|support. no_promise: refused|hardship|dispute|service_error. not_verified: failed|declined. not_reached: callback|no_callback|wrong_number|deceased|unclear. Empty for promise and paid.",
    no_reason_outcomes=("promise", "paid"))

SYSTEM = ("You are " + BANK + "'s digital assistant on an outbound phone call to {{title}} {{last_name}}. Speak English. Keep every turn to one or two short sentences. Address the customer as {{title}} {{last_name}}.\n"
          "Always:\n"
          "- If asked whether you are a robot or an AI: say you are " + BANK + "'s digital assistant, then continue.\n"  # R4
          "- If asked whether this is a scam: say they can verify this call by phoning " + BANK + "'s customer service number, then continue.\n"  # R43
          "- Never invent figures, dates or reasons. If you do not have the information, say so.\n"  # R44
          "- Never offer a discount, waiver, payment plan or any term you were not given.\n"  # R33
          "- Do not say goodbye or end the call yourself: the call is closed for you.\n"
          "- Never call close_call yourself.\n"  # DEV: R46 exactly one close_call (audit gap R64 of the reference)
          "- Call at most one tool per message. When a rule says to call a tool, call it: saying it is not enough.\n"
          "- After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. Follow what_to_do_next in a tool result.\n"
          "- Say amounts as plain numbers, for example 420.50, and dates as weekday, day and month, for example Friday 16 October.")

# DEV: no test_variables (skill + CLAUDE.md: on the chat route they replace the real customer_id).
wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call], None)

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-a-cloud.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "tools:", len(wf["tools"]), "->", out)
