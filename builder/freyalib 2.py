"""freyalib: a brief-agnostic library for generating Freya phone-agent workflows.

Everything platform-specific lives here: the JSON shapes of tools, nodes, transitions and terminals, the pre/post
hooks, the lifecycle close_call tool, the code-node templates (calendar helpers, setup, product reader) and the
final structural checks. Everything bank-specific (holidays, bands, floors, wording, outcome table, identity
fields, prompts) is a parameter that the generator for one brief passes in. The shapes are the ones of the
organisers' proven generator (out/gen_brief-a.py, 10/10 practice cases); docs/workflow-format.md and
docs/tools-and-code.md are the platform reference.

Standard library only. Python 3.10+.

Usage (a minimal generator; see out/gen_brief-a_lib.py for a complete one):

    import sys; sys.path.insert(0, "builder")
    import freyalib as fl

    api = fl.load_api("tools/openapi.json")
    nodes = {}
    # one code node + one end_call node per outcome of the brief's table
    fl.end_pair("refused", "no_promise", "refused", "I understand. Goodbye.", nodes)
    fl.end_pair("promise", "promise", "", "Your promise is recorded. Goodbye.", nodes)
    # dates are computed in code, the model gets finished text
    nodes["setup"] = fl.code_node("setup", fl.SETUP_CODE(holidays=["2026-12-25"], callback_rule={"open": "10:00", "close": "19:00"}),
                                  [fl.always("talk")])
    promise = fl.api_tool(api, "create_promise", baked={"product_id": "{{product_id}}"},
                          description="Record the promise. CALL it after a clear yes.",
                          field_descriptions={"date": "YYYY-MM-DD"}, pre=fl.promise_pre(), post=fl.promise_post())
    nodes["talk"] = fl.conv("talk", "Today is {{today_text}}. Get a payment promise ...", tools=[promise],
                            extraction=[fl.ext("mood", ["none", "refuses"], "refuses = says no twice")],
                            transitions=[fl.ok_true("create_promise", "fin_promise", "promise recorded"),
                                         fl.eq("mood", "refuses", "fin_refused", "refused")])
    close = fl.close_call_tool(api, outcome_desc="promise | no_promise", reason_desc="refused", no_reason_outcomes=("promise",))
    wf = fl.assemble("setup", nodes, "You are the bank's digital assistant.", [close],
                     {"customer_id": "c_test", "now": "2026-10-14T11:00"})
    fl.write_workflow(wf, "out/my.workflow.json")

Design rules baked into the helpers (from the platform docs and the proven generator):
- fixed values use `default`, never `const`; customer_id is always baked from the call variable;
- a model-filled body field is a leaf under body.properties with `default: "{{<field>}}"` and MUST NOT share its
  name with a variable that is already set when the node is entered (it would be baked and hidden from the model);
- booleans from tool results are tested as "true" and "True"; routing flags written by code are strings;
- code snippets read and write `vars`, never raise, and contain no '{{' or '}}';
- every passthrough node ends with an `always` transition; every path reaches an end_call node whose terminal
  function name is the call's endedReason and whose farewell is the terminal's spoken_message.
"""
from __future__ import annotations

import json
import pathlib
import re
from collections import deque

# ----------------------------------------------------------------------------------------------- constants
HEADERS = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}
STRIP_HEADER = "try:\n    if isinstance(result, dict):\n        result.pop('header', None)\nexcept Exception:\n    pass\n"
BUSINESS_WEEKDAYS = [0, 1, 2, 3, 4]        # Monday .. Friday
DEFAULT_TIMEOUT_MS = 12000
CODE_TIMEOUT_MS = 10000
CUSTOMER_ID = "customer_id"


# ----------------------------------------------------------------------------------------------- OpenAPI
def load_api(path):
    """Read the bank's tool API file (OpenAPI 3 JSON)."""
    with open(path) as f:
        return json.load(f)


def base_url(api):
    """The server URL without a trailing slash. Tool <name> is POST <base_url>/<name>."""
    return api["servers"][0]["url"].rstrip("/")


def _json_schema(holder):
    """requestBody / response object -> its application/json schema, or {}."""
    try:
        return ((holder or {}).get("content") or {}).get("application/json", {}).get("schema") or {}
    except AttributeError:
        return {}


def _norm_props(schema):
    req = list(schema.get("required") or [])
    out = {}
    for fname, fs in (schema.get("properties") or {}).items():
        fs = fs if isinstance(fs, dict) else {}
        out[fname] = {"type": fs.get("type", "string"), "description": fs.get("description", ""),
                      "enum": list(fs.get("enum") or []), "required": fname in req}
    return out, req


def tool_spec(api, name):
    """The request and response schema of tool <name>, read from paths["/<name>"]["post"].

    Returns {"fields": {field: {type, description, enum, required}}, "required": [ordered spec list],
             "summary": str, "response_props": {prop: {type, description, enum, required}}}.
    Missing description -> "", missing enum -> [] (never None)."""
    op = ((api.get("paths") or {}).get("/" + name) or {}).get("post")
    if op is None:
        raise KeyError("tool %r: the API file has no POST /%s" % (name, name))
    fields, req = _norm_props(_json_schema(op.get("requestBody")))
    resp, _ = _norm_props(_json_schema(((op.get("responses") or {}).get("200"))))
    return {"fields": fields, "required": req, "summary": op.get("summary", ""), "response_props": resp}


def tool_names(api):
    """Every tool name in the API file, in file order."""
    return [p.lstrip("/") for p, item in (api.get("paths") or {}).items() if "post" in (item or {})]


# ----------------------------------------------------------------------------------------------- tools
def api_tool(api, name, baked=None, description="", required=None, retries=0, pre=None, post=None, mapping=None,
             field_descriptions=None, omit=None, var_map=None, timeout_ms=DEFAULT_TIMEOUT_MS):
    """The api_call tool for tool <name>, built from the OpenAPI request schema.

    url, method and headers are baked. body.properties holds every field of the spec, each as a leaf:
    - customer_id is always baked from the call variable: {"type": "string", "default": "{{customer_id}}"};
    - a field in `baked` gets that literal default (field="date_of_birth", queue="support"). It is hidden from
      the model, so it carries no description or enum. A literal is checked against the spec's enum. The value may
      also be "{{var}}" to bake the field from a variable that an earlier node ALWAYS sets (product_id from the
      prepare node): it is then resolved when the node is entered;
    - every other field is model-filled: {"type", "default": "{{<field>}}", "description", "enum"} with type,
      description and enum copied from the spec (`field_descriptions` overrides a description). RULE: such a
      field must not share its name with a variable that exists when the node is entered, or the engine bakes the
      variable's value and the model never sees the parameter. `var_map` {field: var} reads a model-visible field
      from another variable name instead (used by the lifecycle close_call tool).
    `required` defaults to the spec's required list minus customer_id minus baked/omitted fields. `omit` drops
    optional spec fields the model should not see. `post` defaults to STRIP_HEADER; pass "" for no post hook.
    `mapping` is a tool-level response_mapping (for tools in a conversation node's `tools`)."""
    spec = tool_spec(api, name)
    baked = dict(baked or {})
    field_descriptions = dict(field_descriptions or {})
    var_map = dict(var_map or {})
    omit = set(omit or [])
    unknown = (set(baked) | set(field_descriptions) | set(var_map) | omit) - set(spec["fields"])
    if unknown:
        raise KeyError("tool %r: fields %s are not in the API file (it has %s)"
                       % (name, sorted(unknown), sorted(spec["fields"])))
    if omit & set(spec["required"]):
        raise ValueError("tool %r: cannot omit required API fields %s" % (name, sorted(omit & set(spec["required"]))))
    props = ({CUSTOMER_ID: {"type": spec["fields"][CUSTOMER_ID]["type"], "default": "{{%s}}" % CUSTOMER_ID}}
             if CUSTOMER_ID in spec["fields"] else {})
    for fname, fs in spec["fields"].items():
        if fname == CUSTOMER_ID or fname in omit:
            continue
        leaf = {"type": fs["type"]}
        if fname in baked:
            val = baked[fname]
            if fs["enum"] and not (isinstance(val, str) and "{{" in val) and val not in fs["enum"]:
                raise ValueError("tool %r: baked %s=%r is not one of %s" % (name, fname, val, fs["enum"]))
            leaf["default"] = val
        else:
            leaf["default"] = "{{%s}}" % var_map.get(fname, fname)
            desc = field_descriptions.get(fname, fs["description"])
            if desc:
                leaf["description"] = desc
            if fs["enum"]:
                leaf["enum"] = list(fs["enum"])
        props[fname] = leaf
    if required is None:
        required = [f for f in spec["required"] if f != CUSTOMER_ID and f not in baked and f not in omit]
    elif set(required) - set(props):
        raise ValueError("tool %r: required fields are absent from the body: %s" % (name, sorted(set(required) - set(props))))
    t = {
        "type": "function",
        "config": {"timeoutMs": timeout_ms, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": "%s/%s" % (base_url(api), name)},
                "method": {"type": "string", "default": "POST"},
                "headers": json.loads(json.dumps(HEADERS)),
                "body": {"type": "object", "required": list(required), "properties": props},
            }},
        },
    }
    post = STRIP_HEADER if post is None else post
    if post:
        t["post_process_code"] = post
    if pre:
        t["pre_process_code"] = pre
    if mapping:
        t["response_mapping"] = list(mapping)
    return t


def close_call_tool(api, outcome_desc, reason_desc, description="Record how the call ended, from the conversation.",
                    no_reason_outcomes=None, outcome_var="outcome", reason_var="reason", name="close_call"):
    """The workflow-level end_of_call lifecycle tool. It reads {{outcome}} / {{reason}} (the variables every
    fin_<key> node sets, see end_pair) and sends them to close_call. The outcome enum comes from the API file.
    The pre-hook drops an empty reason, and the reason of any outcome in `no_reason_outcomes`."""
    spec = tool_spec(api, name)
    for f in ("outcome", "reason"):
        if f not in spec["fields"]:
            raise KeyError("tool %r has no %r field in the API file" % (name, f))
    test = "not b.get('reason')"
    if no_reason_outcomes:
        test = "b.get('outcome') in %r or %s" % (tuple(no_reason_outcomes), test)
    pre = ("try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        if %s:\n            b.pop('reason', None)\n"
           "except Exception:\n    pass\n" % test)
    t = api_tool(api, name, description=description, pre=pre, post="",
                 field_descriptions={"outcome": outcome_desc, "reason": reason_desc},
                 var_map={"outcome": outcome_var, "reason": reason_var})
    t["config"]["alwaysRunsAt"] = ["end_of_call"]
    return t


# ----------------------------------------------------------------------------------------------- nodes
def base_node(name, node_type, **kw):
    n = {"name": name, "node_type": node_type, "transitions": [], "max_node_turns": 60,
         "truncation_strategy": "keep_all", "disable_inactivity_monitor": False}
    n.update(kw)
    return n


def conv(name, task, on_enter=None, tools=None, extraction=None, transitions=None, first_only=False, max_turns=60):
    """A conversation node. on_enter defaults to {"type": "llm"}; use {"type": "tts", "text": ...} for a fixed line."""
    return base_node(name, "conversation", task_message=task, on_enter=on_enter or {"type": "llm"},
                     tools=tools or [], extraction_schema=extraction or [], transitions=transitions or [],
                     on_enter_first_entry_only=first_only, max_node_turns=max_turns)


def _need_transitions(name, transitions, kind):
    if not transitions:
        raise ValueError("%s node %r needs at least one transition (end with always(<next>))" % (kind, name))


def code_node(name, code, transitions):
    """A passthrough code node. `transitions` must end with always(<next>). Raises ValueError when empty."""
    _need_transitions(name, transitions, "code")
    return base_node(name, "code", passthrough=True, passthrough_default_transition=transitions[-1]["target_node"],
                     on_enter={"type": "silent"}, disable_inactivity_monitor=True, pre_actions=[{
                         "type": "function",
                         "function": {"name": "code_exec", "handler": "__function__:code_exec", "parameters": {
                             "type": "object", "properties": {
                                 "code": {"type": "string", "default": code},
                                 "timeout_ms": {"type": "number", "default": CODE_TIMEOUT_MS}}}}}],
                     transitions=transitions)


def api_node(name, tool, transitions, mapping=None, on_enter=None):
    """A passthrough api_request node that runs `tool` (an api_tool) on entry. `mapping` is the NODE-level
    response_mapping ([{"path": "data.x", "variable": "x"}]). on_enter defaults to silent; a tts line covers the wait.
    `transitions` must end with always(<next>). Raises ValueError when empty."""
    _need_transitions(name, transitions, "api_request")
    kw = {}
    if mapping:
        kw["response_mapping"] = list(mapping)
    return base_node(name, "api_request", passthrough=True, passthrough_default_transition=transitions[-1]["target_node"],
                     on_enter=on_enter or {"type": "silent"}, disable_inactivity_monitor=True, pre_actions=[tool],
                     transitions=transitions, **kw)


def end_node(name, ended_reason, farewell):
    """An end_call node. `ended_reason` becomes the terminal function name (the call's endedReason);
    the farewell is spoken by the terminal, on_enter is silent."""
    return base_node(name, "end_call", on_enter={"type": "silent"}, disable_inactivity_monitor=True,
                     terminal={"type": "function", "function": {
                         "name": ended_reason,
                         "handler": "__function__:end_call",
                         "parameters": {"type": "object", "properties": {
                             "message_mode": {"type": "string", "default": "custom"},
                             "spoken_message": {"type": "string", "default": farewell}}}}})


def conversation_first(opening_node_name, setup_code, route_var, routes, default_target, nodes, setup_name="setup"):
    """The 'Initial node' pattern: the call starts in a conversation node and the setup code runs right after the
    customer's first turn. The chat route (smoke tests, the local simulator) SKIPS a first code node, so a code node
    must never be the initial node; simulations would run it, the chat route would not, and the two would differ.

    `nodes[opening_node_name]` must already be a conversation node (its on_enter speaks the opening line and its
    extraction_schema extracts `route_var`). Its transitions are replaced by one always(setup_name). Adds
    nodes[setup_name]: a passthrough code node that runs `setup_code` (compute facts from call variables there) and
    then routes on `route_var`: `routes` is a list of (value, target, description) or a dict {value: target};
    anything else goes to `default_target`. Returns opening_node_name: pass it to assemble() as the initial node.
    Prompts of the opening node can only use call variables (test_variables); setup's outputs exist from the
    next node on."""
    op = nodes.get(opening_node_name)
    if not isinstance(op, dict) or op.get("node_type") != "conversation":
        raise ValueError("conversation_first: %r must be a conversation node already in nodes" % opening_node_name)
    if setup_name in nodes:
        raise ValueError("conversation_first: node %r already exists" % setup_name)
    items = [(v, t, "%s is %s" % (route_var, v)) for v, t in routes.items()] if isinstance(routes, dict) else routes
    trs = [eq(route_var, v, t, d) for v, t, d in items] + [always(default_target)]
    op["transitions"] = [always(setup_name)]
    nodes[setup_name] = code_node(setup_name, setup_code, trs)
    return opening_node_name


def outcome_code(outcome, reason, outcome_var="outcome", reason_var="reason"):
    return ("try:\n    vars[%r] = %r\n    vars[%r] = %r\nexcept Exception:\n    pass\n"
            % (outcome_var, outcome, reason_var, reason))


def end_pair(key, outcome, reason, farewell, nodes, outcome_var="outcome", reason_var="reason"):
    """Adds fin_<key> (a code node that sets vars outcome/reason) and end_<key> (the end_call terminal named
    <outcome>_<reason>, or <outcome> when reason is "") to `nodes`. Route every ending to fin_<key>."""
    fin, end = "fin_%s" % key, "end_%s" % key
    nodes[fin] = code_node(fin, outcome_code(outcome, reason, outcome_var, reason_var), [always(end)])
    nodes[end] = end_node(end, "%s_%s" % (outcome, reason) if reason else outcome, farewell)
    return fin, end


# ----------------------------------------------------------------------------------------------- transitions
def cond(var, op, operand=None):
    """One deterministic leaf condition: equals, not_equals, greater_than, less_than, contains, is_set, is_not_set."""
    c = {"variable": var, "operator": op}
    if operand is not None:
        c["operand"] = operand
    return c


def and_group(*conds):
    """An AND group, to nest inside the top-level OR of tr()."""
    return {"logic": "and", "conditions": list(conds)}


def tr(target, desc, *conds):
    """A transition whose condition is the OR of `conds` (leaves from cond() or and_group()s)."""
    return {"target_node": target, "description": desc, "condition": {"logic": "or", "conditions": list(conds)}}


def always(t):
    return {"target_node": t, "description": "always", "condition": {"operator": "always"}}


def eq(var, val, t, desc):
    return tr(t, desc, cond(var, "equals", val))


def neq(var, val, t, desc):
    return tr(t, desc, cond(var, "not_equals", val))


def is_set(var, t, desc):
    return tr(t, desc, cond(var, "is_set"))


def is_true(var, t, desc):
    """Fires when a boolean-ish variable (a tool result flag) is "true" or "True"."""
    return tr(t, desc, cond(var, "equals", "true"), cond(var, "equals", "True"))


def not_true(var):
    """Leaves for an AND group: the variable is neither "true" nor "True"."""
    return [cond(var, "not_equals", "true"), cond(var, "not_equals", "True")]


def count_gt(var, n, t, desc):
    return tr(t, desc, cond(var, "greater_than", n))


def intent(t, desc, intent_desc):
    """A router-evaluated matches_intent transition (judged on the user's latest message)."""
    return {"target_node": t, "description": desc, "condition": {"operator": "matches_intent", "description": intent_desc}}


def intent_tool(t, desc, intent_desc):
    """A tool-call transition: the dialogue model moves by calling transition_to_<t>."""
    return {"target_node": t, "description": desc, "is_tool_call": True,
            "condition": {"operator": "matches_intent", "description": intent_desc}}


def ok_true(tool, t, desc):
    """<tool>_response.data.ok is true (the API carried the action out)."""
    return is_true("%s_response.data.ok" % tool, t, desc)


def tool_failed_twice(tool, t, desc):
    """The write tool failed twice: two HTTP failures, two 200s with ok not true, or one of each. Use it after a
    'retry once with the same values' rule, routing to the service_error ending."""
    ok, sc, fc = "%s_response.data.ok" % tool, "%s_success_count" % tool, "%s_failure_count" % tool
    return tr(t, desc, cond(fc, "greater_than", 1),
              and_group(cond(sc, "greater_than", 1), *not_true(ok)),
              and_group(cond(sc, "greater_than", 0), cond(fc, "greater_than", 0), *not_true(ok)))


def transferred(t, desc, tool="transfer_to_agent"):
    """The transfer tool was called successfully at least once."""
    return count_gt("%s_success_count" % tool, 0, t, desc)


def ext(name, values, desc, conf=0.6, type="string"):
    """An extraction_schema entry with enum values. Always set min_confidence (the default 0.95 drops most values)."""
    return {"name": name, "type": type, "enum_values": list(values), "description": desc, "min_confidence": conf}


# ----------------------------------------------------------------------------------------------- hooks
def truthy(field):
    """Python expression on the result body `d`: field is boolean True or the string "true"."""
    return "d.get(%r) is True or str(d.get(%r)).lower() == 'true'" % (field, field)


def falsy(field):
    return "d.get(%r) is False or str(d.get(%r)).lower() == 'false'" % (field, field)


def what_next_post(branches, else_text=None, prelude=None, key="what_to_do_next"):
    """A post_process_code string: strips the response headers and sets result['data'][key] from an ordered list
    of (python_condition_on_d, text) pairs, `d` being the API's JSON body; `else_text` is the final else.
    `prelude` is a list of statements run before the branches (e.g. "left = d.get('wrong_answers_left')").
    With no branches, no else_text and no prelude the hook only strips the response headers.
    The line tells the dialogue model what the result means and what to say or call next; the prompt says to obey it."""
    out = ("try:\n    if isinstance(result, dict):\n        result.pop('header', None)\n        d = result.get('data')\n"
           "        if isinstance(d, dict):\n")
    if not branches and else_text is None and not prelude:
        # nothing to say: only strip the header (an empty if-block would not compile)
        return STRIP_HEADER
    for line in prelude or []:
        out += "            %s\n" % line
    for i, (c, text) in enumerate(branches):
        out += "            %s %s:\n                d[%r] = %r\n" % ("if" if i == 0 else "elif", c, key, text)
    if else_text is not None:
        if branches:
            out += "            else:\n                d[%r] = %r\n" % (key, else_text)
        else:
            out += "            d[%r] = %r\n" % (key, else_text)
    out += "except Exception:\n    pass\n"
    return out


def ok_post(ok_text, fail_text, ok_field="ok"):
    """what_to_do_next for a plain write tool: one text when ok is true, another otherwise."""
    return what_next_post([(truthy(ok_field), ok_text)], fail_text)


def verify_post(question, hints, max_wrong_text,
                all_verified_text="All security questions passed. Identity is verified.",
                verified_text="Correct. Ask the next security question.",
                unreadable_text="The answer could not be read. It does not count as wrong. Ask again: {question}",
                wrong_text="Wrong answer. Tell the customer it does not match our records and ask again: {question}",
                fields=None):
    """Post hook for one identity question. `hints` maps a response hint value to the text for it (checked first,
    a hint is not a wrong answer). `max_wrong_text` is used when the wrong-answers counter reaches 0.
    `fields` renames the response fields: {"hint", "all_verified", "verified", "ok", "left"}.
    The default texts are generic placeholders: a generator should pass the brief's own wording for every text
    (all_verified_text, verified_text, unreadable_text, wrong_text, max_wrong_text), e.g. what the brief says the
    agent does once identity is verified, how many questions there are, how a wrong answer is worded."""
    f = {"hint": "hint", "all_verified": "all_verified", "verified": "verified", "ok": "ok", "left": "wrong_answers_left"}
    f.update(fields or {})
    q = lambda s: s.replace("{question}", question)
    branches = [("d.get(%r) == %r" % (f["hint"], v), t) for v, t in (hints or {}).items()]
    branches += [(truthy(f["all_verified"]), all_verified_text), (truthy(f["verified"]), verified_text),
                 (falsy(f["ok"]), q(unreadable_text)), ("str(left) == '0'", max_wrong_text)]
    return what_next_post(branches, q(wrong_text), prelude=["left = d.get(%r)" % f["left"]])


def promise_post(tool="create_promise", recorded_text="The promise is recorded.",
                 failed_text="NOT recorded. Do not say it is recorded. Call {tool} once more with exactly the same values."):
    """Post hook of the promise tool: say 'recorded' only on ok true, otherwise retry once with the same values."""
    return ok_post(recorded_text, failed_text.replace("{tool}", tool))


def promise_pre(amount_field="amount", date_field="date"):
    """Pre hook of the promise tool: amount -> float (commas stripped), date -> its first 10 characters (YYYY-MM-DD)."""
    return ("try:\n    b = config.get('body')\n    if isinstance(b, dict):\n"
            "        if %r in b:\n            b[%r] = float(str(b[%r]).replace(',', '').strip())\n"
            "        if %r in b:\n            b[%r] = str(b[%r]).strip()[:10]\nexcept Exception:\n    pass\n"
            % (amount_field, amount_field, amount_field, date_field, date_field, date_field))


# ----------------------------------------------------------------------------------------------- code snippets
def _indent(text, n):
    pad = " " * n
    lines = text.strip("\n").split("\n")
    return "\n".join(pad + l if l.strip() else "" for l in lines)


def guarded(body, state_var, fallbacks=None, fallback_code=""):
    """Wraps a snippet body in try/except: on success vars[state_var] = 'ok', on error 'error <msg>' plus
    vars.setdefault(name, literal) for every fallback (so later prompts never show a bare {{placeholder}}).
    `fallback_code` adds raw statements to the except block."""
    out = "try:\n%s\n    vars[%r] = 'ok'\nexcept Exception as e:\n    vars[%r] = 'error ' + str(e)\n" % (
        _indent(body, 4), state_var, state_var)
    for k, v in (fallbacks or {}).items():
        out += "    vars.setdefault(%r, %r)\n" % (k, v)
    if fallback_code:
        out += _indent(fallback_code, 4) + "\n"
    return out


_CAL_HELPERS = r'''import datetime, json, re
HOL = set(__HOLIDAYS__)
BWD = set(__BWD__)
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MO = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
def isbd(d):
    return d.weekday() in BWD and d.isoformat() not in HOL
def txt(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1] + ' ' + str(d.year)
def txt_short(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1]
def addbd(d, n):
    c = 0
    guard = 0
    while c < n and guard < 4000:
        d = d + datetime.timedelta(days=1)
        guard += 1
        if isbd(d):
            c += 1
    return d
def next_bd(d):
    guard = 0
    while not isbd(d) and guard < 4000:
        d = d + datetime.timedelta(days=1)
        guard += 1
    return d
def lastbd_of_week(monday):
    for k in range(6, -1, -1):
        d = monday + datetime.timedelta(days=k)
        if isbd(d):
            return d
    return None
def weekday_table(today):
    monday = today - datetime.timedelta(days=today.weekday())
    tab = []
    for i in range(7):
        a = monday + datetime.timedelta(days=i)
        b = a + datetime.timedelta(days=7)
        t1 = '"this ' + WD[i] + '" = ' + txt(a) + (' (already past)' if a < today else '')
        tab.append(t1 + '; "next ' + WD[i] + '" = ' + txt(b))
    return '\n'.join(tab)
def calendar_text(today, deadline, extra_days=10):
    cal = []
    d = today
    while d <= deadline + datetime.timedelta(days=extra_days):
        if d > deadline:
            tag = 'AFTER THE DEADLINE, not allowed'
        elif isbd(d):
            tag = 'allowed'
        elif d.weekday() not in BWD:
            tag = 'weekend, not allowed'
        else:
            tag = 'bank holiday, not allowed'
        nb = next_bd(d)
        extra = ''
        if tag.startswith('weekend') or tag.startswith('bank'):
            extra = ' -> next business day ' + txt_short(nb) + ' (' + nb.isoformat() + ')' + ('' if nb <= deadline else ', which is after the deadline: offer the deadline instead')
        cal.append(d.isoformat() + ' ' + txt_short(d) + ('  (today)' if d == today else '') + ': ' + tag + extra)
        d = d + datetime.timedelta(days=1)
    return '\n'.join(cal)
def fmt(x):
    try:
        x = float(x)
    except Exception:
        return str(x)
    s = '%.2f' % x
    return s[:-3] if s.endswith('.00') else s
'''


def CAL_HELPERS(holidays, business_weekdays=BUSINESS_WEEKDAYS):
    """Python source (for the top of a code node) defining, on datetime.date values:
    isbd(d) business day?; txt(d) 'Friday 16 October 2026'; txt_short(d) without the year; addbd(d, n) n business
    days later; next_bd(d) d or the first business day after it; lastbd_of_week(monday) last business day of that
    week or None; weekday_table(today) the '"this Monday" = ...; "next Monday" = ...' table; calendar_text(today,
    deadline, extra_days=10) one tagged line per day (allowed / weekend / bank holiday / after the deadline, with the
    next business day); fmt(x) '420.5' / '420' / '420.25'. Also imports datetime, json, re. No '{{' or '}}'."""
    weekdays = sorted(set(int(x) for x in business_weekdays))
    if not weekdays or any(x < 0 or x > 6 for x in weekdays):
        raise ValueError("business_weekdays must contain weekdays numbered 0 through 6")
    hol = sorted(set(str(h)[:10] for h in holidays or []))
    import datetime
    for holiday in hol:
        datetime.date.fromisoformat(holiday)
    return _CAL_HELPERS.replace("__HOLIDAYS__", repr(hol)).replace("__BWD__", repr(weekdays))


_SETUP_CORE = r'''raw = str(vars.get(__NOW__) or '').strip()
try:
    nowdt = datetime.datetime.fromisoformat(raw[:16])
except Exception:
    nowdt = datetime.datetime.fromisoformat(raw[:10] + 'T09:00')
today = nowdt.date()
vars['today_iso'] = today.isoformat()
vars['today_text'] = txt(today)
vars['now_time'] = nowdt.strftime('%H:%M')
vars['weekday_table'] = weekday_table(today)
'''

_CALLBACK_TODAY = r'''if cur < __CLOSE__:
    start = __OPEN__ if cur < __OPEN__ else 'after ' + cur
    lines.append('Today, ' + txt(today) + ' (' + today.isoformat() + '), from ' + start + ' up to __CLOSE_T__.')
'''

_CALLBACK_DAYS = r'''nbd = today
for _i in range(__DAYS__):
    nbd = addbd(nbd, 1)
    lines.append(txt(nbd) + ' (' + nbd.isoformat() + '), from __OPEN_T__ up to __CLOSE_T__ included.')
tom = today + datetime.timedelta(days=1)
extra = 'Tomorrow is ' + txt(tom) + '.'
if not isbd(tom):
    extra += ' Tomorrow is NOT allowed, it is not a business day.'
vars['callback_text'] = 'The ONLY allowed callback times are:\n- ' + '\n- '.join(lines) + '\n' + extra + ' Any other day or time is outside the window.'
'''


def _callback_code(rule):
    out = "lines = []\ncur = nowdt.strftime('%H:%M')\n"
    if rule["same_day"]:
        out += _CALLBACK_TODAY.replace("__CLOSE__", repr(rule["close"])).replace("__OPEN__", repr(rule["open"])) \
                              .replace("__CLOSE_T__", rule["close"])
    out += _CALLBACK_DAYS.replace("__DAYS__", str(int(rule["days_ahead"]))).replace("__OPEN_T__", rule["open"]) \
                         .replace("__CLOSE_T__", rule["close"])
    return out


def SETUP_CODE(holidays, business_weekdays=BUSINESS_WEEKDAYS, callback_rule=None, extra="", fallbacks=None,
               now_var="now", state_var="setup_state"):
    """The first code node's source. It parses the call variable `now` (never the real clock) and always sets
    today_iso, today_text, now_time, weekday_table and <state_var> ('ok' or 'error ...').
    `callback_rule` = {"open": "10:00", "close": "19:00", "same_day": True, "days_ahead": 1} also sets
    callback_text, the list of allowed callback slots (today up to close if same_day, then days_ahead business
    days from open to close), with a fallback sentence in the except block.
    `extra` is brief-specific source appended inside the try block after the core (it may use today, nowdt and
    every CAL_HELPERS function, e.g. vars['deadline'] = addbd(today, 12).isoformat()). `fallbacks` {var: literal}
    adds vars.setdefault lines to the except block."""
    body = _SETUP_CORE.replace("__NOW__", repr(now_var))
    fb = {}
    if callback_rule:
        rule = {"same_day": True, "days_ahead": 1}
        rule.update(callback_rule)
        for k in ("open", "close"):
            if not re.fullmatch(r"\d\d:\d\d", str(rule.get(k, ""))):
                raise ValueError("callback_rule[%r] must be HH:MM (from the brief), got %r" % (k, rule.get(k)))
        body += _callback_code(rule)
        if rule["same_day"]:
            fb["callback_text"] = ("Callbacks: today later than now up to %s, or the next business day from %s to %s."
                                   % (rule["close"], rule["open"], rule["close"]))
        else:
            fb["callback_text"] = "Callbacks: the next business day from %s to %s." % (rule["open"], rule["close"])
    if extra:
        body += extra.strip("\n") + "\n"
    fb.update(fallbacks or {})
    fb_code = ("vars.setdefault('today_text', str(vars.get(%r)))\nvars.setdefault('today_iso', str(vars.get(%r))[:10])\n"
               "vars.setdefault('now_time', '')\nvars.setdefault('weekday_table', '')" % (now_var, now_var))
    return CAL_HELPERS(holidays, business_weekdays) + guarded(body, state_var, fb, fb_code)


_PRODUCTS_READER = r'''import json, re
__OUT__ = vars.get(__VAR__)
if isinstance(__OUT__, str):
    try:
        __OUT__ = json.loads(__OUT__)
    except Exception:
        __OUT__ = None
if not isinstance(__OUT__, list) or not __OUT__:
    found = {}
    for k, v in list(vars.items()):
        m = re.search(__RX__, str(k))
        if m:
            found.setdefault(int(m.group(1)), {})[m.group(2)] = v
    __OUT__ = [found[i] for i in sorted(found)]
'''


def products_from_vars(var="products", out="prods"):
    """Snippet that reads the product list a get_account node mapped into vars[var] (data.products) into `out`.
    It accepts a list, a JSON string, or the engine's flattened keys (<...>.products.0.product_id). Put it inside
    the try block of a prepare node (guarded())."""
    rx = "r'%s\\.(\\d+)\\.(\\w+)$'" % re.escape(var)
    return _PRODUCTS_READER.replace("__VAR__", repr(var)).replace("__OUT__", out).replace("__RX__", rx)


def counter_code(counter, limit, route_var, reset=None, over="close", under="retry"):
    """A code node snippet that increments vars[counter] and sets vars[route_var] to `over` once it reaches `limit`,
    else `under`; `reset` {var: value} clears extraction flags so the same answer is not counted twice."""
    out = ("try:\n    n = int(float(vars.get(%r) or 0)) + 1\n    vars[%r] = n\n" % (counter, counter))
    for k, v in (reset or {}).items():
        out += "    vars[%r] = %r\n" % (k, v)
    out += ("    vars[%r] = %r if n >= %d else %r\nexcept Exception:\n    vars[%r] = %r\n"
            % (route_var, over, int(limit), under, route_var, under))
    return out


# ----------------------------------------------------------------------------------------------- assembly & checks
def _no_none(o, path, errors):
    if o is None:
        errors.append("null value at %s" % path)
    elif isinstance(o, dict):
        for k, v in o.items():
            _no_none(v, "%s.%s" % (path, k), errors)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _no_none(v, "%s[%d]" % (path, i), errors)


def _check_code(code, where, errors):
    if not isinstance(code, str):
        errors.append("%s: code is not a string" % where)
        return
    if "{{" in code or "}}" in code:
        errors.append("%s: code contains '{{' or '}}' (read values from vars instead)" % where)
    try:
        compile(code, where, "exec")
    except SyntaxError as e:
        errors.append("%s: code does not compile: %s" % (where, e))


def _model_fields(tool):
    """Body fields the model fills: default is exactly "{{<name>}}"."""
    try:
        props = tool["function"]["parameters"]["properties"]["body"]["properties"]
    except (KeyError, TypeError):
        return []
    out = []
    for f, leaf in props.items():
        d = leaf.get("default") if isinstance(leaf, dict) else None
        m = re.fullmatch(r"\{\{(\w+)\}\}", str(d)) if isinstance(d, str) else None
        if m and f != CUSTOMER_ID:
            out.append((f, m.group(1)))
    return out


def check(wf):
    """Structural checks. Raises ValueError listing every problem; returns a list of warnings.
    Errors: null anywhere; unknown initial_node; node name != key; transition target or passthrough_default_transition
    missing; passthrough node not ending with an always transition; tools on a non-conversation node or pre_actions
    on a conversation node; api_request/code node without pre_actions; code or hook that does not compile or has
    '{{'/'}}'; end_call node without a proper terminal or with transitions; a node from which no end_call is
    reachable; a global node without a condition, with a transition to an unknown node (``__previous__`` is
    allowed), or passthrough without a final always transition. Warnings: node unreachable from initial_node; a model-filled tool field that shares its name with a
    test variable or an extracted variable; a workflow-level tool without alwaysRunsAt (it would never run)."""
    errors, warnings = [], []
    nodes = wf.get("nodes") or {}
    _no_none(wf, "workflow", errors)
    if not isinstance(nodes, dict) or not nodes:
        errors.append("workflow has no nodes")
        raise ValueError("workflow check failed:\n- " + "\n- ".join(errors))
    if wf.get("initial_node") not in nodes:
        errors.append("initial_node %r is not a node" % wf.get("initial_node"))
    known_vars = set((wf.get("test_variables") or {}).keys())
    for n in nodes.values():
        for e in n.get("extraction_schema") or []:
            if isinstance(e, dict) and e.get("name"):
                known_vars.add(e["name"])
    succ = {}
    for key, n in nodes.items():
        where = "node %r" % key
        if n.get("name") != key:
            errors.append("%s: name %r differs from its key" % (where, n.get("name")))
        nt = n.get("node_type")
        trs = n.get("transitions") or []
        targets = []
        for i, t in enumerate(trs):
            tgt = t.get("target_node") if isinstance(t, dict) else None
            if tgt != "__previous__" and tgt not in nodes:
                errors.append("%s: transition %d targets unknown node %r" % (where, i, tgt))
            else:
                targets.append(tgt)
            if isinstance(t, dict) and "condition" not in t:
                errors.append("%s: transition %d has no condition" % (where, i))
        if n.get("passthrough"):
            if not trs or (trs[-1].get("condition") or {}).get("operator") != "always":
                errors.append("%s: passthrough node does not end with an always transition" % where)
            pdt = n.get("passthrough_default_transition")
            if pdt not in nodes:
                errors.append("%s: passthrough_default_transition %r is not a node" % (where, pdt))
            else:
                targets.append(pdt)
        if nt == "conversation":
            if n.get("pre_actions"):
                errors.append("%s: pre_actions on a conversation node (the platform strips them)" % where)
            if not trs:
                errors.append("%s: conversation node has no transitions" % where)
        elif n.get("tools"):
            errors.append("%s: tools on a %s node (the platform strips them)" % (where, nt))
        if nt in ("api_request", "code"):
            if not n.get("pre_actions"):
                errors.append("%s: %s node has no pre_actions" % (where, nt))
            if not n.get("passthrough"):
                warnings.append("%s: %s node is not passthrough" % (where, nt))
        if nt == "code":
            for pa in n.get("pre_actions") or []:
                try:
                    _check_code(pa["function"]["parameters"]["properties"]["code"]["default"], where + " code", errors)
                except (KeyError, TypeError):
                    errors.append("%s: code node pre_action has no code default" % where)
        if nt == "end_call":
            term = n.get("terminal") or {}
            fn = term.get("function") or {}
            if fn.get("handler") != "__function__:end_call" or not fn.get("name"):
                errors.append("%s: end_call node has no terminal with an end_call handler and a name" % where)
            if trs:
                errors.append("%s: end_call node has transitions" % where)
        for t in (n.get("tools") or []) + (n.get("pre_actions") or []):
            tname = ((t.get("function") or {}).get("name")) if isinstance(t, dict) else None
            for hk in ("pre_process_code", "post_process_code"):
                if isinstance(t, dict) and t.get(hk):
                    _check_code(t[hk], "%s tool %r %s" % (where, tname, hk), errors)
            if nt == "conversation" and isinstance(t, dict):
                for f, var in _model_fields(t):
                    if var in known_vars:
                        warnings.append("%s tool %r: model-filled field %r reads {{%s}}, which is a known variable: it "
                                        "would be baked and hidden from the model" % (where, tname, f, var))
        succ[key] = targets
    # global nodes: interrupt handlers entered on their own condition from any node
    gnodes = wf.get("global_nodes") or {}
    if not isinstance(gnodes, dict):
        errors.append("global_nodes is not an object")
        gnodes = {}
    for key, n in gnodes.items():
        where = "global node %r" % key
        if not isinstance(n, dict):
            errors.append("%s: not an object" % where)
            continue
        if key in nodes:
            errors.append("%s: same key used in nodes" % where)
        if n.get("name") != key:
            errors.append("%s: name %r differs from its key" % (where, n.get("name")))
        if not isinstance(n.get("condition"), dict) or not n.get("condition"):
            errors.append("%s: has no condition (it would never activate)" % where)
        trs = n.get("transitions") or []
        for i, t in enumerate(trs):
            tgt = t.get("target_node") if isinstance(t, dict) else None
            if tgt != "__previous__" and tgt not in nodes and tgt not in gnodes:
                errors.append("%s: transition %d targets unknown node %r" % (where, i, tgt))
            if isinstance(t, dict) and "condition" not in t:
                errors.append("%s: transition %d has no condition" % (where, i))
        if n.get("passthrough"):
            if not trs or (trs[-1].get("condition") or {}).get("operator") != "always":
                errors.append("%s: passthrough node does not end with an always transition" % where)
            pdt = n.get("passthrough_default_transition")
            if pdt != "__previous__" and pdt not in nodes and pdt not in gnodes:
                errors.append("%s: passthrough_default_transition %r is not a node" % (where, pdt))
        if n.get("node_type", "conversation") == "conversation" and n.get("pre_actions"):
            errors.append("%s: pre_actions on a conversation node (the platform strips them)" % where)
        elif n.get("node_type", "conversation") != "conversation" and n.get("tools"):
            errors.append("%s: tools on a %s node (the platform strips them)" % (where, n.get("node_type")))
        for t in (n.get("tools") or []) + (n.get("pre_actions") or []):
            tname = ((t.get("function") or {}).get("name")) if isinstance(t, dict) else None
            for hk in ("pre_process_code", "post_process_code"):
                if isinstance(t, dict) and t.get(hk):
                    _check_code(t[hk], "%s tool %r %s" % (where, tname, hk), errors)
        if n.get("node_type") == "code":
            for pa in n.get("pre_actions") or []:
                try:
                    _check_code(pa["function"]["parameters"]["properties"]["code"]["default"], where + " code", errors)
                except (KeyError, TypeError):
                    errors.append("%s: code node pre_action has no code default" % where)
    for t in wf.get("tools") or []:
        tname = ((t.get("function") or {}).get("name")) if isinstance(t, dict) else None
        if not (t.get("config") or {}).get("alwaysRunsAt"):
            warnings.append("workflow tool %r has no config.alwaysRunsAt: it never runs" % tname)
        for hk in ("pre_process_code", "post_process_code"):
            if t.get(hk):
                _check_code(t[hk], "workflow tool %r %s" % (tname, hk), errors)
    # every node reaches an end_call node
    ends = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    reach_end = set(ends)
    changed = True
    while changed:
        changed = False
        for k, tg in succ.items():
            if k not in reach_end and any(x in reach_end for x in tg):
                reach_end.add(k)
                changed = True
    for k in nodes:
        if k not in reach_end:
            errors.append("node %r: no end_call node is reachable from it" % k)
    # reachability from the initial node (warning only)
    if wf.get("initial_node") in nodes:
        seen, q = {wf["initial_node"]}, deque([wf["initial_node"]])
        while q:
            for x in succ.get(q.popleft(), []):
                if x in nodes and x not in seen:
                    seen.add(x)
                    q.append(x)
        for k in nodes:
            if k not in seen:
                warnings.append("node %r is not reachable from initial_node" % k)
    if errors:
        raise ValueError("workflow check failed:\n- " + "\n- ".join(errors))
    return warnings


def assemble(initial_node, nodes, system_prompt, tools=None, test_variables=None, global_nodes=None, strict=True):
    """The workflow dict (initial_node, system_prompt, nodes, global_nodes, tools, test_variables), checked.
    With strict=True (default) check() errors raise ValueError and warnings are printed to stderr; nothing
    is added to the dict. Leave agent_config out: the platform fills it in."""
    import sys
    wf = {"initial_node": initial_node, "system_prompt": system_prompt, "nodes": nodes,
          "global_nodes": global_nodes or {}, "tools": list(tools or []), "test_variables": dict(test_variables or {})}
    if strict:
        for w in check(wf):
            print("freyalib warning: " + w, file=sys.stderr)
    return wf


def write_workflow(wf, path):
    """Write the workflow JSON (indent 1, like the proven generator). Creates the parent directory."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(wf, f, indent=1)
    return str(p)
