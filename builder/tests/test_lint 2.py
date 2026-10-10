#!/usr/bin/env python3
"""Tests for builder/lint.py. Plain asserts: python3 builder/tests/test_lint.py"""
import copy
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder"))
from lint import lint, ERROR, WARN, INFO  # noqa: E402

API = json.loads((ROOT / "tools" / "openapi.json").read_text())
BASE = API["servers"][0]["url"].rstrip("/")


def always(t):
    return {"target_node": t, "description": "always", "condition": {"operator": "always"}}


def api_tool(name, body, required=None, description="CALL it when needed."):
    return {
        "type": "function",
        "config": {"timeoutMs": 10000, "maxRetries": 0},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": f"{BASE}/{name}"},
                "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "required": required or [], "properties": body},
            }},
        },
        "post_process_code": "try:\n    if isinstance(result, dict):\n        result.pop('header', None)\nexcept Exception:\n    pass\n",
    }


def minimal():
    """A tiny valid workflow: code node -> conversation with one tool -> end_call."""
    return {
        "initial_node": "setup",
        "system_prompt": "You are a bank assistant.",
        "test_variables": {"customer_id": "c_test", "first_name": "Dana"},
        "global_nodes": {},
        "nodes": {
            "setup": {
                "name": "setup", "node_type": "code", "passthrough": True,
                "passthrough_default_transition": "greet", "on_enter": {"type": "silent"},
                "pre_actions": [{"type": "function", "function": {
                    "name": "code_exec", "handler": "__function__:code_exec",
                    "parameters": {"type": "object", "properties": {
                        "code": {"type": "string", "default": "try:\n    vars['state'] = 'ok'\nexcept Exception:\n    vars['state'] = 'error'\n"},
                        "timeout_ms": {"type": "number", "default": 10000}}}}}],
                "transitions": [always("greet")],
            },
            "greet": {
                "name": "greet", "node_type": "conversation",
                "task_message": "Greet {{first_name}}. CALL get_account when they confirm. After every tool result, speak.",
                "tools": [api_tool("get_account", {"customer_id": {"type": "string", "default": "{{customer_id}}"}})],
                "extraction_schema": [{"name": "wants_end", "type": "string", "enum_values": ["yes", "no"],
                                       "description": "Whether the caller wants to end", "min_confidence": 0.6}],
                "transitions": [
                    {"target_node": "bye", "description": "caller wants to end", "condition": {
                        "logic": "or", "conditions": [{"variable": "wants_end", "operator": "equals", "operand": "yes"}]}},
                    always("greet"),
                ],
            },
            "bye": {
                "name": "bye", "node_type": "end_call", "on_enter": {"type": "silent"},
                "disable_inactivity_monitor": True, "transitions": [],
                "terminal": {"type": "function", "function": {
                    "name": "done", "handler": "__function__:end_call",
                    "parameters": {"type": "object", "properties": {
                        "message_mode": {"type": "string", "default": "custom"},
                        "spoken_message": {"type": "string", "default": "Goodbye {{first_name}}."}}}}},
            },
        },
    }


def errors(wf, api=None):
    return [f for f in lint(wf, api) if f["level"] == ERROR]


def has(findings, level, where_part, msg_part=""):
    return any(f["level"] == level and where_part in f["where"] and msg_part in f["message"] for f in findings)


def test_minimal_is_clean():
    wf = minimal()
    assert errors(wf) == [], errors(wf)
    assert errors(wf, API) == [], errors(wf, API)


def test_null_value():
    wf = minimal()
    wf["nodes"]["greet"]["max_turn_transition"] = None
    f = errors(wf)
    assert has(f, ERROR, "$.nodes.greet.max_turn_transition", "null"), f


def test_missing_targets():
    wf = minimal()
    wf["nodes"]["greet"]["transitions"][0]["target_node"] = "nowhere"
    f = errors(wf)
    assert has(f, ERROR, "nodes.greet.transitions[0]", "does not exist"), f
    wf = minimal()
    wf["initial_node"] = "ghost"
    assert has(errors(wf), ERROR, "$.initial_node", "ghost")
    wf = minimal()
    wf["nodes"]["greet"]["transitions"][0]["target_node"] = "__previous__"
    assert has(errors(wf), ERROR, "nodes.greet.transitions[0]", "__previous__")


def test_placement_tools_and_pre_actions():
    wf = minimal()
    wf["nodes"]["setup"]["tools"] = [api_tool("get_account", {})]
    f = errors(wf)
    assert has(f, ERROR, "nodes.setup.tools", "strips"), f
    wf = minimal()
    wf["nodes"]["greet"]["pre_actions"] = [api_tool("get_account", {})]
    f = errors(wf)
    assert has(f, ERROR, "nodes.greet.pre_actions", "strips"), f


def test_const_url_and_body():
    wf = minimal()
    t = wf["nodes"]["greet"]["tools"][0]["function"]["parameters"]["properties"]
    t["url"] = {"type": "string", "const": t["url"]["default"]}
    f = errors(wf)
    assert has(f, ERROR, "tools[get_account].parameters.url", "const"), f
    wf = minimal()
    t = wf["nodes"]["greet"]["tools"][0]["function"]["parameters"]["properties"]
    t["body"]["properties"]["customer_id"] = {"type": "string", "const": "{{customer_id}}"}
    assert has(errors(wf), ERROR, "parameters.body.customer_id", "const")


def test_top_level_and_group():
    wf = minimal()
    wf["nodes"]["greet"]["transitions"][0]["condition"]["logic"] = "and"
    f = errors(wf)
    assert has(f, ERROR, "nodes.greet.transitions[0].condition", "'and'"), f


def test_mapping_nested_in_pre_action():
    wf = minimal()
    wf["nodes"]["load"] = {
        "name": "load", "node_type": "api_request", "passthrough": True,
        "passthrough_default_transition": "greet", "on_enter": {"type": "silent"},
        "pre_actions": [dict(api_tool("get_account", {"customer_id": {"type": "string", "default": "{{customer_id}}"}}),
                             response_mapping=[{"path": "data.products", "variable": "products"}])],
        "transitions": [always("greet")],
    }
    wf["nodes"]["setup"]["transitions"] = [always("load")]
    wf["nodes"]["setup"]["passthrough_default_transition"] = "load"
    f = errors(wf)
    assert has(f, ERROR, "nodes.load.pre_actions[get_account].response_mapping", "node level"), f
    # the correct placement is clean
    pa = wf["nodes"]["load"]["pre_actions"][0]
    wf["nodes"]["load"]["response_mapping"] = pa.pop("response_mapping")
    assert errors(wf) == [], errors(wf)
    # a path that does not start with data. is a WARN
    wf["nodes"]["load"]["response_mapping"][0]["path"] = "products"
    assert has(lint(wf), WARN, "nodes.load.response_mapping[0]", "data.")


def test_code_rules():
    wf = minimal()
    code = wf["nodes"]["setup"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
    code["default"] = "try:\n    vars['x'] = '{{customer_id}}'\nexcept Exception:\n    pass\n"
    f = errors(wf)
    assert has(f, ERROR, "nodes.setup.pre_actions[code_exec].code", "{{"), f
    code["default"] = "try:\n    x = (\nexcept Exception:\n    pass\n"
    assert has(errors(wf), ERROR, "nodes.setup.pre_actions[code_exec].code", "compile")
    code["default"] = "vars['x'] = vars['customer_id']\n"
    f = lint(wf)
    assert has(f, WARN, "nodes.setup.pre_actions[code_exec].code", "try/except"), f
    assert has(f, WARN, "nodes.setup.pre_actions[code_exec].code", "vars.get"), f
    # hooks are honoured only on api_call tools
    wf = minimal()
    wf["nodes"]["setup"]["pre_actions"][0]["post_process_code"] = "pass"
    assert has(errors(wf), ERROR, "nodes.setup.pre_actions[code_exec].post_process_code", "api_call")


def test_model_filled_field_baked():
    wf = minimal()
    wf["nodes"]["greet"]["tools"] = [api_tool("create_promise", {
        "customer_id": {"type": "string", "default": "{{customer_id}}"},
        "product_id": {"type": "string", "default": "{{product_id}}", "description": "p1 or p2"},
        "amount": {"type": "number", "default": "{{amount}}", "description": "The amount"},
        "date": {"type": "string", "default": "{{date}}", "description": "YYYY-MM-DD"},
    }, ["amount", "date"])]
    assert errors(wf) == [], errors(wf)
    # 'amount' is also an extracted variable -> it would be baked, the model never sees it
    wf["nodes"]["greet"]["extraction_schema"].append(
        {"name": "amount", "type": "float", "description": "amount said", "min_confidence": 0.6})
    f = errors(wf)
    assert has(f, ERROR, "tools[create_promise].parameters.body.amount", "baked"), f
    # a writer that can never precede the node is only a WARN; one that can is an ERROR
    wf = minimal()
    wf["nodes"]["greet"]["tools"] = [api_tool("add_note", {
        "customer_id": {"type": "string", "default": "{{customer_id}}"},
        "product_id": {"type": "string", "default": "{{product_id}}", "description": "p1"},
        "reason": {"type": "string", "default": "{{reason}}", "description": "why", "enum": ["refused", "hardship"]},
    }, ["product_id", "reason"])]
    wf["nodes"]["fin"] = copy.deepcopy(wf["nodes"]["setup"])
    wf["nodes"]["fin"].update(name="fin", passthrough_default_transition="bye", transitions=[always("bye")])
    wf["nodes"]["fin"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = \
        "try:\n    vars['reason'] = 'refused'\nexcept Exception:\n    pass\n"
    wf["nodes"]["greet"]["transitions"][0]["target_node"] = "fin"
    f = lint(wf)
    assert not has(f, ERROR, "tools[add_note].parameters.body.reason"), f
    assert has(f, WARN, "tools[add_note].parameters.body.reason", "cannot precede"), f
    wf["nodes"]["setup"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = \
        "try:\n    vars['reason'] = ''\nexcept Exception:\n    pass\n"
    assert has(errors(wf), ERROR, "tools[add_note].parameters.body.reason", "baked")


def test_passthrough_and_end_call_shape():
    wf = minimal()
    wf["nodes"]["setup"]["transitions"] = [
        {"target_node": "greet", "description": "ok", "condition": {"logic": "or", "conditions": [
            {"variable": "state", "operator": "equals", "operand": "ok"}]}}]
    f = errors(wf)
    assert has(f, ERROR, "nodes.setup.transitions", "always"), f
    wf = minimal()
    del wf["nodes"]["setup"]["passthrough_default_transition"]
    assert has(errors(wf), ERROR, "nodes.setup.passthrough_default_transition", "needs")
    wf = minimal()
    wf["nodes"]["bye"]["transitions"] = [always("greet")]
    assert has(errors(wf), ERROR, "nodes.bye.transitions", "no transitions")
    wf = minimal()
    wf["nodes"]["bye"]["terminal"]["function"]["handler"] = "__function__:api_call"
    assert has(errors(wf), ERROR, "nodes.bye.terminal", "__function__:end_call")


def test_every_node_reaches_end():
    wf = minimal()
    wf["nodes"]["greet"]["transitions"] = [always("greet")]
    f = errors(wf)
    assert has(f, ERROR, "nodes.greet", "end_call"), f
    assert has(f, ERROR, "nodes.setup", "end_call"), f


def test_lifecycle_and_hooks():
    wf = minimal()
    t = api_tool("close_call", {"customer_id": {"type": "string", "default": "{{customer_id}}"},
                                "outcome": {"type": "string", "default": "{{outcome}}", "description": "outcome",
                                            "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"]}},
                 ["outcome"])
    del t["post_process_code"]
    wf["tools"] = [t]
    assert has(errors(wf), ERROR, "tools[close_call].config", "alwaysRunsAt")
    t["config"]["alwaysRunsAt"] = ["each_turn"]
    assert has(errors(wf), ERROR, "tools[close_call].config.alwaysRunsAt", "never fires")
    t["config"]["alwaysRunsAt"] = ["end_of_call"]
    assert errors(wf, API) == [], errors(wf, API)
    # lifecycle tool inside a node is a WARN
    wf["nodes"]["greet"]["tools"].append(copy.deepcopy(t))
    assert has(lint(wf), WARN, "nodes.greet.tools[close_call]", "workflow-level")


def test_boolean_and_tool_call_warnings():
    wf = minimal()
    wf["nodes"]["greet"]["transitions"][0]["condition"]["conditions"] = [
        {"variable": "get_account_response.data.ok", "operator": "equals", "operand": "true"}]
    f = lint(wf)
    assert has(f, WARN, "nodes.greet.transitions[0].condition", "both spellings"), f
    wf["nodes"]["greet"]["transitions"][0]["condition"]["conditions"].append(
        {"variable": "get_account_response.data.ok", "operator": "equals", "operand": "True"})
    assert not has(lint(wf), WARN, "nodes.greet.transitions[0].condition", "both spellings")
    wf = minimal()
    wf["nodes"]["greet"]["transitions"][0]["is_tool_call"] = True
    assert has(lint(wf), WARN, "nodes.greet.transitions[0]", "matches_intent")
    wf = minimal()
    wf["nodes"]["greet"]["tools"] = []
    assert has(lint(wf), WARN, "nodes.greet.task_message", "no tool call")


def test_openapi_checks():
    wf = minimal()
    t = wf["nodes"]["greet"]["tools"][0]
    t["function"]["name"] = "get_accounts"
    t["function"]["parameters"]["properties"]["url"]["default"] = f"{BASE}/get_accounts"
    assert has(errors(wf, API), ERROR, "tools[get_accounts]", "not an operation")
    wf = minimal()
    t = wf["nodes"]["greet"]["tools"][0]
    t["function"]["parameters"]["properties"]["url"]["default"] = f"{BASE}/get_account/"
    assert has(errors(wf, API), ERROR, "parameters.url", "base_url")
    wf = minimal()
    t = wf["nodes"]["greet"]["tools"][0]
    del t["function"]["parameters"]["properties"]["body"]["properties"]["customer_id"]
    assert has(errors(wf, API), ERROR, "parameters.body", "required body field 'customer_id'")
    wf = minimal()
    wf["nodes"]["greet"]["tools"] = [api_tool("transfer_to_agent", {
        "customer_id": {"type": "string", "default": "{{customer_id}}"},
        "queue": {"type": "string", "default": "{{queue}}", "enum": ["general", "billing"], "description": "queue"}}, ["queue"])]
    f = errors(wf, API)
    assert has(f, ERROR, "parameters.body.queue", "not in the spec"), f
    wf["nodes"]["greet"]["tools"][0]["function"]["parameters"]["properties"]["body"]["properties"]["queue"] = {
        "type": "string", "default": "vip"}
    assert has(errors(wf, API), ERROR, "parameters.body.queue", "not an allowed value")


def test_reference_workflows():
    brief_a = json.loads((ROOT / "out" / "brief-a.workflow.json").read_text())
    f = lint(brief_a, API)
    assert [x for x in f if x["level"] in (ERROR, WARN)] == [], f
    base = json.loads((ROOT / "examples" / "base-agent.json").read_text())
    f = errors(base, API)
    assert has(f, ERROR, "$.nodes.identity.max_turn_transition", "null"), f
    assert has(f, ERROR, "tools[close_call].parameters.body.outcome", "close_call outcome"), f


def test_baked_field_info():
    """A bare {{x}} body field (no description/enum/required) set by code, extraction, mapping or a call variable
    is reported as baked (INFO); a described one stays an ERROR."""
    def tool_with(field, extra=None):
        wf = minimal()
        body = wf["nodes"]["greet"]["tools"][0]["function"]["parameters"]["properties"]["body"]["properties"]
        body[field] = dict({"type": "string", "default": "{{%s}}" % field}, **(extra or {}))
        return wf
    wf = tool_with("state")                          # written by the setup code node
    f = lint(wf)
    assert has(f, INFO, "parameters.body.state", "field state is baked by code in node 'setup'"), f
    wf = tool_with("first_name")                     # a call variable
    assert has(lint(wf), INFO, "parameters.body.first_name", "baked by test_variables"), lint(wf)
    wf = tool_with("wants_end")                      # an extraction_schema entry
    assert has(lint(wf), INFO, "parameters.body.wants_end", "baked by extraction_schema in node 'greet'")
    wf = tool_with("state", {"description": "The state."})
    assert has(errors(wf), ERROR, "parameters.body.state", "model-filled field"), errors(wf)


def test_cli_exit_codes():
    r = subprocess.run([sys.executable, str(ROOT / "builder" / "lint.py"), str(ROOT / "out" / "brief-a.workflow.json"),
                        "--api", str(ROOT / "tools" / "openapi.json")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run([sys.executable, str(ROOT / "builder" / "lint.py"), str(ROOT / "examples" / "base-agent.json")],
                       capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout.startswith("ERROR "), r.stdout


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
