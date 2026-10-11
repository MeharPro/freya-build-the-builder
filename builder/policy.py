"""policy: policy as code for the payment part of a Freya collections call (brief-agnostic).

docs/research/sota-techniques.md T1 (offer guard), T2 (counters in code), T3 (state_line first), T20 (decide in code
what the brief decides), T22 (code-built read-back) and T26 (say what was done). The model no longer decides whether
an offer is allowed, how many attempts are left, which offer comes next, whether the read-back was confirmed or what
gets written: code does, from the brief's parameters, and the model only phrases what code decided.

Architecture (one product or up to N products, the same machine):

    prepare (code: register_product per product, init_negotiation)
      └─> negotiate (conversation; on_enter tts {{say_next}}; extracts topic, stance, offer_kind/date/amount)
            ├─ topic hardship/human/no_talk/paid/dispute ─> pol_<topic> (code)         ┐
            ├─ topic new_plan                            ─> xfer_restructuring        │ every pol_* node runs the
            ├─ offer_kind exact|vague                    ─> check_offer (code)        │ same core with one event,
            ├─ stance accept                             ─> accept_offer (code)       │ writes say_next/state_line
            ├─ stance too_much                           ─> too_much (code)           │ and routes on `route`
            └─ stance refuse                             ─> count_refusal (code)      ┘
      confirm (conversation; on_enter tts {{readback_line}}; extracts confirm yes|no|change)
            ├─ yes    ─> rec_next (code) ─> record_promise (api_request create_promise, values = the read-back)
            │                               ─> rec_after (code: ok / retry once / service_error) ─> ...
            ├─ change ─> change_offer (code: the new value goes through the offer guard, read back again)
            └─ no     ─> confirm_no (code: a flat refusal of the read-back offer)
      record_note loop (api_request add_note, only when the brief uses notes) ─> wrapup | finalize
      wrapup (conversation after a recorded promise; on_enter tts {{wrap_line}}; extracts wrap)
      hardship (conversation; on_enter tts {{say_next}}; support yes/no, a named offer still goes to check_offer)
      every ending: route == 'fin' and final_route == <key> ─> fin_<key> (freyalib.end_pair)

Per-product state lives in string variables written only by code: state_<pid> (open, agreed, refused, paid,
dispute, hardship, recorded, service_error), attempts_used_<pid>, too_much_<pid>, offered_floor_<pid>,
refused_offers_<pid>, agreed_<pid>, vague_asked_<pid>, checks_<pid>, fails_<pid>, noted_<pid>. The facts per product
(words_, full_, floor_, floor_name_, deadline_, ladder_) are written by the generator's prepare code through
register_product(). Every policy node ends by rewriting state_line, offer_question and clearing the extracted
variables (so a stale extraction never routes twice).

Everything a bank decides is a parameter: the texts (finished-sentence templates with [amount] [when] [date]
[deadline] [floor] [floor_name] [full] [words] [named] [past_due] [list] placeholders), the ladder rungs per
product, the floor and deadline, whether notes are used and with which reasons, the fin key per final state, the
retry limit, the holiday calendar. Nothing in this module names a holiday, an amount, a band or an outcome.

Standard library only. Every generated snippet: no '{{' or '}}', never raises, string flags for routing.
"""
from __future__ import annotations

import json
import re

import freyalib as fl

# ----------------------------------------------------------------------------------------------- parameters
STATES = ("open", "agreed", "refused", "paid", "dispute", "hardship", "recorded", "service_error")
AMOUNT_RULES = ("full", "floor", "full_or_floor")

# Generic wording. Every generator should pass the brief's own sentences (verbatim ones above all: the
# text-message sentence after a promise, the mobile-app sentence, the hardship sympathy line).
# Texts a brief decides: the generator MUST pass them (Policy() refuses to build without them), so no other bank's
# wording can reach a hidden brief's agent. The defaults below are neutral placeholders for tests and docs only.
REQUIRED_TEXTS = ("too_much_floor", "paid", "dispute", "hardship", "wrap_change", "human_first", "notalk_first", "recorded",
                  "anything_else", "vague", "after_deadline", "weekend_or_holiday", "below_floor")
REQUIRED_TEXTS_MULTI = ("question_all", "one_by_one", "next_product", "recorded_many", "rec_failed")
DEFAULT_TEXTS = {
    "today_word": "today",
    "on_date": "on [date]",
    "question": "Can you pay [amount] [when]?",
    "question_product": "For your [words], can you pay [amount] [when]?",
    "question_all": "Can you pay all of them today?",
    "weekend_or_holiday": "[named] is not a business day. The next business day is [date].",
    "after_deadline": "The latest date I can record is [deadline].",
    "before_today": "[named] has already passed.",
    "below_floor": "I cannot record [named]. The lowest amount I can record is [floor].",
    "below_floor_again": "I cannot record [named].",
    "above_full": "The past-due amount is [full], so I can record at most [full].",
    "vague": "Which exact day would that be?",
    "vague_deadline": "The latest date I can record is [deadline].",
    "cutoff_day": "Sorry, I did not catch the day. Which day would that be?",
    "cutoff_amount": "Sorry, I did not catch the amount or day. Could you repeat it?",
    "too_much_floor": "The lowest amount I can accept is [floor], the [floor_name].",
    "exhausted": "I understand.",
    "one_by_one": "Let us go through them one by one.",
    "next_product": "Your [words] has [past_due] past due.",
    "paid": "Thank you for letting me know. I will not take a promise for your [words].",
    "dispute": "Thank you for telling me. I will not take a promise for your [words].",
    "hardship": "I am sorry to hear that.",
    "human_first": "Is there anything I can help you with myself first?",
    "notalk_first": "I understand.",
    "readback_head": "To confirm: ",
    "readback_item": "[words], [amount], [when]",
    "readback_sep": "; ",
    "own_deadline": ", which is the latest date I can record for it",
    "moved_bd": ", the next business day",
    "readback_tail": ". Do you confirm?",
    "recorded": "Your promise is recorded.",
    "recorded_many": "Your promises for [list] are recorded.",
    "rec_failed": "I could not record the promise for your [words] because of a technical problem.",
    "anything_else": "Is there anything else I can help you with?",
    "wrap_change": "A recorded promise cannot be changed on this call.",
    "and": " and ",
}
ONCE_RULE = ("\nIf state says an offer, sympathy line, or support offer was already spoken once, "
             "do not repeat it in dialogue. Answer side questions briefly, then wait for the customer's answer. "
             "A later code-built entry line may make a new permitted attempt.")

# Extraction variables every policy node clears at its end (enum ones to 'none', value ones to '').
# The platform validates every variable a code node writes against the extraction schema: a value outside an enum
# ('none' for stance/confirm/wrap) or not matching the type ('' for a date or a float) is REJECTED and the old value
# stays (event function_call_complete.validation_errors; seen on Brief A PUB-10: stale offer_date re-fired check_offer
# every turn). So a clear writes a VALID neutral value: the enum's own neutral member, a sentinel date / amount.
CLEAR_ENUMS = {"stance": "other", "offer_kind": "none", "offer_for": "none", "topic": "none", "confirm": "other",
               "confirm_affirmative": "none",
               "hs_answer": "none", "wrap": "other", "aside": "none", "offer_amount_present": "none", "offer_ref": "none"}
CLEAR_VALUES = {"offer_date": "1900-01-01", "offer_amount": "0", "offer_when": ""}
SENTINEL_YEAR = 1900
# the customer's own words for the day, resolved in code against the call's date (the platform's date extraction uses
# the real clock: 'tomorrow' arrived as a date before the call's today on Brief B PUB-12)
WHEN_DESC = ("The customer's OWN WORDS for WHEN they will pay, copied exactly as said (for example 'tomorrow', 'next Friday', "
             "'this Saturday', 'the 23rd', 'the sixth of November', 'end of the month', 'when my salary comes'). "
             "Empty when no day or period is mentioned in the latest message.")


def _tpl(s):
    """'{amount}' -> '[amount]' so that generator templates may use either form; no braces reach the code."""
    return re.sub(r"\{(\w+)\}", r"[\1]", str(s))


def _pylit(obj):
    """A Python string literal holding json.dumps(obj), with every brace escaped (\\x7b / \\x7d): the platform
    refuses '{{' / '}}' in code, and a JSON dump of nested objects ends in '}}'."""
    s = json.dumps(obj, ensure_ascii=True)
    s = s.replace("\\", "\\\\").replace("'", "\\'").replace("{", "\\x7b").replace("}", "\\x7d")
    return "'" + s + "'"


# ----------------------------------------------------------------------------------------------- the core source
_CORE = r'''
P = json.loads(__P__)
def g(V, k, d=''):
    v = V.get(k)
    if v is None:
        return d
    s = str(v)
    return d if s.lower() in ('none', 'null') and d == '' else s
def num(x, d=None):
    try:
        s = str(x).replace(',', '').strip()
        if not s or s.lower() in ('none', 'null', 'nan'):
            return d
        m = re.search(r'-?\d+(\.\d+)?', s)
        return float(m.group(0)) if m else d
    except Exception:
        return d
def pdate(x):
    s = str(x or '').strip()
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if not m or int(m.group(1)) <= 1900:   # 1900-01-01 is the 'cleared' sentinel (schema-valid date)
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except Exception:
        return None
def T(key, **kw):
    s = str(P['texts'].get(key) or '')
    for k, v in kw.items():
        s = s.replace('[' + k + ']', str(v))
    return s
def join(parts):
    return ' '.join([str(x).strip() for x in parts if str(x or '').strip()])
def pids(V):
    return [x for x in g(V, 'pids_csv').split(',') if x]
def pg(V, pid, k, d=''):
    return g(V, k + '_' + pid, d)
def pset(V, pid, k, v):
    V[k + '_' + pid] = str(v)
def today_of(V):
    d = pdate(g(V, 'today_iso')) or pdate(g(V, P['now_var']))
    return d or datetime.date(2000, 1, 1)
def when(V, d):
    if d == today_of(V):
        return T('today_word')
    return T('on_date', date=txt_short(d))
def dtext(V, d):
    return T('today_word') if d == today_of(V) else txt_short(d)
def full_of(V, pid):
    return num(pg(V, pid, 'full'), 0.0) or 0.0
def floor_of(V, pid):
    f = num(pg(V, pid, 'floor'))
    return full_of(V, pid) if f is None or f <= 0 else f
def deadline_of(V, pid):
    return pdate(pg(V, pid, 'deadline')) or today_of(V)
def state(V, pid):
    return pg(V, pid, 'state', 'open')
def multi(V):
    return bool(P['multi']) and len(pids(V)) > 1
def question(V, pid, a, d):
    key = 'question_product' if multi(V) else 'question'
    return T(key, amount=fmt(a), when=when(V, d), words=pg(V, pid, 'words'), date=txt_short(d))
def set_prop(V, pid, a, d):
    V['prop_pid'] = pid
    V['prop_amount'] = str(float(a))
    V['prop_date'] = d.isoformat()
    V['offer_question'] = question(V, pid, a, d)
def prop_of(V, pid):
    if g(V, 'prop_pid') == pid:
        a = num(g(V, 'prop_amount'))
        d = pdate(g(V, 'prop_date'))
        if a is not None and d is not None:
            return a, d
    t = today_of(V)
    return full_of(V, pid), (t if isbd(t) else next_bd(t))
def okey(a, d):
    return fmt(a) + '@' + d.isoformat()
def refused_list(V, pid):
    return [x for x in pg(V, pid, 'refused_offers').split(';') if x]
def ladder(V, pid):
    try:
        L = json.loads(pg(V, pid, 'ladder', '[]'))
        return L if isinstance(L, list) else []
    except Exception:
        return []
def rung(V, pid, i):
    r = ladder(V, pid)[i]
    rule = str(r[0])
    d = pdate(r[1]) or deadline_of(V, pid)
    if rule == 'floor':
        a = floor_of(V, pid)
    elif rule == 'full_or_floor' and pg(V, pid, 'too_much') == 'yes':
        a = floor_of(V, pid)
    else:
        a = full_of(V, pid)
    return a, d
def back_route(V):
    return 'hardship' if g(V, 'mode') == 'hardship' else 'negotiate'
def say(V, text, route=None):
    V['say_next'] = text
    V['route'] = route or back_route(V)
def register_product(V, pid, words, full, floor, floor_name, deadline, rungs):
    pid = str(pid)
    ids = pids(V)
    if pid not in ids:
        ids.append(pid)
    V['pids_csv'] = ','.join(ids)
    pset(V, pid, 'words', words)
    pset(V, pid, 'full', float(full))
    pset(V, pid, 'floor', float(floor))
    pset(V, pid, 'floor_name', floor_name)
    pset(V, pid, 'deadline', deadline.isoformat())
    lad = []
    for r in rungs:
        rd = r[1]
        if rd > deadline:
            rd = deadline
        lad.append([str(r[0]), rd.isoformat()])
    pset(V, pid, 'ladder', json.dumps(lad))
    for k, v in (('state', 'open'), ('attempts_used', '0'), ('too_much', 'no'), ('offered_floor', 'no'),
                 ('refused_offers', ''), ('agreed', ''), ('vague_asked', 'no'), ('checks', '0'), ('fails', '0'),
                 ('noted', 'no')):
        pset(V, pid, k, v)
def init_negotiation(V, statement):
    ids = pids(V)
    V['mode'] = 'negotiate'
    V['stage'] = 'all' if multi(V) else 'one'
    V['cur_pid'] = ids[0] if ids else ''
    V['human_count'] = g(V, 'human_count') or '0'
    V['notalk_count'] = g(V, 'notalk_count') or '0'
    V['wrap_count'] = '0'
    V['wrap_human'] = '0'
    V['vague_all'] = 'no'
    V['hs_offer'] = 'no'
    if ids:
        a, d = prop_of(V, ids[0])
        set_prop(V, ids[0], a, d)
    if V['stage'] == 'all':
        V['offer_question'] = T('question_all')
    V['say_next'] = statement
    V['route'] = 'negotiate'
    finish_turn(V)
def readback(V, ids):
    items = []
    for p in ids:
        parts = pg(V, p, 'agreed').split('|')
        a = num(parts[0], 0.0) if parts else 0.0
        d = pdate(parts[1]) if len(parts) > 1 else None
        tag = parts[2] if len(parts) > 2 else ''
        if d is None:
            continue
        s = T('readback_item', words=pg(V, p, 'words'), amount=fmt(a), when=when(V, d), date=txt_short(d))
        if tag == 'dl':
            s += T('own_deadline')
        elif tag == 'bd':
            s += T('moved_bd')
        items.append(s)
    return T('readback_head') + T('readback_sep').join(items) + T('readback_tail')
def start_product(V, pid, prefix):
    V['stage'] = 'one'
    V['cur_pid'] = pid
    if not ladder(V, pid):
        a, d = full_of(V, pid), deadline_of(V, pid)
    else:
        a, d = rung(V, pid, 0)
        pset(V, pid, 'attempts_used', 1)
    set_prop(V, pid, a, d)
    say(V, join([prefix, T('next_product', words=pg(V, pid, 'words'), past_due=fmt(full_of(V, pid))), V['offer_question']]), 'negotiate')
def advance(V, prefix=''):
    ids = pids(V)
    opn = [p for p in ids if state(V, p) == 'open']
    if opn and g(V, 'mode') == 'hardship':
        for p in opn:
            pset(V, p, 'state', 'hardship')
        opn = []
    if opn:
        start_product(V, opn[0], prefix)
        return
    agreed = [p for p in ids if state(V, p) == 'agreed']
    if agreed:
        V['readback_line'] = join([prefix, readback(V, agreed)])
        V['route'] = 'confirm'
        return
    note_next(V)
def agree(V, pid, a, d, tag='', move=True):
    pset(V, pid, 'state', 'agreed')
    pset(V, pid, 'agreed', str(float(a)) + '|' + d.isoformat() + '|' + tag)
    V['ok_pid'] = pid
    V['ok_amount'] = str(float(a))
    V['ok_date'] = d.isoformat()
    V['offer_verdict'] = 'ok'
    set_prop(V, pid, a, d)
    if move:
        advance(V, '')
def refuse(V, pid, prefix=''):
    if g(V, 'mode') == 'hardship':
        pset(V, pid, 'state', 'hardship')
        advance(V, '')
        return
    a0, d0 = prop_of(V, pid)
    rl = refused_list(V, pid)
    if okey(a0, d0) not in rl:
        rl.append(okey(a0, d0))
    pset(V, pid, 'refused_offers', ';'.join(rl))
    L = ladder(V, pid)
    k = int(num(pg(V, pid, 'attempts_used'), 0) or 0)
    while k < len(L):
        a, d = rung(V, pid, k)
        if okey(a, d) not in rl:
            break
        k += 1
    if k >= len(L):
        pset(V, pid, 'state', 'refused')
        V['offer_verdict'] = 'exhausted'
        advance(V, join([prefix, T('exhausted')]))
        return
    pset(V, pid, 'attempts_used', k + 1)
    set_prop(V, pid, a, d)
    V['next_offer_text'] = V['offer_question']
    say(V, join([prefix, V['offer_question']]), 'negotiate')
def too_much(V, pid, prefix=''):
    pset(V, pid, 'too_much', 'yes')
    a0, d0 = prop_of(V, pid)
    fl_ = floor_of(V, pid)
    if g(V, 'mode') != 'hardship' and pg(V, pid, 'offered_floor') != 'yes' and fl_ < a0 - 0.005:
        pset(V, pid, 'offered_floor', 'yes')
        set_prop(V, pid, fl_, d0)
        say(V, join([prefix, T('too_much_floor', floor=fmt(fl_), floor_name=pg(V, pid, 'floor_name'), words=pg(V, pid, 'words')), V['offer_question']]))
        return
    refuse(V, pid, prefix)
def check_one(V, pid, a, d, kind):
    n = int(num(pg(V, pid, 'checks'), 0) or 0) + 1
    pset(V, pid, 'checks', n)
    if n > int(P['max_checks']):
        pset(V, pid, 'state', 'hardship' if g(V, 'mode') == 'hardship' else 'refused')
        V['offer_verdict'] = 'loop_exhausted'
        advance(V, T('exhausted'))
        return
    pa, pd = prop_of(V, pid)
    t = today_of(V)
    dl = deadline_of(V, pid)
    if kind == 'vague' or (a is None and d is None):
        V['offer_verdict'] = 'vague'
        if pg(V, pid, 'vague_asked') != 'yes':
            pset(V, pid, 'vague_asked', 'yes')
            say(V, T('vague'))
            return
        set_prop(V, pid, pa, dl)
        say(V, join([T('vague_deadline', deadline=txt_short(dl), words=pg(V, pid, 'words')), V['offer_question']]))
        return
    amt = pa if a is None else a
    day = pd if d is None else d
    issues = []
    na, nd = amt, day
    if nd < t:
        issues.append(('before_today', T('before_today', named=txt_short(nd))))
        nd = t if isbd(t) else next_bd(t)
    elif nd > dl:
        issues.append(('after_deadline', T('after_deadline', deadline=txt_short(dl), named=txt_short(nd), words=pg(V, pid, 'words'))))
        nd = dl
    elif not isbd(nd):
        nb = next_bd(nd)
        if P['closed_day_move'] == 'before':
            nb = prev_bd(nd)
            if nb < t:
                nb = next_bd(nd)
        if nb > dl:
            nb = dl
        issues.append(('weekend_or_holiday', T('weekend_or_holiday', named=txt_short(nd), date=txt_short(nb))))
        nd = nb
    fl_ = floor_of(V, pid)
    full = full_of(V, pid)
    if na < fl_ - 0.005:
        if pg(V, pid, 'offered_floor') == 'yes' and g(V, 'mode') != 'hardship':
            # A newly named amount below the floor is not a refusal of the floor. Explain why that
            # amount cannot be recorded without offering the floor a second time; an explicit no
            # to the existing offer reaches the separate refusal event.
            V['offer_verdict'] = 'below_floor'
            say(V, T('below_floor_again', named=fmt(na), floor=fmt(fl_),
                     floor_name=pg(V, pid, 'floor_name'), words=pg(V, pid, 'words')))
            return
        issues.append(('below_floor', T('below_floor', named=fmt(na), floor=fmt(fl_), floor_name=pg(V, pid, 'floor_name'), words=pg(V, pid, 'words'))))
        pset(V, pid, 'offered_floor', 'yes')
        na = fl_
    elif na > full + 0.005:
        issues.append(('above_full', T('above_full', full=fmt(full), named=fmt(na), words=pg(V, pid, 'words'))))
        na = full
    if not issues:
        agree(V, pid, na, nd)
        return
    V['offer_verdict'] = issues[0][0]
    set_prop(V, pid, na, nd)
    V['offer_text'] = join([x[1] for x in issues] + [V['offer_question']])
    say(V, V['offer_text'])
def offer_target(V):
    f = g(V, 'offer_for')
    ids = pids(V)
    order = P['ordinals']
    if f in order:
        i = order.index(f)
        if i < len(ids):
            return ids[i]
    return ''
def all_offer(V, d):
    t = today_of(V)
    for p in [x for x in pids(V) if state(V, x) == 'open']:
        dd = d
        tag = ''
        dl = deadline_of(V, p)
        if dd < t:
            dd = t if isbd(t) else next_bd(t)
        if not isbd(dd):
            dd = next_bd(dd)
            tag = 'bd'
        if dd > dl:
            dd = dl
            tag = 'dl'
        agree(V, p, full_of(V, p), dd, tag, move=False)
    V['offer_verdict'] = 'ok'
    advance(V, '')
WDN = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
MON = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8,
       'september': 9, 'october': 10, 'november': 11, 'december': 12}
NUMW = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
        'nine': 9, 'ten': 10, 'fourteen': 14}
def _month_of(w):
    for k, v in MON.items():
        if w.startswith(k[:3]):
            return v
    return None
ORDW = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9,
        'tenth': 10, 'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14, 'fifteenth': 15, 'sixteenth': 16,
        'seventeenth': 17, 'eighteenth': 18, 'nineteenth': 19, 'twentieth': 20, 'thirtieth': 30}
def _ordinal_words(t):
    for tens, base in (('twenty', 20), ('thirty', 30)):
        for w, n in ORDW.items():
            if n < 10:
                t = t.replace(' %s %s ' % (tens, w), ' %dth ' % (base + n))
    for w in sorted(ORDW, key=len, reverse=True):
        t = t.replace(' %s ' % w, ' %dth ' % ORDW[w])
    return t
CARDW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
         'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
         'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30}
CARD_RX = r'((?:twenty|thirty)(?: (?:one|two|three|four|five|six|seven|eight|nine))?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)'
MON_RX = r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)'
def _cardinal_days(t):
    # A cardinal is a day only when joined to a month or to a tens word after a weekday/the.
    # A bare payment amount such as "twenty" must never be interpreted as the 20th.
    def val(s):
        return sum(CARDW.get(word, 0) for word in s.split())
    t = re.sub(r' (?:the )?' + CARD_RX + r' (?:of )?' + MON_RX + r' ',
               lambda m: ' %d %s ' % (val(m.group(1)), m.group(2)), t)
    t = re.sub(r' ' + MON_RX + r' (?:the )?' + CARD_RX + r' ',
               lambda m: ' %s %d ' % (m.group(1), val(m.group(2))), t)
    return re.sub(r' (monday|tuesday|wednesday|thursday|friday|saturday|sunday|the) (twenty|thirty) (one|two|three|four|five|six|seven|eight|nine) ',
                  lambda m: ' %s %dth ' % (m.group(1), CARDW[m.group(2)] + CARDW[m.group(3)]), t)
def cut_off(text):
    t = ' ' + re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', str(text or '').lower())).strip() + ' '
    return bool(re.search(r' (twenty|thirty) $', t))
def resolve_when(V, text):
    # (date, kind) from the customer's OWN WORDS, relative to the call's today (never the real clock: the platform's
    # date extraction resolved 'tomorrow' with the real clock). kind: 'exact' (with a date), 'vague', or 'none'.
    t = ' ' + re.sub(r'[^a-z0-9 ]', ' ', str(text or '').lower()) + ' '
    t = _cardinal_days(_ordinal_words(re.sub(r'\s+', ' ', t)))
    if not t.strip():
        return None, 'none'
    today = today_of(V)
    D = datetime.timedelta
    if re.search(r' (twenty|thirty) $', t):
        # the words stop on a bare tens word ('I can pay on the twenty'): a cut-off day, never the 20th or the 30th
        # and never the extractor's guess (Freya talkative PUB-04 recorded the 20th for 'the twenty[-third]')
        return None, 'vague'
    if ' day after tomorrow ' in t:
        return today + D(2), 'exact'
    if ' tomorrow ' in t:
        return today + D(1), 'exact'
    if re.search(r' (today|tonight|this morning|this afternoon|this evening) ', t):
        return today, 'exact'
    # "Too much for me right now" is not a promise to pay now. Require an affirmative
    # payment verb near the time phrase, and exclude a nearby negation.
    immediate = re.search(r' (pay|paying|settle|clear|transfer|send|do)( it| that| this| them| everything| all of it| the money)? (right )?(now|straight away|immediately) ', t)
    before = t[max(0, immediate.start() - 40):immediate.start()] if immediate else ''
    if immediate and not re.search(r'\b(?:can t|cannot|can not|won t|not able|unable to|not)\b(?: [a-z]+){0,4}$', before):
        return today, 'exact'
    m = re.search(r' in (\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|fourteen) (day|week|fortnight)s? ', t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMW.get(m.group(1), 1)
        n = n * (7 if m.group(2) == 'week' else 14 if m.group(2) == 'fortnight' else 1)
        return today + D(n), 'exact'
    m = re.search(r' (\d{1,2})(?:st|nd|rd|th)? (?:of )?([a-z]{3,9})(?: (\d{4}))? ', t)
    mo = _month_of(m.group(2)) if m else None
    if m and mo:
        y = int(m.group(3)) if m.group(3) else today.year
        try:
            d = datetime.date(y, mo, int(m.group(1)))
            if not m.group(3) and d < today - D(14):
                d = datetime.date(y + 1, mo, int(m.group(1)))
            return d, 'exact'
        except Exception:
            return None, 'vague'
    m = re.search(r' ([a-z]{3,9}) (?:the )?(\d{1,2})(?:st|nd|rd|th)? ', t)
    mo = _month_of(m.group(1)) if m else None
    if m and mo:
        try:
            d = datetime.date(today.year, mo, int(m.group(2)))
            if d < today - D(14):
                d = datetime.date(today.year + 1, mo, int(m.group(2)))
            return d, 'exact'
        except Exception:
            return None, 'vague'
    # a day of the month wins over a weekday said with it ('Monday the twenty-sixth' is the 26th, never the next
    # Monday): the read-back then names the date's real weekday, so a mismatch is the customer's to correct
    m = (re.search(r' (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday) (?:the )?(\d{1,2})(?:st|nd|rd|th)? ', t)
         or re.search(r' (?:the )?(\d{1,2})(?:st|nd|rd|th) ', t))
    if m:
        n = int(m.group(1))
        y, mo = today.year, today.month
        if n < today.day:
            mo += 1
            if mo > 12:
                mo, y = 1, y + 1
        try:
            return datetime.date(y, mo, n), 'exact'
        except Exception:
            return None, 'vague'
    # weekdays LAST: 'Monday the 26th' is the 26th (the number wins; PUB-07 looped on 'Monday 19 October' when the weekday matched first)
    m = re.search(r' (?:(this|next|coming|on|by) )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday) ', t)
    if m:
        wd = WDN.index(m.group(2))
        qualifier = m.group(1)
        if P.get('weekday_rule') == 'first_after' and qualifier in ('this', 'next', 'coming'):
            # In this brief mode both phrases mean the first named day strictly after today.
            delta = (wd - today.weekday()) % 7 or 7
        elif qualifier == 'next':
            delta = (7 - today.weekday()) + wd  # following calendar week
        elif qualifier == 'this':
            # A current-week day may already be past. Let the ordinary before-today guard
            # explain it rather than silently turning "this Monday" into next Monday.
            delta = wd - today.weekday()
        else:
            delta = (wd - today.weekday()) % 7
        return today + D(delta), 'exact'
    if re.search(r'(next week|week after next|end of (the )?month|end of month|this month|next month|when (my |the )?(salary|pay|wages|money)|'
                 r'after (my |the )?(pay|salary)|a few (days|weeks)|couple of (days|weeks)|soon|later|some ?time|not sure|maybe|'
                 r'next (few|couple)|beginning of|middle of|start of|mid )', t):
        return None, 'vague'
    return None, 'none'
def offer_date_of(V):
    # the customer's words first (offer_when, resolved in code); the extraction's offer_date only as a fallback and
    # never a date before the call's today
    words = g(V, 'offer_when')
    d, kind = resolve_when(V, words)
    prev = g(V, 'when_prev')
    if prev and words.strip() and (kind != 'exact' or cut_off(prev)):
        # Keep one unresolved piece, then join it exactly once with the next customer's words.
        # "thirty" + "October" and "Monday the twenty" + "sixth" must not
        # consume the vague-date retry or become a different date.
        joined, joined_kind = resolve_when(V, prev + ' ' + words)
        if joined_kind == 'exact' and joined is not None:
            d, kind = joined, joined_kind
            prior_scope = g(V, 'when_for_prev')
            if not g(V, 'offer_for') and prior_scope in ['all'] + list(P['ordinals']):
                V['offer_for'] = prior_scope
    if kind != 'exact' and words.strip():
        V['pending_when'] = words
        V['pending_offer_for'] = g(V, 'offer_for')
        V['when_cutoff'] = 'yes' if cut_off(words) else ''
    if kind == 'exact' and d is not None:
        return d, 'exact'
    if kind == 'vague':
        return None, 'vague'
    d = pdate(g(V, 'offer_date'))
    if d is not None and d < today_of(V):
        return None, 'vague'
    return d, g(V, 'offer_kind')
def offered_amount(V):
    a = num(g(V, 'offer_amount'))
    present = g(V, 'offer_amount_present')
    if present == 'yes':
        return a  # Explicit zero/negative amounts must pass through the floor guard.
    if present == 'no':
        return None
    # Compatibility with generators predating the presence field: cleared float is zero.
    return a if a is not None and a > 0 else None
def ref_amount(V, pid, a):
    # The customer may name an amount by its role rather than a number. Resolve against the
    # currently selected product, never a copied value or a different product's floor.
    if a is not None or not pid or pid not in pids(V):
        return a
    ref = g(V, 'offer_ref')
    if ref == 'floor':
        return floor_of(V, pid)
    if ref == 'full':
        return full_of(V, pid)
    return None
def cutoff_turn(V, a, d):
    # One or two neutral clarifications per call. A cut-off day is not a vague
    # period, and a day-sized amount without a day might be the first half of a date.
    used = int(num(g(V, 'cutoff_count'), 0) or 0)
    if used >= 2:
        return False
    if g(V, 'when_cutoff') == 'yes' and (a is None or abs(a - 20) < 0.005 or abs(a - 30) < 0.005):
        V['cutoff_count'] = str(used + 1)
        V['offer_verdict'] = 'cutoff'
        say(V, T('cutoff_day'))
        return True
    if a is not None and d is None and abs(a - round(a)) < 0.005 and 1 <= a <= 31:
        open_ids = [p for p in pids(V) if state(V, p) == 'open']
        cur = g(V, 'cur_pid')
        floor = floor_of(V, cur) if cur in open_ids and not (multi(V) and g(V, 'stage') == 'all') else min([floor_of(V, p) for p in open_ids] or [0.0])
        if a < floor - 0.005 and g(V, 'small_amount_asked') != 'yes':
            V['small_amount_asked'] = 'yes'
            V['cutoff_count'] = str(used + 1)
            V['offer_verdict'] = 'cutoff_amount'
            say(V, T('cutoff_amount'))
            return True
    return False
def ev_offer(V):
    kind = g(V, 'offer_kind')
    a = offered_amount(V)
    d, k2 = offer_date_of(V)
    if d is not None and k2 == 'exact' and cut_off(g(V, 'when_prev')) and a is not None and \
            abs(a - round(a)) < 0.005 and 1 <= a <= 9:
        a = None  # unit completing the prior cut-off day, not a payment amount
    if cutoff_turn(V, a, d):
        return
    if k2 in ('exact', 'vague'):
        kind = k2
    if kind == 'vague':
        d = None
    if not (multi(V) and g(V, 'stage') == 'all'):
        pid = g(V, 'cur_pid')
        a = ref_amount(V, pid, a)
        if g(V, 'stance') == 'too_much' and pid in pids(V):
            pset(V, pid, 'too_much', 'yes')
            fl_ = floor_of(V, pid)
            if a is None or abs(a - fl_) < 0.005:
                if g(V, 'mode') != 'hardship' and pg(V, pid, 'offered_floor') != 'yes' and fl_ < full_of(V, pid) - 0.005:
                    pset(V, pid, 'offered_floor', 'yes')
                    check_one(V, pid, fl_, d, kind)
                    line = T('too_much_floor', floor=fmt(fl_), floor_name=pg(V, pid, 'floor_name'),
                             words=pg(V, pid, 'words'))
                    spoken = 'readback_line' if g(V, 'route') == 'confirm' else 'say_next'
                    V[spoken] = join([line, g(V, spoken)])
                    return
    if multi(V) and g(V, 'stage') != 'all' and g(V, 'offer_for') == 'all' and d is not None and a is None and kind == 'exact':
        all_offer(V, d)
        return
    if multi(V) and g(V, 'stage') == 'all':
        tp = offer_target(V)
        if tp:
            V['stage'] = 'one'
            V['cur_pid'] = tp
            a = ref_amount(V, tp, a)
            check_one(V, tp, a, d, kind)
            return
        if g(V, 'offer_ref') in ('floor', 'full'):
            open_ids = [p for p in pids(V) if state(V, p) == 'open']
            if len(open_ids) == 1:
                V['stage'] = 'one'
                V['cur_pid'] = open_ids[0]
                check_one(V, open_ids[0], ref_amount(V, open_ids[0], a), d, kind)
            elif open_ids:
                # A reference has a different value per product; never apply one floor to all.
                start_product(V, open_ids[0], T('one_by_one'))
            return
        if kind == 'vague' or (d is None and a is None):
            V['offer_verdict'] = 'vague'
            if g(V, 'vague_all') != 'yes':
                V['vague_all'] = 'yes'
                say(V, T('vague'))
                return
            p = pids(V)[0]
            pset(V, p, 'vague_asked', 'yes')
            V['stage'] = 'one'
            V['cur_pid'] = p
            check_one(V, p, None, None, 'vague')
            return
        if d is not None and g(V, 'offer_for') == 'all':
            all_offer(V, d)
            return
        if d is not None:
            # A date by itself does not establish consent for every product.
            # Clarify one product at a time when scope was not extracted.
            start_product(V, pids(V)[0], T('one_by_one'))
            return
        p = pids(V)[0]
        V['stage'] = 'one'
        V['cur_pid'] = p
        check_one(V, p, a, None, 'exact')
        return
    check_one(V, g(V, 'cur_pid'), a, d, kind)
def ev_accept(V):
    if multi(V) and g(V, 'stage') == 'all':
        t = today_of(V)
        tp = offer_target(V)
        if tp:
            agree(V, tp, full_of(V, tp), t if isbd(t) else next_bd(t))
            return
        for p in [x for x in pids(V) if state(V, x) == 'open']:
            agree(V, p, full_of(V, p), t if isbd(t) else next_bd(t), '', move=False)
        advance(V, '')
        return
    pid = g(V, 'cur_pid')
    if state(V, pid) == 'agreed':
        pset(V, pid, 'state', 'open')
    a, d = prop_of(V, pid)
    check_one(V, pid, a, d, 'exact')
def to_one_by_one(V):
    p = pids(V)[0]
    V['stage'] = 'one'
    V['cur_pid'] = p
    return p, join([T('one_by_one'), T('next_product', words=pg(V, p, 'words'), past_due=fmt(full_of(V, p)))])
def ev_refuse(V):
    if multi(V) and g(V, 'stage') == 'all':
        p, pre = to_one_by_one(V)
        refuse(V, p, pre)
        return
    pid = g(V, 'cur_pid')
    if state(V, pid) == 'agreed':
        pset(V, pid, 'state', 'open')
    refuse(V, pid)
def ev_too_much(V):
    if multi(V) and g(V, 'stage') == 'all':
        p, pre = to_one_by_one(V)
        too_much(V, p, pre)
        return
    too_much(V, g(V, 'cur_pid'))
def targets_for_topic(V):
    tp = offer_target(V)
    if tp:
        return [tp]
    if multi(V) and g(V, 'stage') == 'all':
        return [p for p in pids(V) if state(V, p) in ('open', 'agreed')]
    return [g(V, 'cur_pid')]
def ev_settle(V, kind):
    ts = targets_for_topic(V)
    words = [pg(V, p, 'words') for p in ts]
    for p in ts:
        pset(V, p, 'state', kind)
    pre = T(kind, words=T('and').join(words)) if multi(V) else ''
    advance(V, pre)
def ev_human(V):
    c = int(num(g(V, 'human_count'), 0) or 0) + 1
    V['human_count'] = str(c)
    if c >= int(P['human_limit']):
        V['route'] = 'xfer_general'
        return
    say(V, T('human_first'))
def ev_notalk(V):
    c = int(num(g(V, 'notalk_count'), 0) or 0) + 1
    V['notalk_count'] = str(c)
    if c >= int(P['notalk_limit']):
        for p in pids(V):
            if state(V, p) in ('open', 'agreed'):
                pset(V, p, 'state', 'refused')
        advance(V, '')
        return
    say(V, join([T('notalk_first'), g(V, 'offer_question')]))
def ev_hardship(V):
    V['mode'] = 'hardship'
    hd, hk = offer_date_of(V)
    if g(V, 'offer_kind') == 'exact' or hk == 'exact' or g(V, 'offer_ref') in ('floor', 'full'):
        V['hs_offer'] = 'yes'
        V['hs_date'] = hd.isoformat() if hd is not None else ''
        V['hs_amount'] = g(V, 'offer_amount')
        V['hs_amount_present'] = g(V, 'offer_amount_present')
        V['hs_ref'] = g(V, 'offer_ref')
    say(V, T('hardship'), 'hardship')
def ev_hs_decline(V):
    if g(V, 'hs_offer') == 'yes':
        V['hs_offer'] = 'no'
        V['offer_kind'] = 'exact'
        V['offer_date'] = g(V, 'hs_date')
        V['offer_amount'] = g(V, 'hs_amount')
        V['offer_amount_present'] = g(V, 'hs_amount_present')
        V['offer_ref'] = g(V, 'hs_ref')
        ev_offer(V)
        return
    for p in pids(V):
        if state(V, p) == 'open':
            pset(V, p, 'state', 'hardship')
    advance(V, '')
def ev_hs_offer(V):
    ev_offer(V)
def ev_confirm_no(V):
    agreed = [p for p in pids(V) if state(V, p) == 'agreed']
    pid = g(V, 'cur_pid') if g(V, 'cur_pid') in agreed else (agreed[-1] if agreed else g(V, 'cur_pid'))
    V['cur_pid'] = pid
    V['stage'] = 'one'
    parts = pg(V, pid, 'agreed').split('|')
    a = num(parts[0]) if parts else None
    d = pdate(parts[1]) if len(parts) > 1 else None
    if a is not None and d is not None:
        set_prop(V, pid, a, d)
    pset(V, pid, 'state', 'open')
    refuse(V, pid)
def ev_change(V):
    agreed = [p for p in pids(V) if state(V, p) == 'agreed']
    a = offered_amount(V)
    d, k2 = offer_date_of(V)
    tp = offer_target(V)
    if tp and multi(V):
        # A correction/partial confirmation withdraws the other unrecorded
        # agreements; negotiate them again rather than silently recording them.
        for p in agreed:
            if p != tp:
                pset(V, p, 'state', 'open')
                pset(V, p, 'agreed', '')
    if not tp and multi(V) and len(agreed) > 1 and d is not None and a is None:
        for p in agreed:
            pset(V, p, 'state', 'open')
        all_offer(V, d)
        return
    pid = tp or (g(V, 'cur_pid') if g(V, 'cur_pid') in agreed else (agreed[-1] if agreed else g(V, 'cur_pid')))
    a = ref_amount(V, pid, a)
    parts = pg(V, pid, 'agreed').split('|')
    pa = num(parts[0]) if parts else None
    pd = pdate(parts[1]) if len(parts) > 1 else None
    if pa is not None and pd is not None:
        set_prop(V, pid, pa, pd)
    pset(V, pid, 'state', 'open')
    V['cur_pid'] = pid
    V['stage'] = 'one'
    pset(V, pid, 'checks', 0)
    check_one(V, pid, a, d, 'exact')
def rec_next(V):
    for p in pids(V):
        if state(V, p) == 'agreed':
            parts = pg(V, p, 'agreed').split('|')
            V['rec_pid'] = p
            V['rec_amount'] = str(num(parts[0], 0.0))
            V['rec_date'] = parts[1] if len(parts) > 1 else ''
            V['rec_ok'] = 'pending'
            V['route'] = 'record'
            return
    note_next(V)
def ev_confirm_yes(V):
    tp = offer_target(V)
    if multi(V) and tp and any(state(V, p) == 'agreed' for p in pids(V) if p != tp):
        ev_change(V)
        return
    rec_next(V)
def ev_rec_after(V):
    p = g(V, 'rec_pid')
    ok = g(V, 'rec_ok').lower() == 'true'
    if p:
        if ok:
            pset(V, p, 'state', 'recorded')
            rl = [x for x in g(V, 'recorded_pids').split(',') if x]
            if p not in rl:
                rl.append(p)
            V['recorded_pids'] = ','.join(rl)
        else:
            f = int(num(pg(V, p, 'fails'), 0) or 0) + 1
            pset(V, p, 'fails', f)
            if f < int(P['fail_max']):
                V['rec_ok'] = 'pending'
                V['route'] = 'record'
                return
            pset(V, p, 'state', 'service_error')
    rec_next(V)
def note_next(V):
    if P['notes']:
        for p in pids(V):
            st = state(V, p)
            if st in P['note_reasons'] and pg(V, p, 'noted') == 'no':
                V['note_pid'] = p
                V['note_reason'] = P['note_reasons'][st]
                V['note_ok'] = 'pending'
                V['route'] = 'note'
                return
    if [p for p in pids(V) if state(V, p) == 'recorded']:
        enter_wrapup(V)
        return
    finalize(V)
def ev_note_after(V):
    p = g(V, 'note_pid')
    if p:
        if g(V, 'note_ok').lower() == 'true':
            pset(V, p, 'noted', 'yes')
        else:
            f = int(num(pg(V, p, 'note_fails'), 0) or 0) + 1
            pset(V, p, 'note_fails', f)
            if f >= int(P['fail_max']):
                pset(V, p, 'noted', 'failed')
            else:
                V['note_ok'] = 'pending'
                V['route'] = 'note'
                return
    note_next(V)
def enter_wrapup(V):
    rec = [p for p in pids(V) if state(V, p) == 'recorded']
    bad = [p for p in pids(V) if state(V, p) == 'service_error']
    if multi(V) and (len(rec) > 1 or bad):
        line = T('recorded_many', list=T('and').join([pg(V, p, 'words') for p in rec]))
    else:
        line = T('recorded')
    parts = [line] + [T('rec_failed', words=pg(V, p, 'words')) for p in bad]
    if P['after_recorded']:
        parts.append(T('after_recorded'))
    parts.append(T('anything_else'))
    V['wrap_line'] = join(parts)
    V[P['outcome_var']] = P['promise_outcome']
    V[P['reason_var']] = ''
    V['route'] = 'wrapup'
def finalize(V):
    ids = pids(V)
    sts = [state(V, p) for p in ids]
    fk = P['fin_keys']
    if 'recorded' in sts:
        key = fk['promise']
    elif sts and all(s == 'paid' for s in sts):
        key = fk['paid']
    else:
        key = fk['default']
        for s in sts:
            if s != 'paid':
                key = fk.get(s) or fk['default']
                break
    V['final_route'] = key
    V['route'] = 'fin'
def ev_wrap_human(V):
    c = int(num(g(V, 'human_count'), 0) or 0) + 1
    V['human_count'] = str(c)
    if c >= int(P['human_limit']):
        V['route'] = 'xfer_general'
        return
    V['wrap_line'] = T('human_first')
    V['route'] = 'wrapup'
def ev_wrap_notalk(V):
    c = int(num(g(V, 'notalk_count'), 0) or 0) + 1
    V['notalk_count'] = str(c)
    if c >= int(P['notalk_limit']):
        finalize(V)  # Retain the configured outcome precedence for recorded products.
        return
    V['wrap_line'] = T('notalk_first')
    V['route'] = 'wrapup'
def ev_wrap_change(V):
    c = int(num(g(V, 'wrap_count'), 0) or 0) + 1
    V['wrap_count'] = str(c)
    if c > int(P['wrap_turns']):
        finalize(V)
        return
    V['wrap_line'] = join([T('wrap_change'), T('anything_else')])
    V['route'] = 'wrapup'
def ev_finalize(V):
    finalize(V)
def state_line(V):
    ids = pids(V)
    out = []
    cur = g(V, 'cur_pid')
    for i, p in enumerate(ids):
        st = state(V, p)
        L = ladder(V, p)
        head = ('Product ' + str(i + 1) + ' of ' + str(len(ids)) + ': ') if len(ids) > 1 else 'Product: '
        s = head + pg(V, p, 'words') + ' (id ' + p + '). Past due ' + fmt(full_of(V, p)) + ', lowest amount ' + fmt(floor_of(V, p)) + ', latest date ' + txt_short(deadline_of(V, p)) + '.'
        if st == 'open':
            rl = refused_list(V, p)
            if rl:
                s += ' Offers already refused: ' + ', '.join([x.replace('@', ' on ') for x in rl]) + ': never offer them again.'
            s += ' Persuasion attempts used: ' + pg(V, p, 'attempts_used', '0') + ' of ' + str(len(L)) + '.'
            if pg(V, p, 'offered_floor') == 'yes':
                s += ' The lowest amount was already offered once: do not offer it again yourself.'
        elif st == 'agreed':
            s += ' Agreed, not recorded yet: ' + pg(V, p, 'agreed').split('|')[0] + ' on ' + (pg(V, p, 'agreed').split('|') + ['', ''])[1] + '.'
        else:
            s += ' Settled: ' + st + '.'
        out.append(s)
    if g(V, 'mode') == 'hardship':
        out.append('The customer mentioned a hardship: make no persuasion attempt and propose nothing yourself. '
                   'The sympathy and support offer were already spoken once; do not repeat either.')
    elif g(V, 'offer_question'):
        cp = g(V, 'cur_pid')
        a = num(g(V, 'prop_amount'))
        if cp in ids and state(V, cp) == 'open' and pg(V, cp, 'offered_floor') == 'yes' and \
                a is not None and abs(a - floor_of(V, cp)) < 0.005:
            out.append('The current offer has already been spoken once. Do not repeat its amount or question; '
                       'answer a side question briefly and ask only whether they can do that.')
        else:
            out.append('Current offer, ask exactly this: "' + g(V, 'offer_question') + '"')
    rec = [p for p in ids if state(V, p) == 'recorded']
    out.append('Recorded: ' + (', '.join(rec) if rec else 'nothing yet') + '.')
    V['state_line'] = ' '.join(out)
def _clear_enums(V):
    for k, v in P['clear_enums'].items():
        V[k] = v
def _clear_values(V):
    for k, v in P['clear_values'].items():
        V[k] = v
def finish_turn(V):
    # an aside (a side question in the customer's turn: robot? scam?) is answered first, in the line the route speaks;
    # a turn that goes through code into a tts line never reaches the dialogue model, so the answer must be built here
    a = str(V.get('aside') or 'none')
    asides = P.get('asides') or {}
    if a != 'none' and a in asides:
        txt = str(asides[a].get('say') or '')
        key = {'confirm': 'readback_line', 'wrapup': 'wrap_line'}.get(str(V.get('route') or ''), 'say_next')
        line = str(V.get(key) or '')
        if txt and not line.startswith(txt):
            V[key] = (txt + ' ' + line).strip()
    _clear_enums(V)
    _clear_values(V)
    state_line(V)
def main(V, ev):
    try:
        V['policy_event'] = ev
        V['offer_verdict'] = ''
        V['when_prev'] = g(V, 'pending_when')
        V['when_for_prev'] = g(V, 'pending_offer_for')
        V['pending_when'] = ''
        V['pending_offer_for'] = ''
        V['when_cutoff'] = ''
        if ev == 'offer':
            ev_offer(V)
        elif ev == 'accept':
            ev_accept(V)
        elif ev == 'refuse':
            ev_refuse(V)
        elif ev == 'too_much':
            ev_too_much(V)
        elif ev in ('paid', 'dispute'):
            ev_settle(V, ev)
        elif ev == 'human':
            ev_human(V)
        elif ev == 'notalk':
            ev_notalk(V)
        elif ev == 'hardship':
            ev_hardship(V)
        elif ev == 'hs_decline':
            ev_hs_decline(V)
        elif ev == 'confirm_no':
            ev_confirm_no(V)
        elif ev == 'change':
            ev_change(V)
        elif ev == 'confirm_yes':
            ev_confirm_yes(V)
        elif ev == 'rec_after':
            ev_rec_after(V)
        elif ev == 'note_after':
            ev_note_after(V)
        elif ev == 'wrap_notalk':
            ev_wrap_notalk(V)
        elif ev == 'wrap_human':
            ev_wrap_human(V)
        elif ev == 'wrap_change':
            ev_wrap_change(V)
        elif ev == 'finalize':
            ev_finalize(V)
        V['policy_state'] = 'ok'
    except Exception as e:
        V['policy_state'] = 'error ' + ev + ': ' + str(e)
        if not g(V, 'route'):
            V['route'] = 'negotiate'
    try:
        finish_turn(V)
    except Exception as e:
        V['policy_state'] = 'error state_line: ' + str(e)
        V.setdefault('state_line', '')
'''

# Every variable the core writes (besides the per-product <name>_<pid> ones). Declared with vars.setdefault at the
# end of every policy node so that static checks (builder/lint.py) see who sets them; setdefault never overwrites.
WRITTEN = ("say_next", "state_line", "offer_question", "offer_text", "offer_verdict", "next_offer_text", "route",
           "final_route", "readback_line", "wrap_line", "prop_pid", "prop_amount", "prop_date", "ok_pid", "ok_amount",
           "ok_date", "rec_pid", "rec_amount", "rec_date", "rec_ok", "note_pid", "note_reason", "note_ok",
           "recorded_pids", "pids_csv", "cur_pid", "stage", "mode", "human_count", "notalk_count", "wrap_count",
           "wrap_human", "vague_all", "hs_offer", "hs_date", "hs_amount", "hs_amount_present", "hs_ref", "policy_state", "policy_event",
           "pending_when", "when_prev", "pending_offer_for", "when_for_prev", "when_cutoff", "cutoff_count", "small_amount_asked")


def _declare():
    return "".join("vars.setdefault(%r, '')\n" % k for k in WRITTEN)


# Route values the core writes, and the default node each leads to.
ROUTES = ("negotiate", "hardship", "confirm", "record", "note", "wrapup", "xfer_general", "xfer_restructuring",
          "xfer_support")
DEFAULT_TARGETS = {"negotiate": "negotiate", "hardship": "hardship", "confirm": "confirm",
                   "record": "record_promise", "note": "record_note", "wrapup": "wrapup",
                   "xfer_general": "xfer_general", "xfer_restructuring": "xfer_restructuring",
                   "xfer_support": "xfer_support"}

# Policy nodes (name -> event); each runs CAL_HELPERS + core + main(vars, event).
EVENT_NODES = {
    "check_offer": "offer", "accept_offer": "accept", "count_refusal": "refuse", "too_much": "too_much",
    "pol_paid": "paid", "pol_dispute": "dispute", "pol_human": "human", "pol_notalk": "notalk",
    "pol_hardship": "hardship", "hs_decline": "hs_decline", "confirm_no": "confirm_no", "change_offer": "change",
    "rec_next": "confirm_yes", "rec_after": "rec_after", "note_after": "note_after",
    "wrap_human": "wrap_human", "wrap_notalk": "wrap_notalk", "wrap_change": "wrap_change", "finalize": "finalize",
}


class Policy:
    """The negotiation, confirmation and recording part of a call, as code. One instance per generator.

    holidays, business_weekdays: the brief's calendar (CAL_HELPERS).
    texts: {key: template} overriding DEFAULT_TEXTS (see there; '[x]' or '{x}' placeholders).
    multi: the brief allows more than one product (stage 'all' first: one question for every product).
    notes: the brief records a note per product without a promise; note_reasons {state: API reason}.
    fin_keys: {'promise', 'paid', 'default', and per final state 'refused'/'hardship'/'dispute'/'service_error'}
        -> the generator's fin_<key> names (freyalib.end_pair keys).
    fail_max: tries in total of a write before it counts as failed (the brief's retry rule: 'try once more' = 2).
    max_checks: offer-guard loop exit per product (then the product is refused).
    human_limit / notalk_limit: on which request a human transfer / a 'does not want to talk' close happens.
    wrap_turns: how many change requests the wrap-up node answers before it closes.
    closed_day_move: 'after' (offer the next business day) or 'before'.
    ordinals: offer_for enum values naming products in get_account order.
    targets: route -> node name overrides (DEFAULT_TARGETS)."""

    def __init__(self, holidays, texts=None, multi=False, notes=False, note_reasons=None, fin_keys=None,
                 fail_max=2, max_checks=8, human_limit=2, notalk_limit=2, wrap_turns=2, closed_day_move="after",
                 business_weekdays=fl.BUSINESS_WEEKDAYS, ordinals=("first", "second", "third"), targets=None,
                 outcome_var="outcome", reason_var="reason", promise_outcome="promise", now_var="now", asides=None,
                 weekday_rule="this_week"):
        missing = [k for k in REQUIRED_TEXTS + (REQUIRED_TEXTS_MULTI if multi else ()) if k not in (texts or {})]
        if missing and not (texts or {}).get("_allow_defaults"):
            raise ValueError("Policy texts must come from the brief; missing: %s (pass texts={'_allow_defaults': True} only in tests)" % ", ".join(missing))
        t = dict(DEFAULT_TEXTS)
        for k, v in (texts or {}).items():
            t[k] = v
        t = {k: _tpl(v) for k, v in t.items()}
        t.setdefault("after_recorded", "")
        fk = {"promise": "promise", "paid": "paid", "default": "refused", "refused": "refused",
              "hardship": "hardship", "dispute": "dispute", "service_error": "service_error"}
        fk.update(fin_keys or {})
        for k, v in fk.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(v)):
                raise ValueError("fin key %r=%r must be an identifier" % (k, v))
        nr = dict(note_reasons or {})
        bad = set(nr) - set(STATES)
        if bad:
            raise ValueError("note_reasons keys must be states %s, got %s" % (STATES, sorted(bad)))
        if notes and not nr:
            raise ValueError("notes=True needs note_reasons {state: reason}")
        if closed_day_move not in ("after", "before"):
            raise ValueError("closed_day_move must be 'after' or 'before'")
        self.holidays = list(holidays or [])
        self.bwd = list(business_weekdays)
        self.multi = bool(multi)
        self.notes = bool(notes)
        self.fin_keys = fk
        self.targets = dict(DEFAULT_TARGETS)
        self.targets.update(targets or {})
        self.asides = {str(k): {"when": str(v.get("when") or ""), "say": str(v.get("say") or "")} for k, v in (asides or {}).items()}
        self.P = {"texts": t, "multi": self.multi, "notes": self.notes, "note_reasons": nr, "fin_keys": fk, "asides": self.asides, "weekday_rule": str(weekday_rule),
                  "fail_max": int(fail_max), "max_checks": int(max_checks), "human_limit": int(human_limit),
                  "notalk_limit": int(notalk_limit), "wrap_turns": int(wrap_turns),
                  "closed_day_move": closed_day_move, "ordinals": list(ordinals),
                  "clear_enums": dict(CLEAR_ENUMS), "clear_values": dict(CLEAR_VALUES),
                  "outcome_var": outcome_var, "reason_var": reason_var, "promise_outcome": promise_outcome,
                  "now_var": now_var, "after_recorded": bool(t.get("after_recorded"))}

    # ------------------------------------------------------------------ sources
    def core(self):
        """CAL_HELPERS + the policy core (functions only, nothing runs)."""
        src = fl.CAL_HELPERS(self.holidays, self.bwd, self.P.get("weekday_rule", "this_week")) + _CORE.replace("__P__", _pylit(self.P))
        if "{{" in src or "}}" in src:
            raise ValueError("policy core contains '{{' or '}}'")
        return src

    def event_code(self, event):
        """The source of a policy code node: core + main(vars, event), the whole body inside one try (a failing
        core still leaves a route and a state_line), every variable the core writes declared with setdefault."""
        body = self.core() + "\nmain(vars, %r)\n" % event + _declare()
        return ("try:\n%s\nexcept Exception as e:\n    vars['policy_state'] = 'error ' + str(e)\n"
                "    vars.setdefault('route', 'negotiate')\n    vars.setdefault('state_line', '')\n" % fl._indent(body, 4))

    def prepare_code(self, body, statement_expr, fallbacks=None, state_var="prepare_state"):
        """The prepare node: core + a guarded brief-specific `body` that reads the products (e.g. with
        freyalib.products_from_vars()), computes the brief's facts and calls, per product in get_account order,
        register_product(vars, pid, words, full, floor, floor_name, deadline_date, rungs)
        with rungs = [(amount_rule, date), ...] the brief's persuasion ladder (amount_rule in AMOUNT_RULES:
        'full_or_floor' = the floor once the customer said the full amount is too much; a rung date after the
        deadline is capped to it). Then init_negotiation(vars, <statement_expr>) with the statement of the debt
        (a Python expression over the body's names). `today` must be a datetime.date in the body."""
        fb = {"say_next": "", "state_line": "", "offer_question": "", "route": "negotiate"}
        fb.update(fallbacks or {})
        inner = self.core() + body.strip("\n") + "\ninit_negotiation(vars, %s)\n" % statement_expr + _declare()
        return fl.guarded(inner, state_var, fb)

    # ------------------------------------------------------------------ transitions
    def route_transitions(self):
        """The transitions every policy code node shares: endings first (route 'fin' + final_route), then every
        route value, then always -> negotiate."""
        trs = []
        seen = {self.fin_keys["default"]}
        for k in [self.fin_keys["promise"], self.fin_keys["paid"]] + [v for k, v in self.fin_keys.items() if k not in ("promise", "paid", "default")]:
            if k in seen:
                continue
            seen.add(k)
            trs.append(fl.tr("fin_" + k, "the call ends with %s" % k,
                             fl.and_group(fl.cond("route", "equals", "fin"), fl.cond("final_route", "equals", k))))
        # the default ending last and once: the engine merges transitions with the same target into one OR
        trs.append(fl.eq("route", "fin", "fin_" + self.fin_keys["default"], "the call ends"))
        for r in ROUTES:
            if r == "negotiate" or (r == "note" and not self.notes):
                continue
            trs.append(fl.eq("route", r, self.targets[r], "policy route %s" % r))
        trs.append(fl.always(self.targets["negotiate"]))
        return trs

    def add_event_nodes(self, nodes, names=None):
        """Adds the policy code nodes (EVENT_NODES, or the given subset) to `nodes` (note_after only with notes)."""
        for name, ev in EVENT_NODES.items():
            if (names is not None and name not in names) or (name == "note_after" and not self.notes):
                continue
            nodes[name] = fl.code_node(name, self.event_code(ev), self.route_transitions())
        return nodes

    # ------------------------------------------------------------------ helpers the task names
    def aside_extraction(self, conf=0.5):
        """The `aside` entry (only when the Policy has asides): a side question in the customer's LATEST message that
        must be answered before continuing, e.g. robot = asks whether they are talking to a robot. The generator
        supplies `when` (how to recognise it) and `say` (the brief's answer) per value; the core prefixes `say` to the
        line the route speaks (say_next / readback_line / wrap_line). Brief-agnostic."""
        if not self.asides:
            return []
        desc = ("A side question in the customer's LATEST message that must be answered before continuing: " +
                "; ".join("%s = %s" % (k, v["when"]) for k, v in self.asides.items()) +
                "; none = no such question. Pick it even when the message also contains an answer, an offer or a refusal.")
        return [fl.ext("aside", ["none"] + list(self.asides), desc, conf)]

    @staticmethod
    def amount_presence(conf=0.5):
        return fl.ext("offer_amount_present", ["none", "yes", "no"],
                      "yes = the latest message explicitly names a payment amount, INCLUDING zero or a negative "
                      "amount; no = no amount was named (a date or yes alone is not an amount); none = uncertain. "
                      "Set offer_amount to the exact named number, never substitute the current offer.", conf)

    @staticmethod
    def offer_extraction(date_desc, amount_desc, kind_desc, conf=0.5, ref_desc=None):
        """T1: offer_date (date), offer_amount (float), offer_kind (exact|vague|none)."""
        return [fl.ext("offer_kind", ["none", "exact", "vague"], kind_desc, conf),
                {"name": "offer_date", "type": "date", "description": date_desc, "min_confidence": conf},
                {"name": "offer_when", "type": "string", "description": WHEN_DESC, "min_confidence": conf},
                {"name": "offer_amount", "type": "float", "description": amount_desc, "min_confidence": conf},
                Policy.amount_presence(conf),
                fl.ext("offer_ref", ["none", "floor", "full"], ref_desc or
                       "floor = names the lowest permitted amount by reference (minimum, lowest, or the brief's name); "
                       "full = names the whole past-due amount (all of it, full amount); none = no amount reference. "
                       "Use none when the customer states a number.", conf)]

    @staticmethod
    def offer_guard_transitions():
        """offer_kind exact|vague -> check_offer (the guard), stance accept -> accept_offer (the guard on the
        current offer). Put them after the topic transitions and before the stance counter."""
        return [fl.tr("check_offer", "the customer named a date, an amount or a vague period",
                      fl.cond("offer_kind", "equals", "exact"), fl.cond("offer_kind", "equals", "vague"),
                      fl.cond("offer_ref", "equals", "floor"), fl.cond("offer_ref", "equals", "full")),
                fl.eq("stance", "accept", "accept_offer", "the customer accepted the current offer")]

    @staticmethod
    def stance_extraction(desc, conf=0.5, values=("other", "accept", "refuse", "too_much", "offer")):
        """T2: stance in {refuse, too_much, offer, accept, other}, described with the brief's own definitions."""
        return fl.ext("stance", list(values), desc, conf)

    @staticmethod
    def stance_transitions():
        return [fl.eq("stance", "too_much", "too_much", "the customer says the amount is too much"),
                fl.eq("stance", "refuse", "count_refusal", "a flat refusal or a non-answer")]

    @staticmethod
    def topic_transitions(topic_var="topic", values=None):
        """topic value -> policy node (or transfer). `values` maps topic value -> event node / target, default:
        hardship, new_plan (restructuring transfer), human, no_talk, already_paid, dispute."""
        m = {"hardship": "pol_hardship", "new_plan": "xfer_restructuring", "human": "pol_human",
             "no_talk": "pol_notalk", "already_paid": "pol_paid", "dispute": "pol_dispute"}
        if values is not None:
            m = dict(values)
        return [fl.eq(topic_var, v, t, "topic %s" % v) for v, t in m.items()]

    @staticmethod
    def state_first(task, label="STATE (decided by the system; follow it, do not recompute it)"):
        """T3: {{state_line}} FIRST in a prompt."""
        return "%s: {{state_line}}\n\n%s" % (label, task)

    def negotiate_node(self, task, extraction, transitions, name=None):
        """The negotiation conversation node: on every entry it speaks the code-built {{say_next}} (tts),
        state_line first in its prompt, no tools (every write happens in the record nodes)."""
        name = name or self.targets["negotiate"]
        extraction = [dict(e, description=e.get("description", "") + " " + self.product_scope_description())
                      if self.multi and e.get("name") == "offer_for" else e for e in extraction]
        return fl.conv(name, self.state_first(task) + ONCE_RULE, on_enter={"type": "tts", "text": "{{say_next}}"},
                       extraction=fl.with_cutoff(list(extraction) + self.aside_extraction()), transitions=transitions)

    @staticmethod
    def product_scope_description():
        return ("Identify ONLY the products the customer positively offers to pay or confirms, in account order. "
                "Ignore products mentioned in refusals, exclusions or negations. Naming one product to pay and "
                "refusing other products is the ordinal of the offered product, NEVER all. 'all' requires agreement "
                "to every product: explicitly all/everything, or an unqualified answer to the all-products question. "
                "A partial confirmation retains only the confirmed product. 'none' means no product scope is stated.")

    def confirm_node(self, task, confirm_desc, date_desc, amount_desc, topic_entry=None, topic_trs=None,
                     name=None, conf=0.5, ref_desc=None):
        """T22: the read-back. on_enter tts {{readback_line}} (built in code from the agreed values, so what the
        customer hears is what gets written). Extraction confirm in {yes, no, change, other} (+ the new date or
        amount for a change, + the topic entry). yes -> rec_next (record loop), change -> change_offer (offer
        guard, read back again), no -> confirm_no (a flat refusal of the read-back offer). No tools."""
        name = name or self.targets["confirm"]
        confirm_desc += (" An explicit unqualified 'Yes, I confirm', 'yes', or 'that is correct' in answer to "
                         "the whole read-back is yes, never other. No means the customer rejects the read-back, "
                         "not a later 'No, that's all' answer to an anything-else question.")
        if self.multi:
            confirm_desc += (" A confirmation limited to only part of the read-back, or excluding any product, "
                             "is change, not yes. Yes confirms EVERY item read back without an exclusion.")
        affirmative_desc = ("yes only for an explicit, unconditional agreement to the ENTIRE current read-back, "
                            "including 'Yes, I confirm', 'yes', or 'that is correct'. An exclusion, correction, "
                            "changed date or amount, condition, uncertainty, or refusal is none. Otherwise none.")
        if self.multi:
            affirmative_desc += " Agreement to only some products is none, even when the customer says yes."
        ext = [fl.ext("confirm", ["other", "yes", "no", "change"], confirm_desc, conf),
               fl.ext("confirm_affirmative", ["none", "yes"], affirmative_desc, conf),
               {"name": "offer_date", "type": "date", "description": date_desc, "min_confidence": conf},
               {"name": "offer_when", "type": "string", "description": WHEN_DESC, "min_confidence": conf},
               {"name": "offer_amount", "type": "float", "description": amount_desc, "min_confidence": conf},
               Policy.amount_presence(conf),
               fl.ext("offer_ref", ["none", "floor", "full"], ref_desc or
                      "floor = the lowest amount for the named product; full = its whole past-due amount; "
                      "none = no amount named by reference or a number was stated.", conf)]
        if self.multi:
            ext.append(fl.ext("offer_for", ["none", "all"] + self.P["ordinals"],
                              self.product_scope_description(), conf))
        if topic_entry:
            ext.append(topic_entry)
        # confirm routes FIRST: a read-back answer labelled both confirm=change and topic=new_plan is a change of the
        # offer, not a plan request (a different amount or date for this promise is never a restructuring transfer)
        trs = [
            fl.eq("confirm", "change", "change_offer", "the customer changes the date or the amount"),
            fl.eq("confirm", "no", "confirm_no", "the customer said no to the read-back"),
        ]
        if self.multi:
            trs += [fl.eq("offer_for", ordinal, "change_offer", "the customer confirms only one product")
                    for ordinal in self.P["ordinals"]]
        trs.append(fl.tr("rec_next", "the customer explicitly confirmed the entire read-back",
                         fl.cond("confirm", "equals", "yes"),
                         fl.cond("confirm_affirmative", "equals", "yes")))
        trs += list(topic_trs or [])
        record_guard = (" The read-back is only a proposal. After an explicit, unconditional yes to every item "
                        "read back, use the rec_next transition immediately. Do not say the payment is recorded, "
                        "scheduled, or confirmed as completed here. Only the successful create_promise result "
                        "can establish that it was recorded. If the reply is unclear, ask whether the customer "
                        "confirms the exact read-back; do not infer consent from a later goodbye.")
        return fl.conv(name, self.state_first(task) + record_guard,
                       on_enter={"type": "tts", "text": "{{readback_line}}"},
                       extraction=fl.with_cutoff(ext + self.aside_extraction(conf)), transitions=trs)

    def promise_assert_pre(self, pid_field="product_id", amount_field="amount", date_field="date"):
        """Pre hook of the record node: the body MUST equal the approved values (rec_pid, rec_amount, rec_date,
        written by code from the read-back). A mismatch is replaced by the approved value and logged in
        vars['promise_guard'] (never a silent cap to some other value)."""
        return ("try:\n"
                "    b = config.get('body')\n"
                "    if isinstance(b, dict):\n"
                "        want = [(%r, str(vars.get('rec_pid') or '')), (%r, str(vars.get('rec_amount') or '')), (%r, str(vars.get('rec_date') or '')[:10])]\n"
                "        bad = []\n"
                "        for f, w in want:\n"
                "            if not w:\n"
                "                continue\n"
                "            have = b.get(f)\n"
                "            if f == %r:\n"
                "                try:\n"
                "                    same = abs(float(str(have).replace(',', '')) - float(w)) < 0.005\n"
                "                except Exception:\n"
                "                    same = False\n"
                "                if not same:\n"
                "                    bad.append(f)\n"
                "                b[f] = float(w)\n"
                "            else:\n"
                "                if str(have or '').strip()[:10] != w:\n"
                "                    bad.append(f)\n"
                "                b[f] = w\n"
                "        vars['promise_guard'] = ('corrected ' + ','.join(bad)) if bad else 'match'\n"
                "except Exception as e:\n"
                "    try:\n"
                "        vars['promise_guard'] = 'error ' + str(e)\n"
                "    except Exception:\n"
                "        pass\n" % (pid_field, amount_field, date_field, amount_field))

    def record_nodes(self, nodes, api, promise_tool="create_promise", note_tool="add_note", ok_field="ok",
                     pid_field="product_id", amount_field="amount", date_field="date", reason_field="reason"):
        """The write nodes: record_promise (api_request; body baked from rec_pid/rec_amount/rec_date, asserted by
        promise_assert_pre; data.<ok> -> rec_ok) -> rec_after; with notes, record_note (api_request; note_pid /
        note_reason; data.<ok> -> note_ok) -> note_after. The tools' field names are checked against the API."""
        spec = fl.tool_spec(api, promise_tool)
        for f in (pid_field, amount_field, date_field):
            if f not in spec["fields"]:
                raise KeyError("%s has no field %r in the API file" % (promise_tool, f))
        tool = fl.api_tool(api, promise_tool, baked={pid_field: "{{rec_pid}}", amount_field: "{{rec_amount}}",
                                                     date_field: "{{rec_date}}"},
                           description="Record the confirmed promise of one product.",
                           pre=self.promise_assert_pre(pid_field, amount_field, date_field))
        nodes[self.targets["record"]] = fl.api_node(self.targets["record"], tool, [fl.always("rec_after")],
                                                    mapping=[{"path": "data.%s" % ok_field, "variable": "rec_ok"}])
        if self.notes:
            nspec = fl.tool_spec(api, note_tool)
            enum = nspec["fields"].get(reason_field, {}).get("enum") or []
            for st, r in self.P["note_reasons"].items():
                if enum and r not in enum:
                    raise ValueError("note reason %r (state %s) is not in the API's %s.%s enum %s" % (r, st, note_tool, reason_field, enum))
            omit = [f for f in nspec["fields"] if f not in (pid_field, reason_field, fl.CUSTOMER_ID) and f not in nspec["required"]]
            ntool = fl.api_tool(api, note_tool, baked={pid_field: "{{note_pid}}", reason_field: "{{note_reason}}"},
                                description="Record why one product has no promise.", omit=omit)
            nodes[self.targets["note"]] = fl.api_node(self.targets["note"], ntool, [fl.always("note_after")],
                                                      mapping=[{"path": "data.%s" % ok_field, "variable": "note_ok"}])
        return nodes

    def hardship_node(self, task, answer_desc, kind_desc, date_desc, amount_desc, name=None, conf=0.5, ref_desc=None):
        """Hardship (sympathy + support offer spoken from {{say_next}}, no persuasion by routing): hs_answer in
        {support_yes, support_no, accept_offer, none}; a named date or amount still goes through the offer guard
        and the read-back; support_no without a named offer closes the open products as hardship."""
        name = name or self.targets["hardship"]
        ext = [fl.ext("hs_answer", ["none", "support_yes", "support_no", "accept_offer"], answer_desc, conf)] + \
            self.offer_extraction(date_desc, amount_desc, kind_desc, conf, ref_desc)
        trs = [fl.eq("hs_answer", "support_yes", self.targets["xfer_support"], "the customer accepts the support team"),
               fl.tr("check_offer", "the customer names a date or an amount", fl.cond("offer_kind", "equals", "exact"),
                     fl.cond("offer_ref", "equals", "floor"), fl.cond("offer_ref", "equals", "full")),
               fl.eq("hs_answer", "accept_offer", "accept_offer", "the customer accepts the corrected offer"),
               fl.eq("hs_answer", "support_no", "hs_decline", "the customer declines the support team")]
        return fl.conv(name, self.state_first(task) + ONCE_RULE, on_enter={"type": "tts", "text": "{{say_next}}"},
                       extraction=fl.with_cutoff(ext + self.aside_extraction(conf)), transitions=trs)

    def wrapup_node(self, task, wrap_desc, name=None, conf=0.5, max_turns=3):
        """After a recorded promise (on_enter tts {{wrap_line}}: the recorded sentence, the brief's sentence after
        a promise, 'anything else?'). wrap in {done, human, new_plan, change, question, other}: done -> finalize
        (the promise ending), human -> wrap_human (ask once, then transfer), new_plan -> restructuring transfer,
        change -> wrap_change (the brief's sentence, promise unchanged), question -> stay (the model answers);
        max_turns turns at most, then finalize."""
        name = name or self.targets["wrapup"]
        ext = [fl.ext("wrap", ["other", "done", "human", "no_talk", "new_plan", "change", "question"],
                      wrap_desc + " no_talk = explicitly does not want to talk or asks to stop talking.", conf)]
        trs = [fl.eq("wrap", "done", "finalize", "nothing else"),
               fl.eq("wrap", "human", "wrap_human", "asks for a human"),
               fl.eq("wrap", "no_talk", "wrap_notalk", "does not want to talk"),
               fl.eq("wrap", "new_plan", self.targets["xfer_restructuring"], "asks for a new plan"),
               fl.eq("wrap", "change", "wrap_change", "asks to change or cancel the promise")]
        n = fl.conv(name, self.state_first(task), on_enter={"type": "tts", "text": "{{wrap_line}}"},
                    extraction=fl.with_cutoff(ext + self.aside_extraction(conf)), transitions=trs, max_turns=max_turns)
        n["max_turn_transition"] = "finalize"
        return n
