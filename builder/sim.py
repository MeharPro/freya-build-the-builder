#!/usr/bin/env python3
"""Local simulator: run the practice customers against a published phone agent over Freya's chat route, no simulation.

    source env.sh
    python3 builder/sim.py <workflow_id|slot> [--brief A|B] [--only PUB-01,PUB-02] [--reps 1] [--style talkative | --styles none,terse|kit|extra|all]
                           [--concurrency 5] [--max-turns 30] [--out results/sim.json] [--transcripts results/transcripts/]
                           [--customer-model gpt-5-mini] [--judge-model gpt-5] [--verbose]

Replaces tools/run_cases.py for practice runs. Each case is one chat-route call (POST /api/v2/chat/message, one turn at
a time, no simulation queue, so cases run in parallel) against the PUBLISHED workflow, with a model-played customer
(the organisers' persona text from tools/run_cases.py). The score is computed exactly like run_cases.py: the mock bank's
ledger (tools/score.py) plus a judge model that reads the transcript against the case's conversation checks.

Customer and judge models: OpenAI chat completions over urllib when OPENAI_API_KEY is set (defaults gpt-5-mini / gpt-5),
otherwise the Claude CLI (`claude -p`, defaults claude-haiku-5-5 / claude-sonnet-5-5, run from an empty scratch directory so
the repo's CLAUDE.md, settings and skills never reach the customer or the judge). Standard library only.
See builder/SIM.md for how this differs from the organisers' simulation and for the chat route's caveats.
"""
import argparse, json, os, pathlib, re, socket, subprocess, sys, tempfile, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import freya                                      # noqa: E402  stdlib client (FREYA_API_KEY, FREYA_API_URL)
from score import http, score_ledger              # noqa: E402  the mock bank + the ledger check
from run_cases import STYLES, persona_for         # noqa: E402  the organisers' persona text (PERSONA template inside)

# Extra ways of talking, in the organisers' STYLES format (one "HOW YOU TALK:" paragraph appended to the PERSONA; the
# facts of the case never change, so the expected ledger stays the case's). Brief-agnostic: no bank, product, value or
# rule. From docs/personas-plan.md section 3 and the habits of the organisers' persona model seen on Freya (terse lines,
# digits and dates in words unasked, cut-off turns). Local runs only (--provider claude while OpenAI is closed).
EXTRA_STYLES = {
    "terse": "HOW YOU TALK: you answer in one short line, never more than a few words. You say dates, years and digits in words even when nobody asked you to, like 'fourteenth of March nineteen eighty-eight' and 'four four seven one'. Once in the call your sentence stops early, as if you were cut off, and you finish it only when the caller asks.",
    "rambling_corrects": "HOW YOU TALK: you talk a lot and add a sentence about your day before most answers. The first time you say a payment day or an amount, you say a slightly different one. When the caller reads it back to you, you say 'no, sorry, I meant' and give the right one, which is the one written above. Do this once in the call. Never do it with a security answer.",
    "pieces_identity": "HOW YOU TALK: when the caller asks a security question, you give the answer in two parts: say the first half, stop, and give the rest in your next turn or when asked, like 'forty-four' and then 'seventy-one', or 'the fourteenth of March' and then 'nineteen eighty-eight'. This replaces the rule about saying all of it in one turn. Everything else you say in one turn.",
    "impatient": "HOW YOU TALK: you are in a hurry. Your answers are short and a bit irritated. Once in the call, before you answer, you say something like 'Can we make this quick? I'm at work.' or 'How long is this going to take?'. You still give every answer when asked, and you never hang up before the caller says goodbye.",
    "previous_question": "HOW YOU TALK: once in the call, you answer the question the caller asked BEFORE the current one again, as if you had not heard the new question, like repeating your date of birth when asked for something else. When the caller asks again, you answer the current question correctly.",
    "volunteer": "HOW YOU TALK: you like to get things done. As soon as the caller asks the first security question, you give all your security answers in one go. When the caller tells you why they are calling, you say straight away what you can do, as written above, without waiting to be asked. This replaces the rule about not volunteering information. The facts stay exactly as written above.",
    "silent_turn": "HOW YOU TALK: once in the call, right after the caller asks you something, you reply only '...' as if you did not hear or were distracted. In your next turn you answer normally. Once more in the call, when the caller reads a payment back to you, you reply only 'Sorry, say that again?' and confirm only after the caller repeats it.",
    "hangs_up_after_promise": "HOW YOU TALK: you want the call over. As soon as you have said 'Yes, I confirm.' to a payment read-back, your next line is 'Great, thanks, bye.' and after that you say nothing more, whatever the caller says.",
    "final_like": "HOW YOU TALK: you answer in short lines, sometimes with a sentence about your day first. Once in the call you give a long number or date in two parts (the first half, then the rest in your next turn). Once in the call, before you answer, you ask a short question back, like 'why do you need that?'. You say amounts and dates in words, like 'four hundred and twenty' and 'the sixteenth of October'. Whatever the caller replies, you then give your answer. The facts stay exactly as written above.",
}
STYLES.update(EXTRA_STYLES)        # the dict run_cases.persona_for reads; tools/run_cases.py itself stays as shipped
KIT_STYLES = ("pieces", "corrects", "talkative", "asks_back", "in_words")


def styled_cases(cases, spec):
    """One copy of every case per style. `spec` is a comma list of style names, or kit | extra | all; `none` in the
    list adds the unstyled copy (so a run can say 'passes unstyled, fails styled'). A styled copy keeps the original
    mock customer (`mock_case`, else the original id: public cases carry none) and its expected ledger, and gets the
    id '<id>[<style>]' so transcripts do not overwrite each other."""
    names = {"kit": KIT_STYLES, "extra": tuple(EXTRA_STYLES), "all": KIT_STYLES + tuple(EXTRA_STYLES)}.get(spec)
    if names is None:
        names = tuple(x.strip() for x in spec.split(",") if x.strip())
    unknown = [x for x in names if x != "none" and x not in STYLES]
    if unknown:
        raise SystemExit("unknown style(s): %s (known: none, %s)" % (", ".join(unknown), ", ".join(sorted(STYLES))))
    out = []
    for c in cases:
        for st in names:
            st = None if st == "none" else st
            out.append(dict(c, id=c["id"] + ("[%s]" % st if st else ""), mock_case=c.get("mock_case", c["id"]), style=st, base_id=c["id"]))
    return out

OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
DEFAULTS = {"openai": {"customer": "gpt-5-mini", "judge": "gpt-5"}, "claude": {"customer": "claude-sonnet-5-5", "judge": "claude-sonnet-5-5"}}
def _find_claude_cli():
    """The Claude Code binary for the Claude provider: $CLAUDE_CLI, then `claude` on PATH, then the binary bundled in the
    claude-agent-sdk package (a clean clone with only requirements.txt installed), then the user-local install."""
    import shutil
    cand = [os.environ.get("CLAUDE_CLI") or "", shutil.which("claude") or ""]
    try:
        import claude_agent_sdk
        cand.append(str(pathlib.Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"))
    except Exception:
        pass
    cand.append(str(pathlib.Path.home() / ".local/bin/claude"))
    for c in cand:
        if c and os.path.exists(c):
            return c
    return "claude"


CLAUDE_CLI = _find_claude_cli()
TURN_TIMEOUT_S = 240          # one chat turn; the gateway itself gives up after about 60 s (504)
RECOVER_S = 60                # after a 504 mid-call: how long to look for the reply in the call log
PHONE_RULE = "You are on a phone call. Reply with ONLY your next spoken line."
JUDGE_SYSTEM = ("You judge a simulated phone call between a bank's automated phone agent (agent) and a person who answered "
                "the phone (customer). You get the success criteria, the transcript and the list of tool calls the agent made, "
                "in order. Decide whether EVERY criterion is true, from the transcript and the tool calls only. "
                'Answer with JSON only, nothing else: {"outcome": "pass" or "fail", "reason": "one or two sentences: the criterion '
                'that failed and where, or why all hold"}')
GOODBYE = re.compile(r"\b(good-?bye|bye|bye-bye)\b", re.I)

_print_lock = threading.Lock()
_count_lock = threading.Lock()
COUNTS = {"chat_turns": 0, "customer_calls": 0, "judge_calls": 0, "judge_retries": 0, "ledger_polls": 0, "ledger_errors": 0, "call_fetches": 0}
_cli_dir = None


def count(key, n=1):
    with _count_lock:
        COUNTS[key] += n


def cli_dir():
    """An EMPTY scratch directory to run `claude -p` from, made once per process. Run from the repo, Claude Code loads the
    project's CLAUDE.md, .claude/ settings and skills into the session, and the customer and the judge would read the
    builder's scoring rules (verified 10 Oct: asked to quote any project instruction, a run from the repo returned the
    CLAUDE.md heading, a run from an empty directory 'NONE')."""
    global _cli_dir
    with _count_lock:
        if _cli_dir is None or not os.path.isdir(_cli_dir):
            _cli_dir = tempfile.mkdtemp(prefix="sim-claude-")
        return _cli_dir


def say(*a):
    with _print_lock:
        print(*a, flush=True)


# ----------------------------------------------------------------------------------------------------- helpers
def scrub(text):
    """Remove API keys and the bank team key from anything printed, written or sent to a model."""
    text = re.sub(r"fak_[A-Za-z0-9_\-]{8,}", "fak_***", text)
    for name in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        v = os.environ.get(name)
        if v and len(v) >= 8:
            text = text.replace(v, "<" + name + ">")
    return text


def compact(obj, n=300):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    s = scrub(" ".join(s.split()))
    return s if len(s) <= n else s[: n - 3] + "..."


def fn_name(ev):
    f = ev.get("function")
    if isinstance(f, dict):
        return f.get("name") or f.get("function") or "?"
    return str(f or ev.get("name") or ev.get("tool") or "?")


def tool_args_line(args):
    if isinstance(args, dict) and "url" in args:
        return "%s %s body=%s" % (args.get("method", ""), args.get("url", ""), compact(args.get("body"), 260))
    return "args=" + compact(args, 260)


def tool_result_line(result):
    if result is None:
        return "(no result event)"
    if not isinstance(result, dict):
        return compact(result)
    if set(result) == {"error"}:                                   # a function_call_error event
        return "ERROR " + compact(result["error"], 260)
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


def resolve_workflow(arg):
    """A slot name from .freya-agents.json (brief-a, ...) or a workflow id. Returns (workflow_id, agent_id or None)."""
    f = ROOT / ".freya-agents.json"
    if f.exists():
        state = json.loads(f.read_text())
        if arg in state:
            return state[arg]["workflow_id"], state[arg].get("agent_id")
    return arg, None


def first_node_info(workflow_id):
    """(initial node name, is it a code node, the variables its code writes). The chat route may skip a first code step."""
    try:
        w = freya.api("GET", "/api/v2/workflow/%s" % workflow_id, workspaceId=freya.workspace_id())["workflow"]["workflow"]
        name = w.get("initial_node") or ""
        node = (w.get("nodes") or {}).get(name) or {}
        code = str(node.get("code") or "")
        for a in node.get("pre_actions") or []:
            fn = a.get("function") or {}
            code += "\n" + str(a.get("code") or (((fn.get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default") or "")
        written = sorted(set(re.findall(r"vars\[\s*['\"](\w+)['\"]\s*\]\s*=", code)))
        return name, bool(written) or node.get("node_type") == "code", written
    except Exception as e:
        return "?", False, ["(could not read the workflow: %s)" % compact(str(e), 120)]


# ----------------------------------------------------------------------------------------------------- the models
class Provider:
    """Customer and judge model calls. OpenAI chat completions over urllib, or the Claude CLI (`claude -p`)."""

    def __init__(self, kind):
        self.kind = kind

    @staticmethod
    def pick(forced=None):
        if forced in ("openai", "claude"):
            return Provider(forced)
        return Provider("openai" if os.environ.get("OPENAI_API_KEY") else "claude")

    def chat(self, model, system, turns, json_mode=False):
        """`turns` is a list of (role, text), role in ('user', 'assistant'), the last one 'user'. Returns the reply text."""
        if self.kind == "openai":
            return self._openai(model, [{"role": "system", "content": system}] + [{"role": r, "content": t} for r, t in turns], json_mode)
        return self._claude(model, system, self._serialize(turns))

    @staticmethod
    def _serialize(turns):
        """The CLI takes one prompt: the alternating messages as a labelled transcript."""
        lines = []
        for r, t in turns:
            lines.append(("Agent: " if r == "user" else "You: ") + t)
        return "\n".join(lines)

    def _openai(self, model, messages, json_mode):
        key = os.environ.get("OPENAI_API_KEY", "")
        body = {"model": model, "messages": messages}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        last = None
        for attempt in range(4):
            req = urllib.request.Request(OPENAI_URL + "/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    out = json.load(r)
                return (out["choices"][0]["message"].get("content") or "").strip()
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")[:400]
                last = "HTTP %d: %s" % (e.code, text)
                if e.code == 400 and json_mode and "response_format" in text:
                    body.pop("response_format", None); json_mode = False; continue
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(5 * (attempt + 1)); continue
                raise RuntimeError("openai %s" % last)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
                last = repr(e)
                if attempt < 3:
                    time.sleep(5 * (attempt + 1)); continue
        raise RuntimeError("openai: no answer (%s)" % last)

    def _claude(self, model, system, prompt):
        """One `claude -p` call with the persona as the system prompt, no tools, from an empty directory (see cli_dir)."""
        last = None
        for attempt in range(3):
            try:
                r = subprocess.run([CLAUDE_CLI, "-p", "--model", model, "--system-prompt", system, "--tools", "", "--output-format", "text",
                                    "--no-session-persistence", prompt], capture_output=True, text=True, timeout=240, cwd=cli_dir())
            except subprocess.TimeoutExpired:
                last = "claude -p timed out"; continue
            except FileNotFoundError:
                raise RuntimeError("the Claude Code binary was not found (%s): install claude-agent-sdk (it bundles one), put `claude` on PATH, or set CLAUDE_CLI" % CLAUDE_CLI)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
            last = "claude -p rc=%d: %s" % (r.returncode, (r.stderr or r.stdout)[-300:])
            time.sleep(5)
        raise RuntimeError(last or "claude -p failed")


class Customer:
    """The model-played customer: the organisers' persona prompt, the conversation as alternating messages."""

    def __init__(self, provider, model, persona_prompt):
        self.provider, self.model = provider, model
        self.system = persona_prompt + "\n\n" + PHONE_RULE
        self.turns = []                      # (role, text): 'assistant' = the customer (this model), 'user' = the agent

    def record(self, customer_line, agent_line):
        self.turns.append(("assistant", customer_line))
        self.turns.append(("user", agent_line or "(silence on the line)"))

    def next_line(self):
        count("customer_calls")
        raw = self.provider.chat(self.model, self.system, self.turns)
        return clean_line(raw)


def clean_line(s):
    """Only the spoken words: no quotes, no 'You:' label, no stage directions in brackets."""
    s = s.strip().strip('"').strip("'").strip("“”").strip()
    s = re.sub(r"^\s*(\[[^\]]*\]|\([^)]*\))\s*", "", s)             # a leading [stage direction] or (aside)
    s = re.sub(r"^(You|Customer|Caller|Me)\s*:\s*", "", s, flags=re.I)
    s = s.strip().strip('"').strip("'").strip("“”").strip()
    s = re.sub(r"\*[^*]*\*", "", s)                                   # *sighs*
    s = " ".join(s.split())
    return s or "Hello?"


def judge(provider, model, checks, transcript_lines, tool_calls, opening="Hello?"):
    """The organisers' wording ('All of these are true:' + checks) over the transcript and the tool list -> (outcome, reason).
    `opening` is the customer's first line (--opening), which the judge is told to read as picking up the phone."""
    criteria = "All of these are true:\n- " + "\n- ".join(checks)
    tools = "\n".join("%d. %s %s -> %s" % (i, t["tool"], tool_args_line(t.get("args")), tool_result_line(t.get("result")))
                      for i, t in enumerate(tool_calls, 1)) or "(no tool calls)"
    prompt = ("SUCCESS CRITERIA:\n%s\n\nTRANSCRIPT (the customer's first line %s is them picking up the phone; the agent then opens the call; "
              "tool calls are shown where they happened):\n%s\n\nTOOL CALLS IN ORDER:\n%s\n\n"
              'Is every criterion true? Answer with JSON only: {"outcome": "pass" or "fail", "reason": "..."}'
              % (criteria, json.dumps(opening, ensure_ascii=False), "\n".join(transcript_lines), tools))
    count("judge_calls")
    raw = provider.chat(model, JUDGE_SYSTEM, [("user", scrub(prompt))], json_mode=True)
    outcome, reason = parse_verdict(raw)
    if outcome is None:
        # Prose without a verdict. OpenAI's json_object mode makes this rare; the CLI path has no such guard: ask once more.
        count("judge_calls"); count("judge_retries")
        nudge = prompt + ("\n\nYour previous answer contained no verdict. Reply with the JSON object only, nothing else: "
                          '{"outcome": "pass" or "fail", "reason": "..."}')
        outcome, reason = parse_verdict(provider.chat(model, JUDGE_SYSTEM, [("user", scrub(nudge))], json_mode=True))
        if outcome is None:
            return "fail", "no verdict (the judge answered twice without pass/fail): " + reason
    return outcome, reason


def parse_verdict(raw):
    """(outcome, reason): a JSON object with "outcome" (anywhere in the text, fenced or not), an `outcome: pass|fail`
    field, or a reply that IS the one word pass/fail. Anything else -> (None, text): prose that merely contains 'pass'
    or 'fail' is not a verdict (an earlier fallback read 'I cannot pass judgment' as a pass)."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    cands = [text] + re.findall(r"\{.*?\}", text, flags=re.S)
    for c in cands:
        try:
            j = json.loads(c)
        except Exception:
            continue
        if isinstance(j, dict) and "outcome" in j:
            o = str(j.get("outcome", "")).strip().lower()
            if o.startswith("pass") or o in ("true", "yes", "ok"):
                return "pass", " ".join(str(j.get("reason") or "").split())[:600]
            if o.startswith("fail") or o in ("false", "no"):
                return "fail", " ".join(str(j.get("reason") or "").split())[:600]
    m = re.search(r'"?outcome"?\s*[:=]\s*"?(pass|fail)', text, re.I)
    if m:
        return m.group(1).lower(), " ".join(text.split())[:600]
    m = re.fullmatch(r"\W*(pass|fail)(?:ed|es)?\W*", text, re.I)        # the bare word: 'PASS', 'Fail.'
    if m:
        return m.group(1).lower(), " ".join(text.split())[:600]
    return None, " ".join(text.split())[:400]


# ----------------------------------------------------------------------------------------------------- the chat call
def post(path, body, timeout=TURN_TIMEOUT_S):
    """POST to Freya; (status, result). Never raises: an HTTP status comes back as is (a non-JSON body as text), 0 = no answer."""
    req = urllib.request.Request(freya.URL + path, data=json.dumps(body).encode(), headers=freya.HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, text = r.status, r.read().decode(errors="replace")
        try:
            out = json.loads(text)
        except ValueError:
            return status, "not JSON: " + " ".join(re.sub(r"<[^>]+>", " ", text).split())[:200]
        return status, (out.get("data", {}).get("result", out) if isinstance(out, dict) else out)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            j = json.loads(text); msg = (j.get("data") or {}).get("message") or j.get("message") or text
        except Exception:
            msg = re.sub(r"<[^>]+>", " ", text)
        return e.code, " ".join(str(msg).split())[:400]
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        return 0, repr(e)


class Chat:
    """One chat-route call. send() a customer line -> the agent's reply; the harness keeps its own transcript log."""

    def __init__(self, workflow_id, variables, new_session=None):
        self.workflow_id, self.variables = workflow_id, variables
        self.call_id, self.log, self.ended_by_agent, self.ended_how, self.end_result = None, [], False, None, None
        self.server_errors, self.unrecovered_errors, self.warnings = 0, 0, []
        self.new_session, self.retried_customers = new_session, []     # a first-turn retry runs on a fresh practice customer

    def send(self, text, first_turn_retries=3):
        body = {"message": text}
        if self.call_id:
            body["callId"] = self.call_id
        else:
            body["workflowId"] = self.workflow_id; body["customerVariables"] = self.variables
        t0, status, res, attempt = time.time(), 0, None, 0
        for attempt in range(first_turn_retries + 1):
            count("chat_turns")
            status, res = post("/api/v2/chat/message", body)
            # Before the call exists there is nothing to resume: send the first line again after a pause. Mid-call a line
            # is NEVER re-sent: the engine usually processed it although the gateway answered 502/504 (seen: a re-sent
            # line re-ran the end node and close_call three times), so the reply is recovered from the call log instead.
            if status in (502, 503, 504, 0) and not self.call_id and attempt < first_turn_retries:
                self.server_errors += 1
                # The engine may well have created a call for this attempt (a 504 is the gateway giving up, not the
                # engine) and there is no callId to end it with. So the retry opens a FRESH practice customer: whatever
                # that orphan does later (its end_of_call close_call, for one) lands in another ledger, never in this case's.
                try:
                    fresh = self.new_session() if self.new_session else None
                except Exception:
                    fresh = None                                   # the mock hiccuped: retry on the same customer
                if fresh:
                    self.retried_customers.append(self.variables.get("customer_id"))
                    self.variables = body["customerVariables"] = fresh
                time.sleep(15); continue
            break
        turn = {"n": len(self.log) + 1, "customer": text, "agent": "", "status": status, "seconds": round(time.time() - t0, 1), "error": None, "ended_by_agent": False}
        if attempt:
            turn["first_turn_retries"] = attempt
        if status == 200 and isinstance(res, dict):
            self.call_id = res.get("callId") or self.call_id
            turn["agent"] = (res.get("response") or "").strip()
            turn["message_id"] = res.get("messageId")
            if res.get("warning"):
                turn["warning"] = compact(res["warning"], 300); self.warnings.append(turn["warning"])
            if res.get("endedByAgent"):
                self.ended_by_agent, self.ended_how = True, "endedByAgent in the response"
        else:
            if status in (500, 502, 503, 504):
                self.server_errors += 1
            turn["error"] = ("HTTP %s: %s" % (status, res)) if status else ("no answer: %s" % res)
            if status == 500 and not self.call_id:
                turn["error"] += " (a bare 500 on the first turn: the workflow cannot start a call at all)"
        if status in (502, 503, 504, 0) and self.call_id:
            # The gateway gave up (504: after ~60 s; 502: 'no response', seen on every turn in which the agent ended the
            # call) while the engine finished the turn. The reply usually lands in the call log: poll for it.
            t1, limit = time.time(), RECOVER_S if status == 504 else 30
            while time.time() - t1 < limit and not turn["agent"] and not self.ended_by_agent:
                time.sleep(6)
                turn["agent"] = self.collect()
            if self.ended_by_agent and not self.ended_how:
                self.ended_how = "end_call in the call log after HTTP %s" % status
            turn["error"] += " | reply %s the call log after %.0f s%s" % ("recovered from" if turn["agent"] else "NOT found in", time.time() - t1,
                                                                        "; the agent ended the call" if self.ended_by_agent else "")
            turn["seconds"] = round(time.time() - t0, 1)
            if not turn["agent"] and not self.ended_by_agent:
                self.unrecovered_errors += 1                   # a recovered 504 under load is not an error of the call
        elif turn["error"] and self.call_id:                   # a 500 or a non-JSON 200 mid-call: nothing to recover
            self.unrecovered_errors += 1
        turn["ended_by_agent"] = self.ended_by_agent
        self.log.append(turn)
        return turn

    def collect(self):
        """After a gateway error: the reply to our last line (assistant messages after the last user message in
        GET /api/v2/call/{id}); notes an agent-ended call (end_call completed or a call_ended event) on the way."""
        try:
            count("call_fetches")
            msgs = freya.get_call(self.call_id).get("messages") or []
        except Exception:
            return ""
        users = sum(1 for m in msgs if m.get("role") == "user")
        if users < len(self.log) + 1:                  # our last line has not been logged yet
            return ""
        tail = []
        for m in reversed(msgs):
            if m.get("role") == "user":
                break
            tail.append(m)
        said = []
        for m in reversed(tail):
            if m.get("role") == "assistant":
                said.append((m.get("message") or "").strip())
            elif m.get("role") == "system":
                try:
                    ev = json.loads(m.get("message") or "{}")
                except Exception:
                    continue
                if ev.get("event") == "call_ended" or (ev.get("event") == "function_call_complete" and fn_name(ev) == "end_call"):
                    self.ended_by_agent = True
        return " ".join(s for s in said if s)

    def end(self):
        """POST /chat/end once (idempotent, never raises): also called from the error path of run_case."""
        if not self.call_id or self.end_result is not None:
            return self.end_result
        status, res = post("/api/v2/chat/end", {"callId": self.call_id}, timeout=60)
        self.end_result = res if status == 200 else "HTTP %s: %s" % (status, res)
        return self.end_result

    def fetch_call(self):
        """The full call with tool events, or None when the call route does not serve this id."""
        if not self.call_id:
            return None
        for attempt in range(2):
            try:
                count("call_fetches")
                return freya.get_call(self.call_id)
            except Exception:
                time.sleep(3)
        return None


def transcript_from_call(call):
    """(lines, tool_calls, last variable table) from GET /api/v2/call messages; the lines include tool events in place."""
    lines, tools, var_table, slowest, last_user = [], [], None, 0.0, None
    for m in call.get("messages") or []:
        role, text, t = m.get("role"), (m.get("message") or "").strip(), m.get("secondsFromStart")
        if role == "user":
            lines.append("customer: " + text); last_user = t
        elif role == "assistant":
            lines.append("agent: " + text)
            if t is not None and last_user is not None:
                slowest = max(slowest, t - last_user); last_user = None
        elif role == "system":
            try:
                ev = json.loads(text)
            except Exception:
                continue
            e = ev.get("event")
            if e == "function_call_start":
                rec = {"tool": fn_name(ev), "args": ev.get("args"), "result": None}
                tools.append(rec); lines.append("   [tool] %s %s" % (rec["tool"], tool_args_line(rec["args"])))
            elif e == "function_call_complete":
                name = fn_name(ev)
                rec = next((r for r in reversed(tools) if r["tool"] == name and r["result"] is None), None)
                if rec is None:
                    rec = {"tool": name, "args": None, "result": None}; tools.append(rec)
                rec["result"] = ev.get("result"); lines.append("   [tool] %s -> %s" % (name, tool_result_line(rec["result"])))
            elif e == "function_call_error":                       # not in docs/api.md's list; seen when the mock answers 4xx
                name = fn_name(ev)
                rec = next((r for r in reversed(tools) if r["tool"] == name and r["result"] is None), None)
                if rec is None:
                    rec = {"tool": name, "args": None, "result": None}; tools.append(rec)
                rec["result"] = {"error": ev.get("error") or ev.get("message") or "unknown error"}
                lines.append("   [tool] %s -> %s" % (name, tool_result_line(rec["result"])))
            elif e == "call_ended":
                lines.append("   [call] ended%s" % (": " + compact(ev.get("reason") or ev.get("endedReason") or "", 120) if (ev.get("reason") or ev.get("endedReason")) else ""))
            elif e == "route_evaluated":
                if isinstance(ev.get("variable_table"), dict):
                    var_table = ev["variable_table"]
                if ev.get("matched"):
                    lines.append("   [route] %s -> %s: %s" % (ev.get("from_node"), ev.get("target"), compact(ev.get("reason") or "", 140)))
            elif e == "node_enter":
                lines.append("   [node] %s -> %s" % (ev.get("from_node") or "-", ev.get("node")))
            elif e == "error":
                lines.append("   [error] %s %s" % (compact(ev.get("message") or "", 160), compact(ev.get("details") or "", 160)))
    return lines, tools, var_table, round(slowest, 1)


def transcript_from_log(chat, ledger):
    """Fallback when the call route does not serve the chat call: the harness's own log plus the ledger's calls."""
    lines = []
    for t in chat.log:
        lines.append("customer: " + t["customer"])
        lines.append("agent: " + (t["agent"] or "(no reply%s)" % (": " + t["error"] if t.get("error") else "")))
    tools = [{"tool": c.get("tool"), "args": c.get("args") or c.get("body") or c.get("request"), "result": c.get("result")} for c in (ledger or {}).get("calls") or []]
    return lines, tools, None, round(max([t["seconds"] for t in chat.log] or [0]), 1)


# ----------------------------------------------------------------------------------------------------- one case
def ledger_poll(cid, ledger=None):
    """GET the mock ledger. On a transport error, a timeout or a body without `calls`, the previous ledger (or {}) comes
    back and `ledger_errors` counts it, so one transient mock error never aborts a call that is in progress."""
    count("ledger_polls")
    try:
        led = http("/v1/practice/ledger/" + cid)
        if isinstance(led, dict) and "calls" in led:
            return led
    except Exception:
        pass
    count("ledger_errors")
    return ledger if ledger is not None else {}


def closed(ledger):
    return any(c.get("tool") == "close_call" for c in (ledger or {}).get("calls") or [])


def run_case(ctx, case, rep):
    """One practice customer on one chat-route call. Returns a row shaped like run_cases.py's rows."""
    cid, chat, ledger = None, None, None
    row = {"id": case["id"], "level": case["level"], "family": case["family"], "pass": False, "failed": [], "call_id": None, "tools": [], "customer_id": None,
           "transcript": None, "turns": 0, "stop": None, "judge": None, "style": case_style(ctx, case), "mock_case": case.get("mock_case", case["id"])}

    def new_session():
        # an extended case reuses a mock customer (fixed identity, products, faults) under its own id and script
        s = http("/v1/practice/sessions", {"case": case.get("mock_case", case["id"])})
        return s.get("variables") if isinstance(s, dict) else None

    try:
        variables = new_session()
        if not variables:
            row["failed"].append("mock bank: could not open a practice session for " + case.get("mock_case", case["id"])); row["stop"] = "no practice session"
            return finish(ctx, case, rep, row, None, None)
        variables = dict(variables); cid = row["customer_id"] = variables["customer_id"]
        if (case.get("variables") or {}).get("now"): variables["now"] = case["variables"]["now"]   # another call date: the mock enforces no date rule
        persona = persona_for(case, {"identity": case["identity"]}, case_style(ctx, case))
        customer = Customer(ctx.provider, ctx.customer_model, persona["prompt"])
        chat = Chat(ctx.workflow_id, variables, new_session=new_session)
        line, goodbyes, empties = ctx.opening, 0, 0
        for turn in range(1, ctx.max_turns + 1):
            t = chat.send(line)
            row["call_id"] = chat.call_id
            if chat.variables.get("customer_id") != cid:           # the first turn was retried on a fresh practice customer
                cid = row["customer_id"] = chat.variables["customer_id"]
                chat.warnings.append("first turn retried %d time(s) after a 502/503/504/no answer; practice customer(s) %s may hold an orphan "
                                     "call on the engine (no callId to end it with), harmless to this case's ledger"
                                     % (len(chat.retried_customers), ", ".join(map(str, chat.retried_customers))))
            if ctx.verbose:
                say("[%s] customer: %s\n[%s] agent (%.1fs): %s%s" % (case["id"], line, case["id"], t["seconds"], t["agent"] or "(no reply)", (" !! " + t["error"]) if t.get("error") else ""))
            customer.record(line, t["agent"])
            if turn == 1 and "{{" in t["agent"]:
                say("WARNING %s: the agent's opening line contains an unresolved variable '{{': %s" % (case["id"], compact(t["agent"], 200)))
            elif "{{" in t["agent"]:
                say("WARNING %s: an agent line contains '{{' (unresolved variable): %s" % (case["id"], compact(t["agent"], 200)))
            if not chat.call_id:
                row["stop"] = "no call started: " + (t.get("error") or "no callId in the response"); break
            ledger = ledger_poll(cid, ledger)
            if closed(ledger):
                row["stop"] = "close_call in the ledger"; break
            if t["ended_by_agent"]:
                row["stop"] = "ended by the agent (%s)" % chat.ended_how; break
            if not t["agent"]:
                empties += 1
                if empties >= 2:
                    row["stop"] = "two empty replies in a row"; break
            else:
                empties = 0
            if chat.unrecovered_errors >= 3:
                row["stop"] = "3 server errors without a reply (5xx or no answer)"; break
            if goodbyes >= 2:
                row["stop"] = "the customer said goodbye twice"; break
            if turn == ctx.max_turns:
                row["stop"] = "max turns (%d) reached" % ctx.max_turns; break
            try:
                line = customer.next_line()
            except Exception as e:
                row["stop"] = "customer model failed: " + compact(str(e), 200); break
            if GOODBYE.search(line):
                goodbyes += 1
    except Exception as e:
        row["failed"].append("harness: %s: %s" % (type(e).__name__, compact(str(e), 240)))
        row["stop"] = row.get("stop") or "harness error: " + type(e).__name__
    row["turns"] = len(chat.log) if chat else 0
    # Whatever happened above, a call that was started is ended and scored: a harness error (the mock bank down for one
    # poll, say) must not leave the call open on the engine or lose its transcript. No call: no 30 s wait, one ledger read.
    try:
        if chat and chat.call_id:
            chat.end()
            ledger = wait_for_close(cid, ledger)                   # end-of-call tool calls land a few seconds after /chat/end
        elif cid:
            ledger = ledger_poll(cid, ledger)
    except Exception as e:
        row["failed"].append("harness (after the call): %s: %s" % (type(e).__name__, compact(str(e), 200)))
    return finish(ctx, case, rep, row, chat, ledger)


def wait_for_close(cid, ledger, seconds=60):
    """A tool with alwaysRunsAt end_of_call (close_call) runs asynchronously after POST /chat/end: seen 12 s later.
    Poll the ledger until a close_call shows up, 60 s at most (one Brief C call had none after 30 s); nothing to wait for when the ledger is already closed."""
    t0 = time.time()
    while not closed(ledger) and time.time() - t0 < seconds:
        time.sleep(3)
        ledger = ledger_poll(cid, ledger)
    return ledger


def close_from_args(ledger, row):
    """--close-from-args: the organisers' mock checks close_call reasons against the KIT briefs' table, so a synthetic
    brief with its own reason names gets ok:false and an empty ledger outcome. Score the outcome/reason the agent
    SENT in its last close_call instead, and say so in the row. Only used when the ledger outcome is empty."""
    if ledger.get("outcome"):
        return ledger
    closes = [c for c in ledger.get("calls") or [] if c.get("tool") == "close_call"]
    if not closes:
        return ledger
    args = closes[-1].get("args") or {}
    led = dict(ledger)
    led["outcome"], led["reason"] = args.get("outcome"), args.get("reason")
    row["close_from_args"] = {"args": args, "mock_result": closes[-1].get("result")}
    return led


def case_style(ctx, case):
    """--style for every case, else the case's own `style` (a --styles copy, or a generated case that carries one)."""
    return ctx.style or case.get("style")


def finish(ctx, case, rep, row, chat, ledger):
    """Score the ledger, judge the transcript, write the transcript file, print the run_cases-style line."""
    lines, tools, var_table, slowest = [], [], None, 0.0
    call = chat.fetch_call() if chat else None
    if call:
        lines, tools, var_table, slowest = transcript_from_call(call)
        row["ended"] = call.get("endedReason")
        row["transcript_source"] = "GET /api/v2/call/" + chat.call_id
    elif chat:
        lines, tools, var_table, slowest = transcript_from_log(chat, ledger)
        row["transcript_source"] = "harness log (the call route did not serve the chat callId)"
    row["slowest_turn_s"] = slowest
    if chat:
        row["ended_how"] = chat.ended_how
    if ledger is not None and "calls" in ledger:
        try:
            if getattr(ctx, "close_from_args", False):
                ledger = close_from_args(ledger, row)
            row["failed"] += score_ledger(case, ledger)["failed"]
        except Exception as e:
            row["failed"].append("mock bank: the ledger could not be scored: %s: %s" % (type(e).__name__, compact(str(e), 160)))
        row["tools"] = [x.get("tool") for x in ledger["calls"]]
    elif chat:
        row["failed"].append("mock bank: no ledger for " + str(row["customer_id"]))
    if chat and not chat.call_id:                                  # nothing was said: no judge call for a '(no reply: HTTP 500)' transcript
        row["failed"].append("conversation: no call was started, nothing to judge")
    elif chat and lines:
        try:
            outcome, reason = judge(ctx.provider, ctx.judge_model, case["checks"], lines, tools, ctx.opening)
        except Exception as e:
            outcome, reason = "fail", "judge model failed: " + compact(str(e), 200)
        row["judge"] = {"outcome": outcome, "reason": reason, "model": ctx.judge_model}
        if outcome != "pass":
            row["failed"].append("conversation: " + " ".join(str(reason or "no verdict").split())[:400])
    elif chat:
        row["failed"].append("conversation: no transcript to judge")
    row["pass"] = not row["failed"]
    if ctx.first_node[1] and var_table is not None:
        row["first_node_vars_missing"] = [k for k in ctx.first_node[2] if k not in var_table]
    row["transcript"] = write_transcript(ctx, case, rep, row, chat, ledger, lines, tools)
    with _print_lock:
        print(("PASS" if row["pass"] else "FAIL"), case["id"], f"{case['level']:<6}", f"{case['family']:<14}", "|",
              " > ".join(x.replace("verify_identity", "verify").replace("create_promise", "promise") for x in row["tools"]) or "(no tool calls)", flush=True)
        for f in row["failed"]:
            print("       -", f[:260], flush=True)
    return row


def write_transcript(ctx, case, rep, row, chat, ledger, lines, tools):
    if not ctx.transcripts:
        return None
    ctx.transcripts.mkdir(parents=True, exist_ok=True)
    stem = case["id"] + ("" if ctx.reps == 1 else "-r%d" % (rep + 1))
    path = ctx.transcripts / (stem + ".txt")
    st = case_style(ctx, case)
    head = ["# %s %s%s" % (case["id"], case["title"], " [style: %s]" % st if st else " [style: none]"),
            "# mock customer: %s | style text: %s" % (case.get("mock_case", case["id"]), STYLES[st] if st else "(none)"),
            "# workflow %s | call %s | customer %s | %s" % (ctx.workflow_id, row.get("call_id"), row.get("customer_id"), time.strftime("%Y-%m-%d %H:%M:%S")),
            "# customer model %s | judge model %s (%s) | stop: %s | transcript from: %s" % (ctx.customer_model, ctx.judge_model, ctx.provider.kind, row.get("stop"), row.get("transcript_source")),
            "# RESULT: %s%s" % ("PASS" if row["pass"] else "FAIL", "" if row["pass"] else " | " + " | ".join(row["failed"])), ""]
    body = list(lines) or ["(no transcript)"]
    tail = ["", "## tool calls (%d)" % len(tools)]
    tail += ["%d. %s %s -> %s" % (i, t["tool"], tool_args_line(t.get("args")), tool_result_line(t.get("result"))) for i, t in enumerate(tools, 1)] or ["(none)"]
    if ledger:
        tail += ["", "## ledger: outcome=%s reason=%s promises=%s notes=%s callbacks=%s transfers=%s calls=%s" % (
            ledger.get("outcome"), ledger.get("reason"), compact(ledger.get("promises"), 200), compact(ledger.get("notes"), 200),
            compact(ledger.get("callbacks"), 120), compact(ledger.get("transfers"), 120), [c.get("tool") for c in ledger.get("calls") or []])]
    if row.get("judge"):
        tail += ["", "## judge (%s): %s - %s" % (row["judge"]["model"], row["judge"]["outcome"], row["judge"]["reason"])]
    if chat and chat.warnings:
        tail += ["", "## chat route warnings: " + " | ".join(chat.warnings)]
    path.write_text(scrub("\n".join(head + body + tail)) + "\n")
    rec = {"case": case["id"], "rep": rep + 1, "workflow_id": ctx.workflow_id, "call_id": row.get("call_id"), "customer_id": row.get("customer_id"),
           "variables": chat.variables if chat else None, "turns": chat.log if chat else [], "end": chat.end_result if chat else None,
           "transcript": lines, "tool_calls": tools, "ledger": ledger, "judge": row.get("judge"), "failed": row["failed"], "pass": row["pass"], "stop": row.get("stop")}
    (ctx.transcripts / (stem + ".json")).write_text(scrub(json.dumps(rec, indent=1, ensure_ascii=False, default=str)))
    return str(path)


# ----------------------------------------------------------------------------------------------------- main
class Ctx:
    pass


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)   # a run killed mid-way (timeout) still shows every finished case
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow", help="workflow id, or a slot name from .freya-agents.json (brief-a, brief-b, ...)")
    ap.add_argument("--cases", default=str(ROOT / "public-test-set.json")); ap.add_argument("--brief"); ap.add_argument("--only")
    ap.add_argument("--reps", type=int, default=1); ap.add_argument("--style", choices=sorted(STYLES), help="one way of talking for every case (kit styles plus EXTRA_STYLES)")
    ap.add_argument("--styles", help="comma list of styles (none = unstyled), or kit | extra | all: run every selected case once per style and report per style")
    ap.add_argument("--concurrency", type=int, default=5); ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--out"); ap.add_argument("--transcripts", default=str(ROOT / "results" / "transcripts"))
    ap.add_argument("--customer-model"); ap.add_argument("--judge-model")
    ap.add_argument("--provider", choices=["openai", "claude"], help="force a model provider (default: openai when OPENAI_API_KEY is set, else the Claude CLI)")
    ap.add_argument("--opening", default="Hello?", help="the customer's first line, which makes the agent produce its opening (default 'Hello?')")
    ap.add_argument("--verbose", action="store_true", help="print every turn as it happens")
    ap.add_argument("--close-from-args", action="store_true",
                    help="score the outcome/reason sent in close_call when the mock rejected it (synthetic briefs whose reason names the kit's mock does not know)")
    a = ap.parse_args()
    if not os.environ.get("FREYA_API_KEY") or not os.environ.get("FREYA_BANK_TEAM_KEY"):
        sys.exit("FREYA_API_KEY and FREYA_BANK_TEAM_KEY must be set: source env.sh first.")
    ctx = Ctx()
    ctx.workflow_id, agent_id = resolve_workflow(a.workflow)
    ctx.provider = Provider.pick(a.provider)
    ctx.customer_model = a.customer_model or DEFAULTS[ctx.provider.kind]["customer"]
    ctx.judge_model = a.judge_model or DEFAULTS[ctx.provider.kind]["judge"]
    ctx.style, ctx.max_turns, ctx.opening, ctx.verbose, ctx.reps = a.style, a.max_turns, a.opening, a.verbose, a.reps
    ctx.close_from_args = a.close_from_args
    ctx.transcripts = pathlib.Path(a.transcripts) if a.transcripts else None
    cases = [c for c in json.load(open(a.cases)) if (not a.brief or c["brief"] == a.brief) and (not a.only or c["id"] in a.only.split(","))]
    if not cases:
        sys.exit("no cases selected")
    if a.style and a.styles:
        sys.exit("give --style or --styles, not both")
    if a.styles:
        cases = styled_cases(cases, a.styles)
    ctx.first_node = first_node_info(ctx.workflow_id)
    print("sim | workflow %s%s | %d case(s) x %d rep(s) | concurrency %d | customer %s, judge %s (%s)" % (
        ctx.workflow_id, " (slot %s)" % a.workflow if agent_id else "", len(cases), a.reps, a.concurrency, ctx.customer_model, ctx.judge_model, ctx.provider.kind), flush=True)
    if ctx.first_node[1]:
        print("NOTE: the first node %r is a code node (writes %s). The chat route may skip a first code step (docs/api.md); checked after the run." % (
            ctx.first_node[0], ", ".join(ctx.first_node[2]) or "nothing"), flush=True)
    (ROOT / "results").mkdir(exist_ok=True)
    reps, total_s = [], 0.0
    for rep in range(a.reps):
        t0 = time.time()
        rows = []
        with ThreadPoolExecutor(max_workers=max(1, a.concurrency)) as pool:
            for row in pool.map(lambda c: run_case(ctx, c, rep), cases):
                rows.append(row)
                if a.out:   # incremental: a killed run still leaves every finished case on disk
                    try:
                        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
                        json.dump({"runner": "sim", "partial": True, "workflow_id": ctx.workflow_id, "agent_id": agent_id, "rep": rep + 1,
                                   "passed": sum(1 for r in rows if r.get("pass")), "done": len(rows), "total": len(cases), "rows": rows,
                                   "all_rows": reps + [rows]}, open(a.out, "w"), indent=1)
                    except Exception:
                        pass
        took = time.time() - t0; total_s += took
        waits = sorted(r.get("slowest_turn_s") or 0 for r in rows if r.get("call_id"))
        if waits:
            print("\nslowest agent turn per call: median %.0f s, worst %.0f s (chat-route timing, not a simulation's)." % (waits[len(waits) // 2], waits[-1]), flush=True)
        reps.append(rows)
        if a.reps > 1:
            print(f"-- run {rep + 1} of {a.reps}: {sum(r['pass'] for r in rows)} / {len(rows)} passed, {took:.0f} s\n", flush=True)
    need = a.reps                                                # a customer counts only when every run passes
    final = [{"id": c["id"], "family": c["family"], "style": case_style(ctx, c), "passes": sum(r[k]["pass"] for r in reps), "runs": a.reps,
              "pass": sum(r[k]["pass"] for r in reps) >= need} for k, c in enumerate(cases)]
    n = sum(f["pass"] for f in final)
    if a.styles:                                               # per style: k / n, and the cases that pass unstyled but fail styled
        base = {c["id"]: c.get("base_id", c["id"]) for c in cases}
        plain = {base[f["id"]]: f["pass"] for f in final if f["style"] is None}
        for st in dict.fromkeys(f["style"] for f in final):
            fs = [f for f in final if f["style"] == st]
            regress = [base[f["id"]] for f in fs if st and not f["pass"] and plain.get(base[f["id"]])]
            print("style %s: %d / %d passed%s" % (st or "none", sum(f["pass"] for f in fs), len(fs),
                                                  "; pass unstyled, fail styled: " + ", ".join(regress) if regress else ""))
    if a.reps > 1:
        for f in final:
            print(("PASS" if f["pass"] else "FAIL"), f["id"], f"{f['passes']}/{f['runs']}")
    print(f"\n{n} / {len(final)} passed (bank records and conversation checks){'' if a.reps == 1 else f', a customer counts with {need} of {a.reps} runs'}. "
          f"Local chat-route simulation, {total_s:.0f} s.")
    missing = next((r["first_node_vars_missing"] for rows in reps for r in rows if r.get("first_node_vars_missing") is not None), None)
    if ctx.first_node[1]:
        if missing is None:
            print("NOTE: no variable table was read from any call, so whether the first code node %r ran is unknown." % ctx.first_node[0])
        elif missing:
            print("NOTE: the first code node %r ran on the chat route? NO for %s: these never appeared in the variable table (empty here, filled in a simulation)." % (ctx.first_node[0], ", ".join(missing)))
        else:
            print("NOTE: the first code node %r ran on the chat route: all of %s appeared in the variable table." % (ctx.first_node[0], ", ".join(ctx.first_node[2])))
    model_calls = COUNTS["customer_calls"] + COUNTS["judge_calls"]
    extra = "".join(", %d %s" % (COUNTS[k], label) for k, label in (("judge_retries", "judge retries"), ("ledger_errors", "ledger errors")) if COUNTS[k])
    print("cost: %d chat turns, %d model calls (%d customer on %s, %d judge on %s), %d ledger polls, %d call fetches%s." % (
        COUNTS["chat_turns"], model_calls, COUNTS["customer_calls"], ctx.customer_model, COUNTS["judge_calls"], ctx.judge_model, COUNTS["ledger_polls"], COUNTS["call_fetches"], extra))
    with open(ROOT / "results" / "log.jsonl", "a") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "runner": "sim", "workflow_id": ctx.workflow_id, "agent_id": agent_id, "brief": a.brief,
                            "runs": a.reps, "passed": n, "total": len(final), "seconds": round(total_s), "failed": [f["id"] for f in final if not f["pass"]],
                            "style": a.style or a.styles, "chat_turns": COUNTS["chat_turns"], "model_calls": model_calls,
                            "customer_model": ctx.customer_model, "judge_model": ctx.judge_model, "provider": ctx.provider.kind}) + "\n")
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"runner": "sim", "workflow_id": ctx.workflow_id, "agent_id": agent_id, "simulation_id": None, "iteration_id": None, "seconds": round(total_s),
                   "passed": n, "total": len(final), "runs": a.reps, "final": final, "rows": reps[-1], "all_rows": reps,
                   "customer_model": ctx.customer_model, "judge_model": ctx.judge_model, "provider": ctx.provider.kind, "counts": COUNTS},
                  open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
