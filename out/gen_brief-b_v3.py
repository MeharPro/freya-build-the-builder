"""Brief B generator, v3: Brief A + Brief B (one to three products) on builder/policy.py. Writes out/brief-b_v3.workflow.json.

The port of out/gen_brief-b_lib.py onto the policy-as-code architecture of out/gen_brief-a_v3.py (see its docstring
and docs/research/sota-techniques.md T1, T2, T3, T20, T22, T26), conversation-first like gen_brief-a_v2.py:
- the statement names every late product, one sentence each, then asks once whether all can be paid today (B2, B4);
- a yes, or one date for everything, settles every product at once; a date after one product's deadline puts
  that product on its own deadline and the read-back says so (B6); otherwise the products are handled one by one
  in get_account order, each starting at attempt 1 with its own counters, band, floor and deadline (B3, B4, B5);
- paid / dispute settle one product and the call goes on (B9); one read-back for all agreed promises and one
  confirmation, then create_promise once per product in code (B7); a promise that fails twice keeps the others
  and gets a service_error note (B11); every other product without a promise gets add_note with its reason (B8);
- transfers add no notes (B10); the closing outcome follows the B closing rule (finalize in builder/policy.py).
Every Brief A/B value is in this file only."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402
import policy as pol  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")
HOLIDAYS = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]  # from the brief, section 7

nodes = {}

# ---------------------------------------------------------------- terminals (rule 46 table; rule 47 goodbye)
# key: (outcome, reason, farewell). The promise farewell no longer repeats the recorded sentence: the wrap-up
# node said it (rule 38) right after create_promise returned ok.
FINS = {
    "promise": ("promise", "", "Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "paid": ("paid", "", "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise today. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "transferred_restructuring": ("transferred", "restructuring", "Thank you, {{title}} {{last_name}}. A colleague will take over now. Goodbye."),
    "transferred_human": ("transferred", "human", "Thank you, {{title}} {{last_name}}. A colleague will take over now. Goodbye."),
    "transferred_support": ("transferred", "support", "Thank you, {{title}} {{last_name}}. A colleague from customer support will take over now. Goodbye."),
    "refused": ("no_promise", "refused", "I understand. I have not recorded a promise today. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "hardship": ("no_promise", "hardship", "I understand. I have not recorded a promise today. Thank you for your time, {{title}} {{last_name}}, and take care. Goodbye."),
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
# 12 business days ahead, the late band up to 7 (rules 18, 30). Callbacks: today up to 19:00 or the next business
# day 10:00-19:00 (rule 6).
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
# The prompt quotes the opening line too: the chat route (local sim, smoke) replaces the initial node's tts with a
# model turn ("Suppressed: Missing prior assistant message"); simulations play the tts.
nodes["opening"] = fl.conv(
    "opening",
    "If you have not spoken yet, say exactly: \"Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with {{title}} {{last_name}}?\" "
    "Do not call any tool in this turn. Do not say why you are calling.",
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
             "- If the customer asks a question back (why you need it, what this is about, who is calling): answer in one short sentence without naming the reason for the call, then ask the same question again. If they refuse to answer: explain that these questions protect their account, and ask the question again.\n"
             "- If the customer asks for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"
             "- After every tool result, speak to the customer or call the next tool. Follow what_to_do_next.")

REFUSAL_DESC = ("From the customer's LATEST message only: refused if they refuse to answer the security question, say they do not want to talk, "
                "or ask the same thing back again instead of answering. none if they give an answer or say anything else." + fl.QUESTION_ENUM_CLAUSE + fl.REFUSAL_NONE_CLAUSE)

nodes["ask_dob"] = fl.conv(
    "ask_dob",
    "The person confirmed they are {{title}} {{last_name}}. You must check identity with two security questions, one at a time. Now ask the first: their date of birth.\n"
    "When they give it, call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03-05). "
    "If they give only part of the date, ask for the rest before calling the tool.\n" + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "date_of_birth"}, pre=fl.reset_pre(["question_count_dob"]),
                       description="Check the date of birth. CALL it every time the customer gives a full date of birth.",
                       field_descriptions={"answer": "The date of birth as YYYY-MM-DD."},
                       post=fl.verify_post("What is your date of birth?", HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED)), transfer_general],
    extraction=[fl.ext("refusal_dob", ["none", "refused", "question"], REFUSAL_DESC)],
    transitions=[
        fl.eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        fl.is_true("verify_identity_response.data.verified", "ask_phone", "date of birth correct"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_dob", "refused", "count_decline_dob", "customer refused"),
        fl.eq("refusal_dob", "question", "qb_dob", "asks a question back"),
    ])

nodes["ask_phone"] = fl.conv(
    "ask_phone",
    "The date of birth was correct. Now ask the second security question: the last four digits of the phone number on file.\n"
    "When they give four digits, call verify_identity with answer = the four digits only.\n" + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "phone_last4"}, pre=fl.reset_pre(["question_count_phone"]),
                       description="Check the last four digits of the phone number. CALL it every time the customer gives four digits.",
                       field_descriptions={"answer": "Exactly four digits."},
                       post=fl.verify_post("What are the last four digits of the phone number on file?", HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED)), transfer_general],
    extraction=[fl.ext("refusal_phone", ["none", "refused", "question"], REFUSAL_DESC)],
    transitions=[
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_phone", "refused", "count_decline_phone", "customer refused"),
        fl.eq("refusal_phone", "question", "qb_phone", "asks a question back"),
    ])

for stage in ["dob", "phone"]:
    nodes[f"qb_{stage}"] = fl.question_back_node(stage, f"ask_{stage}", "fin_declined")   # a question back: answer, ask again; twice in a row = deflection
    code = fl.counter_code("decline_count", 2, "decline_route", reset={"refusal_dob": "none", "refusal_phone": "none"})
    nodes[f"count_decline_{stage}"] = fl.code_node(f"count_decline_{stage}", code, [
        fl.eq("decline_route", "close", "fin_declined", "second refusal"), fl.always(f"ask_{stage}")])


# ---------------------------------------------------------------- payment: policy as code, one to three products
NOTE_ENUM = fl.tool_spec(API, "add_note")["fields"]["reason"]["enum"]
POLICY = pol.Policy(
    HOLIDAYS,
    texts={
        "question": "Can you pay [amount] [when]?",
        "question_product": "Can you pay [amount] [when] for your [words]?",                                       # B4 one by one
        "question_all": "Can you pay all of them today?",                                                           # B4
        "weekend_or_holiday": "[named] is not a business day, so I cannot record it. The next business day is [date].",   # A20
        "after_deadline": "The latest date I can record for your [words] is [deadline].",  # A23
        "before_today": "[named] has already passed.",
        "below_floor": "I cannot record [named]. The lowest amount I can record is [floor], your [floor_name].",       # A27
        "above_full": "The past-due amount is [full], so that is the most I can record.",
        "vague": "Which exact day would that be?",                                                                    # A21
        "vague_deadline": "The latest date I can record is [deadline].",
        "too_much_floor": "I understand. The lowest amount I can accept is [floor], the [floor_name]. The rest stays overdue.",  # A26
        "exhausted": "I understand.",                                                                                 # A31
        "one_by_one": "Let us go through them one by one.",                                                          # B4
        "next_product": "Next, your [words].",
        "paid": "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise for your [words].",  # A39, B9
        "dispute": "Thank you for telling me. I will not take a promise for your [words].",                          # A40, B9
        "hardship": "I am sorry to hear that. Would you like me to connect you with our customer support team?",      # A32
        "human_first": "I can help you with most things myself. Is there anything I can help you with before I transfer you?",  # A42
        "notalk_first": "I understand. This will only take a moment.",                                               # A45
        "readback_head": "To confirm: your ",                                                                         # A34, B7: all together
        "readback_item": "[words], [amount], [when]",
        "readback_sep": "; your ",
        "own_deadline": ", which is the latest date I can record for it",                                            # B6
        "moved_bd": ", the next business day",
        "readback_tail": ". Do you confirm?",
        "recorded": "Your promise is recorded.",
        "recorded_many": "Your promises for your [list] are recorded.",
        "after_recorded": "You will receive a text message confirming this promise.",                                 # A38
        "rec_failed": "I could not record the promise for your [words] because of a technical problem.",             # B11
        "anything_else": "Is there anything else I can help you with?",
        "wrap_change": "A recorded promise cannot be changed or cancelled on this call, but you can change it in the Freya Bank mobile app.",  # A36
    },
    multi=True,                                                 # B1: one to three products
    notes=True,                                                 # B8: a note per product without a promise
    note_reasons={s: s for s in ("refused", "hardship", "dispute", "paid", "service_error") if s in NOTE_ENUM},
    fin_keys={"promise": "promise", "paid": "paid", "default": "refused", "refused": "refused",
              "hardship": "hardship", "dispute": "dispute", "service_error": "service_error"},  # B closing
    fail_max=2, human_limit=2, notalk_limit=2, closed_day_move="after",
    asides={   # side questions answered before continuing, even on a turn that goes through code into a tts line
        "robot": {"when": "asks whether they are talking to a robot, a machine or an AI", "say": "I am Freya Bank's digital assistant."},
        "scam": {"when": "asks whether this call is a scam or genuine", "say": "You can verify this call by phoning Freya Bank's customer service number."},
    })

# Brief B: every product has its own band, deadline, floor and ladder (B3, B5); attempt 1 = the full amount (the
# floor once 'too much' was said) on the attempt-1 date, attempt 2 (late band) = the floor on that product's
# deadline (A30). Statement: one sentence per product, then one question for all (B2, B4).
PREPARE_BODY = fl.products_from_vars() + r'''
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
a1 = datetime.date.fromisoformat(str(vars.get('attempt1_date')))
items = []
for i, p in enumerate(prods):
    if not isinstance(p, dict):
        continue
    ptype = str(p.get('type') or '')
    pid = str(p.get('product_id') or ('p' + str(i + 1)))
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
    if days_late <= 7:
        deadline = datetime.date.fromisoformat(str(vars.get('early_deadline')))
        rungs = [('full_or_floor', a1)]
    else:
        deadline = datetime.date.fromisoformat(str(vars.get('late_deadline')))
        rungs = [('full_or_floor', a1), ('floor', deadline)]
    register_product(vars, pid, words, past_due, floor, floor_name, deadline, rungs)
    items.append((words, past_due, days_late, deadline))
name = str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '')
if len(items) == 1:
    w, pd, dl_, dd = items[0]
    statement = ('Thank you, ' + name + '. I am calling from the collections team about a late payment on your ' + w + '. The past-due amount is '
                 + fmt(pd) + ', and it is ' + str(dl_) + ' days late. Can you make this payment today?')
else:
    statement = 'Thank you, ' + name + '. I am calling from the collections team about late payments on ' + str(len(items)) + ' of your products. '
    for w, pd, dl_, dd in items:
        statement += 'Your ' + w + ' has ' + fmt(pd) + ' past due, ' + str(dl_) + ' days late. '
    statement += 'Can you pay all of them today?'
lines = []
for w, pd, dl_, dd in items:
    lines.append(w + ': past due ' + fmt(pd) + ', ' + str(dl_) + ' days late, latest date ' + txt_short(dd))
vars['products_facts'] = '; '.join(lines)
'''
PREPARE = POLICY.prepare_code(PREPARE_BODY, "statement", fallbacks={
    "say_next": "Thank you. I am calling from the collections team about late payments. Can you pay all of them today?",
    "products_facts": ""})

nodes["load_account"] = fl.api_node(
    "load_account", fl.api_tool(API, "get_account", description="Get the late products.", retries=2),
    [fl.always("prepare")], mapping=[{"path": "data.products", "variable": "products"}])
nodes["prepare"] = fl.code_node("prepare", PREPARE, [fl.always("negotiate")])

# ---- extraction, in the briefs' own terms
TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a death in the family, or losing their job (this wins over every other value, even when they also name a date or an amount). "
              "already_paid = says they have ALREADY paid a past-due amount (not 'I will pay'). "
              "dispute = says a debt or a product is not theirs, they never had it, or it was closed or paid off in the past. "
              "new_plan = explicitly asks for a new payment plan, lower or smaller instalments, or restructuring. Saying an amount is too much is NOT new_plan; a different amount or date for a payment is NOT new_plan." + fl.PLAN_REQUEST_CLAUSE + " "
              "human = asks to speak to a person, a human, an agent or a colleague. "
              "no_talk = says they do not want to talk or do not want this call (not a refusal to pay). "
              "none = anything else: offers, yes or no answers, refusals to pay, questions.")
STANCE_DESC = ("The customer's answer to the agent's LATEST payment proposal, from the customer's latest message only. "
               "accept = agrees to exactly what the agent proposed ('yes', 'okay', 'fine', 'that works', 'I can do that'). "
               "refuse = a no with no date and no amount ('no', 'I can't', 'not today', 'I won't pay that'), or a non-answer that avoids the question ('I don't know', 'maybe'). "
               "too_much = says the amount is too much, too high, or that they cannot pay that much or all of it, without naming an amount. "
               "offer = names their own date, amount or period: a date or an amount the customer proposes is NEVER a refusal. "
               "other = anything else: a question, small talk, a request.")
KIND_DESC = ("From the customer's LATEST message only. exact = they name a specific payment day (a date, a weekday, 'tomorrow', 'the 30th') or a specific amount of money, or both. "
             "vague = only a vague period without a day ('next week', 'end of the month', 'when my salary comes'). "
             "none = no date, amount or period in the latest message (also 'yes', 'no', questions).")
FOR_DESC = ("Which product the customer's LATEST message is about, in the order the agent listed the products: first, second or third "
            "(match the product they name, e.g. 'the credit card', 'the car loan'). all = all of them, everything, both. none = no product named.")
DATE_DESC = ("The payment date the customer names in their LATEST message. 'this <weekday>' is that weekday in the current Monday-to-Sunday week; "
             "'next <weekday>' is that weekday in the FOLLOWING calendar week. Leave it empty when the latest message names no specific day.")
AMOUNT_DESC = ("The amount of money the customer offers to pay in their LATEST message, as a number ('six forty' = 640). "
               "Leave it empty when the latest message names no amount. A day of the month is not an amount.")
CONFIRM_DESC = ("The customer's answer to the read-back question 'Do you confirm?', from their latest message only. "
                "yes = a clear yes ('yes', 'correct', 'I confirm', 'that's right'). "
                "change = they give a different amount or a different date for a promise ('make it 250 instead', 'actually Monday'). "
                "no = a plain no without a new amount or date. other = anything else, for example a question.")

topic = fl.ext("topic", ["none", "hardship", "already_paid", "dispute", "new_plan", "human", "no_talk"], TOPIC_DESC)
offer_for = fl.ext("offer_for", ["none", "all", "first", "second", "third"], FOR_DESC)
TOPIC_TRS = POLICY.topic_transitions()

FACTS = ("FACTS\n- Products: {{products_facts}}.\n- Today: {{today_text}}.\n")
COMMON = ("- If asked whether you are a robot or an AI: you are Freya Bank's digital assistant. If asked whether this is a scam: they can verify this call by phoning Freya Bank's customer service number.\n"
          "- Never offer a discount, a waiver, a payment plan or any term that is not in STATE. If asked, say you cannot offer that.\n"
          "- A question these facts do not answer: say you do not have that information.\n"
          "- No tool call is allowed here. Never say that a promise is recorded.\n")

NEGOTIATE = ("You are talking with {{title}} {{last_name}}, who is verified, about their late payments. The line you just said and the offer in STATE were decided by the system from the bank's rules.\n"
             "- Never propose, compute or change an amount or a date yourself, and never ask how much they can pay. The only offer you may make is the current offer in STATE, word for word.\n"
             "- If the customer asks a question or says something else, answer it in one short sentence, then ask the current offer again.\n"
             + COMMON + FACTS)
neg_ext = [topic, POLICY.stance_extraction(STANCE_DESC), offer_for] + POLICY.offer_extraction(DATE_DESC, AMOUNT_DESC, KIND_DESC)
neg_trs = TOPIC_TRS + POLICY.offer_guard_transitions() + POLICY.stance_transitions()
nodes["negotiate"] = POLICY.negotiate_node(NEGOTIATE, neg_ext, neg_trs)

CONFIRM = ("You read back the promises and asked \"Do you confirm?\". They are recorded only after a clear yes.\n"
           "- If the customer asks something, answer it in one short sentence, then ask again: \"Do you confirm?\".\n"
           + COMMON + FACTS)
nodes["confirm"] = POLICY.confirm_node(CONFIRM, CONFIRM_DESC, DATE_DESC, AMOUNT_DESC, topic_entry=topic, topic_trs=TOPIC_TRS)

HS_ANSWER_DESC = ("From the customer's LATEST message. support_yes = they want to be connected with the customer support team. "
                  "support_no = they do not want to be connected, say no to that offer, or say they cannot pay and want nothing more. "
                  "accept_offer = they agree to the date and amount the agent just proposed. "
                  "none = anything else, for example a question or a request for a discount.")
HARDSHIP = ("The customer mentioned a hardship (illness, a death in the family or job loss). You said one short sentence of sympathy and offered to connect them with the customer support team.\n"
            "- Make NO persuasion attempt. Never propose an amount or a date yourself.\n"
            "- If they ask a question or for a discount, answer in one short sentence, then ask whether they want to be connected with the customer support team.\n"
            + COMMON + FACTS)
nodes["hardship"] = POLICY.hardship_node(HARDSHIP, HS_ANSWER_DESC, KIND_DESC, DATE_DESC, AMOUNT_DESC)

WRAP_DESC = ("From the customer's LATEST message, after the agent said the promises are recorded and asked whether there is anything else. "
             "done = nothing else ('no', 'that's all', 'thanks', 'goodbye'). "
             "human = asks to speak to a person, a human or an agent, or insists on one. "
             "new_plan = asks for a new payment plan or lower instalments. "
             "change = asks to change, move or cancel a promise just recorded (another date or amount). "
             "question = asks a question. other = anything else.")
WRAPUP = ("The promises in STATE are recorded. You said so and asked whether there is anything else.\n"
          "- If the customer asks a question, answer it in one or two sentences from these facts or say you do not have that information, then ask whether there is anything else you can help with.\n"
          "- A recorded promise cannot be changed or cancelled on this call; they can change it in the Freya Bank mobile app.\n"
          + COMMON + FACTS)
nodes["wrapup"] = POLICY.wrapup_node(WRAPUP, WRAP_DESC)

POLICY.add_event_nodes(nodes)
POLICY.record_nodes(nodes, API)

for q, fin, line in [("restructuring", "fin_transferred_restructuring", "I cannot set up a new plan myself, but I will transfer you to the team that can help with that."),
                     ("support", "fin_transferred_support", "I will connect you with our customer support team now."),
                     ("general", "fin_transferred_human", "I will transfer you to a colleague now.")]:
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

wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call], conduct=True)   # no test_variables (CLAUDE.md); conduct = how customers talk

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-b_v3.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "->", out)
