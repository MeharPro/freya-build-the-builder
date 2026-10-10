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
    missing = set(req) - set(fields)
    if missing:
        raise ValueError("Required API fields have no schema: %s" % sorted(missing))
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
        raise ValueError("Cannot omit required API fields: %s" % sorted(omit & set(spec["required"])))
    props = {}
    if CUSTOMER_ID in spec["fields"]:
        props[CUSTOMER_ID] = {"type": spec["fields"][CUSTOMER_ID]["type"], "default": "{{%s}}" % CUSTOMER_ID}
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
    if set(required) - set(props):
        raise ValueError("Required fields absent from generated request")
    model_fields = set(spec["required"]) - set(baked) - {CUSTOMER_ID}
    if model_fields - set(required):
        raise ValueError("Required model fields dropped: %s" % sorted(model_fields - set(required)))
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


def opening_conv(name, opening_line, task, extraction, max_turns=60):
    """The initial conversation node that speaks `opening_line` word for word. On a phone call the on_enter tts says it;
    on the chat route (smoke, sim.py) the engine answers the customer's first line with the dialogue model instead of
    the tts (seen on Briefs C and D), so the task repeats the line as the model's first message. `task` is what to do
    after the line has been said. Pass the node to conversation_first() as usual."""
    lead = ("If you have not spoken yet in this call, your message is exactly: \"%s\" (word for word, nothing before or "
            "after it). Otherwise: " % opening_line)
    return conv(name, lead + task, on_enter={"type": "tts", "text": opening_line}, extraction=extraction,
                first_only=True, max_turns=max_turns)


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


def ext(name, values, desc, conf=0.5, type="string"):
    """An extraction_schema entry with enum values. Always set min_confidence (the default 0.95 drops most values;
    0.6 dropped a plain "Yes, I confirm." extracted at 0.59 on the platform, so 0.5)."""
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
                fields=None, stop_left=("0",)):
    """Post hook for one identity question. `hints` maps a response hint value to the text for it (checked first,
    a hint is not a wrong answer). `max_wrong_text` is used when the wrong-answers counter reaches 0.
    `fields` renames the response fields: {"hint", "all_verified", "verified", "ok", "left"}.
    `stop_left` = the wrong_answers_left values at which the check is over (default ("0",), the service's own
    limit). A brief stricter than the service (e.g. "the second wrong answer ends the check" on a service that
    allows three) passes the values that mean "limit reached", e.g. ("1", "0"); route the node on the same values.
    The default texts are generic placeholders: a generator should pass the brief's own wording for every text
    (all_verified_text, verified_text, unreadable_text, wrong_text, max_wrong_text), e.g. what the brief says the
    agent does once identity is verified, how many questions there are, how a wrong answer is worded."""
    f = {"hint": "hint", "all_verified": "all_verified", "verified": "verified", "ok": "ok", "left": "wrong_answers_left"}
    f.update(fields or {})
    q = lambda s: s.replace("{question}", question)
    stops = tuple(str(x) for x in stop_left)
    stop = "str(left) == %r" % stops[0] if len(stops) == 1 else "str(left) in %r" % (stops,)
    branches = [("d.get(%r) == %r" % (f["hint"], v), t) for v, t in (hints or {}).items()]
    branches += [(truthy(f["all_verified"]), all_verified_text), (truthy(f["verified"]), verified_text),
                 (falsy(f["ok"]), q(unreadable_text)), (stop, max_wrong_text)]
    return what_next_post(branches, q(wrong_text), prelude=["left = d.get(%r)" % f["left"]])


def verify_count_post(question, limit, hints, limit_text, route_var="id_route", counter="id_wrong",
                      free_hints=None, all_verified_text="All security questions passed. Identity is verified.",
                      verified_text="Correct. Ask the next security question.",
                      unreadable_text="The answer could not be read. It does not count as wrong. Ask again: {question}",
                      wrong_text="Wrong answer. Tell the customer it does not match our records and ask again: {question}",
                      service_limit_text=None):
    """Identity-question post hook that keeps the brief's OWN wrong-answer counter in vars (for a brief whose limit
    is stricter than the service's, or that counts some hints as wrong). vars[counter] counts wrong answers across
    every question; when it reaches `limit` (or the service's wrong_answers_left reaches 0) vars[route_var] =
    'exhausted', else 'open'. Route on eq(route_var, 'exhausted', ...). `hints` {value: text}; `free_hints`
    {value: n} = the first n such hints per call are not wrong answers, later ones count (vars['hint_<value>']
    counts them). Needs a hook with `vars` (seen working 10 Oct); the service counter stays as a fallback."""
    free_hints = dict(free_hints or {})
    qq = lambda t: t.replace("{question}", question)
    code = ("try:\n    if isinstance(result, dict):\n        result.pop('header', None)\n        d = result.get('data')\n"
            "        try:\n            V = vars\n        except Exception:\n            V = None\n"
            "        if isinstance(d, dict):\n            nw = int(float((V or {}).get(%r) or 0))\n            wrong = False\n"
            "            hint = d.get('hint')\n            msg = None\n" % counter)
    for i, (hv, text) in enumerate((hints or {}).items()):
        code += "            %s hint == %r:\n" % ("if" if i == 0 else "elif", hv)
        if hv in free_hints:
            code += ("                nh = int(float((V or {}).get(%r) or 0)) + 1\n"
                     "                if V is not None:\n                    V[%r] = str(nh)\n"
                     "                if nh > %d:\n                    wrong = True\n"
                     "                else:\n                    msg = %r\n" % ("hint_" + hv, "hint_" + hv, int(free_hints[hv]), text))
        else:
            code += "                msg = %r\n" % text
    code += ("            if msg is None and not wrong:\n"
             "                if %s:\n                    msg = %r\n"
             "                elif %s:\n                    msg = %r\n"
             "                elif %s:\n                    msg = %r\n"
             "                else:\n                    wrong = True\n"
             % (truthy("all_verified"), all_verified_text, truthy("verified"), verified_text, falsy("ok"), qq(unreadable_text)))
    code += ("            if wrong:\n                nw += 1\n"
             "            left = d.get('wrong_answers_left')\n"
             "            done = nw >= %d or str(left) == '0'\n"
             "            if V is not None:\n                V[%r] = str(nw)\n                V[%r] = 'exhausted' if done else 'open'\n"
             "            if done:\n                msg = %r\n"
             "            elif wrong:\n                msg = %r\n"
             "            d['what_to_do_next'] = msg\n"
             "except Exception:\n    pass\n"
             % (int(limit), counter, route_var, limit_text, qq(wrong_text)))
    return code


def promise_state_pre(full_var, amount_field="amount", date_field="date", amount_var="promise_amount",
                      date_var="promise_date"):
    """Pre hook of a promise tool for briefs whose closing reason depends on the recorded amount: normalises the
    amount (float) and date ([:10]) like promise_pre, and stores them in vars[amount_var] / vars[date_var];
    vars['promise_kind'] = 'full' when the amount equals vars[full_var] (the full amount, written by code) else
    'partial'. A fin node reads promise_kind (see promise_reason_code)."""
    return ("try:\n    b = config.get('body')\n    if isinstance(b, dict):\n"
            "        if %r in b:\n            b[%r] = float(str(b[%r]).replace(',', '').strip())\n"
            "        if %r in b:\n            b[%r] = str(b[%r]).strip()[:10]\n"
            "        try:\n            V = vars\n        except Exception:\n            V = None\n"
            "        if V is not None:\n            V[%r] = str(b.get(%r))\n            V[%r] = str(b.get(%r))\n"
            "            try:\n                full = float(V.get(%r))\n                amt = float(b.get(%r))\n"
            "                V['promise_kind'] = 'full' if abs(amt - full) < 0.005 else 'partial'\n"
            "            except Exception:\n                pass\nexcept Exception:\n    pass\n"
            % (amount_field, amount_field, amount_field, date_field, date_field, date_field,
               amount_var, amount_field, date_var, date_field, full_var, amount_field))


def promise_state_post(max_calls, recorded_text, retry_text, give_up_text, route_var="promise_route",
                       counter="promise_fails", ok_field="ok"):
    """Post hook of a promise tool with the brief's retry count: on ok true vars['promise_done'] = 'yes' and
    vars[route_var] = 'recorded'; otherwise vars[counter] += 1 and vars[route_var] = 'fault' once `max_calls`
    calls failed (e.g. 3 = 'up to two more times'), else 'retry'. Route on eq(route_var, ...); ok_true and the
    engine failure counters stay as fallbacks."""
    return ("try:\n    if isinstance(result, dict):\n        result.pop('header', None)\n        d = result.get('data')\n"
            "        try:\n            V = vars\n        except Exception:\n            V = None\n"
            "        ok = isinstance(d, dict) and %s\n"
            "        if ok:\n            if V is not None:\n                V['promise_done'] = 'yes'\n                V[%r] = 'recorded'\n"
            "            d['what_to_do_next'] = %r\n"
            "        else:\n            n = int(float((V or {}).get(%r) or 0)) + 1\n"
            "            if V is not None:\n                V[%r] = str(n)\n                V[%r] = 'fault' if n >= %d else 'retry'\n"
            "            if isinstance(d, dict):\n                d['what_to_do_next'] = %r if n >= %d else %r\n"
            "except Exception:\n    pass\n"
            % (truthy(ok_field), route_var, recorded_text, counter, counter, route_var, int(max_calls),
               give_up_text, int(max_calls), retry_text))


def promise_reason_code(outcome="promise", default_kind="full", outcome_var="outcome", reason_var="reason"):
    """fin node code for a promise ending whose reason is vars['promise_kind'] (promise_state_pre)."""
    return ("try:\n    vars[%r] = %r\n    k = str(vars.get('promise_kind') or %r)\n"
            "    vars[%r] = k if k in ('full', 'partial') else %r\nexcept Exception:\n    pass\n"
            % (outcome_var, outcome, default_kind, reason_var, default_kind))


def promise_or_code(outcome, reason, promise_outcome="promise", default_kind="full", outcome_var="outcome",
                    reason_var="reason"):
    """fin node code for an ending that a recorded promise overrides ('if a transfer takes place after a promise
    was recorded, the promise decides'): promise/<promise_kind> when vars['promise_done'] == 'yes', else
    outcome/reason."""
    return ("try:\n    if str(vars.get('promise_done') or '') == 'yes':\n        vars[%r] = %r\n"
            "        k = str(vars.get('promise_kind') or %r)\n        vars[%r] = k if k in ('full', 'partial') else %r\n"
            "    else:\n        vars[%r] = %r\n        vars[%r] = %r\nexcept Exception:\n    pass\n"
            % (outcome_var, promise_outcome, default_kind, reason_var, default_kind, outcome_var, outcome, reason_var, reason))


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
WDRULE = __WDRULE__
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
def prev_bd(d):
    guard = 0
    while not isbd(d) and guard < 4000:
        d = d - datetime.timedelta(days=1)
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
def weekday_table_first_after(today):
    tab = []
    for k in range(1, 8):
        a = today + datetime.timedelta(days=k)
        tab.append('"this ' + WD[a.weekday()] + '" = "next ' + WD[a.weekday()] + '" = ' + txt(a))
    return '\n'.join(tab)
if WDRULE == 'first_after':
    weekday_table = weekday_table_first_after
def calendar_text(today, deadline, extra_days=10):
    cal = []
    d = today
    while d <= deadline + datetime.timedelta(days=extra_days):
        if d > deadline:
            tag = 'AFTER THE DEADLINE, not allowed'
        elif isbd(d):
            tag = 'allowed'
        elif d.weekday() not in BWD:
            tag = 'not a business day (' + WD[d.weekday()] + '), not allowed'
        else:
            tag = 'bank holiday, not allowed'
        nb = next_bd(d)
        extra = ''
        if tag.startswith('not a business day') or tag.startswith('bank'):
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


def CAL_HELPERS(holidays, business_weekdays=BUSINESS_WEEKDAYS, weekday_rule="this_week"):
    """Python source (for the top of a code node) defining, on datetime.date values:
    isbd(d) business day?; next_bd(d) / prev_bd(d) d itself or the first business day after / before it; txt(d) 'Friday 16 October 2026'; txt_short(d) without the year; addbd(d, n) n business
    days later; next_bd(d) d or the first business day after it; lastbd_of_week(monday) last business day of that
    week or None; weekday_table(today) the '"this Monday" = ...; "next Monday" = ...' table; calendar_text(today,
    deadline, extra_days=10) one tagged line per day (allowed / weekend / bank holiday / after the deadline, with the
    next business day); fmt(x) '420.5' / '420' / '420.25'. Also imports datetime, json, re. No '{{' or '}}'.
    `weekday_rule`: "this_week" ("this X" = X of the current week, "next X" = a week later) or "first_after"
    (both "this X" and "next X" = the first X after today), as the brief defines the words."""
    if weekday_rule not in ("this_week", "first_after"):
        raise ValueError("weekday_rule must be 'this_week' or 'first_after', got %r" % weekday_rule)
    import datetime
    weekdays = list(business_weekdays)
    if not weekdays or any(type(x) is not int or not 0 <= x <= 6 for x in weekdays):
        raise ValueError("business_weekdays must be nonempty integers from 0 to 6")
    hol = sorted(set(str(h) for h in holidays or []))
    for holiday in hol:
        if datetime.date.fromisoformat(holiday).isoformat() != holiday:
            raise ValueError("holiday must be an ISO date")
    return _CAL_HELPERS.replace("__HOLIDAYS__", repr(hol)).replace("__BWD__", repr(sorted(set(weekdays)))) \
                       .replace("__WDRULE__", repr(weekday_rule))


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
               now_var="now", state_var="setup_state", weekday_rule="this_week"):
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
    return CAL_HELPERS(holidays, business_weekdays, weekday_rule) + guarded(body, state_var, fb, fb_code)


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


# --- how customers talk (brief-agnostic). Measured on the organisers' simulator with the kit's styles: small talk at a
# security question was read as a refusal (3 calls closed as declined), "how much can I pay instead?" became a plan
# request (a transfer), and sympathy was said for a busy day (the judge counts sympathy sentences).
PERSONA_CONDUCT = (
    "How customers talk: they add small talk, give a number or a date in two parts, correct themselves, ask a question back, "
    "or say amounts and dates in words. The facts stay the same.\n"
    "- Keep to the business of the call. Do not comment on small talk (a busy day, the traffic, a family event) and do not "
    "sympathise with it: sympathy is only for what the rules name.\n"
    "- A message with no answer in it (small talk, a cut-off sentence, 'hmm') is NOT a refusal and NOT a request. If it "
    "stops mid-sentence, say only: 'Sorry, I think you were cut off. Please go on.' Otherwise ask for the answer in one short "
    "sentence; at a security question repeat the question, at a payment proposal do not repeat the amount or the date word "
    "for word (an offer is made once).\n"
    "- A question back (why do you need that, which account, who is this) gets one short answer, then the same question again, "
    "unless the rules say such a question counts. Only what the rules name counts as a refusal.\n"
    "- When a number or a date arrives in parts, wait for the complete value before calling a tool and combine the parts in "
    "order. When the customer corrects a value, the last value stated counts: read that one back.\n"
    "- A question about how much they can, should or have to pay is not a request for a payment plan: propose the amount "
    "the rules give you.")
# appended by builder/policy.py to every enum on the payment nodes (topic, stance, offer_kind, confirm, hs_answer, wrap,
# aside): a persona's cut-off line ("I've been so stressed because my cousin's") was labelled hardship on Freya, and a
# string of cut-off small-talk lines became refusals (talkative style, 10 Oct)
CUTOFF_CLAUSE = (" A cut-off message (it stops mid-sentence, e.g. on 'my', 'the', 'because', 'at') or small talk with no "
                 "answer in it gets the neutral value, even when it contains words like stressed, busy, tired, family, "
                 "wedding or work: judge only what the customer actually said, never where the sentence might be going.")


def with_cutoff(entries, neutral=("none", "other")):
    """Copies of extraction entries with CUTOFF_CLAUSE appended to every enum entry that has a neutral value
    (none/other) and does not carry the clause yet. Non-enum entries are returned unchanged."""
    out = []
    for e in entries or []:
        e = dict(e)
        vals = e.get("enum_values") or []
        if vals and any(v in neutral for v in vals) and CUTOFF_CLAUSE not in str(e.get("description") or ""):
            e["description"] = str(e.get("description") or "") + CUTOFF_CLAUSE
        out.append(e)
    return out


# append to every refusal / decline enum description (the brief's own list of what counts goes first)
REFUSAL_NONE_CLAUSE = (" Small talk, an unrelated sentence, a cut-off or empty message, a partial answer, or a question back "
                       "that the rules do not count is none, never refused: only what the rules name counts.")
# the `question` value of a refusal/decline enum (a question back is not a refusal until it replaces the answer twice)
QUESTION_ENUM_CLAUSE = (" question = asks something back instead of answering (why do you need that, which account or what this is "
                        "about, who is calling) without refusing; refused is only an explicit refusal or not wanting to talk.")


def reset_pre(names):
    """Tool pre hook: zero the named counters (e.g. question_count_<stage> once an answer reaches the identity tool)."""
    return "try:\n" + "".join("    vars[%r] = 0\n" % n for n in names) + "except Exception:\n    pass\n"


def question_back_node(stage, ask_node, close_node, limit=2, flag=None):
    """Code node qb_<stage> for a question asked back at an identity question. The first question is answered and the
    question is asked again (always -> ask_node); the `limit`-th question in a row with no answer in between is a
    deflection and routes to close_node (the brief's "asked instead of answering" close). Measured on the organisers'
    simulator: counting every question back as a refusal closed 4 of 10 calls as declined under the kit's asks_back
    style, whose customer asks twice and then answers. Reset the counter with reset_pre on the identity tool."""
    flag = flag or "refusal_%s" % stage
    code = counter_code("question_count_%s" % stage, limit, "qb_route", reset={flag: "none"})
    return code_node("qb_%s" % stage, code, [eq("qb_route", "close", close_node, "a second question back instead of an answer"),
                                            always(ask_node)])


# append to every plan-request enum description
PLAN_REQUEST_CLAUSE = (" Asking how much they can, should or have to pay, or naming an amount or a date, is NOT a plan "
                       "request: the agent proposes the amount.")


def assemble(initial_node, nodes, system_prompt, tools=None, test_variables=None, global_nodes=None, strict=True,
             conduct=False):
    """The workflow dict (initial_node, system_prompt, nodes, global_nodes, tools, test_variables), checked.
    With strict=True (default) check() errors raise ValueError and warnings are printed to stderr; nothing
    is added to the dict. Leave agent_config out: the platform fills it in.
    conduct=True appends PERSONA_CONDUCT (how customers talk) to the system prompt (the skill's default)."""
    import sys
    if conduct and PERSONA_CONDUCT.split("\n")[0] not in (system_prompt or ""):
        system_prompt = (system_prompt or "").rstrip("\n") + "\n" + PERSONA_CONDUCT
    wf = {"initial_node": initial_node, "system_prompt": system_prompt, "nodes": nodes,
          "global_nodes": global_nodes or {}, "tools": list(tools or [])}
    if test_variables:
        wf["test_variables"] = dict(test_variables)
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


# ----------------------------------------------------------------------------------------------- speech normalisation
# T21 (docs/research/sota-techniques.md): customers say numbers in parts ("463..." then "51"), correct themselves,
# say dates, amounts and times in words. The model often passes the words through to the tool. A pre hook turns
# the spoken form into what the API expects, in code (rule-based, like production inverse text normalisation).
# The hook is idempotent (normal values pass through unchanged) and never raises; on any doubt it leaves the
# value as it is. Everything bank-specific (fields, date order, relative-day table) is a parameter.

NORMALISE_KINDS = ("digits", "date", "dob", "amount", "time", "answer")

_NORM_SRC = r'''def _nz_main(config, vars):
    import re, json, datetime
    FIELDS = __FIELDS__
    ORDER = __ORDER__
    NOW_VAR = __NOW_VAR__
    REL_VAR = __REL_VAR__
    PM_HOURS = __PM_HOURS__
    UNITS = dict(zero=0, oh=0, o=0, nought=0, nil=0, one=1, two=2, three=3, four=4, five=5, six=6, seven=7,
                 eight=8, nine=9)
    TEENS = dict(ten=10, eleven=11, twelve=12, thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17,
                 eighteen=18, nineteen=19)
    TENS = dict(twenty=20, thirty=30, forty=40, fourty=40, fifty=50, sixty=60, seventy=70, eighty=80, ninety=90)
    ORD = dict(first=1, second=2, third=3, fourth=4, fifth=5, sixth=6, seventh=7, eighth=8, ninth=9, tenth=10,
               eleventh=11, twelfth=12, thirteenth=13, fourteenth=14, fifteenth=15, sixteenth=16,
               seventeenth=17, eighteenth=18, nineteenth=19, twentieth=20, thirtieth=30)
    SCALES = dict(hundred=100, thousand=1000, million=1000000)
    MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
              'october', 'november', 'december']
    WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    CURRENCY = set(['dollar', 'dollars', 'pound', 'pounds', 'euro', 'euros', 'bucks', 'usd', 'eur', 'gbp',
                    'quid', 'rupees', 'francs'])
    FILLER = set(['um', 'umm', 'uh', 'uhh', 'er', 'erm', 'hmm', 'ah', 'well', 'so', 'ok', 'okay', 'yes', 'yeah',
                  'yep', 'sure', 'right', 'it', 'its', 'is', 'thats', 'that', 'my', 'the', 'are', 'was', 'were',
                  'then', 'and', 'i', 'think', 'believe', 'let', 'me', 'see', 'like', 'number', 'numbers',
                  'digit', 'digits', 'ends', 'ending', 'in', 'with', 'of', 'on', 'at', 'about', 'around',
                  'just', 'please', 'be', 'would', 'will', 'can', 'pay', 'say', 'lets', 'date', 'born', 'year',
                  'amount', 'time', 'by', 'for', 'a', 'an', 'exactly', 'only', 'now', 'here', 'there'])
    MARKERS = set(['no', 'sorry', 'actually', 'wait', 'correction', 'rather', 'nope', 'oops'])

    def clean(s, keep):
        s = str(s).lower().replace('’', "'")
        s = re.sub(r'\b([ap])\.\s?m\.?', r'\1m', s)
        s = s.replace("o'clock", ' oclock').replace("'", '')
        s = re.sub(r'(?<=[a-z])-(?=[a-z])', ' ', s)
        s = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', s)
        out = []
        for i, ch in enumerate(s):
            if ch.isalnum() or ch == ' ':
                out.append(ch)
            elif ch in keep and 0 < i < len(s) - 1 and s[i - 1].isdigit() and s[i + 1].isdigit():
                out.append(ch)
            else:
                out.append(' ')
        s = ''.join(out)
        s = re.sub(r'\bi mean\b|\bmake that\b|\bscratch that\b|\bor rather\b', ' sorry ', s)
        return s.split()

    def latest(toks):
        idx = -1
        for i, t in enumerate(toks):
            if t in MARKERS:
                idx = i
        if idx < 0:
            return toks
        after = [t for t in toks[idx + 1:] if t not in MARKERS]
        if [t for t in after if t not in FILLER]:
            return after
        return [t for t in toks[:idx] if t not in MARKERS]

    def expand(toks):
        out = []
        i = 0
        while i < len(toks):
            t = toks[i]
            if t in ('double', 'triple') and i + 1 < len(toks) and (toks[i + 1] in UNITS or re.fullmatch(r'\d', toks[i + 1])):
                out += [toks[i + 1]] * (2 if t == 'double' else 3)
                i += 2
                continue
            out.append(t)
            i += 1
        return out

    def is_num_word(t):
        return t in UNITS or t in TEENS or t in TENS or t in ORD or t in SCALES or bool(re.fullmatch(r'\d+', t))

    def segments(toks, amount=False):
        # A run of number words split into the groups a speaker says: "forty four seventy one" -> 44 | 71,
        # "four hundred and twenty" -> 420. Returns a list of [string, value, scaled] or None when a word is
        # neither a number nor a filler.
        segs = []
        cur = None
        n = len(toks)
        for i in range(n):
            t = toks[i]
            prev = toks[i - 1] if i else ''
            nxt = toks[i + 1] if i + 1 < n else ''
            if t in ('oh', 'o') and not (is_num_word(prev) or is_num_word(nxt)):
                continue
            if t == 'a' and nxt in SCALES:
                cur = dict(total=0, group=1, small=1, last='unit', scaled=False, lit=None)
                segs.append(cur)
                continue
            if re.fullmatch(r'\d+', t):
                v = int(t)
                cur = dict(total=0, group=v, small=v if v < 100 else 0, last='lit' if v >= 100 or not amount else 'unit',
                           scaled=False, lit=t)
                segs.append(cur)
                continue
            if t in UNITS or (t in ORD and ORD[t] < 10):
                u = UNITS[t] if t in UNITS else ORD[t]
                if u > 0 and cur is not None and cur['last'] in ('tens', 'scale'):
                    cur['group'] += u
                    cur['small'] += u
                    cur['last'] = 'unit'
                    cur['lit'] = None
                else:
                    cur = dict(total=0, group=u, small=u, last='unit', scaled=False, lit=None)
                    segs.append(cur)
                continue
            if t in TEENS or t in TENS or t in ORD:
                v = TEENS.get(t) or TENS.get(t) or ORD.get(t)
                kind = 'tens' if (t in TENS or v in (20, 30)) else 'teen'
                if cur is not None and cur['last'] == 'scale':
                    cur['group'] += v
                    cur['small'] += v
                    cur['last'] = kind
                    cur['lit'] = None
                else:
                    cur = dict(total=0, group=v, small=v, last=kind, scaled=False, lit=None)
                    segs.append(cur)
                continue
            if t in SCALES:
                m = SCALES[t]
                if cur is None or cur['last'] == 'scale':
                    return None
                if m == 100:
                    if cur['group'] != cur['small'] or cur['small'] == 0:
                        return None
                    cur['group'] = cur['small'] * 100
                else:
                    if cur['group'] == 0:
                        return None
                    cur['total'] += cur['group'] * m
                    cur['group'] = 0
                cur['small'] = 0
                cur['last'] = 'scale'
                cur['scaled'] = True
                cur['lit'] = None
                continue
            if t in FILLER or t in CURRENCY:
                continue
            return None
        out = []
        for c in segs:
            v = c['total'] + c['group']
            out.append([c['lit'] if c['lit'] is not None else str(v), v, c['scaled']])
        return out

    def to_digits(v):
        s = str(v).strip()
        if re.fullmatch(r'\d+', s):
            return s
        s = re.sub(r'\blast\s+(?:\w+\s+)?(?:digits?|numbers?)\b', ' ', s.lower())
        s = re.sub(r'\blast\s+(?:two|three|four|five|six|2|3|4|5|6)\b', ' ', s)
        toks = clean(s, '')
        toks = expand(latest(toks))
        segs = segments(toks)
        if not segs:
            return None
        r = ''.join(x[0] for x in segs)
        return r if re.fullmatch(r'\d+', r) else None

    def now_date():
        try:
            raw = str(vars.get(NOW_VAR) or '').strip()
            return datetime.date.fromisoformat(raw[:10]) if raw else None
        except Exception:
            return None

    def mkdate(y, m, d):
        try:
            return datetime.date(int(y), int(m), int(d))
        except Exception:
            return None

    def year_of(ys, past):
        if re.fullmatch(r'\d{4}', ys):
            return int(ys)
        if not re.fullmatch(r'\d{2}', ys):
            return None
        today = now_date()
        if today is None:
            return None
        yy = int(ys)
        if past:
            y = 2000 + yy
            return y if y <= today.year else 1900 + yy
        cands = [1900 + yy, 2000 + yy, 2100 + yy]
        cands.sort(key=lambda c: abs(c - today.year))
        return cands[0]

    def relative(toks):
        if not REL_VAR:
            return None
        table = vars.get(REL_VAR)
        if isinstance(table, str):
            try:
                table = json.loads(table)
            except Exception:
                return None
        if not isinstance(table, dict):
            return None
        words = [t for t in toks if t not in ('on', 'the', 'um', 'uh', 'er', 'erm', 'please', 'by', 'lets', 'say')]
        key = ' '.join(words)
        r = table.get(key)
        if isinstance(r, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', r):
            return r
        return None

    def to_date(v, past):
        s = str(v).strip()
        m = re.fullmatch(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[t ].*)?', s.lower())
        if m:
            d = mkdate(m.group(1), m.group(2), m.group(3))
            return d.isoformat() if d else None
        toks = latest(clean(s, '/.-'))
        if not toks:
            return None
        r = relative(toks)
        if r:
            return r
        toks = [t for t in toks if t not in WEEKDAYS]
        mon = []
        for i, t in enumerate(toks):
            for k, name in enumerate(MONTHS):
                if t == name or t == name[:3] or (t == 'sept' and k == 8):
                    mon.append((i, k + 1))
                    break
        if len(mon) > 1:
            return None
        if mon:
            i, month = mon[0]
            before = segments(toks[:i])
            after = segments(toks[i + 1:])
            if before is None or after is None:
                return None
            if before:
                if len(before) != 1:
                    return None
                day = before[0][1]
                yparts = after
            else:
                if not after:
                    return None
                day = after[0][1]
                yparts = after[1:]
            if yparts:
                y = year_of(''.join(x[0] for x in yparts), past)
                if y is None:
                    return None
                d = mkdate(y, month, day)
                return d.isoformat() if d else None
            if past:
                return None
            today = now_date()
            if today is None:
                return None
            d = mkdate(today.year, month, day)
            if d is not None and d < today:
                d = mkdate(today.year + 1, month, day)
            return d.isoformat() if d else None
        joined = ' '.join(toks)
        m = re.fullmatch(r'(\d{1,2})[/.\- ](\d{1,2})[/.\- ](\d{2}|\d{4})', joined)
        if m:
            a, b, ys = int(m.group(1)), int(m.group(2)), m.group(3)
        else:
            m8 = re.fullmatch(r'\d{8}', joined)
            if m8:
                if joined[:2] in ('19', '20'):
                    d = mkdate(joined[:4], joined[4:6], joined[6:])
                    if d:
                        return d.isoformat()
                a, b, ys = int(joined[:2]), int(joined[2:4]), joined[4:]
            else:
                segs = segments(toks)
                if not segs or len(segs) < 3 or segs[0][2] or segs[1][2] or segs[0][1] == 0 or segs[1][1] == 0:
                    return None
                a, b = segs[0][1], segs[1][1]
                ys = ''.join(x[0] for x in segs[2:])
        y = year_of(ys, past)
        if y is None:
            return None
        day, month = (a, b) if ORDER == 'dmy' else (b, a)
        d = mkdate(y, month, day)
        if d is None:
            d = mkdate(y, day, month)
        return d.isoformat() if d else None

    def to_amount(v):
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().lower()
        cents = 0.0
        m = re.fullmatch(r'(.*?)\s*(?:dollars?|pounds?|euros?|bucks)\s*(?:and\s+)?(.+?)\s*(?:cents?|pence)', s)
        if m:
            c = to_amount(m.group(2))
            if c is None or c >= 100:
                return None
            cents = c / 100.0
            s = m.group(1)
        s = re.sub(r'[$£€]', ' ', s)
        toks = latest(clean(s, ',.'))
        toks = [t for t in toks if t not in CURRENCY]
        mult = 1.0
        if toks and re.fullmatch(r'[\d.,]+k', toks[-1]):
            toks[-1] = toks[-1][:-1]
            mult = 1000.0
        elif len(toks) >= 2 and toks[-1] == 'k':
            toks = toks[:-1]
            mult = 1000.0
        if len(toks) == 1 and re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+', toks[0]):
            return round(float(toks[0].replace(',', '')) * mult + cents, 2)
        dec = ''
        if 'point' in toks:
            k = toks.index('point')
            dd = to_digits(' '.join(toks[k + 1:]))
            if not dd:
                return None
            dec = '.' + dd
            toks = toks[:k]
        segs = segments(toks, amount=True)
        if segs == [] and dec:
            segs = [['0', 0, False]]
        if not segs:
            return None
        if len(segs) == 1:
            whole = segs[0][1]
        elif len(segs) == 2 and not segs[0][2] and not segs[1][2] and segs[0][1] < 100 and 10 <= segs[1][1] < 100 and segs[0][0].isdigit() and len(segs[0][0]) <= 2:
            whole = segs[0][1] * 100 + segs[1][1]
        elif len(segs) == 3 and not any(x[2] for x in segs) and 0 < segs[0][1] < 100 and segs[1][1] == 0 and segs[1][0] == '0' and segs[2][1] < 10:
            whole = segs[0][1] * 100 + segs[2][1]
        else:
            return None
        return round(float(str(whole) + dec) * mult + cents, 2)

    def to_time(v):
        s = str(v).strip().lower()
        if re.fullmatch(r'\d{2}:\d{2}', s):
            return s if int(s[:2]) < 24 and int(s[3:]) < 60 else None
        s = re.sub(r'(\d)\s*([ap])\.?\s?m\b\.?', r'\1 \2m', s)
        toks = latest(clean(s, ':.'))
        txt = ' ' + ' '.join(toks) + ' '
        mer = ''
        if re.search(r' (am|in the morning|morning) ', txt):
            mer = 'am'
        if re.search(r' (pm|in the afternoon|afternoon|in the evening|evening|at night|tonight) ', txt):
            mer = 'pm' if not mer else 'x'
        if mer == 'x':
            return None
        txt = re.sub(r' (am|pm|in the morning|in the afternoon|in the evening|at night|morning|afternoon|evening|tonight|oclock|minutes|mins|hours|hrs|sharp) ', ' ', txt)
        txt = re.sub(r' (am|pm|in the morning|in the afternoon|in the evening|at night|morning|afternoon|evening|tonight|oclock|minutes|mins|hours|hrs|sharp) ', ' ', txt)
        toks = [t for t in txt.split() if t not in ('at', 'about', 'around', 'say', 'lets', 'the', 'by', 'um', 'uh', 'er', 'erm', 'please', 'maybe')]
        if toks in (['noon'], ['midday']):
            return '12:00'
        if toks == ['midnight']:
            return '00:00'
        h = mi = None

        def num(ws):
            if len(ws) == 1 and re.fullmatch(r'\d{1,2}', ws[0]):
                return int(ws[0])
            if ws == ['half']:
                return 30
            if ws in (['quarter'], ['a', 'quarter']):
                return 15
            sg = segments(ws)
            if sg and len(sg) == 1 and not sg[0][2]:
                return sg[0][1]
            if sg and len(sg) == 2 and sg[0][1] == 0 and sg[1][1] < 10:
                return sg[1][1]
            return None
        for rel in ('past', 'after', 'to', 'before', 'till', 'til'):
            if rel in toks:
                k = toks.index(rel)
                a, b = num(toks[:k]), num(toks[k + 1:])
                if a is None or b is None or a >= 60:
                    return None
                if rel in ('past', 'after'):
                    h, mi = b, a
                else:
                    h, mi = b - 1, 60 - a
                    if h < 0:
                        h = 23
                break
        if h is None:
            if len(toks) == 1 and re.fullmatch(r'\d{1,2}[:.]\d{2}', toks[0]):
                h, mi = int(toks[0][:-3]), int(toks[0][-2:])
            elif len(toks) == 1 and re.fullmatch(r'\d{1,2}', toks[0]):
                h, mi = int(toks[0]), 0
            elif len(toks) == 2 and all(re.fullmatch(r'\d{1,2}', t) for t in toks):
                h, mi = int(toks[0]), int(toks[1])
            else:
                sg = segments(toks)
                if not sg or any(x[2] for x in sg):
                    return None
                if len(sg) == 1:
                    h, mi = sg[0][1], 0
                elif len(sg) == 2:
                    h, mi = sg[0][1], sg[1][1]
                elif len(sg) == 3 and sg[1][1] == 0 and sg[2][1] < 10:
                    h, mi = sg[0][1], sg[2][1]
                else:
                    return None
        if h is None or mi is None or not (0 <= mi < 60) or not (0 <= h < 24):
            return None
        if mer == 'pm' and h < 12:
            h += 12
        elif mer == 'am' and h == 12:
            h = 0
        elif mer == 'am' and h > 12:
            return None
        elif not mer and h in PM_HOURS:
            h += 12
        return '%02d:%02d' % (h, mi)

    def kind_for(name, kind, body):
        if kind != 'answer':
            return kind
        f = str(body.get('field') or body.get('question') or '').lower()
        if re.search(r'date|birth|dob', f):
            return 'dob'
        if f:
            return 'digits'
        return 'answer'

    body = config.get('body') if isinstance(config, dict) else None
    if not isinstance(body, dict):
        return
    for name in FIELDS:
        try:
            if name not in body:
                continue
            val = body.get(name)
            if val is None or (isinstance(val, str) and not val.strip()):
                continue
            kind = kind_for(name, FIELDS[name], body)
            new = None
            if kind == 'amount':
                new = to_amount(val)
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                continue
            elif kind == 'digits':
                new = to_digits(val)
            elif kind in ('date', 'dob'):
                new = to_date(val, kind == 'dob')
            elif kind == 'time':
                new = to_time(val)
            else:
                new = to_date(val, True)
                if new is None:
                    new = to_digits(val)
            if new is not None:
                body[name] = new
        except Exception:
            pass


try:
    _nz_main(config, vars)
except Exception:
    pass
'''


def _guess_kind(field):
    f = field.lower()
    if "birth" in f or "dob" in f:
        return "dob"
    if "date" in f or f.endswith("_day") or f == "day":
        return "date"
    if "amount" in f or "sum" in f or "payment" in f:
        return "amount"
    if "time" in f or "hour" in f:
        return "time"
    if "answer" in f:
        return "answer"
    return "digits"


def normalise_pre(fields, date_order="dmy", now_var="now", relative_var=None, pm_hours=(1, 2, 3, 4, 5, 6, 7)):
    """pre_process_code for an api_call tool: normalises the spoken form of the listed body fields in
    config['body'] before the request (T21). Rule-based, idempotent, never raises, leaves a value as is on doubt.

    `fields`: {field: kind} or a list of names (kind guessed from the name). Kinds:
      digits  "four four seven one", "forty-four seventy-one", "463 ... 51", "double four", "oh" -> "4471"-style
              digit string (spaces, dashes, currency words dropped);
      date    a date in the future or near now: "14 March", "the fourteenth of March 2027", "14/03/27", ISO;
              a month-name date without a year takes the next occurrence on or after `now`;
      dob     a past date ("fourteenth of March 1988", "14 March 88", "March fourteen nineteen eighty-eight");
              two-digit years take the latest century not after `now`;
      amount  "four hundred and twenty point five" -> 420.5, "twelve fifty" -> 1250.0, "1,250.00" -> 1250.0,
              "$300 and fifty cents" -> 300.5; numbers -> float;
      time    "eleven in the morning" -> "11:00", "half past two" -> "14:30", "11am", "9:05" -> "09:05";
              a bare hour in `pm_hours` (call-centre hours) is read as pm;
      answer  identity answer: dob when the body's `field` names a date/birth, digits when it names anything
              else, otherwise a date if it reads as one, else digits.
    `date_order` ('dmy' or 'mdy') reads numbers-only dates ("14/03/1988"); it must come from the brief. A reading
    that is impossible in that order but valid swapped (month > 12) is swapped.
    `now_var`: the call variable holding today's date (ISO), for two-digit years and year-less dates.
    `relative_var`: name of a variable holding a {phrase: 'YYYY-MM-DD'} table (dict or JSON string) the
    generator computed in code (see relative_days_code); "tomorrow", "next friday" are resolved ONLY through it.
    Corrections: the value after the last "no", "sorry", "I mean", "actually", "wait" wins.
    Combine with other pre hooks by concatenating the strings (each is self-contained)."""
    if isinstance(fields, dict):
        fm = {str(k): str(v) for k, v in fields.items()}
    else:
        fm = {str(f): _guess_kind(str(f)) for f in fields}
    for f, k in fm.items():
        if k not in NORMALISE_KINDS:
            raise ValueError("normalise_pre: field %r has unknown kind %r (use one of %s)" % (f, k, ", ".join(NORMALISE_KINDS)))
    if date_order not in ("dmy", "mdy"):
        raise ValueError("normalise_pre: date_order must be 'dmy' or 'mdy'")
    code = (_NORM_SRC.replace("__FIELDS__", repr(fm)).replace("__ORDER__", repr(date_order))
            .replace("__NOW_VAR__", repr(now_var)).replace("__REL_VAR__", repr(relative_var or ""))
            .replace("__PM_HOURS__", repr(tuple(int(h) for h in pm_hours))))
    assert "{{" not in code and "}}" not in code
    return code


_RELATIVE_SRC = r'''import datetime, json
try:
    _raw = str(vars.get(__NOW__) or '').strip()
    _today = datetime.date.fromisoformat(_raw[:10])
    _wd = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    _t = dict()
    _t['today'] = _today.isoformat()
    _t['tomorrow'] = (_today + datetime.timedelta(days=1)).isoformat()
    _t['day after tomorrow'] = (_today + datetime.timedelta(days=2)).isoformat()
    for _i in range(7):
        _d = _today + datetime.timedelta(days=(_i - _today.weekday()) % 7 or 7)
        _n = _d + datetime.timedelta(days=7) if __NEXT_WEEK__ else _d
        _w = _wd[_i]
        for _p in ('', 'this ', 'coming ', 'this coming '):
            _t[_p + _w] = _d.isoformat()
        _t['next ' + _w] = _n.isoformat()
    vars[__OUT__] = json.dumps(_t)
except Exception:
    vars[__OUT__] = ''
'''


def relative_days_code(now_var="now", out_var="relative_days", next_means_week_after=False):
    """Code-node snippet (e.g. in SETUP_CODE extra or its own code node) that writes vars[out_var] as a JSON
    table phrase -> ISO date for normalise_pre(relative_var=out_var): today, tomorrow, day after tomorrow,
    '<weekday>' / 'this <weekday>' / 'coming <weekday>' = the first such day after today, 'next <weekday>' = the
    same day, or one week later when the brief says so (next_means_week_after=True). Take the reading from the
    brief; when the brief is silent keep the default."""
    return (_RELATIVE_SRC.replace("__NOW__", repr(now_var)).replace("__OUT__", repr(out_var))
            .replace("__NEXT_WEEK__", "True" if next_means_week_after else "False"))


def latest_value_note(n_digits=None, what="the digits"):
    """Prompt sentence for identity/promise nodes (T21): parts are joined, the last correction wins."""
    n = ("all %d digits" % n_digits) if n_digits else ("all of %s" % what)
    return ("If the customer gives %s in parts, wait for %s and join them; if they correct themselves, use the "
            "LAST value they gave." % (what, n))


def digit_extraction(name, n_digits, description, conf=0.5, max_retries=2):
    """Extraction entry for a digit answer (T8): validated by '^[0-9]{N}$', retried twice, min_confidence 0.6."""
    return {"name": name, "type": "string", "description": description,
            "validation_pattern": "^[0-9]{%d}$" % int(n_digits), "max_retries": int(max_retries),
            "min_confidence": conf}


# ----------------------------------------------------------------------------------------------- gated identity (opt-in)
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
              "ten": 10, "eleven": 11, "twelve": 12}


def digits_from_spec(api, field_value, tool="verify_identity", answer_field="answer"):
    """N for a digits security question, read from the API file: the identity tool's answer description, e.g.
    "For phone_last4: four digits." -> 4 (the sentence that names `field_value` first, then the field name itself,
    e.g. 'last4'). None when the file gives no count (the generator then passes n_digits from the brief)."""
    fs = tool_spec(api, tool)["fields"].get(answer_field) or {}
    desc = str(fs.get("description") or "")
    num = r"(\d+|%s)[\s-]+digits?" % "|".join(_NUM_WORDS)
    sentences = re.split(r"(?<=[.;])\s+", desc)
    for s in [x for x in sentences if field_value in x] + [field_value]:
        m = re.search(num, s, re.I)
        if m:
            w = m.group(1).lower()
            return int(w) if w.isdigit() else _NUM_WORDS[w]
    return None


def gated_digits_identity(api, stage, field_value, n_digits, ask_task, answer_desc, on_verified, on_all_verified,
                          on_exhausted, wrong_line, unreadable_line, extraction=None, transitions=None,
                          tool_post="", extra_routes=None, stop_left=("0",), tool="verify_identity",
                          field_name="field", answer_field="answer", on_enter=None):
    """OPT-IN identity question whose answer reaches the identity tool only when all N digits are in (the default
    form is a conversation node that holds verify_identity as a model-called tool, prompt-driven). Returns a dict of
    nodes to merge into the workflow:

      ask_<stage>        conversation, extraction `<stage>_digits` (validation_pattern ^[0-9]{N}$), NO tools.
                         Route: <stage>_digits is set and is not the sentinel -> check_<stage>. Half a number
                         ('44'), words the extractor cannot turn into N digits, or a cut-off line never validate,
                         so nothing is sent and the model asks for the rest (say so in `ask_task`).
      ask_<stage>_wrong  the same node, entered after a wrong answer: on_enter tts `wrong_line` (fixed text).
      ask_<stage>_unread the same node, entered after an answer the service could not read: tts `unreadable_line`.
      check_<stage>      api_request: verify_identity with field baked = field_value and answer baked =
                         {{<stage>_digits}}; node-level mapping of ok / verified / all_verified /
                         wrong_answers_left to <stage>_ok, <stage>_verified, <stage>_all, <stage>_left.
      route_<stage>      code: writes the sentinel ('0' * N, schema-valid for the pattern: a cleared value must be
                         valid or the code node fails) so the same answer is not sent twice, then routes in order:
                         `extra_routes` (e.g. the brief's own counter written by `tool_post`), all_verified ->
                         on_all_verified, verified -> on_verified, wrong_answers_left in `stop_left` -> on_exhausted,
                         ok false -> ask_<stage>_unread, else -> ask_<stage>_wrong.

    `extraction` / `transitions`: the brief's other extraction entries and routes (refusal, question back, transfer)
    added to all three ask nodes AFTER the gate route. Every text (ask_task, answer_desc, wrong_line,
    unreadable_line) comes from the brief. Known corner: a customer whose real answer is the sentinel ('0000') is
    never sent; use the default form for such a brief.
    """
    n = int(n_digits)
    var, sentinel = "%s_digits" % stage, "0" * n
    ask, check, route = "ask_%s" % stage, "check_%s" % stage, "route_%s" % stage
    ext_entry = digit_extraction(var, n, answer_desc + " Only when ALL %d digits are in the customer's messages "
                                 "(join parts given in two turns, write digits said in words as digits; if they "
                                 "correct themselves, the LAST value). Leave it empty for fewer digits." % n)
    gate = tr(check, "all %d digits given" % n, and_group(cond(var, "is_set"), cond(var, "not_equals", sentinel)))
    extraction = [ext_entry] + list(extraction or [])
    routes = [gate] + list(transitions or [])
    task = ask_task + ("\nYou do not call a tool for this answer: it is checked automatically once all %d digits are "
                       "given. If the customer gives only part, or the line is cut off, ask for the rest and wait." % n)
    nodes = {}
    for name, enter in ((ask, on_enter), ("%s_wrong" % ask, {"type": "tts", "text": wrong_line}),
                        ("%s_unread" % ask, {"type": "tts", "text": unreadable_line})):
        nodes[name] = conv(name, task, on_enter=enter, extraction=json.loads(json.dumps(extraction)),
                           transitions=json.loads(json.dumps(routes)))
    t = api_tool(api, tool, baked={field_name: field_value, answer_field: "{{%s}}" % var},
                 description="Check the %s answer." % stage, post=tool_post)
    mapping = [{"path": "data.ok", "variable": "%s_ok" % stage}, {"path": "data.verified", "variable": "%s_verified" % stage},
               {"path": "data.all_verified", "variable": "%s_all" % stage},
               {"path": "data.wrong_answers_left", "variable": "%s_left" % stage}]
    nodes[check] = api_node(check, t, [always(route)], mapping=mapping)
    stop = [cond("%s_left" % stage, "equals", str(v)) for v in stop_left]
    code = "try:\n    vars[%r] = %r\nexcept Exception:\n    pass\n" % (var, sentinel)
    nodes[route] = code_node(route, code, list(extra_routes or []) + [
        is_true("%s_all" % stage, on_all_verified, "identity verified"),
        is_true("%s_verified" % stage, on_verified, "answer correct"),
        tr(on_exhausted, "no wrong answers left", *stop),
        tr("%s_unread" % ask, "the service could not read the answer",
           cond("%s_ok" % stage, "equals", "false"), cond("%s_ok" % stage, "equals", "False")),
        always("%s_wrong" % ask)])
    return nodes
