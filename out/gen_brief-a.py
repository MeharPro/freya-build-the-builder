"""Brief A generator, v3: policy as code (builder/policy.py). Writes out/brief-a.workflow.json.

Opening, third party and identity are those of out/gen_brief-a_v2.py (conversation-first). The payment part is
rebuilt on policy.Policy (docs/research/sota-techniques.md T1, T2, T3, T20, T22, T26; docs/ext-a-v2-failures.md):
- every offer the customer names goes through the offer guard in code (check_offer: weekend/holiday, after the
  deadline, below the floor, above the full amount, before today, vague) and every offer the agent makes comes
  from code (the attempt ladder, the floor offered once, the deadline) as a finished sentence spoken by tts;
- refusals, 'too much', 'does not want to talk' and human requests are counted in code; the ladder switches to
  the floor once the customer said the full amount is too much (rule 30);
- a hardship disclosure routes to the hardship node, where no offer is ever proposed (routing, not a prompt
  note); a date or amount the customer still names goes through the guard and the read-back (rule 32);
- the read-back is built in code from the approved values and a change at the read-back goes back through the
  guard and is read back again, never to a transfer (rules 34, 35);
- create_promise runs in an api_request node entered only from a confirmed read-back, with the read-back values
  baked in and asserted by its pre hook; it is retried once (rule 37);
- after a recorded promise the text-message sentence (rule 38) is spoken and a wrap-up node gives the customer
  their next turn (rules 36, 42, 41).
Every Brief A value (holidays, bands, floors, wording) is in this file only."""
import pathlib, sys, json

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
import freyalib as fl  # noqa: E402
import policy as pol  # noqa: E402

API = fl.load_api(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json")
# R08 / R60 conflicts: confirmed by brief rule 3 and API required queue enum.
SPEC = json.load(open(ROOT / 'out/brief-a.spec.json'))['spec']
HOLIDAYS = [h['date'] for h in SPEC['calendar']['holidays']]
WEEKDAYS = ['Mon Tue Wed Thu Fri Sat Sun'.split().index(w) for w in SPEC['calendar']['business_weekdays']]

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
    "deceased": ("not_reached", "deceased", "I am sorry for your loss. Thank you, goodbye."),
    "unclear": ("not_reached", "unclear", "I am sorry, I could not confirm who I am speaking with. Thank you, goodbye."),
}
for key, (outcome, reason, farewell) in FINS.items():
    row = next(r for r in SPEC['outcomes'] if r['outcome'] == outcome and r['reason'] == reason)
    fl.end_pair(key, row['outcome'], row['reason'], farewell, nodes)

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
for band in BANDS:
    vars[band['name'] + '_deadline'] = addbd(today, band['deadline_rule']['n']).isoformat()
vars['callback_next'] = addbd(today, CALLBACK['days_ahead_business']).isoformat()
'''
ATTEMPT_DATES = 'import json\nBANDS = ' + 'json.loads(' + pol._pylit(SPEC['bands']) + ')' + '\nCALLBACK = ' + repr(SPEC['callback']) + '\n' + ATTEMPT_DATES
SETUP = fl.SETUP_CODE(HOLIDAYS, business_weekdays=WEEKDAYS, callback_rule={**SPEC['callback'], 'days_ahead': SPEC['callback']['days_ahead_business']}, extra=ATTEMPT_DATES)

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
    "If you have not spoken yet, say exactly: \"Hello, I am a digital assistant calling from Freya Bank and this call is recorded. Am I speaking with {{title}} {{last_name}}?\" "
    "Do not call any tool in this turn. Do not say why you are calling.",
    on_enter={"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank and this call is recorded. Am I speaking with {{title}} {{last_name}}?"},
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

# R10-R15 R59: callback components validated in code as soon as supplied.
CB_RULE = SPEC['callback']

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
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "date_of_birth"}, pre=fl.normalise_pre({"answer":"dob"}, date_order="dmy"),
                       description="Check the date of birth. CALL it every time the customer gives a full date of birth.",
                       field_descriptions={"answer": "The date of birth as YYYY-MM-DD."},
                       post=fl.verify_count_post("What is your date of birth?", SPEC["max_wrong_answers"], HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED)), transfer_general],
    extraction=[fl.ext("refusal_dob", ["none", "refused", "question"], REFUSAL_DESC)],
    transitions=[
        fl.eq("id_route", "exhausted", "fin_failed", "three wrong answers"),
        fl.is_true("verify_identity_response.data.verified", "ask_phone", "date of birth correct"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_dob", "refused", "count_decline_dob", "customer refused"),
        fl.eq("refusal_dob", "question", "qb_dob", "asks a question back"),
    ])

nodes["ask_phone"] = fl.conv(
    "ask_phone",
    "The date of birth was correct. Now ask the second security question: the last four digits of the phone number on file.\n"
    "When they give four digits, call verify_identity with answer = the four digits only.\n" + fl.latest_value_note(4) + ID_COMMON,
    tools=[fl.api_tool(API, "verify_identity", baked={"field": "phone_last4"}, pre=fl.normalise_pre({"answer":"digits"}, date_order="dmy"),
                       description="Check the last four digits of the phone number. CALL it every time the customer gives four digits.",
                       field_descriptions={"answer": "Exactly four digits."},
                       post=fl.verify_count_post("What are the last four digits of the phone number on file?", SPEC["max_wrong_answers"], HINTS, MAX_WRONG, all_verified_text=ALL_VERIFIED)), transfer_general],
    extraction=[fl.ext("refusal_phone", ["none", "refused", "question"], REFUSAL_DESC)],
    transitions=[
        fl.is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        fl.eq("id_route", "exhausted", "fin_failed", "three wrong answers"),
        fl.transferred("fin_transferred_human", "transferred"),
        fl.eq("refusal_phone", "refused", "count_decline_phone", "customer refused"),
        fl.eq("refusal_phone", "question", "qb_phone", "asks a question back"),
    ])

for stage in ["dob", "phone"]:
    nodes[f"qb_{stage}"] = fl.question_back_node(stage, f"ask_{stage}", "fin_declined")   # a question back: answer, ask again; twice in a row = deflection
    code = fl.counter_code("decline_count", 2, "decline_route", reset={"refusal_dob": "none", "refusal_phone": "none"})
    nodes[f"count_decline_{stage}"] = fl.code_node(f"count_decline_{stage}", code, [
        fl.eq("decline_route", "close", "fin_declined", "second refusal"), fl.always(f"ask_{stage}")])


# ---------------------------------------------------------------- payment: policy as code
# R28: explicit this weekday stays in current calendar week, even in past.
# R35: named offers never exhaust a synthetic check limit.
class BriefPolicy(pol.Policy):
    def core(self):
        src = super().core()
        src = src.replace("else:\n            delta = (wd - today.weekday()) % 7\n        return today + D(delta), 'exact'", "elif m.group(1) == 'this':\n            delta = wd - today.weekday()\n        else:\n            delta = (wd - today.weekday()) % 7\n        return today + D(delta), 'exact'")
        src = src.replace("if n > int(P['max_checks']):", "if False:")
        # R51 second explicit stop-talking request is the specified refused ending.
        src = src.replace("finalize(V)  # Retain the configured outcome precedence for recorded products.", "V['final_route'] = P['fin_keys']['refused']; V['route'] = 'fin'")
        # R38: stop-talking during hardship must not repeat a payment proposal.
        src = src.replace("say(V, join([T('notalk_first'), g(V, 'offer_question')]))", "say(V, join([T('notalk_first'), 'Would you like me to connect you with our customer support team?']), 'hardship') if g(V, 'mode') == 'hardship' else say(V, join([T('notalk_first'), g(V, 'offer_question')]))")
        # R41: a correction is validated afresh; never treat its below-floor value as refusal.
        src = src.replace("if pg(V, pid, 'offered_floor') == 'yes' and g(V, 'mode') != 'hardship':", "if pg(V, pid, 'offered_floor') == 'yes' and g(V, 'mode') != 'hardship' and g(V, 'confirmation_change') != 'yes':")
        src = src.replace("    check_one(V, pid, a, d, 'exact')\ndef rec_next(V):", "    pset(V, pid, 'agreed', '')\n    V['confirmation_change'] = 'yes'\n    check_one(V, pid, a, d, 'exact')\n    V['confirmation_change'] = 'no'\ndef rec_next(V):")
        # R35: a named amount is validation, never a flat refusal, including repeats.
        src = src.replace("            V['offer_verdict'] = 'below_floor'\n            refuse(V, pid)\n            return", "            V['offer_verdict'] = 'below_floor'\n            set_prop(V, pid, fl_, nd)\n            say(V, join([T('below_floor', named=fmt(na), floor=fmt(fl_), floor_name=pg(V, pid, 'floor_name'), words=pg(V, pid, 'words')), V['offer_question']]))\n            return")
        # R38: support declined after hardship at confirmation withdraws old consent.
        src = src.replace("    for p in pids(V):\n        if state(V, p) == 'open':\n            pset(V, p, 'state', 'hardship')\n    advance(V, '')", "    for p in pids(V):\n        if state(V, p) in ('open', 'agreed'):\n            pset(V, p, 'agreed', '')\n            pset(V, p, 'state', 'hardship')\n    advance(V, '')")
        return src

POLICY = BriefPolicy(
    HOLIDAYS,
    texts={
        # rule 28 (first ask) is in the statement; every later offer is one of these finished sentences
        "question": "Can you pay [amount] [when]?",
        "weekend_or_holiday": "[named] is not a business day, so I cannot record it. The next business day is [date].",   # R20
        "after_deadline": "The latest date I can record is [deadline].",                                               # R23
        "before_today": "[named] has already passed.",                                                                 # R19
        "below_floor": "I cannot record [named]. The lowest amount I can record is [floor], your [floor_name].",       # R27
        "above_full": "Your past-due amount is [full], so that is the most I can record.",                            # R27
        "vague": "Which exact day would that be?",                                                                    # R21
        "vague_deadline": "The latest date I can record is [deadline].",                                              # R21
        "too_much_floor": "I understand. The lowest amount I can accept is [floor], your [floor_name]. The rest stays overdue.",  # R26
        "exhausted": "I understand.",                                                                                 # R31
        "hardship": "I am sorry to hear that. Would you like me to connect you with our customer support team?",      # R32
        "paid": "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise.",   # R39
        "dispute": "Thank you for telling me. I will not take a payment promise today.",   # R40
        "human_first": "I can help you with most things myself. Is there anything I can help you with before I transfer you?",  # R42
        "notalk_first": "I understand. This will only take a moment.",                                               # R45
        "readback_head": "To confirm: your ",                                                                         # R34
        "readback_item": "[words], [amount], [when]",
        "readback_tail": ". Do you confirm?",
        "recorded": "Your promise is recorded.",                                                                      # R37
        "after_recorded": "You will receive a text message confirming this promise.",                                 # R38
        "rec_failed": "I could not record the promise for your [words] because of a technical problem.",
        "anything_else": "Is there anything else I can help you with?",
        "wrap_change": "A recorded promise cannot be changed or cancelled on this call, but you can change it in the Freya Bank mobile app.",  # R36
    },
    business_weekdays=WEEKDAYS, weekday_rule="this_week", multi=False, notes=False,                                   # one product; Brief A never uses add_note
    fin_keys={"promise": "promise", "paid": "paid", "default": "refused", "refused": "refused",
              "hardship": "hardship", "dispute": "dispute", "service_error": "service_error"},
    fail_max=2,                                                 # R37: try once more, then service_error
    human_limit=2, notalk_limit=2,                              # R42 ask once, R45 twice
    closed_day_move="after",                                    # R20 next business day
    asides={   # R4 / R43: side questions answered before continuing, even on a turn that goes through code into a tts line
        "robot": {"when": "asks whether they are talking to a robot, a machine or an AI", "say": "I am Freya Bank's digital assistant."},
        "scam": {"when": "asks whether this call is a scam or genuine", "say": "You can verify this call by phoning Freya Bank's customer service number."},
    })

# Brief A: one product (R1); floor = minimum payment (card) or instalment (loans) (R25); early band (<= 7 days
# late) = deadline 12 business days, 1 attempt; late = 7 business days, 2 attempts (R18); attempt 1 = the full
# amount or the floor once 'too much' was said, on the attempt-1 date; attempt 2 = the floor on the deadline (R30).
PREPARE_BODY = 'import json\nBANDS = ' + 'json.loads(' + pol._pylit(SPEC['bands']) + ')' + '\nFLOORS = ' + 'json.loads(' + pol._pylit(SPEC['floors']) + ')' + '\n' + fl.products_from_vars() + r'''
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
p = prods[0] if prods else {}
if not isinstance(p, dict):
    p = {}
ptype = str(p.get('type') or '')
pid = str(p.get('product_id') or 'p1')
if ptype == 'credit_card':
    words = 'credit card ending ' + str(p.get('card_last4') or '')
    floor = p.get(next(f['rule']['field'] for f in FLOORS if ptype in f['product_types']))
    floor_name = 'minimum payment'
else:
    words = ptype.replace('_', ' ') if ptype else 'loan'
    floor = p.get(next(f['rule']['field'] for f in FLOORS if ptype in f['product_types']))
    floor_name = 'monthly instalment'
past_due = float(p.get('past_due') or 0)
try:
    floor = float(floor)
except Exception:
    floor = past_due
days_late = int(float(p.get('days_late') or 0))
a1 = datetime.date.fromisoformat(str(vars.get('attempt1_date')))
band = next(b for b in BANDS if b['min_days'] <= days_late <= b['max_days'])
if band['attempts'] == 1:
    deadline = datetime.date.fromisoformat(str(vars.get('early_deadline')))
    rungs = [('full_or_floor', a1)]
else:
    deadline = datetime.date.fromisoformat(str(vars.get('late_deadline')))
    rungs = [('full_or_floor', a1), ('floor', deadline)]
register_product(vars, pid, words, past_due, floor, floor_name, deadline, rungs)
vars['product_id'] = pid
vars['product_words'] = words
vars['past_due_fmt'] = fmt(past_due)
vars['days_late_txt'] = str(days_late)
vars['deadline_text'] = txt_short(deadline)
statement = ('Thank you, ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + '. I am calling from the collections team about a late payment on your '
             + words + '. The past-due amount is ' + fmt(past_due) + ', and it is ' + str(days_late) + ' days late. Can you make this payment today?')
'''
PREPARE = POLICY.prepare_code(PREPARE_BODY, "statement", fallbacks={
    "say_next": "Thank you. I am calling from the collections team about a late payment. Can you make this payment today?",
    "product_words": "account", "past_due_fmt": "the past-due amount", "days_late_txt": "", "deadline_text": ""})

nodes["load_account"] = fl.api_node(
    "load_account", fl.api_tool(API, "get_account", description="Get the late products.", retries=2),
    [fl.always("prepare")], mapping=[{"path": "data.products", "variable": "products"}])
nodes["prepare"] = fl.code_node("prepare", PREPARE, [fl.always("negotiate")])

# ---- extraction, in the brief's own terms
TOPIC_DESC = ("What the customer's LATEST message says, if it is one of these. "
              "hardship = mentions illness, a death in the family, or losing their job (this wins over every other value, even when they also name a date or an amount). "
              "already_paid = says they have ALREADY paid this past-due amount (not 'I will pay'). "
              "dispute = says the debt or the product is not theirs, they never had it, or it was closed or paid off in the past. "
              "new_plan = explicitly asks for a new payment plan, lower or smaller instalments, or restructuring. Saying the amount is too much is NOT new_plan; a different amount or date for this payment is NOT new_plan." + fl.PLAN_REQUEST_CLAUSE + " "
              "human = asks to speak to a person, a human, an agent or a colleague. "
              "no_talk = says they do not want to talk or do not want this call (not a refusal to pay). "
              "none = anything else: offers, yes or no answers, refusals to pay, questions.")
STANCE_DESC = ("The customer's answer to the agent's LATEST payment proposal, from the customer's latest message only. "
               "accept = agrees to exactly what the agent proposed ('yes', 'okay', 'fine', 'that works', 'I can do that'). "
               "refuse = a no with no date and no amount ('no', 'I can't', 'not today', 'I won't pay'), or a non-answer that avoids the question ('I don't know', 'maybe', 'we will see'). "
               "too_much = says the amount is too much, too high, or that they cannot pay that much or all of it, without naming an amount. "
               "offer = names their own date, amount or period: a date or an amount the customer proposes is NEVER a refusal. "
               "other = anything else: a question, small talk, a request. I do not know the exact day after an exact-day question is vague, not refuse." + fl.REFUSAL_NONE_CLAUSE)
KIND_DESC = ("From the customer's LATEST message only. exact = they name a specific payment day (a date, a weekday, 'tomorrow', 'the 22nd', 'on the 6th of November when my salary comes') or a specific amount of money, or both. "
             "vague = also I do not know the exact day after an exact-day question; only a vague period without a day ('next week', 'the week after next', 'end of the month', 'when my salary comes', 'in a few days'). "
             "none = no date, amount or period in the latest message (also 'yes', 'no', questions).")
DATE_DESC = ("The payment date the customer names in their LATEST message. 'this <weekday>' is that weekday in the current Monday-to-Sunday week; "
             "'next <weekday>' is that weekday in the FOLLOWING calendar week, so 'next Friday' said on a Wednesday is the Friday of the next week. "
             "Leave it empty when the latest message names no specific day.")
AMOUNT_DESC = ("The amount of money the customer offers to pay in their LATEST message, as a number ('seven hundred' = 700, 'two fifty' = 250). "
               "Leave it empty when the latest message names no amount. A day of the month is not an amount.")
CONFIRM_DESC = ("The customer's answer to the read-back question 'Do you confirm?', from their latest message only. "
                "yes = a clear yes ('yes', 'correct', 'I confirm', 'that's right'). "
                "change = they give a different amount or a different date for this promise ('make it 250 instead', 'actually Monday'). "
                "no = a plain no without a new amount or date. "
                "other = anything else, for example a question.")

topic = fl.ext("topic", ["none", "hardship", "already_paid", "dispute", "new_plan", "human", "no_talk"], TOPIC_DESC)
TOPIC_TRS = POLICY.topic_transitions()

FACTS = ("FACTS\n- Product: {{product_words}}. Past-due amount: {{past_due_fmt}}. Days late: {{days_late_txt}}.\n"
         "- Today: {{today_text}}. The latest date that can be recorded: {{deadline_text}}.\n")
COMMON = ("- If asked whether you are a robot or an AI: you are Freya Bank's digital assistant. If asked whether this is a scam: they can verify this call by phoning Freya Bank's customer service number.\n"
          "- Never offer a discount, a waiver, a payment plan or any term that is not in STATE. If asked, say you cannot offer that.\n"
          "- A question these facts do not answer: say you do not have that information.\n"
          "- No tool call is allowed here. Never say that a promise is recorded.\n")

NEGOTIATE = ("You are talking with {{title}} {{last_name}}, who is verified, about the late payment. The line you just said and the offer in STATE were decided by the system from the bank's rules.\n"
             "- Never propose, compute or change an amount or a date yourself, and never ask how much they can pay. The only offer you may make is the current offer in STATE, word for word.\n"
             "- If the customer asks a question or says something else, answer it in one short sentence, then ask the current offer again.\n"
             + COMMON + FACTS)
neg_ext = [topic, POLICY.stance_extraction(STANCE_DESC)] + POLICY.offer_extraction(DATE_DESC, AMOUNT_DESC, KIND_DESC)
neg_trs = TOPIC_TRS + POLICY.offer_guard_transitions() + POLICY.stance_transitions()
nodes["negotiate"] = POLICY.negotiate_node(NEGOTIATE, neg_ext, neg_trs)

CONFIRM = ("You read back the promise and asked \"Do you confirm?\". The promise is recorded only after a clear yes.\n"
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

WRAP_DESC = ("From the customer's LATEST message, after the agent said the promise is recorded and asked whether there is anything else. "
             "done = nothing else ('no', 'that's all', 'thanks', 'goodbye'). "
             "human = asks to speak to a person, a human or an agent, or insists on one. "
             "new_plan = asks for a new payment plan or lower instalments. "
             "change = asks to change, move or cancel the promise just recorded (another date or amount). "
             "question = asks a question. other = anything else.")
WRAPUP = ("The promise is recorded (STATE). You said so and asked whether there is anything else.\n"
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


# R11/R12: no model-called booking; invalid alternatives share a once-only counter.
CB_CODE = POLICY.event_code('finalize') if False else POLICY.core() + "\n" + r"""
try:
    import re
    rule = json.loads(CB_RULE_LITERAL)
    nowdt = datetime.datetime.fromisoformat(str(vars.get('now')))
    today = nowdt.date()
    nextday = addbd(today, rule['days_ahead_business'])
    words = str(vars.get('cb_when') or '')
    timewords = str(vars.get('cb_time') or '')
    invalid = False
    if words:
        d, kind = resolve_when(vars, words)
        if d is not None:
            vars['cb_date_ok'] = d.isoformat()
            invalid = d not in (today, nextday)
        else:
            invalid = True
    if timewords:
        from_dummy = timewords
        m = re.search(r'(\d{1,2}):(\d{2})', timewords)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2))
            tm = '%02d:%02d' % (hh, mm)
            vars['cb_time_ok'] = tm
            invalid = invalid or hh > 23 or mm > 59 or not (rule['open'] <= tm <= rule['close'])
        else:
            invalid = True
    ds = str(vars.get('cb_date_ok') or '')
    ts = str(vars.get('cb_time_ok') or '')
    if ds and ts:
        invalid = invalid or datetime.datetime.fromisoformat(ds + 'T' + ts) <= nowdt
    if invalid:
        n = int(vars.get('cb_invalid') or 0) + 1
        vars['cb_invalid'] = str(n)
        vars['cb_date_ok'] = ''
        vars['cb_time_ok'] = ''
        vars['cb_route'] = 'close' if n >= 2 else 'retry'
        vars['cb_line'] = 'We can call today or the next business day, between ' + rule['open'] + ' and ' + rule['close'] + ', later than now. What other time would suit?'
    elif ds and ts:
        vars['cb_route'] = 'book'
    else:
        vars['cb_route'] = 'retry'
        vars['cb_line'] = 'What time can we reach them?' if ds else 'Which day can we reach them?'
    vars['cb_when'] = ''
    vars['cb_time'] = ''
except Exception:
    vars['cb_route'] = 'retry'
    vars['cb_line'] = 'When can we reach them?'
"""
CB_CODE = CB_CODE.replace('CB_RULE_LITERAL', pol._pylit(CB_RULE))
nodes['third_party'] = fl.conv('third_party',
    'Someone else answered. Do not disclose the reason, an account, any product or amounts. Do not accept security answers from a relative. Ask when the customer can be reached. ' 
    'Use call dates in these facts only: {{callback_text}}. Extract day words verbatim into cb_when, and time as HH:MM into cb_time. ' 
    'If only one component is supplied extract it immediately. Do not book yourself.',
    extraction=[fl.ext('tp_status',['none','wrong_number','deceased','unavailable'], 'wrong_number: number does not belong to customer; deceased: customer died; unavailable: cannot give any callback; none: otherwise'),
    {'name':'cb_when','type':'string','description':'Customer own words for callback day, empty if none.'},
    {'name':'cb_time','type':'string','description':'Offered callback time normalised HH:MM, use 24 hour time. Empty if none.'}],
    transitions=[fl.eq('tp_status','deceased','fin_deceased','died'), fl.eq('tp_status','wrong_number','fin_wrong_number','wrong number'),
    fl.eq('tp_status','unavailable','fin_no_callback','cannot arrange'), fl.is_set('cb_when','check_callback','day supplied'),fl.is_set('cb_time','check_callback','time supplied')])
nodes['callback_retry'] = fl.conv('callback_retry', nodes['third_party']['task_messages'][0]['content'] if False else
    'Continue arranging a callback, never disclose the reason or account. {{callback_text}}. Extract supplied day verbatim and time as HH:MM. Never book yourself.',
    on_enter={'type':'tts','text':'{{cb_line}}'}, extraction=nodes['third_party']['extraction_schema'], transitions=nodes['third_party']['transitions'])
nodes['check_callback'] = fl.code_node('check_callback', CB_CODE, [fl.eq('cb_route','close','fin_no_callback','second invalid'), fl.eq('cb_route','book','book_callback','valid'), fl.always('callback_retry')])
nodes['book_callback'] = fl.api_node('book_callback', fl.api_tool(API,'schedule_callback', baked={'date':'{{cb_date_ok}}','time':'{{cb_time_ok}}'},pre=fl.normalise_pre({'date':'date','time':'time'}, date_order='dmy'),post=fl.ok_post('Callback booked.','Could not book the callback.')),
    [fl.is_true('cb_ok','fin_callback','booked'),fl.always('callback_error')],mapping=[{'path':'data.ok','variable':'cb_ok'}])
nodes['callback_error'] = fl.conv('callback_error','Say the callback could not be booked.',on_enter={'type':'tts','text':'I could not book the callback.'},transitions=[fl.always('fin_no_callback')])

# R20 R48 R51: per-call counters. What-is-this-about is a decline, not a free clarification.
for stage in ['dob','phone']:
    node = nodes['ask_' + stage]
    node['tools'] = node['tools'][:1]
    node['extraction_schema'] = [fl.ext('refusal_' + stage,['none','refused','question','human'],
        'LATEST message: refused = refuses security, does not want to talk, or asks what the call is about instead of answering. '
        'human = requests a person, never a refusal. question = genuine clarification about why security is needed, robot or scam. none = answers or other message.' + fl.REFUSAL_NONE_CLAUSE)]
    node['transitions'] = [t for t in node['transitions'] if t['target_node'] != 'fin_transferred_human'] if False else node['transitions']
    node['transitions'].insert(0, fl.eq('refusal_' + stage,'human','id_human_' + stage,'human request'))
    nodes['id_human_' + stage] = fl.code_node('id_human_' + stage, fl.counter_code('human_count',2,'human_route',reset={'refusal_' + stage:'none'}),
        [fl.eq('human_route','close','xfer_general','insists'),fl.always('id_help_' + stage)])
    nodes['id_help_' + stage] = fl.conv('id_help_' + stage, 'Ask once whether you can help before transferring. Do not disclose why you called.',
        on_enter={'type':'tts','text':'Can I help you first?'}, extraction=node['extraction_schema'],
        transitions=[fl.eq('refusal_' + stage,'human','id_human_' + stage,'insists'),fl.always('ask_' + stage)])
    nodes['count_decline_' + stage] = fl.code_node('count_decline_' + stage,
        fl.counter_code('decline_count',2,'decline_route',reset={'refusal_dob':'none','refusal_phone':'none'}),
        [fl.eq('decline_route','close','fin_declined','second decline'),fl.always('decline_explain_' + stage)])
    nodes['decline_explain_' + stage] = fl.conv('decline_explain_' + stage, node['task_message'],
        on_enter={'type':'tts','text':'These questions protect your account.'}, tools=node['tools'], extraction=node['extraction_schema'],transitions=node['transitions'])

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

# R38 R45 R46: topic priority also applies during read-back.
ct = nodes['confirm']['transitions']
nodes['confirm']['transitions'] = TOPIC_TRS + [t for t in ct if t not in TOPIC_TRS]
# R48: human requests are handled in hardship with the same call-wide counter.
nodes['hardship']['extraction_schema'].append(topic)
nodes['hardship']['transitions'] = [fl.eq('topic','human','pol_human','human request'), fl.eq('topic','no_talk','pol_notalk','stop talking')] + nodes['hardship']['transitions']
for stage in ['dob','phone']:
    nodes['decline_explain_' + stage]['task_message'] = nodes['ask_' + stage]['task_message']
    nodes['id_help_' + stage]['tools'] = nodes['ask_' + stage]['tools']
    nodes['id_help_' + stage]['transitions'] = [fl.eq('refusal_' + stage,'human','id_human_' + stage,'insists')] + nodes['ask_' + stage]['transitions'][1:]
    nodes['id_help_' + stage]['task_message'] += ' If a security answer is supplied, check it with verify_identity.'
for k in ['third_party','callback_retry']:
    nodes[k]['task_message'] += ' No tool call is allowed in this turn.'
    for e in nodes[k]['extraction_schema']:
        e.setdefault('min_confidence', 0.5)
# R45 R46 apply if newly raised in hardship as well.
nodes['hardship']['transitions'] = [fl.eq('topic','already_paid','pol_paid','paid'), fl.eq('topic','dispute','pol_dispute','dispute')] + nodes['hardship']['transitions']
# R48 at opening: same human_count before and after verification.
for key, var in [('opening','who1'),('opening_retry','who2')]:
    nodes[key]['extraction_schema'][0]['enum_values'].append('human')
    nodes[key]['extraction_schema'][0]['description'] += ' human = requests a human or real person; this takes precedence over unclear.'
nodes['setup']['transitions'].insert(0,fl.eq('who1','human','opening_human','requests human'))
nodes['opening_retry']['transitions'].insert(0,fl.eq('who2','human','opening_human','requests human'))
nodes['opening_human'] = fl.code_node('opening_human',fl.counter_code('human_count',2,'human_route'),[fl.eq('human_route','close','xfer_general','insists'),fl.always('opening_human_help')])
nodes['opening_human_help'] = fl.conv('opening_human_help','Ask once whether you can help first. No tool call is allowed. If they instead confirm their name proceed to security.',on_enter={'type':'tts','text':'Can I help you first?'},extraction=[fl.ext('who2',WHO_VALUES + ['human'],WHO_DESC + ' human = requests or insists on a person.')],transitions=[fl.eq('who2','human','opening_human','insists'),fl.eq('who2','customer','ask_dob','confirmed'),fl.always('opening_retry')])
# R51: one stop-talking counter across opening, identity, policy and wrap-up.
# A refusal of security (R20) is distinct from an explicit request not to talk.
for key, var in [('setup','who1'),('opening_retry','who2'),('opening_human_help','who2')]:
    nodes[key]['transitions'] = [t for t in nodes[key]['transitions'] if not ('refuses' in str(t))]
    nodes[key]['transitions'].insert(0, fl.eq(var,'refuses','opening_notalk','stop talking'))
nodes['opening_notalk'] = fl.code_node('opening_notalk',
    fl.counter_code('notalk_count',2,'notalk_route',reset={'who1':'unclear','who2':'unclear'}),
    [fl.eq('notalk_route','close','fin_declined','second stop-talking request'),fl.always('opening_retry')])
for stage in ['dob','phone']:
    for key in ['ask_' + stage,'decline_explain_' + stage,'id_help_' + stage]:
        n = nodes[key]
        e = n['extraction_schema'][0]
        if 'no_talk' not in e['enum_values']:
            e['enum_values'].append('no_talk')
        e['description'] = ('LATEST message: no_talk = explicitly does not want to talk or wants this call to stop; '
            'refused = refuses security or asks what the call is about instead of answering; '
            'human = requests a person, never refusal; question = genuine clarification about security, robot or scam; '
            'none = answers or anything else.' + fl.REFUSAL_NONE_CLAUSE)
        n['transitions'].insert(0,fl.eq('refusal_' + stage,'no_talk','id_notalk_' + stage,'stop talking'))
    nodes['id_notalk_' + stage] = fl.code_node('id_notalk_' + stage,
        fl.counter_code('notalk_count',2,'notalk_route',reset={'refusal_dob':'none','refusal_phone':'none'}),
        [fl.eq('notalk_route','close','fin_declined','second stop-talking request'),fl.always('id_notalk_help_' + stage)])
    n = nodes['ask_' + stage]
    nodes['id_notalk_help_' + stage] = fl.conv('id_notalk_help_' + stage,n['task_message'],
        on_enter={'type':'tts','text':'I understand. This will only take a moment.'},
        tools=n['tools'],extraction=n['extraction_schema'],transitions=n['transitions'])
# R13 / R31: audit's earlier evidence strings were absent, but active routes and
# brief-sourced floor field selection remain explicit in third_party and PREPARE_BODY.
wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call], conduct=True)   # no test_variables (CLAUDE.md); conduct = how customers talk

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "out/brief-a.workflow.json"
    fl.write_workflow(wf, out)
    print("nodes:", len(nodes), "->", out)
