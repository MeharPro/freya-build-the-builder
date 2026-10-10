#!/usr/bin/env python3
"""Smoke-test a published Freya workflow over the chat route, with no simulation. Standard library only.

    source env.sh
    # scripted: fixed customer lines + expectations, exit 1 on a failed expectation
    python3 builder/smoke.py <workflow_id|slot> --script builder/smoke_scripts/opening.json
    # driven: a Claude-played customer follows a persona (optional mode, needs the Claude Agent SDK or the `claude` CLI)
    python3 builder/smoke.py <workflow_id|slot> --customer "You are Daniel Reyes, born 14 March 1988, ..." --max-turns 12

`POST /api/v2/chat/message` runs one turn against the PUBLISHED workflow and answers in seconds (docs/api.md,
"Talk to your workflow turn by turn"). The harness sends the customer's lines one at a time, prints every agent
reply, then reads the call's event log (`GET /api/v2/call/{callId}`) for tool calls, routing and extraction events,
and ends the call with `POST /api/v2/chat/end`. See builder/SMOKE.md for the script format and the limits of the route.

Exit codes: 0 all expectations passed (or driven mode finished), 1 an expectation failed, 2 the call could not be run
(no API key, a bad script file, a 500 or no answer from the route).
"""
import argparse, asyncio, json, os, pathlib, re, socket, subprocess, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402  (stdlib client; reads FREYA_API_KEY / FREYA_API_URL)

DEFAULT_VARIABLES = {"customer_id": "c_smoke", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}
DEFAULT_CUSTOMER_MODEL = "claude-haiku-5-5"
TURN_TIMEOUT_S = 240
# The engine's own functions: a code node runs as `code_exec`, an end_call node's terminal as `end_call`. They are
# listed with the bank tools, but `no_tool_calls` ignores them (a workflow that enters a code node after the
# customer's first answer, the conversation_first pattern, is not "calling a tool" in the bank's sense).
ENGINE_FUNCTIONS = ("code_exec", "end_call")


def die(msg, code=2):
    """Print a clear message and exit with `code` (2 = the run could not be set up or the call could not be run)."""
    print("smoke: " + msg, file=sys.stderr)
    sys.exit(code)

CUSTOMER_SYSTEM = """You are playing a CUSTOMER on a phone call, for a test of a bank's automated phone agent. The agent is \
the other speaker. OUTPUT RULE: write only the words you say on the phone. One or two short sentences, then stop. No stage \
directions, no brackets, no quotation marks, no explanations.
RULES: Answer what you are asked. Do not volunteer facts nobody asked for. Stay in character and do not invent facts that are \
not in your persona; for anything not covered give a short neutral answer. When you give a number or a date, say all of it \
in one turn. If the agent reads something back and it matches what you agreed, say "Yes, I confirm." When the agent says \
goodbye or the call is clearly over, reply with exactly [HANGUP] and nothing else."""


# ----------------------------------------------------------------------------------------------------- HTTP helpers
def scrub(text):
    """Remove API keys and the bank team key from anything that gets printed."""
    text = re.sub(r"fak_[A-Za-z0-9_\-]{8,}", "fak_***", text)
    for name in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY"):
        v = os.environ.get(name)
        if v and len(v) >= 8:
            text = text.replace(v, "<" + name + ">")
    return text


def post(path, body, timeout=TURN_TIMEOUT_S):
    """POST and return (http_status, result). Never raises: status 0 means no answer at all (network); a 2xx whose body
    is not JSON (an empty body, a Cloudflare HTML page) comes back as (status, "non-JSON body: ...") with a str result."""
    req = urllib.request.Request(freya.URL + path, data=json.dumps(body).encode(), headers=freya.HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read().decode(errors="replace")
        try:
            out = json.loads(raw)
        except ValueError:
            return status, "non-JSON body: " + (" ".join(re.sub(r"<[^>]+>", " ", raw).split())[:300] or "(empty)")
        return status, (out.get("data", {}).get("result", out) if isinstance(out, dict) else out)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            j = json.loads(text)
            msg = (j.get("data") or {}).get("message") or j.get("message") or text
        except Exception:
            msg = re.sub(r"<[^>]+>", " ", text)      # an HTML page (Cloudflare 1010, a wrong route, a gateway timeout)
        return e.code, " ".join(str(msg).split())[:600]
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
        return 0, repr(e)


def compact(obj, n=320):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    s = scrub(" ".join(s.split()))
    return s if len(s) <= n else s[: n - 3] + "..."


def fn_name(ev):
    f = ev.get("function")
    if isinstance(f, dict):
        return f.get("name") or f.get("function") or "?"
    return str(f or ev.get("name") or ev.get("tool") or "?")


def tool_result_line(result):
    """One line for a function_call_complete result: HTTP status + data, or the message; ERROR for a function_call_error."""
    if not isinstance(result, dict):
        return compact(result)
    if "error" in result and len(result) == 1:
        return "ERROR " + compact(result["error"], 300)
    parts = []
    if result.get("status_code") is not None:
        parts.append("HTTP %s" % result["status_code"])
    elif result.get("status"):
        parts.append(str(result["status"]))
    if "data" in result:
        parts.append("data=" + compact(result["data"], 260))
    elif result.get("message"):
        parts.append(compact(result["message"], 260))
    return " ".join(parts) or compact(result)


# ----------------------------------------------------------------------------------------------------- the chat call
class Chat:
    """One chat-route call: send() a customer line, get the agent's reply plus the engine events of that turn."""

    def __init__(self, workflow_id, variables):
        self.workflow_id, self.variables = workflow_id, variables
        self.call_id, self.seen, self.turns, self.tool_calls, self.last_vars = None, 0, [], [], None
        self.ended_by_agent, self.end_result, self.in_tail, self.tail_events = False, None, False, []

    @staticmethod
    def describe(status, res, started):
        if status == 504:
            return "HTTP 504: the agent service timed out (the gateway waits about 60 s; the platform may be busy)"
        if status == 502:
            return "HTTP 502: the agent service returned no response (seen when the agent ends the call during the turn, or on a busy platform)"
        if status == 503:
            return "HTTP 503: %s (the agent service did not take the message: busy platform, or agent not configured)" % res
        if status == 500:
            return "HTTP 500: %s%s" % (res, "" if started else " (a bare 500 on the first turn: the workflow cannot start a call at all)")
        if 200 <= status < 300:
            return "HTTP %s with a body the harness cannot read: %s" % (status, compact(res, 300))
        return "HTTP %s: %s" % (status, res) if status else "no answer: %s" % res

    def send(self, text, retries=3, recover_s=60):
        """Send one customer line. On 502/503/504 the engine may still have handled the turn (seen: a 502 when the agent
        ended the call in that turn; a 504 when a turn ran past the gateway limit), so the call log is read before the
        line is sent again. Without a callId there is nothing to read: the first turn is simply sent again."""
        n = len(self.turns) + 1
        body = {"message": text}
        if self.call_id:
            body["callId"] = self.call_id
        else:
            body["workflowId"] = self.workflow_id
            body["customerVariables"] = self.variables
        turn = {"n": n, "customer": text, "agent": "", "status": None, "seconds": 0, "events": [], "error": None}
        self.turns.append(turn)
        t0 = time.time()
        for attempt in range(retries + 1):
            status, res = post("/api/v2/chat/message", body)
            turn["status"] = status
            if status == 200 and isinstance(res, dict):
                self.call_id = res.get("callId") or self.call_id
                turn["agent"] = (res.get("response") or "").strip()
                turn["message_id"] = res.get("messageId")
                turn["error"] = None
                if res.get("warning"):
                    turn["warning"] = res["warning"]
                if res.get("endedByAgent"):
                    turn["ended_by_agent"] = self.ended_by_agent = True
                break
            turn["error"] = self.describe(status, res, bool(self.call_id))
            # transient: the engine may have handled the turn although the route did not deliver the reply
            transient = status in (502, 503, 504, 0) or 200 <= status < 300      # 2xx here: a body that was not JSON
            if self.call_id and transient:
                wait, t1 = (12 if status == 503 else recover_s), time.time()
                while True:
                    self.collect(turn)
                    if turn["agent"] or self.ended_by_agent or time.time() - t1 >= wait:
                        break
                    time.sleep(6)
                if turn["agent"] or self.ended_by_agent:
                    turn["error"] += " | the engine handled the turn anyway (%s, from the call log after %.0f s)" % (
                        "reply recovered" if turn["agent"] else "the call ended", time.time() - t1)
                    break
                turn["events"].append("[harness] nothing new in the call log after %.0f s" % (time.time() - t1))
            if transient and attempt < retries:
                turn["events"].append("[harness] %s%s: sending the line again in 15 s (%d/%d)"
                                      % ("HTTP %d" % status if status else "no answer", "" if self.call_id else " before the call exists", attempt + 1, retries))
                time.sleep(15)
                continue
            break
        turn["seconds"] = round(time.time() - t0, 1)
        self.collect(turn)
        if turn.get("ended_by_agent") is None and self.ended_by_agent:
            turn["ended_by_agent"] = True
        return turn

    def collect(self, turn):
        """Read the call's event log and attach the new events (and, after a 504, the missing reply) to `turn`."""
        if not self.call_id:
            return
        try:
            msgs = freya.get_call(self.call_id).get("messages") or []
        except Exception as e:
            turn["events"].append("[harness] could not read the call log: %s" % compact(str(e), 200))
            return
        new, self.seen = msgs[self.seen:], len(msgs)
        for m in new:
            role = m.get("role")
            if role == "assistant":
                if not turn["agent"] and turn["customer"]:        # the reply the chat route did not deliver (504)
                    turn["agent"] = (m.get("message") or "").strip()
            elif role == "system":
                try:
                    ev = json.loads(m.get("message") or "{}")
                except Exception:
                    continue
                self.event(ev, turn)

    def event(self, ev, turn):
        e, lines = ev.get("event"), turn["events"]
        if e == "node_enter":
            lines.append("[node] %s -> %s%s" % (ev.get("from_node") or "-", ev.get("node"), " (%s)" % ev["reason"] if ev.get("reason") else ""))
        elif e == "route_evaluated":
            if isinstance(ev.get("variable_table"), dict):
                self.last_vars = ev["variable_table"]
            if ev.get("matched"):
                lines.append("[route] %s -> %s: %s" % (ev.get("from_node"), ev.get("target"), compact(ev.get("reason") or "", 160)))
            else:
                lines.append("[route] stays in %s (no transition matched)" % ev.get("from_node"))
        elif e == "variable_extracted":
            lines.append("[extract] %s = %r" % (ev.get("name"), ev.get("value")))
        elif e == "function_call_start":
            name, args = fn_name(ev), ev.get("args")
            if name == "api_call" and isinstance(args, dict) and args.get("url"):   # a pre_action api_request: name it by its endpoint
                name = args["url"].rstrip("/").rsplit("/", 1)[-1].split("?")[0] or name
                self.api_alias = name
            rec = {"turn": turn["n"], "tool": name, "args": args, "result": None, "after_end": self.in_tail}
            self.tool_calls.append(rec)
            if isinstance(args, dict) and "url" in args:
                lines.append("[tool] %s %s %s body=%s" % (name, args.get("method", ""), args.get("url", ""), compact(args.get("body"), 240)))
            else:
                lines.append("[tool] %s args=%s" % (name, compact(args, 240)))
        elif e in ("function_call_complete", "function_call_error"):
            name = fn_name(ev)
            if name == "api_call" and getattr(self, "api_alias", None):
                name = self.api_alias
            result = ev.get("result")
            if e == "function_call_error":       # {"event", "function", "error": "API request failed: {...}"}
                result = {"error": ev.get("error") or ev.get("message") or "error"}
            rec = next((r for r in reversed(self.tool_calls) if r["tool"] == name and r["result"] is None), None)
            if rec is None:
                rec = {"turn": turn["n"], "tool": name, "args": None, "result": None, "after_end": self.in_tail}
                self.tool_calls.append(rec)
            rec["result"] = result
            lines.append("[tool] %s -> %s" % (name, tool_result_line(result)))
        elif e == "call_ended":
            self.ended_by_agent = True
            lines.append("[call] ended by the engine")
        elif e == "error":
            lines.append("[error] %s %s" % (compact(ev.get("message") or "", 200), compact(ev.get("details") or "", 200)))

    def end(self):
        if not self.call_id:
            return None
        status, res = post("/api/v2/chat/end", {"callId": self.call_id}, timeout=60)
        self.end_result = res if status == 200 else "HTTP %s: %s" % (status, res)
        # End-of-call tools (close_call runs at end_of_call) are logged up to half a minute after the call ends: poll until quiet.
        # They are the consequence of ending the call, not of a customer line: kept apart from the turns ("end").
        self.in_tail = True
        tail, quiet, t0 = {"n": len(self.turns), "customer": "", "agent": "", "events": self.tail_events}, 0, time.time()
        while time.time() - t0 < 45 and quiet < 3:
            before = self.seen
            self.collect(tail)
            quiet = quiet + 1 if self.seen == before else 0
            time.sleep(4)
        return self.end_result

    def plain_vars(self):
        """The variable table after the last routing, without the engine's own entries."""
        out = {}
        for k, v in (self.last_vars or {}).items():
            if k.endswith("_turns") or k.startswith("system.") or k.startswith("call."):
                continue
            out[k] = v.get("value") if isinstance(v, dict) and "value" in v else v
        return out


# ----------------------------------------------------------------------------------------------------- printing
def print_turn(turn, who="customer"):
    print("--- turn %d" % turn["n"])
    print("%s: %s" % (who, turn["customer"]))
    if turn.get("error"):
        print("agent: !! %s" % turn["error"])
    if turn["agent"]:
        print("agent (%.1fs): %s" % (turn.get("seconds", 0), turn["agent"]))
    elif not turn.get("error"):
        print("agent (%.1fs): (empty reply)" % turn.get("seconds", 0))
    if turn.get("warning"):
        print("   [warning] %s" % compact(turn["warning"], 300))
    for line in turn["events"]:
        print("   " + line)
    if turn.get("ended_by_agent"):
        print("   [call] ended by the agent")
    sys.stdout.flush()


def print_summary(chat):
    print("== tool calls (%d) from GET /api/v2/call/%s" % (len(chat.tool_calls), chat.call_id))
    for i, t in enumerate(chat.tool_calls, 1):
        a = t["args"] if isinstance(t["args"], dict) else {}
        req = "%s %s body=%s" % (a.get("method", ""), a.get("url", ""), compact(a.get("body"), 300)) if "url" in a else "args=" + compact(t["args"], 300)
        print(" %d. %-7s %-18s %s" % (i, "end" if t.get("after_end") else "turn %d" % t["turn"], t["tool"], req))
        print("    -> %s" % (tool_result_line(t["result"]) if t["result"] is not None else "(no result event)"))
    if not chat.tool_calls:
        print(" (none)")
    v = chat.plain_vars()
    print("== variables after the last routing (%d): %s" % (len(v), compact(v, 900)))


def first_node_note(workflow_id, chat):
    """Say so when the workflow starts with a code node whose variables never appeared: the chat route skips it (docs/api.md)."""
    try:
        w = freya.api("GET", "/api/v2/workflow/%s" % workflow_id, workspaceId=freya.workspace_id())["workflow"]["workflow"]
        first = (w.get("nodes") or {}).get(w.get("initial_node") or "", {})

        def strings(o):                      # the code of a code node sits in pre_actions[].function.parameters
            if isinstance(o, str):
                yield o
            elif isinstance(o, dict):
                for v in o.values():
                    yield from strings(v)
            elif isinstance(o, list):
                for v in o:
                    yield from strings(v)
        code = "\n".join(strings([first.get("pre_actions"), first.get("code")]))
        written = sorted(set(re.findall(r"vars\[\s*['\"](\w+)['\"]\s*\]\s*=", code)))
        if written:
            seen = chat.plain_vars()
            missing = [k for k in written if k not in seen]
            if missing:
                print("NOTE: the first node %r is a code node that writes %s; %s never appeared in the variable table. "
                      "The chat route can skip a first code step (docs/api.md): values it computes are empty here but not in a simulation."
                      % (w.get("initial_node"), ", ".join(written), ", ".join(missing)))
            else:
                print("NOTE: the first node %r is a code node and its variables (%s) are present." % (w.get("initial_node"), ", ".join(written)))
    except Exception as e:
        print("NOTE: could not read the workflow to check its first node: %s" % compact(str(e), 160))


# ----------------------------------------------------------------------------------------------------- expectations
def find(term, text):
    """The first match of a term in the text, or None. `re:<regex>` is a case-insensitive regex; anything else a
    case-insensitive substring. Raises re.error for an invalid regex (validate_script catches that before the call)."""
    pattern = term[3:] if isinstance(term, str) and term.startswith("re:") else re.escape(str(term))
    return re.search(pattern, text, re.I)


def matches(term, text):
    return find(term, text) is not None


def load_script(path):
    """The script file as a dict; a missing file, invalid JSON or a non-object exits 2 with a clear message."""
    try:
        script = json.loads(pathlib.Path(path).read_text())
    except FileNotFoundError:
        die("script not found: %s" % path)
    except OSError as e:
        die("cannot read the script %s: %s" % (path, e))
    except ValueError as e:
        die("the script %s is not valid JSON: %s" % (path, e))
    if not isinstance(script, dict):
        die("the script %s must be a JSON object with turns and expect" % path)
    return script


def validate_script(script):
    """Problems in a script's turns and expectations, found before any call is made (a bad script is exit 2, not a
    failed expectation): turns that are not strings, an `after_turn` beyond the turns, an unknown key, an invalid regex."""
    problems, turns = [], script.get("turns")
    if not isinstance(turns, list) or not turns or not all(isinstance(t, str) and t.strip() for t in turns):
        problems.append("turns must be a non-empty list of customer lines (strings)")
    expect = script.get("expect") or []
    if not isinstance(expect, list):
        problems.append("expect must be a list")
        expect = []
    known = {"after_turn", "cumulative", "contains_any", "contains_all", "not_contains", "no_tool_calls", "tools_called_any", "tools_not_called", "tool", "note"}
    for i, ex in enumerate(expect, 1):
        if not isinstance(ex, dict):
            problems.append("expect[%d] is not an object" % i)
            continue
        for k in ex:
            if k not in known:
                problems.append("expect[%d]: unknown key %r (known: %s)" % (i, k, ", ".join(sorted(known))))
        tl = ex.get("tool")
        if tl is not None:
            if not isinstance(tl, dict) or not isinstance(tl.get("name"), str) or not set(tl) <= {"name", "count", "values_in_order", "results_true"}:
                problems.append("expect[%d]: tool must be an object {name, count?, values_in_order?, results_true?}" % i)
            elif ("count" in tl and (not isinstance(tl["count"], int) or isinstance(tl["count"], bool))) or \
                    not all(isinstance(x, str) for x in (tl.get("values_in_order") or []) + (tl.get("results_true") or [])):
                problems.append("expect[%d]: tool.count must be an integer, values_in_order and results_true lists of strings" % i)
        n = ex.get("after_turn")
        if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n < 1 or (isinstance(turns, list) and n > len(turns))):
            problems.append("expect[%d]: after_turn %r is not a turn number between 1 and %d" % (i, n, len(turns) if isinstance(turns, list) else 0))
        for key in ("contains_any", "contains_all", "not_contains", "tools_called_any", "tools_not_called"):
            terms = ex.get(key)
            if terms is None:
                continue
            if not isinstance(terms, list) or not all(isinstance(t, str) for t in terms):
                problems.append("expect[%d]: %s must be a list of strings" % (i, key))
                continue
            for t in terms:
                if key.startswith("tools"):
                    continue
                try:
                    find(t, "")
                except re.error as e:
                    problems.append("expect[%d]: %s has an invalid regex %r: %s" % (i, key, t, e))
    return problems


def evaluate(expect, chat):
    """Return a list of (ok, line). One line per check. An invalid regex gives a FAIL line, never a traceback."""
    out, turns = [], chat.turns

    def text_for(ex):
        n = ex.get("after_turn")
        if n is None:
            return " \n".join(t["agent"] for t in turns), "all turns", None
        if not isinstance(n, int) or n < 1 or n > len(turns):
            return None, "turn %s" % n, "no such turn (%d sent)" % len(turns)
        t = turns[n - 1]
        if not t["agent"]:
            return None, "turn %d" % n, "no reply (%s)" % (t.get("error") or "empty")
        if ex.get("cumulative"):
            return " \n".join(x["agent"] for x in turns[:n]), "turns 1-%d" % n, None
        return t["agent"], "turn %d" % n, None

    for ex in expect:
        text, label, err = text_for(ex)
        if err:
            out.append((False, "FAIL %s: %s" % (label, err)))
            continue
        try:
            if ex.get("contains_any"):
                hit = next((t for t in ex["contains_any"] if matches(t, text)), None)
                out.append((hit is not None, "%s %s contains_any %s%s" % ("PASS" if hit else "FAIL", label, json.dumps(ex["contains_any"], ensure_ascii=False)[:160], " -> %r" % hit if hit else " -> none found in: %r" % compact(text, 200))))
            for term in ex.get("contains_all") or []:
                ok = matches(term, text)
                out.append((ok, "%s %s contains %r" % ("PASS" if ok else "FAIL", label, term)))
            for term in ex.get("not_contains") or []:
                m = find(term, text)
                where = ""
                if m:
                    lo = max(0, m.start() - 60)
                    where = " in: %r" % (" ".join(text[lo: m.end() + 60].split()))
                out.append((m is None, "%s %s not_contains %r%s" % ("PASS" if m is None else "FAIL", label, term, where)))
        except re.error as e:
            out.append((False, "FAIL %s: invalid regex in the script: %s" % (label, e)))
        n = ex.get("after_turn")          # with after_turn: the tools of the conversation up to that turn, not the end-of-call ones
        tools = [t["tool"] for t in chat.tool_calls if n is None or (t["turn"] <= n and not t.get("after_end"))]
        if ex.get("no_tool_calls"):       # the engine's own code_exec / end_call do not count: see ENGINE_FUNCTIONS
            bank, engine = [t for t in tools if t not in ENGINE_FUNCTIONS], [t for t in tools if t in ENGINE_FUNCTIONS]
            ok = not bank
            out.append((ok, "%s %s no_tool_calls%s%s" % ("PASS" if ok else "FAIL", label, "" if ok else " -> called " + ", ".join(bank),
                                                        " (engine's own %s ignored)" % ", ".join(sorted(set(engine))) if engine else "")))
        if ex.get("tools_called_any"):
            hit = next((t for t in ex["tools_called_any"] if t in tools), None)
            out.append((hit is not None, "%s %s tools_called_any %s%s" % ("PASS" if hit else "FAIL", label, ex["tools_called_any"], " -> " + hit if hit else " -> called " + (", ".join(tools) or "nothing"))))
        for name in ex.get("tools_not_called") or []:
            ok = name not in tools
            out.append((ok, "%s %s tool %s not called%s" % ("PASS" if ok else "FAIL", label, name, "" if ok else " -> it was")))
        if ex.get("tool"):
            out.extend(check_tool(ex["tool"], [t for t in chat.tool_calls if n is None or (t["turn"] <= n and not t.get("after_end"))], label))
    return out


def _digits(v):
    return re.sub(r"\D", "", str(v))


def body_of(rec):
    a = rec.get("args") if isinstance(rec.get("args"), dict) else {}
    b = a.get("body", a)
    if isinstance(b, str):
        try:
            b = json.loads(b)
        except ValueError:
            b = {"_": b}
    return b if isinstance(b, dict) else {}


def result_of(rec):
    r = rec.get("result")
    if isinstance(r, dict) and isinstance(r.get("data"), dict):
        r = r["data"]
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except ValueError:
            pass
    return r if isinstance(r, dict) else {}


def check_tool(spec, recs, label):
    """`tool` expectation: the calls of one tool. `count` exact number of calls; `values_in_order`: the k-th call's body
    holds a value equal to the k-th expected value (compared on its digits when the expected value has digits, so
    '1988-03-14' matches an ISO answer and '4471' a four-digit one; never a value in words); `results_true`: every
    call's result has these keys and they are true (e.g. ok, verified)."""
    out, name = [], spec["name"]
    calls = [r for r in recs if r["tool"] == name]
    if "count" in spec:
        ok = len(calls) == spec["count"]
        out.append((ok, "%s %s tool %s called %d time(s), expected %d" % ("PASS" if ok else "FAIL", label, name, len(calls), spec["count"])))
    for k, want in enumerate(spec.get("values_in_order") or []):
        if k >= len(calls):
            out.append((False, "FAIL %s tool %s call %d with %r -> no such call (%d made)" % (label, name, k + 1, want, len(calls))))
            continue
        vals = [v for v in body_of(calls[k]).values() if isinstance(v, (str, int, float)) and not isinstance(v, bool)]
        wd = _digits(want)
        ok = any((_digits(v) == wd and re.fullmatch(r"[\d\s\-/.]+", str(v).strip() or "x")) if wd else str(v).strip().lower() == want.strip().lower() for v in vals)
        out.append((ok, "%s %s tool %s call %d carries %r%s" % ("PASS" if ok else "FAIL", label, name, k + 1, want, "" if ok else " -> body " + compact(body_of(calls[k]), 200))))
    for key in spec.get("results_true") or []:
        bad = [i + 1 for i, r in enumerate(calls) if result_of(r).get(key) is not True]
        ok = bool(calls) and not bad
        out.append((ok, "%s %s tool %s result %s true on every call%s" % ("PASS" if ok else "FAIL", label, name, key,
                                                                         "" if ok else " -> not on call(s) %s" % (bad or "none made"))))
    return out


# ----------------------------------------------------------------------------------------------------- the customer model (driven mode)
async def _ask_sdk(system, prompt, model):
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
    opts = ClaudeAgentOptions(model=model, system_prompt=system, tools=[], permission_mode="dontAsk", max_turns=1,
                              setting_sources=[], cwd=str(ROOT))
    out = []
    async for m in query(prompt=prompt, options=opts):
        if isinstance(m, AssistantMessage):
            for b in m.content:
                if isinstance(b, TextBlock):
                    out.append(b.text)
    return "\n".join(out).strip()


def ask_customer(system, prompt, model):
    """The customer's next line, from the Claude Agent SDK, or from `claude -p` when the SDK is not installed."""
    try:
        import claude_agent_sdk  # noqa: F401
        return asyncio.run(_ask_sdk(system, prompt, model))
    except ImportError:
        pass
    r = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", system, "--tools", "", "--output-format", "text",
                        "--no-session-persistence", prompt], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("claude -p failed: " + (r.stderr or r.stdout)[-400:])
    return r.stdout.strip()


def customer_prompt(persona, turns):
    lines = []
    for t in turns:
        lines.append("You: " + t["customer"])
        lines.append("Agent: " + (t["agent"] or "(no reply)"))
    return ("YOUR PERSONA:\n%s\n\nTRANSCRIPT SO FAR:\n%s\n\nWrite your next line on the phone (or exactly [HANGUP] if the call is over)."
            % (persona, "\n".join(lines) or "(the phone just rang, you picked up)"))


def clean_line(s):
    s = s.strip().strip('"').strip("'").strip()
    s = re.sub(r"^(You|Customer)\s*:\s*", "", s, flags=re.I)
    return " ".join(s.split())


# ----------------------------------------------------------------------------------------------------- main
def resolve_workflow(arg):
    f = ROOT / ".freya-agents.json"
    if f.exists():
        state = json.loads(f.read_text())
        if arg in state:
            return state[arg]["workflow_id"]
    return arg


def case_by_id(case_id, path=None):
    path = path or ROOT / "public-test-set.json"
    data = json.load(open(path))
    for c in (data.get("cases") if isinstance(data, dict) else data) or []:
        if c["id"] == case_id:
            return c
    die("no case %s in %s" % (case_id, path))


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def spoken(v):
    """How a customer says a case value: an ISO date as '14 March 1988', anything else as it is."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    return "%d %s %s" % (int(m.group(3)), MONTHS[int(m.group(2)) - 1], m.group(1)) if m else str(v)


def answer_values(case, answers=None):
    """Placeholders for scripts: {{answerN}} (spoken) and {{answerN_raw}} (as the case stores it), N = 1.. in the order
    of the case's `identity` (the order a brief asks its security questions in the practice set); --answers overrides."""
    raw = [str(x) for x in (answers if answers is not None else list((case or {}).get("identity", {}).values()))]
    out = {}
    for i, v in enumerate(raw, 1):
        out["answer%d" % i], out["answer%d_raw" % i] = spoken(v), v
    return out


def fill(obj, values):
    """Replace {{name}} in every string of obj; an unknown name is left as it is (validate_placeholders reports it)."""
    if isinstance(obj, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, list):
        return [fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: fill(v, values) for k, v in obj.items()}
    return obj


def practice_variables(case):
    """Open a practice customer on the mock bank for this case (its `mock_case`, else its id): real customer_id, so
    the bank tools answer for real over the chat route. Needs FREYA_BANK_TEAM_KEY."""
    sys.path.insert(0, str(ROOT / "tools"))
    from score import http      # noqa: E402  the kit's mock-bank client
    s = http("/v1/practice/sessions", {"case": case.get("mock_case", case["id"])})
    v = s.get("variables") if isinstance(s, dict) else None
    if not v or not v.get("customer_id"):
        die("the mock bank opened no practice session for %s: %s" % (case["id"], compact(s, 200)))
    v = dict(v)
    if (case.get("variables") or {}).get("now"):
        v["now"] = case["variables"]["now"]
    return v


def persona_from_case(case):
    v, i = case["variables"], case.get("identity") or {}
    me = "%s %s" % (v["first_name"], v["last_name"])
    if case.get("family") == "Third party" or case.get("third_party"):
        who = "You are NOT %s. You answered this phone. You do not know %s's security answers and would not give them." % (me, me)
    else:
        who = "You are %s. " % me + " ".join("Your %s is %s." % (k.replace("_", " "), x) for k, x in i.items()) + " Give these only when asked."
    return who + "\nWHAT HAPPENS IN THIS CALL: " + case["script"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow", help="workflow id, or a slot name from .freya-agents.json (e.g. brief-a)")
    ap.add_argument("--script", help="scripted mode: JSON with variables, turns and expectations")
    ap.add_argument("--customer", help="driven mode: persona text for the Claude-played customer")
    ap.add_argument("--max-turns", type=int, default=12, help="driven mode: customer lines at most (default 12)")
    ap.add_argument("--model", default=DEFAULT_CUSTOMER_MODEL, help="driven mode: the customer's model (default %s)" % DEFAULT_CUSTOMER_MODEL)
    ap.add_argument("--opening", default="Hello?", help="driven mode: the customer's first line (default 'Hello?')")
    ap.add_argument("--case", help="take the call variables (and, in driven mode without --customer, the persona) from this practice case id")
    ap.add_argument("--cases", help="the case file --case is looked up in (default public-test-set.json; a generated cases file works, its mock_case opens the practice customer)")
    ap.add_argument("--practice", action="store_true", help="with --case: open a practice customer on the mock bank (real customer_id), so bank tools answer for real")
    ap.add_argument("--answers", help="JSON list of the security answers for {{answer1}}, {{answer2}}, ... (default: the case's identity values in order)")
    ap.add_argument("--vars", help="JSON object merged over the call variables, e.g. '{\"customer_id\": \"c_123\"}'")
    ap.add_argument("--out", help="write a JSON record of the run here")
    a = ap.parse_args(argv)
    if not os.environ.get("FREYA_API_KEY"):
        die("FREYA_API_KEY is not set. source env.sh first.")
    if not a.script and not (a.customer or a.case):
        ap.error("give --script <file> (scripted) or --customer '<persona>' / --case <id> (driven)")

    workflow_id = resolve_workflow(a.workflow)
    script = load_script(a.script) if a.script else {}
    if a.script:
        problems = validate_script(script)
        if problems:
            die("the script %s cannot be run:\n  - %s" % (a.script, "\n  - ".join(problems)))
    variables = dict(DEFAULT_VARIABLES)
    case = case_by_id(a.case, a.cases) if a.case else None
    if a.practice and not case:
        die("--practice needs --case <id>")
    if case:
        variables.update(case["variables"])
    if a.script:
        try:
            answers = json.loads(a.answers) if a.answers else None
        except ValueError as e:
            die("--answers is not valid JSON: %s" % e)
        values = {k: str(v) for k, v in ((case or {}).get("variables") or {}).items()}   # {{first_name}}, {{last_name}}, ...
        values.update(answer_values(case, answers))
        script = fill(script, values)
        left = sorted(set(re.findall(r"\{\{(\w+)\}\}", json.dumps({"t": script.get("turns"), "e": script.get("expect")}))))
        if left:
            die("the script %s uses %s: give --case <id> (its identity values) or --answers '[...]'" % (a.script, ", ".join("{{%s}}" % x for x in left)))
    variables.update(script.get("variables") or {})
    if a.vars:
        try:
            extra = json.loads(a.vars)
        except ValueError as e:
            die("--vars is not valid JSON: %s" % e)
        if not isinstance(extra, dict):
            die("--vars must be a JSON object")
        variables.update(extra)
    if a.practice:
        variables.update(practice_variables(case))
    variables.setdefault("customer_id", "c_smoke")

    mode = "scripted" if a.script else "driven"
    persona = None
    if mode == "driven":
        persona = a.customer or (persona_from_case(case) if case else None)
        if not persona:
            die("driven mode needs --customer '<persona text>' or --case <id>")
    print("smoke %s | workflow %s | %s" % (mode, workflow_id, a.script or "persona"))
    if script.get("name"):
        print("script: %s" % script["name"])
    print("variables: %s" % json.dumps(variables, ensure_ascii=False))
    chat = Chat(workflow_id, variables)
    rc, checks = 0, []
    try:
        if mode == "scripted":
            turns = script.get("turns") or []
            for i, line in enumerate(turns):
                if chat.ended_by_agent:
                    print("--- the agent ended the call; %d scripted turn(s) not sent" % (len(turns) - i))
                    break
                t = chat.send(line)
                print_turn(t)
                if t["status"] in (500, 0) or not chat.call_id:
                    print("!! %s on turn %d. Stopping%s." % (t["error"], t["n"], "" if chat.call_id else ": no call was started"))
                    rc = 2
                    break
        else:
            print("customer model: %s" % a.model)
            if not a.customer:
                print("persona (from case %s): %s" % (a.case, compact(persona, 400)))
            line = a.opening
            for i in range(a.max_turns):
                t = chat.send(line)
                print_turn(t)
                if t["status"] in (500, 0) or not chat.call_id:
                    print("!! %s on turn %d. Stopping%s." % (t["error"], t["n"], "" if chat.call_id else ": no call was started"))
                    rc = 2
                    break
                if chat.ended_by_agent:
                    break
                if i + 1 == a.max_turns:
                    print("--- max turns (%d) reached" % a.max_turns)
                    break
                t0 = time.time()
                try:
                    nxt = clean_line(ask_customer(CUSTOMER_SYSTEM, customer_prompt(persona, chat.turns), a.model))
                except Exception as e:
                    print("!! the customer model failed: %s. Stopping." % compact(str(e), 300))
                    rc = 2
                    break
                if not nxt or "[HANGUP]" in nxt.upper():
                    print("--- customer hung up (%.1fs)" % (time.time() - t0))
                    break
                line = nxt
    except KeyboardInterrupt:
        print("\n!! interrupted")
        rc = 2
    finally:
        end = chat.end()
        print("--- POST /api/v2/chat/end -> %s" % compact(end if end is not None else "(no call was started)", 200))
        for line in chat.tail_events:
            print("   " + line)

    if chat.call_id:
        print_summary(chat)
        first_node_note(workflow_id, chat)
    if mode == "scripted":
        checks = evaluate(script.get("expect") or [], chat)
        print("== expectations (%d)" % len(checks))
        for ok, line in checks:
            print(" " + line)
        failed = sum(1 for ok, _ in checks if not ok)
        if failed and rc == 0:
            rc = 1
        print("RESULT: %s | %d/%d checks passed | call %s" % ("PASS" if rc == 0 else "FAIL", len(checks) - failed, len(checks), chat.call_id))
    else:
        print("RESULT: transcript of %d turn(s), %d tool call(s) | call %s" % (len(chat.turns), len(chat.tool_calls), chat.call_id))
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        rec = {"mode": mode, "workflow_id": workflow_id, "call_id": chat.call_id, "variables": variables, "script": a.script, "persona": persona,
               "case": a.case, "customer_model": a.model if mode == "driven" else None,
               "turns": chat.turns, "tool_calls": chat.tool_calls, "end": chat.end_result, "checks": [{"ok": ok, "line": l} for ok, l in checks],
               "variables_after": chat.plain_vars(), "exit_code": rc}
        open(a.out, "w").write(scrub(json.dumps(rec, indent=1, ensure_ascii=False, default=str)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
