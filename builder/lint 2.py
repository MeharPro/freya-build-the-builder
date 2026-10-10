#!/usr/bin/env python3
"""Static checker for Freya workflow JSON.

Encodes the rules of docs/workflow-format.md, docs/tools-and-code.md and the
pitfalls of the kit README. Standard library only.

CLI:
    python3 builder/lint.py <workflow.json> [--api tools/openapi.json]
prints one line per finding  'ERROR|WARN|INFO <node or path>: message'
and exits 1 when any ERROR was found.

Importable:
    from lint import lint
    findings = lint(workflow_dict, api=openapi_dict_or_None)
    -> list of {"level": "ERROR"|"WARN"|"INFO", "where": str, "message": str}
"""
import ast
import json
import re
import sys

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"
LEVEL_ORDER = {ERROR: 0, WARN: 1, INFO: 2}

NODE_TYPES_CORE = {"conversation", "api_request", "code", "end_call"}
NODE_TYPES_OTHER = {"transfer_call", "integration", "knowledge_base", "reschedule_call", "invoke_agent", "exit"}
ACTION_NODE_TYPES = {"api_request", "code"} | NODE_TYPES_OTHER - {"exit"}
ON_ENTER_TYPES = {"llm", "tts", "silent", "audio"}
TRUNCATION = {"keep_all", "keep_recent", "summarize"}
REASONING = {"auto", "enabled", "disabled"}
EXTRACTION_TYPES = {"string", "integer", "float", "boolean", "date", "datetime", "name", "phone_number"}
VAR_OPERATORS = {"equals", "not_equals", "greater_than", "less_than", "contains", "is_set", "is_not_set"}
OPERAND_OPERATORS = {"equals", "not_equals", "greater_than", "less_than", "contains"}
ALL_OPERATORS = VAR_OPERATORS | {"always", "matches_intent"}
HANDLERS = {"__function__:api_call", "__function__:code_exec", "__function__:end_call"}
HANDLER_API, HANDLER_CODE, HANDLER_END = "__function__:api_call", "__function__:code_exec", "__function__:end_call"
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
LIFECYCLE_VALUES = {"start_of_call", "end_of_call", "each_turn"}
API_TOP_LEVEL = {"url", "method", "headers", "body", "connect_retries"}
MESSAGE_MODES = {"custom", "llm", "none"}
SYSTEM_VAR_PREFIXES = ("system.", "call.", "date.", "time.", "extractor.")
EXTRACTION_PROMPT_PLACEHOLDERS = ["{{extractor.speech}}", "{{extractor.conversation.last-10}}",
                                  "{{extractor.type_preamble}}", "{{extractor.variables_list}}"]

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
NAME_RE = re.compile(r"^[a-zA-Z_]\w*$")
SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
NO_TOOL_RE = re.compile(
    r"(no tool calls? (?:is|are)? ?(?:allowed|permitted)"
    r"|not call (?:any |a |the )?tools?\b"
    r"|never call (?:any |a |the )?tools?\b"
    r"|without (?:calling |using )?(?:a |any )?tools?\b"
    r"|tools? (?:calls? )?(?:is|are) not (?:allowed|permitted|available)"
    r"|not allowed to (?:call|use) (?:any |a )?tools?"
    r"|do not use (?:any |a )?tools?\b"
    r"|no tools? (?:is |are )?(?:allowed|available|permitted))", re.I)
BOOL_OPERAND_RE = re.compile(r"^(true|false)$", re.I)
DATE_NAME_RE = re.compile(r"(^|_)(date|dob|birthday|birth_date|day|deadline)(_\w+)?$|_on$|^(date|dob)_")


class _Linter:
    def __init__(self, wf, api=None):
        self.wf = wf if isinstance(wf, dict) else {}
        self.api = api
        self.findings = []
        self.nodes = self.wf.get("nodes") if isinstance(self.wf.get("nodes"), dict) else {}
        self.globals = self.wf.get("global_nodes") if isinstance(self.wf.get("global_nodes"), dict) else {}
        self.all_nodes = {}
        self.all_nodes.update(self.nodes)
        self.all_nodes.update(self.globals)
        # variable knowledge
        self.known_vars = set()         # exact names set by something in the workflow
        self.var_writers = {}           # var name -> set of node keys ('$' = test_variables / workflow level)
        self.var_writer_desc = {}       # var name -> set of human-readable writers ("code node 'setup'", ...)
        self.reach = {}                 # node key -> set of node keys reachable from it (itself included)
        self._current_node = "$"
        self.result_prefixes = set()    # names N for which N_response.* / N_args.* / N_*_count exist
        self.tool_names = set()
        self.end_tool_nodes = set()     # conversation nodes that carry an end_call tool

    # ------------------------------------------------------------ helpers
    def add(self, level, where, message):
        self.findings.append({"level": level, "where": where, "message": message})

    def err(self, where, message):
        self.add(ERROR, where, message)

    def warn(self, where, message):
        self.add(WARN, where, message)

    def info(self, where, message):
        self.add(INFO, where, message)

    @staticmethod
    def tool_label(tool, idx):
        fn = tool.get("function") if isinstance(tool, dict) else None
        name = fn.get("name") if isinstance(fn, dict) else None
        return name if isinstance(name, str) and name else str(idx)

    @staticmethod
    def placeholders(text):
        out = []
        for m in PLACEHOLDER_RE.finditer(text or ""):
            v = m.group(1).strip()
            if ":" in v:
                v = v.split(":", 1)[0].strip()
            out.append(v)
        return out

    @staticmethod
    def single_placeholder(value):
        """Return the variable name when value is exactly one '{{x}}' placeholder."""
        if not isinstance(value, str):
            return None
        m = PLACEHOLDER_RE.fullmatch(value.strip())
        if not m:
            return None
        v = m.group(1).strip()
        return v.split(":", 1)[0].strip() if ":" in v else v

    def note_var(self, name, kind="variable"):
        self.known_vars.add(name)
        self.var_writers.setdefault(name, set()).add(self._current_node)
        where = "the workflow" if self._current_node == "$" else f"node '{self._current_node}'"
        desc = "test_variables (call variable)" if kind == "test_variables" else f"{kind} in {where}"
        self.var_writer_desc.setdefault(name, set()).add(desc)

    def writer_text(self, name):
        return ", ".join(sorted(self.var_writer_desc.get(name, ()))) or "?"

    def writer_can_precede(self, name, node_key):
        """True when some writer of the variable is test_variables, workflow level, a global node,
        or a node from which node_key is reachable (node_key itself included)."""
        for w in self.var_writers.get(name, ()):
            if w == "$" or w in self.globals or w == node_key:
                return True
            if node_key in self.reach.get(w, ()):
                return True
        return False

    def is_system_var(self, name):
        if name.startswith(SYSTEM_VAR_PREFIXES):
            return True
        for suffix in (".current_turns", ".total_turns"):
            if name.endswith(suffix) and name[: -len(suffix)] in self.all_nodes:
                return True
        return False

    def is_known_var(self, name):
        if name in self.known_vars or self.is_system_var(name):
            return True
        for p in self.result_prefixes:
            if name.startswith(p + "_response.") or name.startswith(p + "_args."):
                return True
            if name in (p + "_success_count", p + "_failure_count", p + "_status_code"):
                return True
        return False

    # ------------------------------------------------------------ code analysis
    @staticmethod
    def code_assigned_vars(code):
        """Names the snippet writes into vars (vars['x'] = ..., vars.setdefault('x', ...), vars.update({...}))."""
        names = set()
        try:
            tree = ast.parse(code)
        except Exception:
            return names
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "vars":
                    key = t.slice
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        names.add(key.value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "vars":
                    if node.func.attr == "setdefault" and node.args and isinstance(node.args[0], ast.Constant) \
                            and isinstance(node.args[0].value, str):
                        names.add(node.args[0].value)
                    if node.func.attr == "update" and node.args and isinstance(node.args[0], ast.Dict):
                        for k in node.args[0].keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                names.add(k.value)
        return names

    def check_python(self, code, where, kind):
        """Compile check, '{{' check, try/except wrap, vars[...] reads, boolean writes. kind: 'code' or 'hook'."""
        if not isinstance(code, str):
            self.err(where, f"{kind} must be a string")
            return
        if "{{" in code or "}}" in code:
            if kind == "code":
                self.err(where, "code contains '{{' or '}}': the snippet may be templated and an unset placeholder breaks the Python. Read values from vars and avoid nested dict literals ending in '}}'")
            else:
                self.warn(where, "hook contains '{{' or '}}': read values from vars instead of templating them into Python")
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.err(where, f"{kind} does not compile: {e.msg} (line {e.lineno})")
            return
        safe_top = (ast.Import, ast.ImportFrom, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass)
        exposed = []
        for stmt in tree.body:
            if isinstance(stmt, safe_top):
                continue
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            exposed.append(type(stmt).__name__)
        if not any(isinstance(s, ast.Try) for s in tree.body):
            self.warn(where, f"{kind} is not wrapped in try/except: a raising snippet leaves every later placeholder unresolved")
        elif exposed:
            self.warn(where, f"{kind} has statements outside try/except ({', '.join(sorted(set(exposed)))}); wrap the whole body")
        assigned = self.code_assigned_vars(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "vars" \
                    and isinstance(node.ctx, ast.Load):
                key = node.slice.value if isinstance(node.slice, ast.Constant) else None
                if key is not None and key in assigned:
                    continue
                self.warn(where, f"{kind} reads vars[{key if key is not None else '...'!r}] directly; a never-set variable is absent and raises KeyError. Use vars.get()")
                break
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                for t in node.targets:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "vars":
                        key = t.slice.value if isinstance(t.slice, ast.Constant) else "..."
                        self.warn(where, f"{kind} writes a Python boolean into vars[{key!r}]; equals compares strings ('True' vs 'true'). Write a string flag such as 'yes'/'no'")
                        break

    # ------------------------------------------------------------ pass 0: nulls and top level
    def check_nulls(self, obj, path="$"):
        if obj is None:
            self.err(path, "null value: the schema is strict, leave the field out or use \"\"")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                self.check_nulls(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                self.check_nulls(v, f"{path}[{i}]")

    def check_top_level(self):
        wf = self.wf
        if not isinstance(self.wf, dict):
            self.err("$", "workflow must be a JSON object")
            return
        if not isinstance(wf.get("nodes"), dict) or not wf.get("nodes"):
            self.err("$.nodes", "nodes must be a non-empty object")
        init = wf.get("initial_node")
        if not isinstance(init, str) or not init:
            self.err("$.initial_node", "initial_node is required")
        elif init not in self.nodes:
            self.err("$.initial_node", f"initial_node '{init}' is not a key of nodes")
        if "agent_config" in wf:
            self.warn("$.agent_config", "leave agent_config out: the platform fills defaults and a simulation may never start a call with it present (kit README)")
        if "context_variables" in wf:
            self.warn("$.context_variables", "context_variables was dropped by the API on save without an error; write {{var}} into the prompts instead")
        if "global_nodes" in wf and not isinstance(wf["global_nodes"], dict):
            self.err("$.global_nodes", "global_nodes must be an object")
        if "test_variables" in wf and not isinstance(wf["test_variables"], dict):
            self.err("$.test_variables", "test_variables must be an object")
        if "tools" in wf and not isinstance(wf["tools"], list):
            self.err("$.tools", "workflow-level tools must be an array")
        sp = wf.get("system_prompt")
        if sp is not None and not isinstance(sp, str):
            self.err("$.system_prompt", "system_prompt must be a string")
        for key, nodes in (("nodes", self.nodes), ("global_nodes", self.globals)):
            for k, n in nodes.items():
                if not isinstance(n, dict):
                    self.err(f"$.{key}.{k}", "node must be an object")
        dup = set(self.nodes) & set(self.globals)
        for k in sorted(dup):
            self.err(f"$.global_nodes.{k}", "same key used in nodes and global_nodes")

    # ------------------------------------------------------------ pass 1: collect variable knowledge
    def node_edges(self):
        edges = {}
        for key, n in self.all_nodes.items():
            out = set()
            if isinstance(n, dict):
                for t in n.get("transitions") or []:
                    if isinstance(t, dict) and isinstance(t.get("target_node"), str):
                        out.add(t["target_node"])
                for fld in ("passthrough_default_transition", "max_turn_transition"):
                    v = n.get(fld)
                    if isinstance(v, str) and v:
                        out.add(v)
            edges[key] = {o for o in out if o in self.nodes}
        return edges

    def compute_reach(self):
        edges = self.node_edges()
        for start in self.all_nodes:
            seen, stack = set(), [start]
            while stack:
                k = stack.pop()
                if k in seen:
                    continue
                seen.add(k)
                stack.extend(edges.get(k, ()))
            self.reach[start] = seen

    def collect_vars(self):
        self.compute_reach()
        self._current_node = "$"
        tv = self.wf.get("test_variables")
        if isinstance(tv, dict):
            for k in tv:
                if isinstance(k, str):
                    self.note_var(k, "test_variables")
        for key, n in self.all_nodes.items():
            if not isinstance(n, dict):
                continue
            self._current_node = key
            for e in n.get("extraction_schema") or []:
                if isinstance(e, dict) and isinstance(e.get("name"), str):
                    self.note_var(e["name"], "extraction_schema")
            if n.get("node_type") in ACTION_NODE_TYPES and n.get("pre_actions"):
                self.result_prefixes.add(key)
                for m in n.get("response_mapping") or []:
                    if isinstance(m, dict) and isinstance(m.get("variable"), str):
                        self.note_var(m["variable"], "response_mapping")
            for tool in n.get("tools") or []:
                self._collect_tool_vars(tool, in_tools=True)
                if isinstance(tool, dict) and isinstance(tool.get("function"), dict) \
                        and tool["function"].get("handler") == HANDLER_END and n.get("node_type") == "conversation":
                    self.end_tool_nodes.add(key)
            for tool in n.get("pre_actions") or []:
                self._collect_tool_vars(tool, in_tools=False)
        self._current_node = "$"
        for tool in self.wf.get("tools") or []:
            self._collect_tool_vars(tool, in_tools=True)

    def _collect_tool_vars(self, tool, in_tools):
        if not isinstance(tool, dict):
            return
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = fn.get("name")
        handler = fn.get("handler")
        if isinstance(name, str) and name:
            self.tool_names.add(name)
            if handler == HANDLER_API:
                self.result_prefixes.add(name)
        if in_tools:
            for m in tool.get("response_mapping") or []:
                if isinstance(m, dict) and isinstance(m.get("variable"), str):
                    self.note_var(m["variable"], "tool response_mapping")
        for hook in ("pre_process_code", "post_process_code"):
            if isinstance(tool.get(hook), str):
                for v in self.code_assigned_vars(tool[hook]):
                    self.note_var(v, hook)
        if handler == HANDLER_CODE:
            props = (fn.get("parameters") or {}).get("properties") if isinstance(fn.get("parameters"), dict) else None
            code = (props or {}).get("code") if isinstance(props, dict) else None
            if isinstance(code, dict) and isinstance(code.get("default"), str):
                for v in self.code_assigned_vars(code["default"]):
                    self.note_var(v, "code")

    # ------------------------------------------------------------ pass 2: nodes
    def check_nodes(self):
        for key, n in self.nodes.items():
            if isinstance(n, dict):
                self.check_node(key, n, f"nodes.{key}", is_global=False)
        for key, n in self.globals.items():
            if isinstance(n, dict):
                self.check_node(key, n, f"global_nodes.{key}", is_global=True)

    def target_exists(self, target, is_global):
        if target == "__previous__":
            return is_global
        return target in self.all_nodes

    def check_node(self, key, n, where, is_global):
        ntype = n.get("node_type")
        if not isinstance(ntype, str) or not ntype:
            if is_global:
                self.warn(where, "global node without node_type; treated as conversation")
                ntype = "conversation"
            else:
                self.err(where, "node_type is required")
                ntype = ""
        elif ntype not in NODE_TYPES_CORE:
            if ntype in NODE_TYPES_OTHER:
                self.warn(where, f"node_type '{ntype}' is not covered by the docs for this event")
            else:
                self.err(where, f"unknown node_type '{ntype}'")
        name = n.get("name")
        if name != key:
            self.warn(where, f"name {name!r} differs from the node key '{key}'")
        if not SNAKE_RE.match(key):
            self.info(where, "node key is not snake_case")

        # on_enter
        oe = n.get("on_enter")
        if oe is not None:
            if not isinstance(oe, dict):
                self.err(f"{where}.on_enter", "on_enter must be an object")
            else:
                t = oe.get("type")
                if t not in ON_ENTER_TYPES:
                    self.err(f"{where}.on_enter", f"on_enter.type must be one of {sorted(ON_ENTER_TYPES)}, got {t!r}")
                if t == "tts" and not isinstance(oe.get("text"), str):
                    self.err(f"{where}.on_enter", "on_enter of type tts needs a text string")
                if t == "tts" and isinstance(oe.get("text"), str):
                    self.check_placeholders(oe["text"], f"{where}.on_enter.text", spoken=True)
                if t == "llm" and isinstance(oe.get("prompt"), str):
                    self.check_placeholders(oe["prompt"], f"{where}.on_enter.prompt")

        # misc fields
        for fld, allowed in (("truncation_strategy", TRUNCATION), ("reasoning_override", REASONING)):
            if fld in n and n[fld] not in allowed:
                self.err(f"{where}.{fld}", f"must be one of {sorted(allowed)}, got {n[fld]!r}")
        for fld in ("passthrough", "on_enter_first_entry_only", "disable_inactivity_monitor", "suppress_tool_results"):
            if fld in n and not isinstance(n[fld], bool):
                self.err(f"{where}.{fld}", "must be a boolean")
        mnt = n.get("max_node_turns")
        if mnt is not None:
            if not isinstance(mnt, int) or isinstance(mnt, bool) or mnt < 1:
                self.err(f"{where}.max_node_turns", "must be a positive integer")
            elif ntype == "conversation" and not n.get("max_turn_transition"):
                self.info(f"{where}.max_node_turns", f"max_node_turns={mnt} without max_turn_transition: the cap changes nothing (engine records the overrun and keeps routing)")
        mtt = n.get("max_turn_transition")
        if mtt is not None and mtt != "":
            if not isinstance(mtt, str) or not self.target_exists(mtt, is_global):
                self.err(f"{where}.max_turn_transition", f"target '{mtt}' does not exist")

        # prompts
        for fld in ("task_message", "role_message", "loop_prompt", "routing_prompt", "loop_condition"):
            v = n.get(fld)
            if v is not None and not isinstance(v, str):
                self.err(f"{where}.{fld}", "must be a string")
            elif isinstance(v, str):
                self.check_placeholders(v, f"{where}.{fld}")

        # placement of tools / pre_actions
        tools = n.get("tools")
        pre = n.get("pre_actions")
        if tools is not None and not isinstance(tools, list):
            self.err(f"{where}.tools", "tools must be an array")
            tools = []
        if pre is not None and not isinstance(pre, list):
            self.err(f"{where}.pre_actions", "pre_actions must be an array")
            pre = []
        if tools and ntype != "conversation":
            self.err(f"{where}.tools", f"tools on a '{ntype}' node: the platform keeps tools only on conversation nodes and strips them silently")
        if pre and ntype not in ACTION_NODE_TYPES:
            self.err(f"{where}.pre_actions", f"pre_actions on a '{ntype}' node: the platform keeps pre_actions only on api_request/code nodes and strips them silently. Put the call in its own api_request node in front")
        if tools and pre:
            self.err(where, "a node cannot carry both tools and pre_actions")
        node_mapping = n.get("response_mapping")
        if node_mapping is not None and not isinstance(node_mapping, list):
            self.err(f"{where}.response_mapping", "response_mapping must be an array")
            node_mapping = []
        if node_mapping and ntype == "conversation":
            self.warn(f"{where}.response_mapping", "node-level response_mapping on a conversation node is not applied; put the mapping on the tool")
        if node_mapping and ntype == "code":
            self.warn(f"{where}.response_mapping", "a code node returns data=null; a mapping has nothing to read. Write into vars instead")
        if node_mapping:
            self.check_mapping(node_mapping, f"{where}.response_mapping")

        # extraction
        es = n.get("extraction_schema")
        if es is not None:
            self.check_extraction(es, f"{where}.extraction_schema")

        # transitions
        trs = n.get("transitions")
        if trs is None:
            if ntype != "end_call":
                self.err(f"{where}.transitions", "transitions array is required (use [] on end_call nodes)")
            trs = []
        elif not isinstance(trs, list):
            self.err(f"{where}.transitions", "transitions must be an array")
            trs = []
        self.check_transitions(key, n, trs, where, is_global)

        # passthrough
        if n.get("passthrough") is True:
            pdt = n.get("passthrough_default_transition")
            if not isinstance(pdt, str) or not pdt:
                self.err(f"{where}.passthrough_default_transition", "passthrough node needs passthrough_default_transition")
            elif not self.target_exists(pdt, is_global):
                self.err(f"{where}.passthrough_default_transition", f"target '{pdt}' does not exist")
            last = trs[-1] if trs else None
            last_cond = last.get("condition") if isinstance(last, dict) else None
            if not (isinstance(last_cond, dict) and last_cond.get("operator") == "always"):
                self.err(f"{where}.transitions", "passthrough node must end with an unconditional 'always' transition or it deadlocks")
            elif isinstance(pdt, str) and pdt and last.get("target_node") != pdt:
                self.info(f"{where}.passthrough_default_transition", f"differs from the final always target '{last.get('target_node')}'")
            oe_type = oe.get("type") if isinstance(oe, dict) else "llm"
            if oe_type == "llm":
                self.warn(f"{where}.on_enter", "passthrough node with on_enter llm: use silent or a short fixed tts line")
        elif ntype in ("api_request", "code"):
            self.warn(where, f"{ntype} node is not passthrough: it waits for a user message after its entry action")
        elif "passthrough_default_transition" in n and n["passthrough_default_transition"] not in ("", None):
            pdt = n["passthrough_default_transition"]
            if not isinstance(pdt, str) or not self.target_exists(pdt, is_global):
                self.err(f"{where}.passthrough_default_transition", f"target '{pdt}' does not exist")

        # per type
        if ntype == "conversation":
            self.check_conversation(key, n, where, tools or [], trs)
        elif ntype == "api_request":
            self.check_api_request_node(key, n, where, pre or [])
        elif ntype == "code":
            self.check_code_node(key, n, where, pre or [])
        elif ntype == "end_call":
            self.check_end_call(key, n, where, trs)
        if ntype != "end_call" and "terminal" in n:
            self.warn(f"{where}.terminal", "terminal is used only on end_call nodes")

        # global node extras
        if is_global:
            cond = n.get("condition")
            if not isinstance(cond, dict):
                self.err(f"{where}.condition", "global node needs a condition")
            else:
                self.check_condition(cond, f"{where}.condition", top=True)
                self.check_bool_pairs(cond, f"{where}.condition")
            ex = n.get("excluded_nodes")
            if ex is not None:
                if not isinstance(ex, list):
                    self.err(f"{where}.excluded_nodes", "must be an array of node keys")
                    ex = []
                for e in ex:
                    if e not in self.nodes:
                        self.err(f"{where}.excluded_nodes", f"'{e}' is not a node key")
            ends = [k for k, v in self.nodes.items() if isinstance(v, dict) and v.get("node_type") == "end_call"]
            missing = [e for e in ends if e not in (ex or [])]
            if missing:
                self.warn(f"{where}.excluded_nodes", f"end_call nodes not excluded ({', '.join(missing)}): a global node can fire from a terminal node and loop")
        else:
            for fld in ("condition", "excluded_nodes"):
                if fld in n:
                    self.warn(f"{where}.{fld}", f"'{fld}' belongs to global nodes only")

    # ------------------------------------------------------------ conversation nodes
    def check_conversation(self, key, n, where, tools, trs):
        task = n.get("task_message")
        if not isinstance(task, str) or not task.strip():
            self.warn(f"{where}.task_message", "conversation node without a task_message")
            task = task if isinstance(task, str) else ""
        loop_prompt = n.get("loop_prompt") if isinstance(n.get("loop_prompt"), str) else ""
        if not tools:
            if not NO_TOOL_RE.search(task):
                self.warn(f"{where}.task_message", "node has no tools but task_message does not say that no tool call is allowed in this turn")
            if loop_prompt and not NO_TOOL_RE.search(loop_prompt):
                self.warn(f"{where}.loop_prompt", "node has no tools but loop_prompt does not say that no tool call is allowed (the rule must be in both prompts)")
        names_seen = {}
        for i, tool in enumerate(tools):
            label = self.tool_label(tool, i)
            twhere = f"{where}.tools[{label}]"
            if not isinstance(tool, dict):
                self.err(twhere, "tool must be an object")
                continue
            self.check_tool(tool, twhere, placement="tools", node_key=key)
            fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            handler = fn.get("handler")
            desc = fn.get("description")
            if not isinstance(desc, str) or not desc.strip():
                self.warn(twhere, "tool has no description: it is the only text the dialogue model reads about the tool")
            elif "call" not in desc.lower():
                self.info(twhere, "description does not say when to CALL the tool; a plain description lets the model acknowledge in words and never call it")
            if handler == HANDLER_END:
                self.warn(twhere, "end_call as a tool on a conversation node: the documented form is an end_call node with a terminal")
            if isinstance(fn.get("name"), str):
                if fn["name"] in names_seen:
                    self.warn(twhere, f"duplicate tool name '{fn['name']}' in this node")
                names_seen[fn["name"]] = True
                if fn["name"] and fn["name"] not in task and handler != HANDLER_END:
                    self.info(twhere, f"task_message never names the tool '{fn['name']}'; say when to call it")
            cfg = tool.get("config")
            if isinstance(cfg, dict) and cfg.get("alwaysRunsAt"):
                self.warn(twhere, "lifecycle tool (alwaysRunsAt) inside a node: it runs only when the call starts/ends in this node. Put it in the workflow-level tools array")
        # transition_to_<node> mentions
        tool_call_targets = {t.get("target_node") for t in trs if isinstance(t, dict) and t.get("is_tool_call") is True}
        for m in re.finditer(r"transition_to_([A-Za-z0-9_]+)", task + "\n" + loop_prompt):
            tgt = m.group(1)
            if tgt not in tool_call_targets:
                self.warn(f"{where}.task_message", f"prompt mentions transition_to_{tgt} but there is no is_tool_call transition to '{tgt}' in this node")
        for tgt in sorted(t for t in tool_call_targets if isinstance(t, str)):
            if f"transition_to_{tgt}" not in task and f"transition_to_{tgt}" not in loop_prompt:
                self.info(f"{where}.transitions", f"is_tool_call transition to '{tgt}' is never named as transition_to_{tgt} in the prompt")
        # naming other nodes in the prompt
        for other in self.all_nodes:
            if other == key or "_" not in other:
                continue
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(other) + r"(?![A-Za-z0-9_])", task):
                self.info(f"{where}.task_message", f"task_message names the node '{other}': the model does not know about nodes and may narrate steps")

    # ------------------------------------------------------------ action nodes
    def check_api_request_node(self, key, n, where, pre):
        if not pre:
            self.err(f"{where}.pre_actions", "api_request node needs a pre_actions entry")
        for i, tool in enumerate(pre):
            label = self.tool_label(tool, i)
            twhere = f"{where}.pre_actions[{label}]"
            if not isinstance(tool, dict):
                self.err(twhere, "pre_action must be an object")
                continue
            self.check_tool(tool, twhere, placement="pre_actions")
            fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            if fn.get("handler") == HANDLER_CODE:
                self.warn(twhere, "code_exec in an api_request node; use node_type code")

    def check_code_node(self, key, n, where, pre):
        if not pre:
            self.err(f"{where}.pre_actions", "code node needs a pre_actions entry with a code_exec function")
        if len(pre) > 1:
            self.warn(f"{where}.pre_actions", "code node with more than one pre_action")
        for i, tool in enumerate(pre):
            label = self.tool_label(tool, i)
            twhere = f"{where}.pre_actions[{label}]"
            if not isinstance(tool, dict):
                self.err(twhere, "pre_action must be an object")
                continue
            self.check_tool(tool, twhere, placement="pre_actions")
            fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            if fn.get("handler") != HANDLER_CODE:
                self.err(twhere, f"code node pre_action handler must be {HANDLER_CODE}")

    # ------------------------------------------------------------ end_call nodes
    def check_end_call(self, key, n, where, trs):
        if trs:
            self.err(f"{where}.transitions", "end_call node must have no transitions")
        term = n.get("terminal")
        if not isinstance(term, dict):
            self.err(f"{where}.terminal", "end_call node needs a terminal object")
            return
        if term.get("type") != "function":
            self.err(f"{where}.terminal", "terminal.type must be 'function'")
        fn = term.get("function")
        if not isinstance(fn, dict):
            self.err(f"{where}.terminal", "terminal.function is required")
            return
        if fn.get("handler") != HANDLER_END:
            self.err(f"{where}.terminal", f"terminal handler must be {HANDLER_END}, got {fn.get('handler')!r}")
        if not isinstance(fn.get("name"), str) or not fn["name"]:
            self.warn(f"{where}.terminal", "terminal function has no name: the call's endedReason is this name")
        params = fn.get("parameters")
        props = params.get("properties") if isinstance(params, dict) else None
        if not isinstance(props, dict):
            self.warn(f"{where}.terminal", "terminal has no parameters.properties (message_mode / spoken_message)")
            props = {}
        mode = (props.get("message_mode") or {}).get("default") if isinstance(props.get("message_mode"), dict) else None
        if mode is not None and mode not in MESSAGE_MODES:
            self.err(f"{where}.terminal", f"message_mode must be one of {sorted(MESSAGE_MODES)}, got {mode!r}")
        if mode == "custom":
            sm = (props.get("spoken_message") or {}).get("default") if isinstance(props.get("spoken_message"), dict) else None
            if not isinstance(sm, str) or not sm.strip():
                self.warn(f"{where}.terminal", "message_mode custom without a spoken_message default")
            elif isinstance(sm, str):
                self.check_placeholders(sm, f"{where}.terminal.spoken_message", spoken=True)
        if mode == "llm":
            lp = (props.get("llm_prompt") or {}).get("default") if isinstance(props.get("llm_prompt"), dict) else None
            if not isinstance(lp, str) or not lp.strip():
                self.warn(f"{where}.terminal", "message_mode llm without an llm_prompt default")
        if isinstance(props.get("interruptible"), dict) and props["interruptible"].get("default") is True:
            tpb = (props.get("trigger_pattern_both") or {}).get("default") if isinstance(props.get("trigger_pattern_both"), dict) else None
            if not tpb:
                self.warn(f"{where}.terminal", "interruptible without trigger_pattern_both: every polite reply cancels the hang-up")
        for k, v in props.items():
            if isinstance(v, dict) and "const" in v:
                self.err(f"{where}.terminal.{k}", "const does not bake a value; use default")
        oe = n.get("on_enter")
        oe_type = oe.get("type") if isinstance(oe, dict) else "llm"
        if oe_type != "silent":
            self.warn(f"{where}.on_enter", "end_call node should use on_enter silent and put the farewell in the terminal's spoken_message")
        if n.get("disable_inactivity_monitor") is not True:
            self.warn(where, "end_call node should set disable_inactivity_monitor to true")

    # ------------------------------------------------------------ tools (any placement)
    def check_tool(self, tool, where, placement, node_key=None):
        """placement: 'tools' | 'pre_actions' | 'workflow'."""
        if tool.get("type") != "function":
            self.err(where, "tool.type must be 'function'")
        fn = tool.get("function")
        if not isinstance(fn, dict):
            self.err(where, "tool.function is required")
            return
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            self.err(where, "function.name is required")
        handler = fn.get("handler")
        if handler not in HANDLERS:
            if isinstance(handler, str) and handler.startswith("__function__:"):
                self.warn(where, f"handler '{handler}' is not covered by the docs")
            else:
                self.err(where, f"function.handler must be one of {sorted(HANDLERS)}, got {handler!r}")
        cfg = tool.get("config")
        if cfg is not None and not isinstance(cfg, dict):
            self.err(f"{where}.config", "config must be an object")
            cfg = {}
        cfg = cfg or {}
        for fld in ("timeoutMs", "maxRetries"):
            if fld in cfg and (not isinstance(cfg[fld], (int, float)) or isinstance(cfg[fld], bool) or cfg[fld] < 0):
                self.err(f"{where}.config.{fld}", "must be a non-negative number")
        if "connect_retries" in cfg:
            self.warn(f"{where}.config", "connect_retries is a baked parameter next to url and method, not a config field")
        ara = cfg.get("alwaysRunsAt")
        if ara is not None:
            if not isinstance(ara, list):
                self.err(f"{where}.config.alwaysRunsAt", "must be an array")
            else:
                for v in ara:
                    if v not in LIFECYCLE_VALUES:
                        self.err(f"{where}.config.alwaysRunsAt", f"unknown value {v!r}")
                    elif v == "each_turn":
                        self.err(f"{where}.config.alwaysRunsAt", "'each_turn' is accepted by the schema but never fires")
                if placement == "workflow" and not ara:
                    self.err(f"{where}.config.alwaysRunsAt", "workflow-level tool with empty alwaysRunsAt never runs and the model never sees it")
                if "end_of_call" in ara and tool.get("response_mapping"):
                    self.warn(f"{where}.response_mapping", "response_mapping is not applied for end_of_call tools")
        elif placement == "workflow":
            self.err(f"{where}.config", "workflow-level tool without alwaysRunsAt never runs and the model never sees it")
        # hooks
        for hook in ("pre_process_code", "post_process_code"):
            if hook in tool:
                if handler != HANDLER_API:
                    self.err(f"{where}.{hook}", f"{hook} is honoured only on api_call tools; the platform removes it from {handler}")
                elif isinstance(tool[hook], str) and tool[hook].strip():
                    self.check_python(tool[hook], f"{where}.{hook}", "hook")
                elif not isinstance(tool[hook], str):
                    self.err(f"{where}.{hook}", "hook must be a string")
        # mapping placement
        if placement == "pre_actions":
            if "response_mapping" in tool:
                self.err(f"{where}.response_mapping", "response_mapping nested inside a pre_actions entry is ignored; put it at node level")
            if "extraction_schema" in tool:
                self.err(f"{where}.extraction_schema", "extraction_schema nested inside a pre_actions entry is ignored; put it at node level")
        elif "response_mapping" in tool:
            if not isinstance(tool["response_mapping"], list):
                self.err(f"{where}.response_mapping", "response_mapping must be an array")
            else:
                self.check_mapping(tool["response_mapping"], f"{where}.response_mapping")
        if "interruptible" in cfg and cfg["interruptible"] is False:
            self.info(f"{where}.config", "background tool: results arrive one or more turns later; gate transitions with is_set")
        # parameters by handler
        params = fn.get("parameters")
        if handler == HANDLER_API:
            self.check_api_params(params, where, placement, name if isinstance(name, str) else "", node_key)
        elif handler == HANDLER_CODE:
            self.check_code_params(params, where, placement)
        elif handler == HANDLER_END:
            if params is not None and not isinstance(params, dict):
                self.err(f"{where}.parameters", "parameters must be an object")

    def check_code_params(self, params, where, placement):
        if not isinstance(params, dict) or not isinstance(params.get("properties"), dict):
            self.err(f"{where}.parameters", "code_exec needs parameters.properties with a code property")
            return
        props = params["properties"]
        code = props.get("code")
        if not isinstance(code, dict):
            self.err(f"{where}.parameters.code", "code property is required")
            return
        if placement == "pre_actions" or "default" in code:
            if not isinstance(code.get("default"), str):
                self.err(f"{where}.parameters.code", "code must be a baked default string")
            else:
                self.check_python(code["default"], f"{where}.code", "code")
        if "const" in code:
            self.err(f"{where}.parameters.code", "const does not bake; use default")
        tm = props.get("timeout_ms")
        if isinstance(tm, dict) and "default" in tm and (not isinstance(tm["default"], (int, float)) or isinstance(tm["default"], bool)):
            self.err(f"{where}.parameters.timeout_ms", "timeout_ms default must be a number")

    def check_api_params(self, params, where, placement, name, node_key=None):
        if not isinstance(params, dict):
            self.err(f"{where}.parameters", "api_call needs a parameters object")
            return
        props = params.get("properties")
        if not isinstance(props, dict):
            self.err(f"{where}.parameters", "parameters.properties is required")
            return
        for k in props:
            if k not in API_TOP_LEVEL:
                self.err(f"{where}.parameters.{k}", "field spec at the top level of parameters.properties is not a body field; declare it under body.properties")
        # url / method
        for fld in ("url", "method"):
            p = props.get(fld)
            if not isinstance(p, dict):
                self.err(f"{where}.parameters.{fld}", f"{fld} is required with a default")
                continue
            if "const" in p:
                self.err(f"{where}.parameters.{fld}", "const does not bake a value; the engine reads only default (an api_call with a const url fails with 'URL is required')")
            if not isinstance(p.get("default"), str) or not p["default"]:
                self.err(f"{where}.parameters.{fld}", f"{fld} needs a non-empty default")
        url = props.get("url", {}).get("default") if isinstance(props.get("url"), dict) else None
        if isinstance(url, str):
            for v in self.placeholders(url):
                if not self.is_known_var(v):
                    self.warn(f"{where}.parameters.url", f"url references {{{{{v}}}}} which nothing sets; the literal placeholder would be sent")
        method = props.get("method", {}).get("default") if isinstance(props.get("method"), dict) else None
        if isinstance(method, str) and method.upper() not in HTTP_METHODS:
            self.warn(f"{where}.parameters.method", f"unusual HTTP method {method!r}")
        # headers
        hdr = props.get("headers")
        if hdr is not None:
            if not isinstance(hdr, dict):
                self.err(f"{where}.parameters.headers", "headers must be an object schema")
            else:
                if "const" in hdr:
                    self.err(f"{where}.parameters.headers", "const does not bake; use default")
                hp = hdr.get("properties")
                if isinstance(hp, dict):
                    for hk, hv in hp.items():
                        if not isinstance(hv, dict):
                            self.err(f"{where}.parameters.headers.{hk}", "header must be an object with a default")
                        elif "const" in hv:
                            self.err(f"{where}.parameters.headers.{hk}", "const does not bake; use default")
                        elif "default" not in hv:
                            self.warn(f"{where}.parameters.headers.{hk}", "header without a default: the model is asked to fill it")
                elif "default" in hdr and isinstance(hdr["default"], dict):
                    self.warn(f"{where}.parameters.headers", "headers given as one default object; declare each header as a property with its own default")
        # connect_retries
        cr = props.get("connect_retries")
        if isinstance(cr, dict):
            d = cr.get("default")
            if "const" in cr:
                self.err(f"{where}.parameters.connect_retries", "const does not bake; use default")
            if d is not None and (not isinstance(d, (int, float)) or isinstance(d, bool) or d < 0 or d > 5):
                self.warn(f"{where}.parameters.connect_retries", "default should be a number from 0 to 5 (hard cap 5)")
        # body
        body = props.get("body")
        body_fields = {}
        if body is not None:
            if not isinstance(body, dict):
                self.err(f"{where}.parameters.body", "body must be an object schema")
            else:
                if "const" in body:
                    self.err(f"{where}.parameters.body", "const does not bake; use default")
                if isinstance(body.get("default"), dict):
                    self.err(f"{where}.parameters.body", "body.default template object: the engine looks for field specs at body.properties.<field>, the dashboard shows an empty form and saving from there removes the tool")
                bp = body.get("properties")
                if not isinstance(bp, dict):
                    if "default" not in body:
                        self.warn(f"{where}.parameters.body", "body without properties")
                else:
                    body_fields = bp
                    req = body.get("required")
                    if req is not None:
                        if not isinstance(req, list):
                            self.err(f"{where}.parameters.body.required", "required must be an array")
                            req = []
                        for r in req:
                            if r not in bp:
                                self.err(f"{where}.parameters.body.required", f"required field '{r}' is not declared under body.properties")
                    req = req or []
                    for fk, fv in bp.items():
                        fwhere = f"{where}.parameters.body.{fk}"
                        if not isinstance(fv, dict):
                            self.err(fwhere, "body field must be an object schema")
                            continue
                        if "const" in fv:
                            self.err(fwhere, "const does not bake a value and never resolves {{var}}; use default")
                        if isinstance(fv.get("properties"), dict):
                            self.warn(fwhere, "nested object under a body field: each body field should be a leaf under body.properties")
                        if "default" not in fv:
                            self.warn(fwhere, "body field without a default: give each leaf its own default ('{{" + fk + "}}' for a model-filled field)")
                            continue
                        d = fv["default"]
                        ph = self.single_placeholder(d)
                        model_intended = bool(fv.get("description")) or "enum" in fv or fk in req
                        if ph is not None:
                            if placement == "tools":
                                if self.is_known_var(ph) and not self.is_system_var(ph):
                                    if model_intended and (node_key is None or self.writer_can_precede(ph, node_key)):
                                        writers = ", ".join(sorted(self.var_writers.get(ph, ())))
                                        self.err(fwhere, f"model-filled field: default {{{{{ph}}}}} names a variable that is set elsewhere ({writers}) before this node can be entered, so the value is baked on node entry and the model never sees the parameter")
                                    elif model_intended:
                                        writers = ", ".join(sorted(self.var_writers.get(ph, ())))
                                        self.warn(fwhere, f"model-filled field shares its name with a variable written in {writers}; those nodes cannot precede this one today, but a re-entry or a new path would bake the value. Rename one of them")
                                    else:
                                        # no description/enum/required: probably meant to be baked; say from where
                                        self.info(fwhere, f"field {fk} is baked by {self.writer_text(ph)} ({{{{{ph}}}}}): the model never fills it")
                                elif not model_intended and ph == fk:
                                    self.info(fwhere, f"{{{{{ph}}}}} is not set by test_variables, extraction, mapping or code: unless it is a call variable, the model fills it with no description")
                                elif not model_intended and ph != fk:
                                    self.warn(fwhere, f"default {{{{{ph}}}}} is never set in the workflow and the field has no description: the model is asked for '{ph}' blind")
                            elif placement == "pre_actions":
                                if not self.is_known_var(ph):
                                    self.warn(fwhere, f"engine-run call: {{{{{ph}}}}} is never set, so the field is dropped from the request")
                            elif placement == "workflow":
                                if not self.is_known_var(ph) and not model_intended:
                                    self.info(fwhere, f"lifecycle tool: {{{{{ph}}}}} is never set; one model call fills the parameter at run time")
                        elif isinstance(d, str) and "{{" in d:
                            for v in self.placeholders(d):
                                if not self.is_known_var(v):
                                    self.warn(fwhere, f"mixed value references {{{{{v}}}}} which nothing sets; the literal placeholder is sent")
                        if "enum" in fv:
                            if not isinstance(fv["enum"], list) or not fv["enum"]:
                                self.err(fwhere, "enum must be a non-empty array")
                            elif ph is None and d not in fv["enum"]:
                                self.err(fwhere, f"baked default {d!r} is not one of the field's own enum values")
        self.check_api_against_spec(name, props, body_fields, where, placement)

    # ------------------------------------------------------------ OpenAPI cross-check
    def _spec(self):
        if not isinstance(self.api, dict):
            return None
        if hasattr(self, "_spec_cache"):
            return self._spec_cache
        servers = self.api.get("servers") or []
        base = servers[0].get("url", "").rstrip("/") if servers and isinstance(servers[0], dict) else ""
        ops = {}
        for path, item in (self.api.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            name = path.strip("/").split("/")[-1]
            for method, op in item.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(op, dict):
                    continue
                schema = {}
                try:
                    schema = op["requestBody"]["content"]["application/json"]["schema"]
                except Exception:
                    schema = {}
                ops.setdefault(name, {})[method.upper()] = {
                    "path": path,
                    "properties": schema.get("properties") or {},
                    "required": schema.get("required") or [],
                }
        self._spec_cache = {"base": base, "ops": ops}
        return self._spec_cache

    def check_api_against_spec(self, name, props, body_fields, where, placement):
        spec = self._spec()
        if spec is None or not name:
            return
        ops = spec["ops"].get(name)
        if not ops:
            self.err(where, f"api_call tool '{name}' is not an operation of the OpenAPI file ({', '.join(sorted(spec['ops'])) or 'no operations'})")
            return
        url = props.get("url", {}).get("default") if isinstance(props.get("url"), dict) else None
        expected = f"{spec['base']}/{name}"
        if isinstance(url, str) and url != expected:
            self.err(f"{where}.parameters.url", f"url {url!r} is not base_url + '/' + name ({expected!r})")
        method = props.get("method", {}).get("default") if isinstance(props.get("method"), dict) else None
        m = method.upper() if isinstance(method, str) else None
        op = ops.get(m) if m else None
        if op is None:
            self.err(f"{where}.parameters.method", f"method {method!r} is not offered for /{name} (spec: {', '.join(sorted(ops))})")
            op = next(iter(ops.values()))
        sprops, sreq = op["properties"], op["required"]
        for r in sreq:
            leaf = body_fields.get(r)
            if not isinstance(leaf, dict):
                self.err(f"{where}.parameters.body", f"required body field '{r}' of the spec is missing (declare it under body.properties with a default)")
            elif "default" not in leaf:
                self.err(f"{where}.parameters.body.{r}", "required body field has no default: neither baked nor model-filled")
        for fk, fv in body_fields.items():
            fwhere = f"{where}.parameters.body.{fk}"
            if fk not in sprops:
                self.warn(fwhere, f"body field '{fk}' is not in the spec for /{name}")
                continue
            if not isinstance(fv, dict):
                continue
            sp = sprops[fk] if isinstance(sprops[fk], dict) else {}
            senum = sp.get("enum")
            d = fv.get("default")
            ph = self.single_placeholder(d)
            if isinstance(senum, list):
                if isinstance(fv.get("enum"), list):
                    extra = [v for v in fv["enum"] if v not in senum]
                    missing = [v for v in senum if v not in fv["enum"]]
                    if extra:
                        self.err(fwhere, f"enum values not in the spec: {extra} (spec: {senum})")
                    if missing:
                        if name == "close_call" and fk == "outcome":
                            self.err(fwhere, f"close_call outcome enum does not match the spec: missing {missing} (spec: {senum})")
                        else:
                            self.warn(fwhere, f"enum is a subset of the spec: missing {missing}")
                elif ph is None and d is not None:
                    if d not in senum:
                        self.err(fwhere, f"baked value {d!r} is not an allowed value of the spec {senum}")
                elif ph is not None and (placement == "tools" or placement == "workflow"):
                    self.warn(fwhere, f"model-filled field without an enum although the spec restricts it to {senum}: the model may invent a value")
            stype = sp.get("type")
            ftype = fv.get("type")
            if stype and ftype and stype != ftype and not (stype == "number" and ftype == "integer"):
                self.warn(fwhere, f"type '{ftype}' differs from the spec type '{stype}'")

    # ------------------------------------------------------------ mappings, extraction, conditions
    def check_mapping(self, mapping, where):
        for i, m in enumerate(mapping):
            mw = f"{where}[{i}]"
            if not isinstance(m, dict):
                self.err(mw, "mapping entry must be an object")
                continue
            path, var = m.get("path"), m.get("variable")
            if not isinstance(path, str) or not path:
                self.err(mw, "mapping needs a path")
            elif not path.startswith("data."):
                self.warn(mw, f"path '{path}' does not start with 'data.': the result is an envelope and only data.* paths are verified to work")
            if not isinstance(var, str) or not var:
                self.err(mw, "mapping needs a variable name")
            elif not NAME_RE.match(var):
                self.warn(mw, f"variable name '{var}' is not a plain identifier")

    def check_extraction(self, es, where):
        if not isinstance(es, list):
            self.err(where, "extraction_schema must be an array")
            return
        seen = set()
        for i, e in enumerate(es):
            ew = f"{where}[{i}]"
            if not isinstance(e, dict):
                self.err(ew, "entry must be an object")
                continue
            name = e.get("name")
            if not isinstance(name, str) or not name:
                self.err(ew, "extraction entry needs a name")
                name = ""
            else:
                ew = f"{where}[{name}]"
                if not NAME_RE.match(name):
                    self.warn(ew, "variable name should match ^[a-zA-Z_]\\w*$")
                if name in seen:
                    self.warn(ew, "duplicate variable name in this schema")
                seen.add(name)
            t = e.get("type")
            if t == "enum":
                self.warn(ew, "type 'enum' is deprecated and becomes string; use type string with enum_values")
            elif t not in EXTRACTION_TYPES:
                self.err(ew, f"type must be one of {sorted(EXTRACTION_TYPES)}, got {t!r}")
            ev = e.get("enum_values")
            if ev is not None and (not isinstance(ev, list) or not ev):
                self.err(ew, "enum_values must be a non-empty array")
            if "min_confidence" not in e:
                self.warn(ew, "no min_confidence: the default 0.95 is strict and a discarded value leaves no trace")
            else:
                mc = e["min_confidence"]
                if not isinstance(mc, (int, float)) or isinstance(mc, bool) or not 0 <= mc <= 1:
                    self.err(ew, "min_confidence must be a number from 0.0 to 1.0")
            if name and t == "string" and ev is None and DATE_NAME_RE.search(name):
                self.warn(ew, f"'{name}' looks like a date but is typed string: use type date so the extractor gets today's date and relative-date rules")
            ep = e.get("extraction_prompt")
            if isinstance(ep, str) and ep.strip():
                missing = [p for p in EXTRACTION_PROMPT_PLACEHOLDERS if p not in ep]
                if missing:
                    self.err(ew, f"extraction_prompt replaces the whole template and lacks {missing}: the extractor never sees the user's message")
            if "description" not in e or not isinstance(e.get("description"), str) or not e["description"].strip():
                self.warn(ew, "extraction entry without a description")
            vp = e.get("validation_pattern")
            if isinstance(vp, str) and vp:
                try:
                    re.compile(vp)
                except re.error as ex:
                    self.err(ew, f"validation_pattern does not compile: {ex}")

    def check_condition(self, c, where, top):
        if not isinstance(c, dict):
            self.err(where, "condition must be an object")
            return
        if "logic" in c:
            logic = c.get("logic")
            if logic not in ("or", "and"):
                self.err(where, f"logic must be 'or' or 'and', got {logic!r}")
            if top and logic == "and":
                self.err(where, "top-level condition group uses logic 'and': the top level must be 'or' (nest the AND group inside it)")
            conds = c.get("conditions")
            if not isinstance(conds, list) or not conds:
                self.err(where, "condition group needs a non-empty conditions array")
                return
            for i, sub in enumerate(conds):
                self.check_condition(sub, f"{where}.conditions[{i}]", top=False)
            return
        op = c.get("operator")
        if op not in ALL_OPERATORS:
            self.err(where, f"unknown operator {op!r}")
            return
        if op == "always":
            if not top:
                self.warn(where, "'always' inside a group makes the whole group unconditional")
            return
        if op == "matches_intent":
            if not isinstance(c.get("description"), str) or not c["description"].strip():
                self.err(where, "matches_intent needs a description")
            if not top:
                self.info(where, "matches_intent inside a variable group mixes a model judgement into a deterministic check")
            return
        var = c.get("variable")
        if not isinstance(var, str) or not var:
            self.err(where, f"operator {op} needs a variable")
        else:
            if top:
                self.info(where, "bare variable condition directly under condition; the verified shape is a {\"logic\": \"or\", \"conditions\": [...]} group")
            if not self.is_known_var(var):
                self.warn(where, f"variable '{var}' is not set by anything in the workflow (test_variables, extraction, mapping, code, tool results)")
            self.check_placeholders(var, where)
        if op in OPERAND_OPERATORS and "operand" not in c:
            self.err(where, f"operator {op} needs an operand")
        if op in ("greater_than", "less_than"):
            try:
                float(c.get("operand"))
            except (TypeError, ValueError):
                self.err(where, f"operand of {op} must be numeric")

    def _collect_leaves(self, c, out):
        if not isinstance(c, dict):
            return
        if "logic" in c:
            for sub in c.get("conditions") or []:
                self._collect_leaves(sub, out)
        elif c.get("operator") in ("equals", "not_equals"):
            out.append((c.get("variable"), c.get("operator"), c.get("operand")))

    def check_bool_pairs(self, cond, where):
        leaves = []
        self._collect_leaves(cond, leaves)
        pairs = {(v, op, str(o)) for v, op, o in leaves}
        reported = set()
        for v, op, o in leaves:
            if not isinstance(v, str) or v in reported:
                continue
            so = str(o)
            if BOOL_OPERAND_RE.match(so):
                other = so[0].swapcase() + so[1:]
                if (v, op, other) not in pairs:
                    reported.add(v)
                    self.warn(where, f"{op} on '{v}' tests only {so!r}: booleans arrive as 'true' or 'True' depending on the writer, test both spellings or route on a string flag")

    def check_transitions(self, key, n, trs, where, is_global):
        ntype = n.get("node_type")
        seen_targets = {}
        always_at = None
        seen_intent = False
        for i, t in enumerate(trs):
            tw = f"{where}.transitions[{i}]"
            if not isinstance(t, dict):
                self.err(tw, "transition must be an object")
                continue
            tgt = t.get("target_node")
            if not isinstance(tgt, str) or not tgt:
                self.err(tw, "transition needs a target_node")
            elif not self.target_exists(tgt, is_global):
                if tgt == "__previous__":
                    self.err(tw, "__previous__ is allowed only in global nodes")
                else:
                    self.err(tw, f"target_node '{tgt}' does not exist")
            desc = t.get("description")
            if not isinstance(desc, str) or not desc.strip():
                self.warn(tw, "transition without a description: the routing model reads it")
            elif isinstance(desc, str):
                self.check_placeholders(desc, f"{tw}.description")
            cond = t.get("condition")
            if cond is None:
                self.err(tw, "transition needs a condition")
                continue
            self.check_condition(cond, f"{tw}.condition", top=True)
            self.check_bool_pairs(cond, f"{tw}.condition")
            op = cond.get("operator") if isinstance(cond, dict) else None
            is_det = isinstance(cond, dict) and ("logic" in cond or op in VAR_OPERATORS)
            if t.get("is_tool_call") is True:
                if op != "matches_intent":
                    self.warn(tw, "is_tool_call transition without a matches_intent condition: the dialogue model triggers it as a tool and the condition should describe that intent")
            else:
                if op == "matches_intent":
                    seen_intent = True
                elif is_det and seen_intent:
                    self.info(tw, "deterministic condition listed after a matches_intent transition; put deterministic conditions first")
            if always_at is not None and t.get("is_tool_call") is not True:
                self.warn(tw, f"transition after the unconditional 'always' transition at index {always_at} can never fire")
            if op == "always" and always_at is None:
                always_at = i
            if isinstance(tgt, str):
                if tgt in seen_targets:
                    self.info(tw, f"second transition to '{tgt}': the engine merges them with OR at load time")
                seen_targets[tgt] = i
        if ntype == "conversation" and not trs and key not in self.end_tool_nodes and not n.get("max_turn_transition"):
            self.err(f"{where}.transitions", "conversation node with no transitions cannot be left")

    # ------------------------------------------------------------ placeholders in text
    def check_placeholders(self, text, where, spoken=False):
        for v in self.placeholders(text):
            if not self.is_known_var(v):
                if spoken:
                    self.warn(where, f"{{{{{v}}}}} is never set: the agent would say the literal placeholder aloud")
                else:
                    self.warn(where, f"{{{{{v}}}}} is never set by test_variables, extraction, mapping, code or tool results: the model sees the literal placeholder")

    # ------------------------------------------------------------ workflow-level tools
    def check_workflow_tools(self):
        tools = self.wf.get("tools")
        if not isinstance(tools, list):
            return
        for i, tool in enumerate(tools):
            label = self.tool_label(tool, i)
            tw = f"tools[{label}]"
            if not isinstance(tool, dict):
                self.err(tw, "tool must be an object")
                continue
            self.check_tool(tool, tw, placement="workflow")

    # ------------------------------------------------------------ graph
    def check_graph(self):
        init = self.wf.get("initial_node")
        edges = {}
        for key, n in self.nodes.items():
            if not isinstance(n, dict):
                continue
            out = set()
            for t in n.get("transitions") or []:
                if isinstance(t, dict) and isinstance(t.get("target_node"), str):
                    out.add(t["target_node"])
            for fld in ("passthrough_default_transition", "max_turn_transition"):
                v = n.get(fld)
                if isinstance(v, str) and v:
                    out.add(v)
            edges[key] = {o for o in out if o in self.nodes}
        # global node targets also enter the graph from everywhere
        global_targets = set()
        for g in self.globals.values():
            if isinstance(g, dict):
                for t in g.get("transitions") or []:
                    if isinstance(t, dict) and isinstance(t.get("target_node"), str) and t["target_node"] in self.nodes:
                        global_targets.add(t["target_node"])
                for fld in ("passthrough_default_transition", "max_turn_transition"):
                    v = g.get(fld)
                    if isinstance(v, str) and v in self.nodes:
                        global_targets.add(v)
        # reachability from initial_node
        if isinstance(init, str) and init in self.nodes:
            seen, stack = set(), [init]
            while stack:
                k = stack.pop()
                if k in seen:
                    continue
                seen.add(k)
                stack.extend(edges.get(k, ()))
                if self.globals:
                    stack.extend(global_targets)
            for k in self.nodes:
                if k not in seen:
                    self.warn(f"nodes.{k}", "node is not reachable from initial_node")
        # every node reaches an end
        sinks = {k for k, n in self.nodes.items() if isinstance(n, dict) and n.get("node_type") == "end_call"}
        sinks |= self.end_tool_nodes
        if not sinks:
            self.err("$.nodes", "no end_call node: every path must reach an end_call node")
        can_end = set(sinks)
        changed = True
        while changed:
            changed = False
            for k, out in edges.items():
                if k not in can_end and out & can_end:
                    can_end.add(k)
                    changed = True
        for k in self.nodes:
            if k not in can_end and sinks:
                self.err(f"nodes.{k}", "no path from this node to an end_call node")
        for k, g in self.globals.items():
            if not isinstance(g, dict):
                continue
            targets = set()
            for t in g.get("transitions") or []:
                if isinstance(t, dict) and isinstance(t.get("target_node"), str):
                    targets.add(t["target_node"])
            pdt = g.get("passthrough_default_transition")
            if isinstance(pdt, str):
                targets.add(pdt)
            if "__previous__" in targets:
                continue
            if targets and not (targets & can_end):
                self.err(f"global_nodes.{k}", "global node has no path back (__previous__) and none to an end_call node")

    # ------------------------------------------------------------ run
    def run(self):
        self.check_nulls(self.wf)
        self.check_top_level()
        if not isinstance(self.wf, dict):
            return self.findings
        self.collect_vars()
        self.check_nodes()
        self.check_workflow_tools()
        self.check_graph()
        self.findings.sort(key=lambda f: LEVEL_ORDER.get(f["level"], 9))
        return self.findings


def lint(wf, api=None):
    """Lint a workflow dict. Returns a list of {level, where, message} sorted ERROR, WARN, INFO."""
    return _Linter(wf, api).run()


def format_findings(findings):
    return "\n".join(f"{f['level']} {f['where']}: {f['message']}" for f in findings)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    api = None
    if "--api" in argv:
        i = argv.index("--api")
        if i + 1 >= len(argv):
            print("usage: lint.py <workflow.json> [--api openapi.json]", file=sys.stderr)
            return 2
        api_path = argv[i + 1]
        args = [a for a in args if a != api_path]
        with open(api_path) as fh:
            api = json.load(fh)
    if len(args) != 1:
        print("usage: lint.py <workflow.json> [--api openapi.json]", file=sys.stderr)
        return 2
    with open(args[0]) as fh:
        wf = json.load(fh)
    if isinstance(wf, dict) and "workflow" in wf and isinstance(wf["workflow"], dict) and "nodes" not in wf:
        wf = wf["workflow"]
    findings = lint(wf, api)
    out = format_findings(findings)
    if out:
        print(out)
    counts = {lvl: sum(1 for f in findings if f["level"] == lvl) for lvl in (ERROR, WARN, INFO)}
    print(f"-- {counts[ERROR]} error(s), {counts[WARN]} warning(s), {counts[INFO]} info")
    return 1 if counts[ERROR] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
