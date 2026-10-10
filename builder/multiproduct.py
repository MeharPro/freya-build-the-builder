"""multiproduct: brief-agnostic helpers for Freya phone agents whose customer can be late on one to three products.

It generalises the machinery the organisers' example builder added in out/gen_brief-b.py (3/3 on the Brief B
practice cases): per-product facts prepared in code, a per-product state machine kept in workflow variables by the
pre/post hooks of the promise tool and the note tool, and a finalize code node that picks the closing outcome.
builder/freyalib.py holds the platform shapes (tools, nodes, transitions, guarded code); this module only produces
Python source for hooks and code nodes, plus the finalize transitions. builder/MULTIPRODUCT.md describes the state
machine and how a generator wires it.

Everything a bank decides is a parameter: bands, floors (a product field or a formula), product wording, the
spoken statement, tool names, request/response field names, the product field names of the account tool, note
reasons and fin keys. The DEFAULTS of those parameters are the organisers' Brief A/B conventions (product_id /
past_due / days_late / type, create_promise / add_note, reason service_error, fin keys promise / paid / refused,
the A/B persuasion-ladder wording): a generator passes the hidden brief's own values, and when it passes
`api=<the loaded tool API file>` every function refuses a field name, product type or note reason that file does
not have, so a changed API fails at generation time instead of recording promises for 0.

Standard library only. Python 3.10+. `python3 builder/multiproduct.py` runs the self-test.

Variables the hooks and code nodes use (all strings, see MULTIPRODUCT.md):
    pids_csv   every product id, in get_account order, comma separated   (prepare)
    dl_<pid>   that product's deadline, YYYY-MM-DD                        (prepare; promise_pre caps the date)
    pd_<pid>   that product's past-due amount, str(float)                 (prepare; promise_pre caps the amount)
    rec_pids   ids with a recorded promise                                 (promise_post)
    note_log   "<pid>:<reason>" per noted product, comma separated         (note_post)
    open_pids  ids with neither a promise nor a note                       (prepare, _status)
    all_done   "yes" once open_pids is empty, else "no"                    (prepare, _status) -> ALL_DONE transition
    pending_pid, pending_note   what the current tool call is about        (promise_pre, note_pre)
    fail_<pid> failed promise calls for that product                       (promise_post)
    final_route  the fin key the finalize node chose                       (finalize)
"""
from __future__ import annotations

import pathlib
import re
import sys

try:
    import freyalib as fl
except ImportError:  # imported from somewhere other than builder/
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import freyalib as fl  # noqa: E402

ROUTE_VAR = "final_route"
STATE_VARS = ("pids_csv", "rec_pids", "note_log", "open_pids", "all_done", "pending_pid", "pending_note")


def _ident(name, what="name"):
    """Tool names, fin keys (node name suffixes) and variable names are spliced into the generated code and the
    workflow graph: identifiers only."""
    if not isinstance(name, str) or not re.fullmatch(r"\w+", name):
        raise ValueError("%s must be an identifier (letters, digits, _), got %r" % (what, name))
    return name


def _literal(name, what="value"):
    """Note reasons are spliced into string literals of the generated code (repr'd, or raw inside a quoted message)
    and stored in note_log as '<pid>:<reason>' comma separated: letters, digits, _ . - and spaces only."""
    if not isinstance(name, str) or not name or not re.fullmatch(r"[A-Za-z0-9_.\- ]+", name):
        raise ValueError("%s must be letters, digits, '_', '.', '-' or spaces (no quotes, commas or colons), got %r" % (what, name))
    return name


def _no_braces(code, where):
    if "{{" in code or "}}" in code:
        raise ValueError("%s: generated code contains '{{' or '}}' (check the templates)" % where)
    return code


# ----------------------------------------------------------------------------------------------- API lookups
def _json_schema(holder):
    try:
        return ((holder or {}).get("content") or {}).get("application/json", {}).get("schema") or {}
    except AttributeError:
        return {}


def _resolve(api, schema):
    """Follows '#/...' $ref pointers (components/schemas) up to ten levels; anything else gives {}."""
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema and seen < 10:
        ref = str(schema["$ref"])
        if not ref.startswith("#/"):
            return {}
        cur = api
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            cur = cur.get(part) if isinstance(cur, dict) else None
        schema = cur
        seen += 1
    return schema if isinstance(schema, dict) else {}


def note_reasons(api, note_tool="add_note", reason_field="reason"):
    """The allowed values of the note tool's reason field, read from the API file ([] when it has no enum)."""
    f = fl.tool_spec(api, note_tool)["fields"].get(reason_field)
    if f is None:
        raise ValueError("tool %r has no request field %r in the API file (fields: %s)"
                         % (note_tool, reason_field, ", ".join(fl.tool_spec(api, note_tool)["fields"])))
    return [str(x) for x in f["enum"]]


def product_fields(api, account_tool="get_account", products_field=None):
    """{field: {"type", "description", "enum"}} of ONE product as the account tool returns it: the items of its
    `products_field` array in the 200 response (None = the first array property). Raises ValueError when the API
    file describes no such array."""
    op = ((api.get("paths") or {}).get("/" + account_tool) or {}).get("post")
    if op is None:
        raise KeyError("tool %r: the API file has no POST /%s" % (account_tool, account_tool))
    schema = _resolve(api, _json_schema((op.get("responses") or {}).get("200")))
    props = schema.get("properties") or {}
    if products_field is None:
        for k, v in props.items():
            v = _resolve(api, v)
            if v.get("type") == "array" or "items" in v:
                products_field = k
                break
    arr = _resolve(api, props.get(products_field) or {}) if products_field else {}
    items = _resolve(api, arr.get("items") or {})
    out = {}
    for k, v in (items.get("properties") or {}).items():
        v = _resolve(api, v) if isinstance(v, dict) else {}
        out[str(k)] = {"type": v.get("type", "string"), "description": v.get("description", ""),
                       "enum": [str(x) for x in (v.get("enum") or [])]}
    if not out:
        raise ValueError("the API file's %s response has no product array with item properties (looked at %r; "
                         "response properties: %s)" % (account_tool, products_field, ", ".join(props) or "none"))
    return out


def _check_request_fields(api, tool, names, where):
    fields = fl.tool_spec(api, tool)["fields"]
    for what, name in names:
        if name not in fields:
            raise ValueError("%s: %s %r is not a request field of %s in the API file (fields: %s)"
                             % (where, what, name, tool, ", ".join(fields)))


def _check_response_field(api, tool, name, where):
    props = fl.tool_spec(api, tool)["response_props"]
    if props and name not in props:
        raise ValueError("%s: ok_field %r is not a response property of %s in the API file (properties: %s)"
                         % (where, name, tool, ", ".join(props)))


def _check_reasons(api, note_tool, reason_field, reasons, where):
    allowed = note_reasons(api, note_tool, reason_field)
    if not allowed:
        return
    for what, r in reasons:
        if r not in allowed:
            raise ValueError("%s: %s %r is not one of the API's %s.%s values %s"
                             % (where, what, r, note_tool, reason_field, allowed))


# ----------------------------------------------------------------------------------------------- shared state
_STATE_FN = r"""
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
        s += 'Still open: ' + ', '.join(opn) + __OPEN_TEXT__
    return s
"""


def state_fn_code(promise_tool="create_promise", note_tool="add_note", still_open_text=None):
    """Source defining, for a hook: _getv() (the `vars` dict, or None when the hook has no vars) and _status(V),
    which recomputes open_pids / all_done from pids_csv, rec_pids and note_log and returns the status sentence for
    what_to_do_next. `still_open_text` is the tail appended after 'Still open: p1, p2'."""
    _ident(promise_tool, "promise_tool")
    _ident(note_tool, "note_tool")
    if still_open_text is None:
        still_open_text = (". For each open product: if the customer confirmed a promise for it, call %s for it now; "
                           "otherwise call %s for it with the right reason. One tool call per message." % (promise_tool, note_tool))
    return _no_braces(_STATE_FN.replace("__OPEN_TEXT__", repr(str(still_open_text))), "state_fn_code")


# ----------------------------------------------------------------------------------------------- promise hooks
_PROMISE_PRE = r"""
try:
    V = _getv()
    b = config.get('body')
    if isinstance(b, dict):
        pid = str(b.get(__PID__) or '').strip()
__PREFIX_BLOCK__        b[__PID__] = pid
        if __AMOUNT__ in b:
            b[__AMOUNT__] = float(str(b[__AMOUNT__]).replace(',', '').strip())
        if __DATE__ in b:
            b[__DATE__] = str(b[__DATE__]).strip()[:10]
        if V is not None:
            V['pending_pid'] = pid
__CAP_DATE____CAP_AMOUNT____SNAP__except Exception:
    pass
"""
_SNAP = """        if b.get(__DATE__):
            import datetime
            _hol = set(__HOL__)
            _bwd = set(__BWD__)
            _d = datetime.date.fromisoformat(str(b[__DATE__])[:10])
            _g = 0
            while (_d.weekday() not in _bwd or _d.isoformat() in _hol) and _g < 30:
                _d = _d + datetime.timedelta(days=__STEP__)
                _g += 1
            b[__DATE__] = _d.isoformat()
"""
_PREFIX_BLOCK = """        if pid.isdigit():
            pid = __PREFIX__ + pid
"""
_CAP_DATE = """            dl = str(V.get('dl_' + pid) or '')
            if dl and b.get(__DATE__) and str(b[__DATE__]) > dl:
                b[__DATE__] = dl
"""
_CAP_AMOUNT = """            pd = V.get('pd_' + pid)
            if pd and float(b.get(__AMOUNT__) or 0) > float(pd):
                b[__AMOUNT__] = float(pd)
"""


def promise_pre_code(cap_to_deadline=True, cap_to_amount=True, id_prefix="p", pid_field="product_id",
                     amount_field="amount", date_field="date", promise_tool="create_promise", note_tool="add_note",
                     api=None, snap_closed=None, holidays=(), business_weekdays=fl.BUSINESS_WEEKDAYS):
    """Pre hook of the promise tool. Normalises the product id (a bare number gets `id_prefix`, so '1' -> 'p1';
    None skips it), amount -> float (commas stripped), date -> YYYY-MM-DD, remembers vars['pending_pid'], and
    with cap_to_deadline / cap_to_amount clamps the date to vars['dl_<pid>'] and the amount to vars['pd_<pid>']
    (the per-product facts the prepare node wrote), so the model can never record past a product's deadline or
    above its past-due amount. pid_field / amount_field / date_field are the promise tool's request fields; with
    `api` they are checked against the API file.
    snap_closed: None, or "before" / "after" = a date that is not a business day (a weekday outside
    `business_weekdays` or one of `holidays`) is moved to the business day before / after it, after the deadline
    cap (a safety net for the brief's closed-day rule; the read-back should already carry the moved date)."""
    if snap_closed not in (None, "before", "after"):
        raise ValueError("snap_closed must be None, 'before' or 'after'")
    _ident(promise_tool, "promise_tool")
    if api is not None:
        _check_request_fields(api, promise_tool, [("pid_field", pid_field), ("amount_field", amount_field), ("date_field", date_field)],
                              "promise_pre_code")
    code = _PROMISE_PRE
    code = code.replace("__PREFIX_BLOCK__", _PREFIX_BLOCK.replace("__PREFIX__", repr(str(id_prefix))) if id_prefix else "")
    code = code.replace("__CAP_DATE__", _CAP_DATE if cap_to_deadline else "")
    code = code.replace("__CAP_AMOUNT__", _CAP_AMOUNT if cap_to_amount else "")
    snap = ""
    if snap_closed:
        hol = sorted(set(str(h)[:10] for h in holidays or []))
        snap = (_SNAP.replace("__HOL__", repr(hol)).replace("__BWD__", repr(sorted(set(int(x) for x in business_weekdays))))
                .replace("__STEP__", "-1" if snap_closed == "before" else "1"))
    code = code.replace("__SNAP__", snap)
    code = code.replace("__PID__", repr(pid_field)).replace("__AMOUNT__", repr(amount_field)).replace("__DATE__", repr(date_field))
    return _no_braces(state_fn_code(promise_tool, note_tool) + code, "promise_pre_code")


_PROMISE_POST = r"""
try:
    V = _getv()
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        ok = isinstance(d, dict) and (d.get(__OK__) is True or str(d.get(__OK__)).lower() == 'true')
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
                if n >= __MAXF__:
                    msg = 'NOT recorded, failed __TIMES__. Tell the customer you could not record the promise for ' + pid + ', then call __NOTE__ for ' + pid + ' with reason __REASON__. '
                else:
                    msg = 'NOT recorded. Do not say it is recorded. Call __TOOL__ once more for ' + pid + ' with exactly the same values. '
            msg += _status(V)
        else:
            msg = 'The promise is recorded.' if ok else 'NOT recorded. Do not say it is recorded. Call __TOOL__ once more with exactly the same values.'
        if isinstance(d, dict):
            d['what_to_do_next'] = msg
        else:
            result['what_to_do_next'] = msg
except Exception:
    pass
"""


def promise_post_code(max_fails=2, fail_reason="service_error", promise_tool="create_promise", note_tool="add_note",
                      ok_field="ok", api=None, reason_field="reason"):
    """Post hook of the promise tool. On ok true adds pending_pid to rec_pids and says it is recorded; otherwise
    counts fail_<pid>: below `max_fails` it asks for one retry with the same values, at `max_fails` it tells the
    model to inform the customer and call the note tool with `fail_reason` (one of the API's note reasons: pass
    `api` and the value is checked against the note tool's `reason_field` enum, since the default 'service_error'
    is Brief A/B's word). Every message ends with the _status sentence (recorded / noted / still open), which
    also refreshes open_pids and all_done so the ALL_DONE transition fires in the same turn."""
    _ident(promise_tool, "promise_tool")
    _ident(note_tool, "note_tool")
    if not isinstance(fail_reason, str) or not fail_reason.strip():
        raise ValueError("fail_reason must be a nonempty API value")
    if api is not None:
        _check_reasons(api, note_tool, reason_field, [("fail_reason", fail_reason)], "promise_post_code")
        _check_response_field(api, promise_tool, ok_field, "promise_post_code")
    max_fails = int(max_fails)
    if max_fails < 1:
        raise ValueError("max_fails must be >= 1")
    times = {1: "once", 2: "twice"}.get(max_fails, "%d times" % max_fails)
    code = (_PROMISE_POST.replace("__MAXF__", str(max_fails)).replace("__TIMES__", times).replace("__NOTE__", note_tool)
            .replace("__REASON__", "' + " + repr(fail_reason) + " + '").replace("__TOOL__", promise_tool).replace("__OK__", repr(ok_field)))
    return _no_braces(state_fn_code(promise_tool, note_tool) + code, "promise_post_code")


# ----------------------------------------------------------------------------------------------- note hooks
_NOTE_PRE = r"""
try:
    V = _getv()
    b = config.get('body')
    if isinstance(b, dict):
        pid = str(b.get(__PID__) or '').strip()
__PREFIX_BLOCK__        b[__PID__] = pid
        if V is not None:
            V['pending_note'] = pid + ':' + str(b.get(__REASON__) or '')
except Exception:
    pass
"""


def note_pre_code(id_prefix="p", pid_field="product_id", reason_field="reason", promise_tool="create_promise",
                  note_tool="add_note", api=None):
    """Pre hook of the note tool: normalises the product id like promise_pre_code and remembers
    vars['pending_note'] = '<pid>:<reason>' for the post hook. With `api` the two field names are checked."""
    _ident(note_tool, "note_tool")
    if api is not None:
        _check_request_fields(api, note_tool, [("pid_field", pid_field), ("reason_field", reason_field)], "note_pre_code")
    code = _NOTE_PRE.replace("__PREFIX_BLOCK__", _PREFIX_BLOCK.replace("__PREFIX__", repr(str(id_prefix))) if id_prefix else "")
    code = code.replace("__PID__", repr(pid_field)).replace("__REASON__", repr(reason_field))
    return _no_braces(state_fn_code(promise_tool, note_tool) + code, "note_pre_code")


_NOTE_POST = r"""
try:
    V = _getv()
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        ok = isinstance(d, dict) and (d.get(__OK__) is True or str(d.get(__OK__)).lower() == 'true')
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
                msg = 'The note failed. Call __NOTE__ once more with the same values. '
            msg += _status(V)
        else:
            msg = 'Note saved.' if ok else 'The note failed. Call __NOTE__ once more.'
        if isinstance(d, dict):
            d['what_to_do_next'] = msg
        else:
            result['what_to_do_next'] = msg
except Exception:
    pass
"""


def note_post_code(promise_tool="create_promise", note_tool="add_note", ok_field="ok", api=None):
    """Post hook of the note tool: on ok true appends pending_note to note_log (one note per product), otherwise
    asks for one retry; then the _status sentence, which refreshes open_pids and all_done."""
    _ident(note_tool, "note_tool")
    if api is not None:
        _check_response_field(api, note_tool, ok_field, "note_post_code")
    code = _NOTE_POST.replace("__NOTE__", note_tool).replace("__OK__", repr(ok_field))
    return _no_braces(state_fn_code(promise_tool, note_tool) + code, "note_post_code")


# ----------------------------------------------------------------------------------------------- transitions
def all_done_tr(target="finalize", desc="every product has a recorded promise or a note"):
    """The deterministic ALL_DONE transition: vars['all_done'] == 'yes' (written by the hooks) -> `target`."""
    return fl.eq("all_done", "yes", target, desc)


def done_intent_tr(target="finalize", desc="Every product now has a recorded promise or a note, and nothing is left to record.",
                   intent_desc="Every product has a recorded promise or a note"):
    """The tool-call fallback for the same event (the model calls transition_to_<target>)."""
    return fl.intent_tool(target, desc, intent_desc)


# ----------------------------------------------------------------------------------------------- finalize
_FINALIZE = r"""
try:
    rec = [x for x in str(vars.get('rec_pids') or '').split(',') if x]
    notes = [x for x in str(vars.get('note_log') or '').split(',') if x]
    pids = [x for x in str(vars.get('pids_csv') or '').split(',') if x]
    nd = dict()
    for x in notes:
        if ':' in x:
            nd[x.split(':')[0]] = x.split(':', 1)[1]
    keys = dict(__PAIRS__)
    if rec:
        r = __PROMISE__
    elif nd and all(nd.get(p) == __PAID_REASON__ for p in pids if p in nd) and len(nd) >= len(pids):
        r = __PAID__
    else:
        r = __DEFAULT__
__PICK__        if not rec and not nd:
            try:
                if int(float(vars.get(__SC__) or 0)) > 0 and str(vars.get(__OKVAR__)).lower() == 'true':
                    r = __PROMISE__
            except Exception:
                pass
    vars[__ROUTE__] = r
except Exception:
    vars[__ROUTE__] = __DEFAULT__
"""
_PICK_PRODUCT = """        for p in pids:
            if p in nd and nd[p] != __PAID_REASON__:
                r = keys.get(nd[p], __DEFAULT__)
                break
"""
_PICK_PRECEDENCE = """        for reason, key in __PAIRS__:
            if any(nd.get(p) == reason for p in pids):
                r = key
                break
"""


def _pairs(precedence):
    if isinstance(precedence, dict):
        pairs = list(precedence.items())
    else:
        pairs = [tuple(x) for x in precedence]
    for reason, key in pairs:
        _literal(reason, "note reason")
        _ident(key, "fin key")
    return pairs


def finalize_code(precedence, promise_key="promise", paid_key="paid", default_key="refused", paid_reason=None,
                  order="product", promise_tool="create_promise", route_var=ROUTE_VAR, ok_field="ok", api=None,
                  note_tool="add_note", reason_field="reason"):
    """Source of the finalize code node: writes vars[route_var] = the fin key of the closing outcome.
    `precedence` is the ordered list of (note_reason, fin_key) pairs (or an ordered dict) for the no-promise
    endings. Rules, in this order:
      1. at least one promise recorded (rec_pids)                      -> promise_key
      2. every product noted and every note is `paid_reason`           -> paid_key  (paid_reason defaults to paid_key)
      3. otherwise the fin key of a non-paid note:
           order="product":    the first product in get_account order whose note is not paid (Brief B's rule)
           order="precedence": the first pair of `precedence` that some product carries
         an unknown reason, or no note at all, gives default_key
      4. no hook state at all (hooks had no vars): <promise_tool>_success_count > 0 and ok true -> promise_key.
    Fin keys are the generator's own node name suffixes (fin_<key>); note reasons are the API's values, and with
    `api` every reason (precedence and paid_reason) is checked against the note tool's enum.
    Route the node with finalize_transitions(...) built from the same arguments."""
    pairs = _pairs(precedence)
    for k, what in ((promise_key, "promise_key"), (paid_key, "paid_key"), (default_key, "default_key")):
        _ident(k, what)
    _ident(promise_tool, "promise_tool")
    paid_reason = paid_key if paid_reason is None else _literal(paid_reason, "paid_reason")
    if order not in ("product", "precedence"):
        raise ValueError("order must be 'product' or 'precedence'")
    if api is not None:
        _check_reasons(api, note_tool, reason_field, [("paid_reason", paid_reason)] + [("precedence reason", r) for r, _ in pairs],
                       "finalize_code")
        _check_response_field(api, promise_tool, ok_field, "finalize_code")
    pick = _PICK_PRODUCT if order == "product" else _PICK_PRECEDENCE
    code = (_FINALIZE.replace("__PICK__", pick).replace("__PAIRS__", repr(pairs)).replace("__PROMISE__", repr(promise_key))
            .replace("__PAID_REASON__", repr(paid_reason)).replace("__PAID__", repr(paid_key)).replace("__DEFAULT__", repr(default_key))
            .replace("__SC__", repr("%s_success_count" % promise_tool)).replace("__OKVAR__", repr("%s_response.data.%s" % (promise_tool, ok_field)))
            .replace("__ROUTE__", repr(route_var)))
    return _no_braces(code, "finalize_code")


def finalize_transitions(precedence, promise_key="promise", paid_key="paid", default_key="refused", route_var=ROUTE_VAR,
                         fin_prefix="fin_"):
    """The finalize node's transitions: route_var == <key> -> fin_<key> for promise_key, paid_key and every fin key
    of `precedence` (in that order, once each), then always -> fin_<default_key>."""
    pairs = _pairs(precedence)
    out, seen = [], set()
    for key in [promise_key, paid_key] + [k for _, k in pairs]:
        if key in seen or key == default_key:
            continue
        seen.add(key)
        out.append(fl.eq(route_var, key, fin_prefix + key, key.replace("_", " ")))
    out.append(fl.always(fin_prefix + default_key))
    return out


# ----------------------------------------------------------------------------------------------- per-product facts
LINE_TEMPLATE = ("{pid} = {words}: full past-due amount {past_due}, {days_late} days late ({band} band). "
                 "Floor (lowest amount allowed) {floor} (the {floor_name}). "
                 "Deadline (latest date allowed) {deadline_text} ({deadline_iso}). "
                 "Attempt 1: propose {past_due} (or the floor {floor} if the customer already said the full amount is too much) on {a1_text} ({a1_iso}). ")
ATTEMPT2_TEMPLATE = "Attempt 2: propose the floor {floor} on the deadline {deadline_text}. Persuasion attempts allowed: {attempts}."
ONE_ATTEMPT_TEMPLATE = "NO attempt 2: persuasion attempts allowed: {attempts}."
PLACEHOLDERS = ("pid", "words", "past_due", "days_late", "band", "floor", "floor_name", "deadline_text", "deadline_iso",
                "a1_text", "a1_iso", "attempts", "title", "last_name", "first_name", "n")

_FACTS_BODY = r'''
prods = [p for p in prods if isinstance(p, dict)]
today = datetime.date.fromisoformat(str(vars.get('today_iso')))
a1base = __A1BASE__
BANDS = __BANDS__
WORDS = __WORDS__
bdl = dict()
for _b in BANDS:
    if _b[3]:
        bdl[_b[0]] = datetime.date.fromisoformat(str(vars.get(_b[3])))
    else:
        bdl[_b[0]] = addbd(today, int(_b[4] or 0))
def _fill(t, d):
    return re.sub(r'\{(\w+)\}', lambda m: '' if d.get(m.group(1)) is None else str(d.get(m.group(1))), t)
infos = []
for i, p in enumerate(prods):
    ptype = str(p.get(__TYPEF__) or '')
    pid = str(p.get(__PIDF__) or (__PREFIX__ + str(i + 1)))
    f = dict(p)
    f['type_words'] = ptype.replace('_', ' ') if ptype else __UNKNOWN__
    words = ''
    for _w in WORDS:
        if _w[0] is None or ptype in _w[0]:
            words = _fill(_w[1], f)
            break
    past_due = float(p.get(__AMTF__) or 0)
    amount = past_due
    days_late = int(float(p.get(__DAYSF__) or 0))
    dl = days_late
    floor = None
    floor_name = ''
__FLOOR_CHAIN__
    try:
        floor = float(floor)
    except Exception:
        floor = past_due
    band = BANDS[-1]
    for _b in BANDS:
        if _b[1] is None or dl <= int(_b[1]):
            band = _b
            break
    deadline = bdl[band[0]]
    att = int(band[2])
    a1 = a1base if a1base is not None and a1base <= deadline else deadline
    infos.append(dict(pid=pid, words=words, past_due=past_due, floor=floor, floor_name=floor_name, dl=dl, band=band[0], att=att, deadline=deadline, a1=a1))
    vars['dl_' + pid] = deadline.isoformat()
    vars['pd_' + pid] = str(past_due)
n = len(infos)
vars['n_products'] = str(n)
vars['pids_csv'] = ','.join(x['pid'] for x in infos)
vars['open_pids'] = vars['pids_csv']
vars['rec_pids'] = ''
vars['note_log'] = ''
vars['all_done'] = 'no'
base = dict(title=str(vars.get('title') or ''), last_name=str(vars.get('last_name') or ''), first_name=str(vars.get('first_name') or ''), n=str(n))
def _facts(x):
    f = dict(base)
    f.update(x)
    f['past_due'] = fmt(x['past_due'])
    f['floor'] = fmt(x['floor'])
    f['days_late'] = str(x['dl'])
    f['deadline_text'] = txt_short(x['deadline'])
    f['deadline_iso'] = x['deadline'].isoformat()
    f['a1_text'] = txt_short(x['a1'])
    f['a1_iso'] = x['a1'].isoformat()
    f['attempts'] = str(x['att'])
    return f
lines = []
for x in infos:
    f = _facts(x)
    lines.append('- ' + _fill(__LINE__, f) + _fill(__ATT2__ if x['att'] >= 2 else __ATT1__, f))
vars['products_text'] = '\n'.join(lines)
if n == 1:
    st = _fill(__ST_ONE__, _facts(infos[0]))
else:
    st = _fill(__ST_HEAD__, base)
    for x in infos:
        st += _fill(__ST_ITEM__, _facts(x))
    st += _fill(__ST_TAIL__, base)
vars['statement_text'] = st
maxdl = max([x['deadline'] for x in infos] or [today])
cal = []
d = today
while d <= maxdl + datetime.timedelta(days=__EXTRA__):
    nb = next_bd(d)
    if isbd(d):
        ok = [x['pid'] for x in infos if d <= x['deadline']]
        bad = [x['pid'] for x in infos if d > x['deadline']]
        tag = 'business day.'
        if ok:
            tag += ' Allowed for ' + ', '.join(ok) + '.'
        if bad:
            tag += ' AFTER THE DEADLINE of ' + ', '.join(bad) + ' (use that product\'s deadline instead).'
    elif __MOVE__ == 'before':
        pb = prev_bd(d)
        tag = ('weekend' if d.weekday() not in BWD else 'closure day') + ', NOT allowed.'
        ok = [x['pid'] for x in infos if d <= x['deadline']]
        bad = [x['pid'] for x in infos if d > x['deadline']]
        if ok and pb >= today:
            tag += ' For ' + ', '.join(ok) + ': offer the business day BEFORE it, ' + txt_short(pb) + ' (' + pb.isoformat() + ').'
        elif ok:
            tag += ' For ' + ', '.join(ok) + ': no business day before it from today, ask for another day.'
        if bad:
            tag += ' AFTER THE DEADLINE of ' + ', '.join(bad) + ' (offer that product\'s deadline instead).'
    else:
        tag = ('weekend' if d.weekday() not in BWD else 'bank holiday') + ', NOT allowed -> offer the next business day ' + txt_short(nb) + ' (' + nb.isoformat() + ') where it is not after the deadline.'
    cal.append(d.isoformat() + ' ' + txt_short(d) + ('  (today)' if d == today else '') + ': ' + tag)
    d = d + datetime.timedelta(days=1)
vars['calendar_text'] = '\n'.join(cal)
'''


def _types(rule, what):
    t = rule.get("types")
    if t is None:
        return None
    if isinstance(t, str):
        t = [t]
    return [str(x) for x in t]


def _check_template(tpl, what, allowed):
    if not isinstance(tpl, str):
        raise ValueError("%s must be a string template" % what)
    if "{{" in tpl or "}}" in tpl:
        raise ValueError("%s: a template may not contain '{{' or '}}'" % what)
    bad = [m for m in re.findall(r"\{(\w+)\}", tpl) if m not in allowed]
    if bad:
        raise ValueError("%s: unknown placeholders %s (allowed: %s)" % (what, bad, ", ".join(sorted(allowed))))
    return tpl


def _floor_rows(floor_rules):
    """[(types or None, field or None, expr or None, name)] from the brief's floor rules; `field` reads the product
    field, `expr` is a Python expression over p (the product dict), amount (its past-due float), days_late (int)
    and ptype (str), plus the CAL_HELPERS functions."""
    rows = []
    for r in floor_rules:
        field, expr = r.get("field"), r.get("expr")
        if (field is None) == (expr is None):
            raise ValueError("floor rule %r needs exactly one of 'field' (a product field) or 'expr' (a Python expression)" % (r,))
        if expr is not None:
            if not isinstance(expr, str) or not expr.strip() or "\n" in expr or "{{" in expr or "}}" in expr:
                raise ValueError("floor rule 'expr' must be a one-line Python expression without '{{' / '}}', got %r" % (expr,))
            try:
                compile(expr, "<floor expr>", "eval")
            except SyntaxError as e:
                raise ValueError("floor rule 'expr' %r does not compile: %s" % (expr, e))
        rows.append((_types(r, "floor rule"), None if field is None else str(field), None if expr is None else expr.strip(), str(r["name"])))
    if not rows or rows[-1][0] is not None:
        raise ValueError("floor_rules must end with a catch-all rule (types None)")
    return rows


def _floor_chain(rows):
    """The if/elif chain (inside the per-product loop) that sets floor and floor_name from the first matching rule.
    An expression that raises leaves floor None, which the body then replaces by the past-due amount."""
    out = ["    try:"]
    for i, (types, field, expr, name) in enumerate(rows):
        cond = "True" if types is None else "ptype in %r" % (tuple(types),)
        out.append("        %s %s:" % ("if" if i == 0 else "elif", cond))
        out.append("            floor_name = %r" % name)
        out.append("            floor = %s" % ("p.get(%r)" % field if field is not None else "(%s)" % expr))
    out += ["    except Exception:", "        floor = None"]
    return "\n".join(out)


def products_facts_code(bands, floor_rules, wording, statement, attempt1_var="attempt1_date", id_prefix="p",
                        unknown_type_words="account", line_template=LINE_TEMPLATE, attempt2_template=ATTEMPT2_TEMPLATE,
                        one_attempt_template=ONE_ATTEMPT_TEMPLATE, calendar_extra_days=10, pid_field="product_id",
                        amount_field="past_due", days_late_field="days_late", type_field="type", api=None,
                        account_tool="get_account", products_field=None, closed_day_move="after"):
    """The body of the prepare code node (put it after freyalib.products_from_vars() inside guarded(), with
    CAL_HELPERS on top; prepare_code() does that). From the product list `prods` it writes, per product,
    dl_<pid> and pd_<pid>, then n_products, pids_csv, open_pids (= pids_csv), rec_pids '', note_log '',
    all_done 'no', products_text (one '- ' line per product), statement_text (the opening statement) and
    calendar_text (one tagged line per day up to the latest deadline + calendar_extra_days, saying for which
    products a business day is allowed and which are past their deadline).

    bands: ordered list of {"name", "max_days_late" (None = catch-all, the last band), "attempts",
           "deadline_var" (an ISO date variable the setup node always sets) or "deadline_bdays" (business days
           from today)}; a product takes the first band with days_late <= max_days_late.
    floor_rules: ordered list of {"types": [product types] or None (any), "name": its words, and EITHER "field":
           the product field holding the floor OR "expr": a one-line Python expression over p (the product dict),
           amount (the past-due float), days_late (int), ptype (str) and the CAL_HELPERS functions, e.g.
           "min(2 * float(p.get('minimum_payment') or 0), amount)" or "min(-(-amount * 0.25 // 10) * 10, amount)"};
           no usable floor (missing field, an expression that raises or is not a number) -> the past-due amount.
    wording: ordered list of {"types": [...] or None, "template": "credit card ending {card_last4}"}; placeholders
           are the product's fields plus {type_words} (the type with '_' -> ' ', or `unknown_type_words`).
    statement: {"one": template for a single product, "many_head", "many_item" (per product), "many_tail"};
           placeholders: PLACEHOLDERS ({title}, {last_name}, {first_name}, {n} and the per-product facts).
    attempt1_var: the ISO variable with the attempt-1 date (capped at the product's deadline); None -> the deadline.
    line_template / attempt2_template / one_attempt_template: the products_text wording (per-product facts
           line, then the ladder sentence for 2+ attempts or for 1); the defaults are the organisers' wording of
           the Brief A/B ladder: override them when the brief's ladder differs.
    pid_field / amount_field / days_late_field / type_field: the names of the product's id, past-due amount,
           days-late and product-type fields AS THE ACCOUNT TOOL RETURNS THEM (defaults: Brief A/B's product_id,
           past_due, days_late, type; type_field None = the products have no type). A missing amount field reads
           as 0, so pass `api` (the loaded API file): then these names, every floor rule's field (and the
           p.get('..') / p['..'] fields of an expr), the `types` lists (against the type field's enum) and the
           wording placeholders are checked against the product schema of `account_tool`'s response
           (`products_field` None = its first array property) and a wrong name fails here, not on the call.
    closed_day_move: what the calendar offers for a weekend or closure day the customer names: "after" = the next
           business day (Brief A/B), "before" = the business day before it (a brief whose payments on a closed
           day would be late, so the promise moves back); needs prev_bd from CAL_HELPERS."""
    if closed_day_move not in ("after", "before"):
        raise ValueError("closed_day_move must be 'after' or 'before'")
    if not bands:
        raise ValueError("bands must list at least one band")
    band_rows = []
    for b in bands:
        name = str(b["name"])
        mx = b.get("max_days_late")
        mx = None if mx is None else int(mx)
        att = int(b.get("attempts", 1))
        dvar = b.get("deadline_var")
        dbd = b.get("deadline_bdays")
        if not dvar and dbd is None:
            raise ValueError("band %r needs deadline_var or deadline_bdays" % name)
        band_rows.append((name, mx, att, str(dvar) if dvar else "", None if dbd is None else int(dbd)))
    if band_rows[-1][1] is not None:
        raise ValueError("the last band must have max_days_late None (it catches every later product)")
    floor_rows = _floor_rows(floor_rules)
    word_rows = [(_types(r, "wording"), str(r["template"])) for r in wording]
    if not word_rows or word_rows[-1][0] is not None:
        raise ValueError("wording must end with a catch-all rule (types None)")
    for _, tpl in word_rows:
        if "{{" in tpl or "}}" in tpl:
            raise ValueError("wording template may not contain '{{' or '}}'")
    for what, name in (("pid_field", pid_field), ("amount_field", amount_field), ("days_late_field", days_late_field)):
        if not isinstance(name, str) or not name:
            raise ValueError("%s must be a product field name, got %r" % (what, name))
    if type_field is not None and (not isinstance(type_field, str) or not type_field):
        raise ValueError("type_field must be a product field name or None, got %r" % (type_field,))
    if api is not None:
        pf = product_fields(api, account_tool, products_field)
        names = [("pid_field", pid_field), ("amount_field", amount_field), ("days_late_field", days_late_field)]
        if type_field is not None:
            names.append(("type_field", type_field))
        for types, field, expr, name in floor_rows:
            if field is not None:
                names.append(("floor rule %r field" % name, field))
            else:
                for m in re.findall(r"p\s*(?:\.get\(|\[)\s*['\"](\w+)['\"]", expr):
                    names.append(("floor rule %r expr field" % name, m))
        for _, tpl in word_rows:
            for m in re.findall(r"\{(\w+)\}", tpl):
                if m != "type_words":
                    names.append(("wording placeholder", m))
        for what, name in names:
            if name not in pf:
                raise ValueError("%s %r is not a product field of %s in the API file (fields: %s)"
                                 % (what, name, account_tool, ", ".join(pf)))
        enum = pf[type_field]["enum"] if type_field is not None else []
        if enum:
            for types in [r[0] for r in floor_rows] + [r[0] for r in word_rows]:
                for t in types or []:
                    if t not in enum:
                        raise ValueError("product type %r is not in the API's %s.%s enum %s" % (t, account_tool, type_field, enum))
    allowed = set(PLACEHOLDERS)
    st = {k: _check_template(statement[k], "statement[%r]" % k, allowed) for k in ("one", "many_head", "many_item", "many_tail")}
    line = _check_template(line_template, "line_template", allowed)
    att2 = _check_template(attempt2_template, "attempt2_template", allowed)
    att1 = _check_template(one_attempt_template, "one_attempt_template", allowed)
    a1 = "datetime.date.fromisoformat(str(vars.get(%r)))" % str(attempt1_var) if attempt1_var else "None"
    code = (_FACTS_BODY.replace("__A1BASE__", a1).replace("__BANDS__", repr(band_rows)).replace("__FLOOR_CHAIN__", _floor_chain(floor_rows))
            .replace("__WORDS__", repr(word_rows)).replace("__PREFIX__", repr(str(id_prefix or "")))
            .replace("__UNKNOWN__", repr(str(unknown_type_words))).replace("__LINE__", repr(line)).replace("__ATT2__", repr(att2))
            .replace("__ATT1__", repr(att1)).replace("__ST_ONE__", repr(st["one"])).replace("__ST_HEAD__", repr(st["many_head"]))
            .replace("__ST_ITEM__", repr(st["many_item"])).replace("__ST_TAIL__", repr(st["many_tail"]))
            .replace("__EXTRA__", str(int(calendar_extra_days))).replace("__PIDF__", repr(pid_field)).replace("__AMTF__", repr(amount_field))
            .replace("__DAYSF__", repr(days_late_field)).replace("__TYPEF__", repr(type_field))
            .replace("__MOVE__", repr(closed_day_move)))
    return _no_braces(code, "products_facts_code")


def products_facts_fallbacks(statement_fallback, id_prefix="p", products_fallback="Product data could not be prepared."):
    """The guarded() fallbacks of the prepare node: what the prompts show when the product data could not be
    prepared (a single product named <id_prefix>1 stays open so the call still reaches finalize)."""
    pid = "%s1" % (id_prefix or "")
    return {"products_text": products_fallback, "statement_text": statement_fallback, "calendar_text": "",
            "pids_csv": pid, "open_pids": pid, "all_done": "no"}


def prepare_code(holidays, statement_fallback, business_weekdays=fl.BUSINESS_WEEKDAYS, state_var="prepare_state",
                 products_var="products", extra_code="", **facts):
    """The complete prepare code node source:
        guarded(CAL_HELPERS + products_from_vars(products_var) + extra_code + products_facts_code(**facts))
    so nothing runs outside the try (lint-clean). `facts` are the products_facts_code keyword arguments (bands,
    floor_rules, wording, statement, the field names, api, ...). `extra_code` is brief-specific source run after
    the product list `prods` exists and before the facts are computed: derive fields a floor rule or wording can
    then read (for p in prods: p['x'] = ...), drop or reorder products, or anything else the brief asks for. A
    generator that needs more composes the pieces by hand: CAL_HELPERS(...) + guarded(products_from_vars() +
    <own snippets> + products_facts_code(...), state_var, products_facts_fallbacks(...))."""
    if extra_code:
        _no_braces(extra_code, "extra_code")
        try:
            compile(extra_code, "<extra_code>", "exec")
        except SyntaxError as e:
            raise ValueError("extra_code does not compile: %s" % e)
        extra_code = extra_code.strip("\n") + "\n"
    body = fl.CAL_HELPERS(holidays, business_weekdays) + fl.products_from_vars(products_var) + extra_code + products_facts_code(**facts)
    fb = products_facts_fallbacks(statement_fallback, facts.get("id_prefix", "p"))
    return fl.guarded(body, state_var, fb)


# ----------------------------------------------------------------------------------------------- self-test
def _selftest():
    """Executes the generated prepare code and the validations on two API shapes: the kit's tools/openapi.json
    (product_id / past_due / days_late / type) and tests/synthetic/brief-e.openapi.json (overdue_amount, other
    types and note reasons). Plain asserts; prints one line per check."""
    import copy
    import json
    root = pathlib.Path(__file__).resolve().parent.parent
    api_b = fl.load_api(root / "tools/openapi.json")
    api_e_path = root / "tests/synthetic/brief-e.openapi.json"
    api_e = fl.load_api(api_e_path) if api_e_path.exists() else None
    hol = ["2026-10-26"]
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond)))
        print("  %s %s %s" % ("PASS" if cond else "FAIL", name, detail))

    def raises(name, fn, needle):
        try:
            fn()
        except (ValueError, KeyError) as e:
            ok(name, needle in str(e), "" if needle in str(e) else "got %r" % (str(e),))
        else:
            ok(name, False, "no error raised")

    def run(code, v):
        g = {"vars": copy.deepcopy(v)}
        exec(code, g)
        return g["vars"]

    setup = fl.SETUP_CODE(hol, extra="vars['dl_a'] = addbd(today, 5).isoformat()\nvars['a1'] = addbd(today, 2).isoformat()")
    base = run(setup, {"now": "2026-10-14T11:00", "title": "Ms", "last_name": "Test", "first_name": "Ann"})
    ok("setup for the self-test", base["setup_state"] == "ok", base["setup_state"])
    bands = [{"name": "only", "max_days_late": None, "attempts": 2, "deadline_var": "dl_a"}]
    stmt = {"one": "{title} {last_name}: {words} {past_due} {days_late}", "many_head": "{n}: ", "many_item": "{words} {past_due}; ", "many_tail": "end"}
    common = dict(statement_fallback="fallback", bands=bands, statement=stmt, attempt1_var="a1")

    # 1. default field names on the kit's API, checked against it
    b_rules = dict(floor_rules=[{"types": ["credit_card"], "field": "minimum_payment", "name": "minimum payment"},
                                {"types": None, "field": "instalment_amount", "name": "instalment"}],
                   wording=[{"types": ["credit_card"], "template": "credit card ending {card_last4}"}, {"types": None, "template": "{type_words}"}])
    code = prepare_code(hol, api=api_b, **common, **b_rules)
    ok("prepare_code starts with try (nothing outside the guard)", code.startswith("try:\n") and "{{" not in code)
    compile(code, "prepare", "exec")
    v = run(code, dict(base, products=[{"product_id": "p1", "type": "credit_card", "card_last4": "4821", "past_due": 420.5, "days_late": 5, "minimum_payment": 60}]))
    ok("kit shape: pd_p1 / floor / words", v["prepare_state"] == "ok" and v["pd_p1"] == "420.5" and "allowed) 60 (the minimum payment)" in v["products_text"]
       and v["statement_text"] == "Ms Test: credit card ending 4821 420.50 5", v.get("prepare_state"))
    raises("kit API refuses a wrong amount_field", lambda: prepare_code(hol, api=api_b, amount_field="overdue_amount", **common, **b_rules), "amount_field 'overdue_amount'")
    raises("kit API refuses a wrong floor field", lambda: prepare_code(hol, api=api_b, **common, wording=b_rules["wording"],
                                                                      floor_rules=[{"types": None, "field": "min_pay", "name": "x"}]), "floor rule 'x' field 'min_pay'")
    raises("kit API refuses a type outside the enum", lambda: prepare_code(hol, api=api_b, **common, floor_rules=b_rules["floor_rules"],
                                                                           wording=[{"types": ["overdraft"], "template": "x"}, {"types": None, "template": "{type_words}"}]), "product type 'overdraft'")
    raises("kit API refuses a wording placeholder it lacks", lambda: prepare_code(hol, api=api_b, **common, floor_rules=b_rules["floor_rules"],
                                                                                  wording=[{"types": None, "template": "{account_ref}"}]), "wording placeholder 'account_ref'")
    raises("floor rule needs field or expr", lambda: prepare_code(hol, **common, wording=b_rules["wording"], floor_rules=[{"types": None, "name": "x"}]), "exactly one")
    raises("floor expr must compile", lambda: prepare_code(hol, **common, wording=b_rules["wording"], floor_rules=[{"types": None, "expr": "min(", "name": "x"}]), "does not compile")

    # 2. a formula floor (twice a field, capped) and an extra_code hook
    code = prepare_code(hol, api=api_b, **common, wording=b_rules["wording"],
                        floor_rules=[{"types": ["credit_card"], "expr": "min(2 * float(p.get('minimum_payment') or 0), amount)", "name": "double minimum"},
                                     {"types": None, "field": "instalment_amount", "name": "instalment"}])
    v = run(code, dict(base, products=[{"product_id": "p1", "type": "credit_card", "card_last4": "1", "past_due": 420.5, "days_late": 5, "minimum_payment": 60},
                                       {"product_id": "p2", "type": "credit_card", "card_last4": "2", "past_due": 420.5, "days_late": 5, "minimum_payment": 300},
                                       {"product_id": "p3", "type": "car_loan", "past_due": 100, "days_late": 5}]))
    ok("expr floor: 2 x 60 -> 120, 2 x 300 capped to 420.5, missing field -> past due",
       v["prepare_state"] == "ok" and "allowed) 120 (the double minimum)" in v["products_text"] and "allowed) 420.50 (the double minimum)" in v["products_text"]
       and "allowed) 100 (the instalment)" in v["products_text"], v["prepare_state"])
    code = prepare_code(hol, **common, wording=b_rules["wording"], extra_code="for p in prods:\n    if isinstance(p, dict):\n        p['floor_calc'] = 5\n",
                        floor_rules=[{"types": None, "field": "floor_calc", "name": "computed"}])
    v = run(code, dict(base, products=[{"product_id": "p1", "type": "car_loan", "past_due": 100, "days_late": 5}]))
    ok("extra_code runs before the facts (derived floor field)", v["prepare_state"] == "ok" and "allowed) 5 (the computed)" in v["products_text"], v["prepare_state"])
    raises("extra_code must compile", lambda: prepare_code(hol, **common, **b_rules, extra_code="for p in"), "extra_code does not compile")

    # 3. a changed API: other field names, no type-specific floor, a rounded-up percentage floor
    e_prod = {"product_id": "P-1001-C", "type": "overdraft", "account_last4": "7781", "overdue_amount": 980.5, "days_late": 33}
    v = run(prepare_code(hol, **common, **b_rules), dict(base, products=[e_prod]))
    ok("default names on a changed shape read the amount as 0 (why api= exists)", v["prepare_state"] == "ok" and v["pd_P-1001-C"] == "0.0")
    e_rules = dict(amount_field="overdue_amount",
                   floor_rules=[{"types": None, "expr": "min(-(-amount * 0.25 // 10) * 10, amount)", "name": "quarter rounded up to ten"}],
                   wording=[{"types": ["overdraft"], "template": "overdraft on the account ending {account_last4}"}, {"types": None, "template": "{type_words}"}])
    if api_e is not None:
        raises("changed API refuses the default amount_field", lambda: prepare_code(hol, api=api_e, **common, **b_rules), "amount_field 'past_due'")
        raises("changed API refuses a kit product type", lambda: prepare_code(hol, api=api_e, **common, amount_field="overdue_amount", floor_rules=e_rules["floor_rules"],
                                                                              wording=b_rules["wording"]), "product type 'credit_card'")
        ok("product_fields reads the changed schema", set(product_fields(api_e)) >= {"product_id", "type", "overdue_amount", "days_late", "account_last4"})
        ok("note_reasons reads the changed enum", "tool_failure" in note_reasons(api_e) and "service_error" not in note_reasons(api_e))
        code = prepare_code(hol, api=api_e, **common, **e_rules)
    else:
        code = prepare_code(hol, **common, **e_rules)
    prods = [dict(e_prod), dict(e_prod, product_id="P2", overdue_amount=412), dict(e_prod, product_id="P3", overdue_amount=1135),
             dict(e_prod, product_id="P4", overdue_amount=760), dict(e_prod, product_id="P5", overdue_amount=25)]
    v = run(code, dict(base, products=prods))
    want = {"P-1001-C": ("980.50", "250"), "P2": ("412", "110"), "P3": ("1135", "290"), "P4": ("760", "190"), "P5": ("25", "10")}
    got = {}
    for line in v["products_text"].split("\n"):
        pid = line[2:].split(" = ")[0]
        amt = line.split("full past-due amount ")[1].split(",")[0]
        flo = line.split("allowed) ")[1].split(" (")[0]
        got[pid] = (amt, flo)
    ok("changed shape: amounts and rounded-up percentage floors", v["prepare_state"] == "ok" and got == want and v["pd_P-1001-C"] == "980.5"
       and v["statement_text"].startswith("5: overdraft on the account ending 7781 980.50;"), "%s / %s" % (got, v["prepare_state"]))
    v = run(prepare_code(hol, **common, type_field=None, amount_field="overdue_amount", floor_rules=e_rules["floor_rules"],
                         wording=[{"types": None, "template": "{type_words}"}]), dict(base, products=[{"product_id": "x1", "overdue_amount": 50, "days_late": 2}]))
    ok("type_field None: no type, unknown_type_words used", v["prepare_state"] == "ok" and v["statement_text"] == "Ms Test: account 50 2", v["statement_text"])

    # 4. hooks and finalize: reasons checked against the API, literal-safe reasons, fin keys identifiers
    raises("promise_post_code refuses a reason the API lacks", lambda: promise_post_code(fail_reason="service_error", api=api_e or api_b, note_tool="add_note")
           if api_e is not None else promise_post_code(fail_reason="tool_failure", api=api_b), "is not one of the API's add_note.reason values")
    pp = promise_post_code(fail_reason="tool-failure", max_fails=3)
    compile(pp, "promise_post", "exec")
    sample = {"vars": {"pending_pid": "p1", "pids_csv": "p1", "fail_p1": 2}, "result": {"data": {"ok": False}}}
    exec(pp, sample)
    ok("promise_post_code accepts a hyphenated reason", "with reason tool-failure." in sample["result"]["data"]["what_to_do_next"])
    sample = {"vars": {"pending_pid": "p1", "pids_csv": "p1"}, "result": {"data": {"ok": False}}}
    exec(promise_post_code(max_fails=1, fail_reason="it's"), sample)
    ok("promise_post_code safely quotes a reason", "with reason it's." in sample["result"]["data"]["what_to_do_next"])
    raises("promise_post_code checks ok_field", lambda: promise_post_code(fail_reason="service_error", api=api_b, ok_field="success"), "ok_field 'success'")
    raises("promise_pre_code checks the request fields", lambda: promise_pre_code(api=api_b, pid_field="product"), "pid_field 'product'")
    raises("note_pre_code checks the request fields", lambda: note_pre_code(api=api_b, reason_field="why"), "reason_field 'why'")
    ok("promise_pre / note_pre / note_post / finalize accept the kit API",
       promise_pre_code(api=api_b) and note_pre_code(api=api_b) and note_post_code(api=api_b)
       and finalize_code([("hardship", "hardship")], api=api_b) and promise_post_code(fail_reason="service_error", api=api_b))
    fc = finalize_code([("tool-failure", "service_error"), ("no.promise", "refused")], paid_reason="settled")
    g = {"vars": {"pids_csv": "p1,p2", "rec_pids": "", "note_log": "p1:no.promise,p2:tool-failure"}}
    exec(fc, g)
    ok("finalize_code with literal reasons routes by product order", g["vars"]["final_route"] == "refused", g["vars"].get("final_route"))
    raises("finalize_code refuses a fin key that is not an identifier", lambda: finalize_code([("x", "tool-failure")]), "fin key")
    if api_e is not None:
        raises("finalize_code checks paid_reason against the API", lambda: finalize_code([("declined", "refused")], api=api_e), "paid_reason 'paid'")
        ok("finalize_code accepts the changed API's reasons", bool(finalize_code([("declined", "refused"), ("distress", "hardship")], paid_reason="settled", api=api_e)))
    raises("state_fn_code refuses braces", lambda: state_fn_code(still_open_text="{{x}}"), "'{{'")
    failed = [n for n, c in checks if not c]
    print("%d checks, %d failed" % (len(checks), len(failed)))
    return not failed


if __name__ == "__main__":
    sys.exit(0 if _selftest() else 1)
