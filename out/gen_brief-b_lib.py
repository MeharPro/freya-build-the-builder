"""Port of out/gen_brief-b.py onto builder/freyalib.py + builder/multiproduct.py. Generates
out/brief-b.lib.workflow.json from the rules of briefs/brief-a.md + briefs/brief-b.md and tools/openapi.json.
Everything bank-specific is in this file; every JSON shape, hook and code template comes from the two libraries."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402
import multiproduct as mp  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")
HOLIDAYS = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]  # from the brief, section 7

nodes = {}

# ---------------------------------------------------------------- terminals
# key: (outcome, reason, farewell)
FINS = {
    "promise": ("promise", "", "Thank you. You will receive a text message confirming this promise. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
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

# Brief B: one to three products, each with its own band (<= 7 days late = early, 1 persuasion attempt; later =
# late, 2 attempts), floor (minimum payment of a credit card, instalment of a loan) and deadline. The product field
# names are the API file's get_account product fields; api=API makes multiproduct check every name, type and
# placeholder below against that file.
PREPARE = mp.prepare_code(
    HOLIDAYS,
    api=API, pid_field="product_id", amount_field="past_due", days_late_field="days_late", type_field="type",
    statement_fallback="Thank you. I am calling from the collections team about a late payment. Can you make this payment today?",
    bands=[{"name": "early", "max_days_late": 7, "attempts": 1, "deadline_var": "early_deadline"},
           {"name": "late", "max_days_late": None, "attempts": 2, "deadline_var": "late_deadline"}],
    floor_rules=[{"types": ["credit_card"], "field": "minimum_payment", "name": "minimum payment"},
                 {"types": None, "field": "instalment_amount", "name": "instalment"}],
    wording=[{"types": ["credit_card"], "template": "credit card ending {card_last4}"},
             {"types": None, "template": "{type_words}"}],
    unknown_type_words="loan",
    statement={
        "one": "Thank you, {title} {last_name}. I am calling from the collections team about a late payment on your {words}. The past-due amount is {past_due}, and it is {days_late} days late. Can you make this payment today?",
        "many_head": "Thank you, {title} {last_name}. I am calling from the collections team about late payments on {n} of your products. ",
        "many_item": "Your {words} has {past_due} past due, {days_late} days late. ",
        "many_tail": "Can you pay all of them today?",
    },
    attempt1_var="attempt1_date")

nodes["setup"] = fl.code_node("setup", SETUP, [fl.always("opening")])

# ---------------------------------------------------------------- opening
WHO_VALUES = ["customer", "someone_else", "wrong_number", "deceased", "refuses", "unclear"]
WHO_DESC = ("Who answered, judged ONLY from the person's latest message. "
            "customer = they confirm they are {{title}} {{last_name}}: 'yes', 'that's me', 'speaking', or they say the customer's own name ({{first_name}} / {{last_name}}). "
            "someone_else = another person answered (a relative, partner, colleague), or says the customer is not here / not available, or offers to take a message. "
            "wrong_number = says this number does not belong to that person / they do not know them. "
            "deceased = says the customer has died / passed away. "
            "refuses = says they do not want to talk / not interested. "
            "unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', a question, silence.")

opening_tr = [
    fl.eq("who1", "customer", "ask_dob", "the customer confirmed who they are"),
    fl.eq("who1", "deceased", "fin_deceased", "the customer has died"),
    fl.eq("who1", "wrong_number", "fin_wrong_number", "wrong number"),
    fl.eq("who1", "someone_else", "third_party", "someone else answered"),
    fl.always("opening_retry"),
]
nodes["opening"] = fl.conv(
    "opening",
    "You have just introduced yourself and asked whether you are speaking with {{title}} {{last_name}}. Do not call any tool in this turn. Do not say why you are calling.",
    on_enter={"type": "tts", "text": "Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with {{title}} {{last_name}}?"},
    extraction=[fl.ext("who1", WHO_VALUES, WHO_DESC)], transitions=opening_tr, first_only=True)

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
ID_OK = "Both answers are correct. Identity verified."   # the brief has two security questions

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
                       post=fl.verify_post("What is your date of birth?", HINTS, MAX_WRONG, all_verified_text=ID_OK)), transfer_general],
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
                       post=fl.verify_post("What are the last four digits of the phone number on file?", HINTS, MAX_WRONG, all_verified_text=ID_OK)), transfer_general],
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

# ---------------------------------------------------------------- promise + note tools (per-product state machine)
NOTE_ENUM = fl.tool_spec(API, "add_note")["fields"]["reason"]["enum"]
# Brief B rule 11: a promise that fails twice keeps the others and gets a service_error note (api=API checks the
# reason against add_note's enum and the field names against the two tools' schemas).
PROMISE_PRE = mp.promise_pre_code(cap_to_deadline=True, cap_to_amount=True, api=API)
PROMISE_POST = mp.promise_post_code(max_fails=2, fail_reason="service_error", api=API)
NOTE_PRE = mp.note_pre_code(api=API)
NOTE_POST = mp.note_post_code(api=API)


def promise_tool():
    return fl.api_tool(API, "create_promise",
                       description="Record ONE product's payment promise. CALL it once per agreed product, only after you read back ALL agreed promises together and the customer clearly said yes.",
                       field_descriptions={"product_id": "The product id exactly as in PRODUCTS, for example p1.",
                                           "amount": "The agreed amount for this product, a number like 420.5.",
                                           "date": "The agreed payment date for this product as YYYY-MM-DD."},
                       pre=PROMISE_PRE, post=PROMISE_POST)


def note_tool():
    return fl.api_tool(API, "add_note", omit=["text"],
                       description="Record why ONE product ended without a promise. CALL it once for every product that has no recorded promise, after the promises are recorded. Never call it when the call is being transferred.",
                       field_descriptions={"product_id": "The product id exactly as in PRODUCTS, for example p2.",
                                           "reason": "Why this product has no promise. One of: " + ", ".join(NOTE_ENUM) + "."},
                       pre=NOTE_PRE, post=NOTE_POST)


TRANSFERRED = fl.transferred("fin_transferred_human", "transferred to a human")
ALL_DONE = mp.all_done_tr("finalize", "every product has a recorded promise or a note")

FACTS = ("PRODUCTS (in get_account order)\n{{products_text}}\n"
         "DATES\n- Today: {{today_text}} ({{today_iso}}).\n"
         "- A promise date must be a business day (Monday to Friday, not a bank holiday) from today up to THAT product's deadline.\n"
         "WEEKDAY WORDS\n{{weekday_table}}\nCALENDAR (look every date up here)\n{{calendar_text}}\n")

NEGOTIATE = (
    "The customer is verified. You have just stated every late product and asked whether they can pay (all of them) today. Now get payment promises.\n\n"
    "ORDER OF WORK\n"
    "A. If they can pay everything today: the promises are the full amount of each product, today. Go to READ-BACK.\n"
    "B. If they name ONE date (and no amount) for everything: each product gets its full amount on that date, checked per product against the CALENDAR. "
    "If that date is after a product's deadline, that product gets ITS OWN deadline instead and you say so in the read-back; the other products keep the named date. Go to READ-BACK.\n"
    "C. Otherwise go through the products ONE BY ONE in the order of PRODUCTS. Do not ask about today again. For each product start at its attempt 1: "
    "propose its full amount on its attempt 1 date, unless the customer already named a date or amount for it. Settle one product (agreed, or finally refused) before moving to the next.\n\n"
    "RULES PER PRODUCT\n"
    "1. You propose every amount. NEVER ask how much they can pay.\n"
    "2. A date or an amount the customer proposes is never a refusal. Check it:\n"
    "   - Date: look it up in the CALENDAR. Allowed for that product -> accept. Weekend or bank holiday not after the deadline -> offer the next business day shown. "
    "After that product's deadline -> say the latest date you can record for it is its deadline and offer it; if they refuse that, it is a flat refusal.\n"
    "   - Vague period ('next week', 'end of the month', 'when my salary comes') -> ask once for the exact day. If they still give none, propose that product's deadline.\n"
    "   - 'next <weekday>' / 'this <weekday>': use WEEKDAY WORDS.\n"
    "   - Amount from the floor up to the full amount, both included -> accept. Below the floor -> say it cannot be recorded and offer the floor once; if not accepted, it is a flat refusal.\n"
    "3. Full amount too much -> offer that product's floor once and say the rest stays overdue. Floor refused -> flat refusal.\n"
    "4. A flat refusal (a no with no date and no amount, a non-answer, refusing your offer) uses one persuasion attempt of THAT product. Attempts are counted per product: "
    "attempt 1 and attempt 2 exactly as in PRODUCTS. When that product's attempts are used up and they refuse again, that product is refused: stop, never repeat an offer, and move to the next product.\n"
    "5. 'I already paid' this product -> say payments can take one business day to appear; no promise for it (reason paid). "
    "'Not mine' / 'never had it' / 'it was closed or paid off' -> do not argue; no promise for it (reason dispute). Then continue with the other products.\n\n"
    "READ-BACK AND RECORDING (only when every product is settled)\n"
    "6. If at least one product is agreed: read back ALL agreed promises together in one turn (product in words, amount, date as weekday day month, and say when a product uses its own deadline) and ask \"Do you confirm?\". "
    "If they change something, check it and read back again. After a clear yes, call create_promise once per agreed product, one per message, product_id from PRODUCTS, amount as a number, date as YYYY-MM-DD.\n"
    "7. If create_promise fails, call it once more. Never say a promise is recorded unless the result says so. If it fails twice, tell the customer you could not record that one, then call add_note with reason service_error for it.\n"
    "8. Then, for EVERY product without a recorded promise, call add_note with its product_id and reason: " + ", ".join(NOTE_ENUM[:-1]) + " or " + NOTE_ENUM[-1] + ". This applies even when no product got a promise. "
    "The call is closed for you automatically once every product has a promise or a note.\n\n"
    "OTHER\n"
    "- Never offer a discount, waiver, payment plan or any other term.\n"
    "- If they ask for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent (and never add_note).\n"
    "- If they say twice that they do not want to talk: every product without a promise is refused; call add_note for each.\n"
    "- If they ask to change or cancel a recorded promise: they can do it in the mobile app.\n"
    "- If they ask something these facts do not answer, say you do not have that information.\n"
    "- Follow what_to_do_next in every tool result. After every tool result, speak to the customer or call the next tool.\n\n" + FACTS)

TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a death in the family, or losing their job (this wins over all others). "
              "new_plan = explicitly asks for a new payment plan, lower or smaller instalments, or restructuring (just saying the amount is too much is NOT new_plan). "
              "none = anything else.")

neg_tr = [
    ALL_DONE,
    TRANSFERRED,
    fl.eq("topic", "hardship", "hardship", "hardship"),
    fl.eq("topic", "new_plan", "xfer_restructuring", "wants a new plan"),
    mp.done_intent_tr("finalize", "Every product now has a recorded promise or a note (add_note), and nothing is left to record.",
                      "Every product has a recorded promise or a note"),
]
nodes["negotiate"] = fl.conv(
    "negotiate", NEGOTIATE,
    on_enter={"type": "tts", "text": "{{statement_text}}"},
    first_only=True,
    tools=[promise_tool(), note_tool(), transfer_general],
    extraction=[fl.ext("topic", ["none", "hardship", "new_plan"], TOPIC_DESC)],
    transitions=neg_tr)

nodes["hardship"] = fl.conv(
    "hardship",
    "The customer mentioned a hardship (illness, a death in the family, or job loss). Do NOT try to persuade them and do not propose any payment.\n"
    "On your first turn here: say one short sentence of sympathy, then offer to connect them with the customer support team. Offer it only once.\n"
    "Never offer a discount, waiver, payment plan or any other term.\n"
    "If the customer themselves names a date or an amount to pay for a product, check it against PRODUCTS and the CALENDAR, read it back, and record it with create_promise after a clear yes.\n"
    "Follow what_to_do_next in every tool result. After every tool result, speak to the customer or call the next tool.\n\n" + FACTS,
    tools=[promise_tool()],
    extraction=[fl.ext("support_choice", ["none", "accept", "decline"],
                       "Answer to the offer to connect with the customer support team, from the customer's LATEST message: accept if they want to be connected, decline if they do not want it or say no, none otherwise or if the offer has not been made yet.")],
    transitions=[
        ALL_DONE,
        fl.eq("support_choice", "accept", "xfer_support", "accepts support"),
        fl.eq("support_choice", "decline", "hardship_notes", "declines support"),
    ])

nodes["hardship_notes"] = fl.conv(
    "hardship_notes",
    "The customer declined the support team. Do not persuade. Say you understand. Then call add_note with reason hardship for each product still open: {{open_pids}} (product ids from PRODUCTS), one per message. "
    "Follow what_to_do_next in every tool result.\n\n" + FACTS,
    tools=[note_tool()],
    transitions=[ALL_DONE, mp.done_intent_tr("finalize", "Every product has a note or a promise.", "Every product has a note or a promise")])

# Brief B closing: a recorded promise wins; every product noted paid -> paid; otherwise no_promise with the reason
# of the first product (get_account order) whose note is not paid. Reasons are the API's add_note enum; the fin
# keys are the rows of the outcome table above.
PRECEDENCE = [(r, r) for r in NOTE_ENUM if r != "paid"]          # hardship, dispute, service_error, refused -> fin_<r>
nodes["finalize"] = fl.code_node(
    "finalize", mp.finalize_code(PRECEDENCE, promise_key="promise", paid_key="paid", default_key="refused", order="product", api=API),
    mp.finalize_transitions(PRECEDENCE, promise_key="promise", paid_key="paid", default_key="refused"))

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

wf = fl.assemble("setup", nodes, SYSTEM, [close_call],
                 {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"})

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-b.lib.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "->", out)
