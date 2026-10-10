"""Generates out/brief-b.workflow.json from the rules of briefs/brief-a.md and tools/openapi.json."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = json.load(open(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/openapi.json"))
BASE = API["servers"][0]["url"].rstrip("/")
HOLIDAYS = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]  # from the brief, section 7

HEADERS = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}

STRIP_HEADER = "try:\n    if isinstance(result, dict):\n        result.pop('header', None)\nexcept Exception:\n    pass\n"


def api_tool(name, body_props, description="", required=None, retries=0, post=None, pre=None, mapping=None):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props.update(body_props)
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": f"{BASE}/{name}"},
                "method": {"type": "string", "default": "POST"},
                "headers": HEADERS,
                "body": {"type": "object", "required": required or [], "properties": props},
            }},
        },
        "post_process_code": post or STRIP_HEADER,
    }
    if pre:
        t["pre_process_code"] = pre
    if mapping:
        t["response_mapping"] = mapping
    return t


def base_node(name, node_type, **kw):
    n = {"name": name, "node_type": node_type, "transitions": [], "max_node_turns": 60,
         "truncation_strategy": "keep_all", "disable_inactivity_monitor": False}
    n.update(kw)
    return n


def conv(name, task, on_enter=None, tools=None, extraction=None, transitions=None, first_only=False):
    return base_node(name, "conversation", task_message=task, on_enter=on_enter or {"type": "llm"},
                     tools=tools or [], extraction_schema=extraction or [], transitions=transitions or [],
                     on_enter_first_entry_only=first_only)


def code_node(name, code, transitions):
    return base_node(name, "code", passthrough=True, passthrough_default_transition=transitions[-1]["target_node"],
                     on_enter={"type": "silent"}, disable_inactivity_monitor=True, pre_actions=[{
                         "type": "function",
                         "function": {"name": "code_exec", "handler": "__function__:code_exec", "parameters": {
                             "type": "object", "properties": {
                                 "code": {"type": "string", "default": code},
                                 "timeout_ms": {"type": "number", "default": 10000}}}}}],
                     transitions=transitions)


def always(t):
    return {"target_node": t, "description": "always", "condition": {"operator": "always"}}


def eq(var, val, t, desc):
    return {"target_node": t, "description": desc, "condition": {"logic": "or", "conditions": [
        {"variable": var, "operator": "equals", "operand": val}]}}


def is_true(var, t, desc):
    return {"target_node": t, "description": desc, "condition": {"logic": "or", "conditions": [
        {"variable": var, "operator": "equals", "operand": "true"},
        {"variable": var, "operator": "equals", "operand": "True"}]}}


def ext(name, values, desc, conf=0.6):
    return {"name": name, "type": "string", "enum_values": values, "description": desc, "min_confidence": conf}


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
    code = f"try:\n    vars['outcome'] = '{outcome}'\n    vars['reason'] = '{reason}'\nexcept Exception:\n    pass\n"
    nodes[f"fin_{key}"] = code_node(f"fin_{key}", code, [always(f"end_{key}")])
    nodes[f"end_{key}"] = base_node(f"end_{key}", "end_call", on_enter={"type": "silent"}, disable_inactivity_monitor=True,
                                    terminal={"type": "function", "function": {
                                        "name": f"{outcome}_{reason}" if reason else outcome,
                                        "handler": "__function__:end_call",
                                        "parameters": {"type": "object", "properties": {
                                            "message_mode": {"type": "string", "default": "custom"},
                                            "spoken_message": {"type": "string", "default": farewell}}}}})

# ---------------------------------------------------------------- setup: dates
SETUP = r'''
import datetime
try:
    HOL = set(HOLIDAYS_LIST)
    WD = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    MO = ['January','February','March','April','May','June','July','August','September','October','November','December']
    raw = str(vars.get('now') or '').strip()
    try:
        nowdt = datetime.datetime.fromisoformat(raw[:16])
    except Exception:
        nowdt = datetime.datetime.fromisoformat(raw[:10] + 'T09:00')
    today = nowdt.date()
    def isbd(d):
        return d.weekday() < 5 and d.isoformat() not in HOL
    def txt(d):
        return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month-1] + ' ' + str(d.year)
    def addbd(d, n):
        c = 0
        while c < n:
            d = d + datetime.timedelta(days=1)
            if isbd(d):
                c += 1
        return d
    nbd = addbd(today, 1)
    vars['today_iso'] = today.isoformat()
    vars['today_text'] = txt(today)
    vars['now_time'] = nowdt.strftime('%H:%M')
    lines = []
    cur = nowdt.strftime('%H:%M')
    if cur < '19:00':
        start = '10:00' if cur < '10:00' else 'after ' + cur
        lines.append('Today, ' + txt(today) + ' (' + today.isoformat() + '), from ' + start + ' up to 19:00.')
    lines.append(txt(nbd) + ' (' + nbd.isoformat() + '), from 10:00 up to 19:00 included.')
    tom = today + datetime.timedelta(days=1)
    extra = 'Tomorrow is ' + txt(tom) + '.'
    if tom != nbd:
        extra += ' Tomorrow is NOT allowed, it is not a business day.'
    vars['callback_text'] = 'The ONLY allowed callback times are:\n- ' + '\n- '.join(lines) + '\n' + extra + ' Any other day or time is outside the window.'
    # week tables
    monday = today - datetime.timedelta(days=today.weekday())
    tab = []
    for i in range(7):
        a = monday + datetime.timedelta(days=i)
        b = a + datetime.timedelta(days=7)
        t1 = '"this ' + WD[i] + '" = ' + txt(a) + (' (already past)' if a < today else '')
        tab.append(t1 + '; "next ' + WD[i] + '" = ' + txt(b))
    vars['weekday_table'] = '\n'.join(tab)
    # last business day of this week, else of next week
    def lastbd(mon):
        for k in range(4, -1, -1):
            d = mon + datetime.timedelta(days=k)
            if isbd(d):
                return d
        return None
    a1 = lastbd(monday)
    if a1 is None or a1 <= today:
        a1 = lastbd(monday + datetime.timedelta(days=7))
    vars['attempt1_date'] = a1.isoformat()
    vars['early_deadline'] = addbd(today, 12).isoformat()
    vars['late_deadline'] = addbd(today, 7).isoformat()
    vars['setup_state'] = 'ok'
except Exception as e:
    vars['setup_state'] = 'error ' + str(e)
    vars.setdefault('callback_text', 'Callbacks: today later than now up to 19:00, or the next business day from 10:00 to 19:00.')
    vars.setdefault('today_text', str(vars.get('now')))
    vars.setdefault('weekday_table', '')
'''.replace("HOLIDAYS_LIST", repr(HOLIDAYS))

PREPARE = r"""
import datetime, json, re
try:
    HOL = set(HOLIDAYS_LIST)
    WD = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    MO = ['January','February','March','April','May','June','July','August','September','October','November','December']
    def isbd(d):
        return d.weekday() < 5 and d.isoformat() not in HOL
    def txt(d):
        return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month-1]
    def fmt(x):
        try:
            x = float(x)
        except Exception:
            return str(x)
        s = '%.2f' % x
        return s[:-3] if s.endswith('.00') else s
    prods = vars.get('products')
    if isinstance(prods, str):
        try:
            prods = json.loads(prods)
        except Exception:
            prods = None
    if not isinstance(prods, list) or not prods:
        found = dict()
        for k, v in list(vars.items()):
            m = re.search(r'products\.(\d+)\.(\w+)$', str(k))
            if m:
                found.setdefault(int(m.group(1)), dict())[m.group(2)] = v
        prods = [found[i] for i in sorted(found)]
    prods = [p for p in prods if isinstance(p, dict)]
    today = datetime.date.fromisoformat(str(vars.get('today_iso')))
    a1base = datetime.date.fromisoformat(str(vars.get('attempt1_date')))
    early = datetime.date.fromisoformat(str(vars.get('early_deadline')))
    late = datetime.date.fromisoformat(str(vars.get('late_deadline')))
    infos = []
    for i, p in enumerate(prods):
        ptype = str(p.get('type') or '')
        pid = str(p.get('product_id') or ('p' + str(i + 1)))
        if ptype == 'credit_card':
            words = 'credit card ending ' + str(p.get('card_last4') or '')
            floor = p.get('minimum_payment'); floor_name = 'minimum payment'
        else:
            words = ptype.replace('_', ' ') if ptype else 'loan'
            floor = p.get('instalment_amount'); floor_name = 'instalment'
        past_due = float(p.get('past_due') or 0)
        try:
            floor = float(floor)
        except Exception:
            floor = past_due
        dl = int(float(p.get('days_late') or 0))
        if dl <= 7:
            band = 'early'; att = 1; deadline = early
        else:
            band = 'late'; att = 2; deadline = late
        a1 = a1base if a1base <= deadline else deadline
        infos.append(dict(pid=pid, words=words, past_due=past_due, floor=floor, floor_name=floor_name, dl=dl, band=band, att=att, deadline=deadline, a1=a1))
        vars['dl_' + pid] = deadline.isoformat()
        vars['pd_' + pid] = str(past_due)
    n = len(infos)
    vars['n_products'] = str(n)
    vars['pids_csv'] = ','.join(x['pid'] for x in infos)
    vars['open_pids'] = vars['pids_csv']
    vars['rec_pids'] = ''
    vars['note_log'] = ''
    vars['all_done'] = 'no'
    lines = []
    for x in infos:
        l = x['pid'] + ' = ' + x['words'] + ': full past-due amount ' + fmt(x['past_due']) + ', ' + str(x['dl']) + ' days late (' + x['band'] + ' band). '
        l += 'Floor (lowest amount allowed) ' + fmt(x['floor']) + ' (the ' + x['floor_name'] + '). '
        l += 'Deadline (latest date allowed) ' + txt(x['deadline']) + ' (' + x['deadline'].isoformat() + '). '
        l += 'Attempt 1: propose ' + fmt(x['past_due']) + ' (or the floor ' + fmt(x['floor']) + ' if the customer already said the full amount is too much) on ' + txt(x['a1']) + ' (' + x['a1'].isoformat() + '). '
        if x['att'] >= 2:
            l += 'Attempt 2: propose the floor ' + fmt(x['floor']) + ' on the deadline ' + txt(x['deadline']) + '. Persuasion attempts allowed: 2.'
        else:
            l += 'NO attempt 2: persuasion attempts allowed: 1.'
        lines.append('- ' + l)
    vars['products_text'] = '\n'.join(lines)
    if n == 1:
        x = infos[0]
        st = 'Thank you, ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + '. I am calling from the collections team about a late payment on your ' + x['words'] + '. The past-due amount is ' + fmt(x['past_due']) + ', and it is ' + str(x['dl']) + ' days late. Can you make this payment today?'
    else:
        st = 'Thank you, ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + '. I am calling from the collections team about late payments on ' + str(n) + ' of your products. '
        for x in infos:
            st += 'Your ' + x['words'] + ' has ' + fmt(x['past_due']) + ' past due, ' + str(x['dl']) + ' days late. '
        st += 'Can you pay all of them today?'
    vars['statement_text'] = st
    maxdl = max([x['deadline'] for x in infos] or [today])
    cal = []
    d = today
    while d <= maxdl + datetime.timedelta(days=10):
        nb = d
        while not isbd(nb):
            nb = nb + datetime.timedelta(days=1)
        if isbd(d):
            ok = [x['pid'] for x in infos if d <= x['deadline']]
            bad = [x['pid'] for x in infos if d > x['deadline']]
            tag = 'business day.'
            if ok:
                tag += ' Allowed for ' + ', '.join(ok) + '.'
            if bad:
                tag += ' AFTER THE DEADLINE of ' + ', '.join(bad) + ' (use that product\'s deadline instead).'
        else:
            tag = ('weekend' if d.weekday() >= 5 else 'bank holiday') + ', NOT allowed -> offer the next business day ' + txt(nb) + ' (' + nb.isoformat() + ') where it is not after the deadline.'
        cal.append(d.isoformat() + ' ' + txt(d) + ('  (today)' if d == today else '') + ': ' + tag)
        d = d + datetime.timedelta(days=1)
    vars['calendar_text'] = '\n'.join(cal)
    vars['prepare_state'] = 'ok'
except Exception as e:
    vars['prepare_state'] = 'error ' + str(e)
    vars.setdefault('products_text', 'Product data could not be prepared.')
    vars.setdefault('statement_text', 'Thank you. I am calling from the collections team about a late payment. Can you make this payment today?')
    vars.setdefault('calendar_text', '')
    vars.setdefault('pids_csv', 'p1')
    vars.setdefault('open_pids', 'p1')
    vars.setdefault('all_done', 'no')
""".replace("HOLIDAYS_LIST", repr(HOLIDAYS))

nodes["setup"] = code_node("setup", SETUP, [always("opening")])

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
    eq("who1", "customer", "ask_dob", "the customer confirmed who they are"),
    eq("who1", "deceased", "fin_deceased", "the customer has died"),
    eq("who1", "wrong_number", "fin_wrong_number", "wrong number"),
    eq("who1", "someone_else", "third_party", "someone else answered"),
    always("opening_retry"),
]
nodes["opening"] = conv(
    "opening",
    "You have just introduced yourself and asked whether you are speaking with {{title}} {{last_name}}. Do not call any tool in this turn. Do not say why you are calling.",
    on_enter={"type": "tts", "text": "Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with {{title}} {{last_name}}?"},
    extraction=[ext("who1", WHO_VALUES, WHO_DESC)], transitions=opening_tr, first_only=True)

nodes["opening_retry"] = conv(
    "opening_retry",
    "You called {{title}} {{last_name}} and asked whether you are speaking with them, but the answer did not confirm it. "
    "No tool call is allowed in this turn. Do not say why you are calling, and do not mention any account, product, debt, payment or collections.\n"
    "If the person asked a question, answer it briefly first: who you are -> you are Freya Bank's digital assistant; a robot or AI -> you are Freya Bank's digital assistant; "
    "a scam -> they can verify this call by phoning Freya Bank's customer service number; what it is about -> you can only discuss that with {{title}} {{last_name}}. "
    "If they said they do not want to talk, say you only need a moment. "
    "Then ask exactly: \"Am I speaking with {{title}} {{last_name}}?\"",
    extraction=[ext("who2", WHO_VALUES, WHO_DESC)],
    transitions=[
        eq("who2", "customer", "ask_dob", "the customer confirmed who they are"),
        eq("who2", "deceased", "fin_deceased", "the customer has died"),
        eq("who2", "wrong_number", "fin_wrong_number", "wrong number"),
        eq("who2", "someone_else", "third_party", "someone else answered"),
        eq("who2", "refuses", "fin_declined", "refuses again"),
        always("fin_unclear"),
    ])

# ---------------------------------------------------------------- third party
cb_tool = api_tool("schedule_callback", {
    "date": {"type": "string", "default": "{{date}}", "description": "Callback date as YYYY-MM-DD. Must be one of the allowed days."},
    "time": {"type": "string", "default": "{{time}}", "description": "Callback time as HH:MM, 24 hour, between 10:00 and 19:00."},
}, "Book a callback for the customer. CALL it as soon as the person names a day and time inside the allowed window.", ["date", "time"],
    post="try:\n    if isinstance(result, dict):\n        result.pop('header', None)\n        d = result.get('data')\n        if isinstance(d, dict):\n            d['what_to_do_next'] = 'Callback booked.' if d.get('ok') else 'The booking failed. Try schedule_callback once more with the same values.'\nexcept Exception:\n    pass\n")

nodes["third_party"] = conv(
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
    extraction=[ext("tp_status", ["none", "wrong_number", "deceased"],
                    "From the person's latest message: wrong_number if they say this number does not belong to the customer or they do not know the customer; deceased if they say the customer has died; otherwise none.")],
    transitions=[
        is_true("schedule_callback_response.data.ok", "fin_callback", "callback booked"),
        eq("tp_status", "deceased", "fin_deceased", "customer died"),
        eq("tp_status", "wrong_number", "fin_wrong_number", "wrong number"),
        {"target_node": "fin_no_callback", "description": "No callback can be booked: the person gave a second time outside the allowed window, or cannot say when the customer is reachable.",
         "is_tool_call": True, "condition": {"operator": "matches_intent", "description": "No callback can be booked inside the allowed window"}},
    ])

# ---------------------------------------------------------------- identity
def verify_post(question):
    return ("try:\n    if isinstance(result, dict):\n        result.pop('header', None)\n        d = result.get('data')\n        if isinstance(d, dict):\n"
            "            left = d.get('wrong_answers_left')\n"
            "            if d.get('hint') == 'day_month_swapped':\n"
            "                d['what_to_do_next'] = 'Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for example 14 March 1988.'\n"
            "            elif d.get('all_verified') is True or str(d.get('all_verified')).lower() == 'true':\n"
            "                d['what_to_do_next'] = 'Both answers are correct. Identity verified.'\n"
            "            elif d.get('verified') is True or str(d.get('verified')).lower() == 'true':\n"
            "                d['what_to_do_next'] = 'Correct. Ask the next security question.'\n"
            "            elif d.get('ok') is False or str(d.get('ok')).lower() == 'false':\n"
            f"                d['what_to_do_next'] = 'The answer could not be read. It does not count as wrong. Ask again: {question}'\n"
            "            elif str(left) == '0':\n"
            "                d['what_to_do_next'] = 'Three wrong answers. The check has ended. Say nothing about the account.'\n"
            "            else:\n"
            f"                d['what_to_do_next'] = 'Wrong answer. Tell the customer it does not match our records and ask again: {question}'\n"
            "except Exception:\n    pass\n")


transfer_general = api_tool("transfer_to_agent", {"queue": {"type": "string", "default": "general"}},
                            "Transfer the call to a human colleague. CALL it only when the customer insists on a human after you asked once whether you can help.")

ID_COMMON = ("Rules for this step:\n"
             "- Do not mention the reason for the call, collections, a debt, a payment, a product or an amount. If asked what the call is about or how much they owe, say you can explain right after the security questions.\n"
             "- If the customer refuses to answer, or asks what the call is about instead of answering: explain that these questions protect their account, and ask the question again.\n"
             "- If the customer asks for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.\n"
             "- After every tool result, speak to the customer or call the next tool. Follow what_to_do_next.")

REFUSAL_DESC = ("From the customer's LATEST message only: refused if they refuse to answer the security question, say they do not want to talk, "
                "or ask what the call is about instead of answering it. none if they give an answer or say anything else.")

nodes["ask_dob"] = conv(
    "ask_dob",
    "The person confirmed they are {{title}} {{last_name}}. You must check identity with two security questions, one at a time. Now ask the first: their date of birth.\n"
    "When they give it, call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03-05). "
    "If they give only part of the date, ask for the rest before calling the tool.\n" + ID_COMMON,
    tools=[api_tool("verify_identity", {
        "field": {"type": "string", "default": "date_of_birth"},
        "answer": {"type": "string", "default": "{{answer}}", "description": "The date of birth as YYYY-MM-DD."}},
        "Check the date of birth. CALL it every time the customer gives a full date of birth.", ["answer"],
        post=verify_post("What is your date of birth?")), transfer_general],
    extraction=[ext("refusal_dob", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        is_true("verify_identity_response.data.verified", "ask_phone", "date of birth correct"),
        {"target_node": "fin_transferred_human", "description": "transferred", "condition": {"logic": "or", "conditions": [
            {"variable": "transfer_to_agent_success_count", "operator": "greater_than", "operand": 0}]}},
        eq("refusal_dob", "refused", "count_decline_dob", "customer refused"),
    ])

nodes["ask_phone"] = conv(
    "ask_phone",
    "The date of birth was correct. Now ask the second security question: the last four digits of the phone number on file.\n"
    "When they give four digits, call verify_identity with answer = the four digits only.\n" + ID_COMMON,
    tools=[api_tool("verify_identity", {
        "field": {"type": "string", "default": "phone_last4"},
        "answer": {"type": "string", "default": "{{answer}}", "description": "Exactly four digits."}},
        "Check the last four digits of the phone number. CALL it every time the customer gives four digits.", ["answer"],
        post=verify_post("What are the last four digits of the phone number on file?")), transfer_general],
    extraction=[ext("refusal_phone", ["none", "refused"], REFUSAL_DESC)],
    transitions=[
        is_true("verify_identity_response.data.all_verified", "load_account", "identity verified"),
        eq("verify_identity_response.data.wrong_answers_left", "0", "fin_failed", "three wrong answers"),
        {"target_node": "fin_transferred_human", "description": "transferred", "condition": {"logic": "or", "conditions": [
            {"variable": "transfer_to_agent_success_count", "operator": "greater_than", "operand": 0}]}},
        eq("refusal_phone", "refused", "count_decline_phone", "customer refused"),
    ])

for stage in ["dob", "phone"]:
    code = ("try:\n    n = int(float(vars.get('decline_count') or 0)) + 1\n    vars['decline_count'] = n\n"
            "    vars['refusal_dob'] = 'none'\n    vars['refusal_phone'] = 'none'\n"
            "    vars['decline_route'] = 'close' if n >= 2 else 'retry'\nexcept Exception:\n    vars['decline_route'] = 'retry'\n")
    nodes[f"count_decline_{stage}"] = code_node(f"count_decline_{stage}", code, [
        eq("decline_route", "close", "fin_declined", "second refusal"), always(f"ask_{stage}")])

# ---------------------------------------------------------------- account
nodes["load_account"] = base_node(
    "load_account", "api_request", passthrough=True, passthrough_default_transition="prepare",
    on_enter={"type": "silent"}, disable_inactivity_monitor=True,
    pre_actions=[api_tool("get_account", {}, "Get the late products.", retries=2)],
    response_mapping=[{"path": "data.products", "variable": "products"}],
    transitions=[always("prepare")])
nodes["prepare"] = code_node("prepare", PREPARE, [always("negotiate")])


# Shared state helper for hooks: rec_pids (recorded), note_log (pid:reason), open_pids, all_done.
STATE_FN = r"""
def _getv():
    try:
        return vars
    except Exception:
        return None
def _status(V):
    pids = [x for x in str(V.get('pids_csv') or '').split(',') if x]
    rec = [x for x in str(V.get('rec_pids') or '').split(',') if x]
    notes = [x for x in str(V.get('note_log') or '').split(',') if x]
    noted = [x.split(':')[0] for x in notes]
    opn = [x for x in pids if x not in rec and x not in noted]
    V['open_pids'] = ','.join(opn)
    V['all_done'] = 'yes' if pids and not opn else 'no'
    s = 'Recorded promises: ' + (', '.join(rec) or 'none') + '. Notes: ' + (', '.join(notes) or 'none') + '. '
    if opn:
        s += 'Still open: ' + ', '.join(opn) + '. For each open product: if the customer confirmed a promise for it, call create_promise for it now; otherwise call add_note for it with the right reason. One tool call per message.'
    return s
"""

promise_pre = STATE_FN + r"""
try:
    V = _getv()
    b = config.get('body')
    if isinstance(b, dict):
        pid = str(b.get('product_id') or '').strip()
        if re.match(r'^[0-9]+$', pid):
            pid = 'p' + pid
        b['product_id'] = pid
        if 'amount' in b:
            b['amount'] = float(str(b['amount']).replace(',', '').strip())
        if 'date' in b:
            b['date'] = str(b['date']).strip()[:10]
        if V is not None:
            V['pending_pid'] = pid
            dl = str(V.get('dl_' + pid) or '')
            if dl and b.get('date') and str(b['date']) > dl:
                b['date'] = dl
            pd = V.get('pd_' + pid)
            if pd and float(b.get('amount') or 0) > float(pd):
                b['amount'] = float(pd)
except Exception:
    pass
"""
promise_pre = "import re\n" + promise_pre

promise_post = STATE_FN + r"""
try:
    V = _getv()
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        ok = isinstance(d, dict) and (d.get('ok') is True or str(d.get('ok')).lower() == 'true')
        msg = ''
        if V is not None:
            pid = str(V.get('pending_pid') or '')
            if ok and pid:
                rec = [x for x in str(V.get('rec_pids') or '').split(',') if x]
                if pid not in rec:
                    rec.append(pid)
                V['rec_pids'] = ','.join(rec)
                msg = 'The promise for ' + pid + ' is recorded. '
            elif pid:
                n = int(float(V.get('fail_' + pid) or 0)) + 1
                V['fail_' + pid] = n
                if n >= 2:
                    msg = 'NOT recorded, failed twice. Tell the customer you could not record the promise for ' + pid + ', then call add_note for ' + pid + ' with reason service_error. '
                else:
                    msg = 'NOT recorded. Do not say it is recorded. Call create_promise once more for ' + pid + ' with exactly the same values. '
            msg += _status(V)
        else:
            msg = 'The promise is recorded.' if ok else 'NOT recorded. Do not say it is recorded. Call create_promise once more with exactly the same values.'
        if isinstance(d, dict):
            d['what_to_do_next'] = msg
        else:
            result['what_to_do_next'] = msg
except Exception:
    pass
"""

note_pre = STATE_FN + r"""
try:
    V = _getv()
    b = config.get('body')
    if isinstance(b, dict):
        pid = str(b.get('product_id') or '').strip()
        if pid.isdigit():
            pid = 'p' + pid
        b['product_id'] = pid
        if V is not None:
            V['pending_note'] = pid + ':' + str(b.get('reason') or '')
except Exception:
    pass
"""

note_post = STATE_FN + r"""
try:
    V = _getv()
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        ok = isinstance(d, dict) and (d.get('ok') is True or str(d.get('ok')).lower() == 'true')
        msg = ''
        if V is not None:
            pn = str(V.get('pending_note') or '')
            if ok and pn:
                notes = [x for x in str(V.get('note_log') or '').split(',') if x]
                if pn.split(':')[0] not in [x.split(':')[0] for x in notes]:
                    notes.append(pn)
                V['note_log'] = ','.join(notes)
                msg = 'Note saved. '
            elif pn:
                msg = 'The note failed. Call add_note once more with the same values. '
            msg += _status(V)
        else:
            msg = 'Note saved.' if ok else 'The note failed. Call add_note once more.'
        if isinstance(d, dict):
            d['what_to_do_next'] = msg
        else:
            result['what_to_do_next'] = msg
except Exception:
    pass
"""

NOTE_ENUM = API["paths"]["/add_note"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["reason"]["enum"]


def promise_tool():
    return api_tool("create_promise", {
        "product_id": {"type": "string", "default": "{{product_id}}", "description": "The product id exactly as in PRODUCTS, for example p1."},
        "amount": {"type": "number", "default": "{{amount}}", "description": "The agreed amount for this product, a number like 420.5."},
        "date": {"type": "string", "default": "{{date}}", "description": "The agreed payment date for this product as YYYY-MM-DD."},
    }, "Record ONE product's payment promise. CALL it once per agreed product, only after you read back ALL agreed promises together and the customer clearly said yes.",
        ["product_id", "amount", "date"], post=promise_post, pre=promise_pre)


def note_tool():
    return api_tool("add_note", {
        "product_id": {"type": "string", "default": "{{product_id}}", "description": "The product id exactly as in PRODUCTS, for example p2."},
        "reason": {"type": "string", "default": "{{reason}}", "enum": NOTE_ENUM, "description": "Why this product has no promise. One of: " + ", ".join(NOTE_ENUM) + "."},
    }, "Record why ONE product ended without a promise. CALL it once for every product that has no recorded promise, after the promises are recorded. Never call it when the call is being transferred.",
        ["product_id", "reason"], post=note_post, pre=note_pre)


TRANSFERRED = {"target_node": "fin_transferred_human", "description": "transferred to a human", "condition": {"logic": "or", "conditions": [
    {"variable": "transfer_to_agent_success_count", "operator": "greater_than", "operand": 0}]}}
ALL_DONE = eq("all_done", "yes", "finalize", "every product has a recorded promise or a note")

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
    "8. Then, for EVERY product without a recorded promise, call add_note with its product_id and reason: refused, hardship, dispute, paid or service_error. This applies even when no product got a promise. "
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
    eq("topic", "hardship", "hardship", "hardship"),
    eq("topic", "new_plan", "xfer_restructuring", "wants a new plan"),
    {"target_node": "finalize", "description": "Every product now has a recorded promise or a note (add_note), and nothing is left to record.",
     "is_tool_call": True, "condition": {"operator": "matches_intent", "description": "Every product has a recorded promise or a note"}},
]
nodes["negotiate"] = conv(
    "negotiate", NEGOTIATE,
    on_enter={"type": "tts", "text": "{{statement_text}}"},
    first_only=True,
    tools=[promise_tool(), note_tool(), transfer_general],
    extraction=[ext("topic", ["none", "hardship", "new_plan"], TOPIC_DESC)],
    transitions=neg_tr)

nodes["hardship"] = conv(
    "hardship",
    "The customer mentioned a hardship (illness, a death in the family, or job loss). Do NOT try to persuade them and do not propose any payment.\n"
    "On your first turn here: say one short sentence of sympathy, then offer to connect them with the customer support team. Offer it only once.\n"
    "Never offer a discount, waiver, payment plan or any other term.\n"
    "If the customer themselves names a date or an amount to pay for a product, check it against PRODUCTS and the CALENDAR, read it back, and record it with create_promise after a clear yes.\n"
    "Follow what_to_do_next in every tool result. After every tool result, speak to the customer or call the next tool.\n\n" + FACTS,
    tools=[promise_tool()],
    extraction=[ext("support_choice", ["none", "accept", "decline"],
                    "Answer to the offer to connect with the customer support team, from the customer's LATEST message: accept if they want to be connected, decline if they do not want it or say no, none otherwise or if the offer has not been made yet.")],
    transitions=[
        ALL_DONE,
        eq("support_choice", "accept", "xfer_support", "accepts support"),
        eq("support_choice", "decline", "hardship_notes", "declines support"),
    ])

nodes["hardship_notes"] = conv(
    "hardship_notes",
    "The customer declined the support team. Do not persuade. Say you understand. Then call add_note with reason hardship for each product still open: {{open_pids}} (product ids from PRODUCTS), one per message. "
    "Follow what_to_do_next in every tool result.\n\n" + FACTS,
    tools=[note_tool()],
    transitions=[ALL_DONE, {"target_node": "finalize", "description": "Every product has a note or a promise.", "is_tool_call": True,
                            "condition": {"operator": "matches_intent", "description": "Every product has a note or a promise"}}])

FINALIZE = r"""
try:
    rec = [x for x in str(vars.get('rec_pids') or '').split(',') if x]
    notes = [x for x in str(vars.get('note_log') or '').split(',') if x]
    pids = [x for x in str(vars.get('pids_csv') or '').split(',') if x]
    nd = dict()
    for x in notes:
        if ':' in x:
            nd[x.split(':')[0]] = x.split(':', 1)[1]
    if rec:
        r = 'promise'
    elif nd and all(nd.get(p) == 'paid' for p in pids if p in nd) and len(nd) >= len(pids):
        r = 'paid'
    else:
        r = 'refused'
        for p in pids:
            if p in nd and nd[p] != 'paid':
                r = nd[p]
                break
        if not rec and not nd:
            try:
                if int(float(vars.get('create_promise_success_count') or 0)) > 0 and str(vars.get('create_promise_response.data.ok')).lower() == 'true':
                    r = 'promise'
            except Exception:
                pass
    vars['final_route'] = r
except Exception:
    vars['final_route'] = 'refused'
"""
nodes["finalize"] = code_node("finalize", FINALIZE, [
    eq("final_route", "promise", "fin_promise", "promise"),
    eq("final_route", "paid", "fin_paid", "paid"),
    eq("final_route", "hardship", "fin_hardship", "hardship"),
    eq("final_route", "dispute", "fin_dispute", "dispute"),
    eq("final_route", "service_error", "fin_service_error", "service error"),
    always("fin_refused")])

for q, fin, line in [("restructuring", "fin_transferred_restructuring", "I cannot set up a new plan myself, but I will transfer you to the team that can help with that."),
                     ("support", "fin_transferred_support", "I will connect you with our customer support team now.")]:
    nodes[f"xfer_{q}"] = base_node(
        f"xfer_{q}", "api_request", passthrough=True, passthrough_default_transition=fin,
        on_enter={"type": "tts", "text": line}, disable_inactivity_monitor=True,
        pre_actions=[api_tool("transfer_to_agent", {"queue": {"type": "string", "default": q}}, "Transfer.", retries=1)],
        transitions=[always(fin)])

# ---------------------------------------------------------------- close_call lifecycle
close_call = api_tool("close_call", {
    "outcome": {"type": "string", "default": "{{outcome}}",
                "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"],
                "description": "promise: a promise was recorded. paid: says already paid. transferred: handed to a person. no_promise: verified, no promise. not_verified: identity not passed. not_reached: the customer was not reached."},
    "reason": {"type": "string", "default": "{{reason}}",
               "description": "transferred: restructuring|human|support. no_promise: refused|hardship|dispute|service_error. not_verified: failed|declined. not_reached: callback|no_callback|wrong_number|deceased|unclear. Empty for promise and paid."},
}, "Record how the call ended, from the conversation.", ["outcome"],
    pre="try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        if b.get('outcome') in ('promise', 'paid') or not b.get('reason'):\n            b.pop('reason', None)\nexcept Exception:\n    pass\n")
close_call["config"]["alwaysRunsAt"] = ["end_of_call"]
del close_call["post_process_code"]

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

wf = {
    "initial_node": "setup",
    "system_prompt": SYSTEM,
    "nodes": nodes,
    "global_nodes": {},
    "tools": [close_call],
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
}


def check(o):
    if o is None:
        raise SystemExit("null in workflow")
    if isinstance(o, dict):
        for v in o.values():
            check(v)
    if isinstance(o, list):
        for v in o:
            check(v)


check(wf)
for n in nodes.values():
    for t in n.get("transitions", []):
        assert t["target_node"] in nodes, t["target_node"]
    if n["node_type"] == "code":
        c = n["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        assert "{{" not in c and "}}" not in c, n["name"]
        compile(c, n["name"], "exec")
json.dump(wf, open(ROOT / "out/brief-b.workflow.json", "w"), indent=1)
print("nodes:", len(nodes))
