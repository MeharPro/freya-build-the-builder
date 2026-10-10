# builder/smoke.py — chat-route smoke tests for a published workflow

`builder/smoke.py` talks to a published Freya workflow over `POST /api/v2/chat/message`, one turn at a time, with no
simulation and no queue (docs/api.md, "Talk to your workflow turn by turn"). A turn answers in seconds on a quiet
platform, so this is the fastest way to see what a phone agent says first, whether it routes where it should and which
tools it calls, before a 3–11 minute simulation. Standard library only, except the optional driven mode. It never
edits a workflow.

```bash
source env.sh
# scripted: fixed customer lines plus expectations; exit 1 when an expectation fails
python3 builder/smoke.py <workflow_id|slot> --script builder/smoke_scripts/opening.json
python3 builder/smoke.py brief-a --script builder/smoke_scripts/third_party.json --out results/smoke-third_party.json
# driven: a Claude-played customer follows a persona; no pass/fail, a transcript to read
python3 builder/smoke.py brief-a --customer "You are Daniel Reyes, born 14 March 1988, phone ending 4471. You can pay the full amount today." --max-turns 12
python3 builder/smoke.py brief-a --case PUB-02 --vars '{"customer_id": "c_smoke2"}' --max-turns 6 --customer "You are NOT Maria Costa. You are Paulo, her husband ..."
```

`<workflow_id|slot>` is a workflow id or a slot name from `.freya-agents.json` (`brief-a`, `brief-b`, ...). The
workflow must be published: `freya.save_workflow` publishes, a bare PUT does not. Run scripts one after the other,
never in parallel (see "504, 503, 502" below).

## What one run prints

```
--- turn 1
customer: Hello?
agent (8.2s): Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with Ms Costa?
   [route] setup -> opening: always always
   [node] setup -> opening (always always)
--- turn 2
customer: This is her husband, she is not here. What is this about?
agent (8.0s): I can only discuss this with Ms Costa personally. When would be a good time to reach her?
   [extract] who1 = 'someone_else'
   [route] opening -> third_party: someone else answered who1 == 'someone_else'
--- turn 3
customer: She should be back tomorrow morning, around eleven.
agent (9.4s): I'm sorry, I've encountered a technical issue. Could you please confirm if tomorrow at 11:00 is the best time to reach Ms Costa?
   [tool] schedule_callback POST https://freya-bank-mock.freyavoice.workers.dev/v1/schedule_callback body={"date": "2025-05-15", "time": "11:00", "customer_id": "c_test"}
   [tool] schedule_callback -> ERROR API request failed: {'ok': False, 'error': 'unknown customer_id'}
--- POST /api/v2/chat/end -> {"callId": "...", "ended": true, "endedReason": "customer-ended-call"}
== tool calls (2) from GET /api/v2/call/<callId>
 1. turn 3  schedule_callback  POST .../v1/schedule_callback body={"date": "2025-05-15", "time": "11:00", "customer_id": "c_test"}
    -> ERROR API request failed: {'ok': False, 'error': 'unknown customer_id'}
 2. end     close_call         POST .../v1/close_call body={"reason": "callback", "outcome": "not_reached", "customer_id": "c_smoke"}
    -> ERROR API request failed: {'ok': False, 'error': 'unknown customer_id'}
== variables after the last routing (6): {"now": "2026-10-14T11:00", ..., "who1": "someone_else"}
NOTE: the first node 'setup' is a code node that writes attempt1_date, ..., today_iso; ... never appeared in the variable table. ...
== expectations (39)
 PASS turn 1 contains_any ["Freya Bank"] -> 'Freya Bank'
 ...
RESULT: PASS | 39/39 checks passed | call <callId>
```

After every turn the harness reads `GET /api/v2/call/{callId}` and prints that turn's engine events, one line each:
`[node]` node_enter, `[route]` route_evaluated (the matched transition and its reason, or "stays in"), `[extract]`
variable_extracted, `[tool]` function_call_start (method, url, body) and function_call_complete (HTTP status, `data`)
or function_call_error (`ERROR ...`), `[call] ended by the engine` (call_ended), `[error]`. Code nodes appear as
`code_exec` tool calls and the end node as `end_call`: they are the engine's own functions, listed next to the bank
tools. The summary at the end lists every tool call with its request body and result, and the variable table after
the last routing without the engine's own entries. `--out` writes the same as JSON (turns, events, tool calls,
checks, variable table). API keys and the bank team key are scrubbed from everything printed.

## Script format (scripted mode)

```json
{
 "name": "opening: identity before any debt talk",
 "variables": {"customer_id": "c_smoke", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
 "turns": ["Hello?", "Yes, this is me"],
 "expect": [
  {"after_turn": 1, "contains_any": ["Freya Bank"], "not_contains": ["debt", "collection", "payment", "re:\\blate\\b"]},
  {"after_turn": 2, "cumulative": true, "not_contains": ["debt", "payment"]},
  {"after_turn": 2, "contains_any": ["date of birth", "re:\\bborn\\b", "postcode"], "no_tool_calls": true},
  {"tools_not_called": ["get_account", "create_promise"]}
 ]
}
```

| Key | Meaning |
|---|---|
| `variables` | The call variables. Merged over the defaults (`c_smoke`, Daniel Reyes, `now` 2026-10-14T11:00); `--case PUB-02` and `--vars '{...}'` merge on top. |
| `turns` | The customer's lines, in order. Sending stops when the agent ends the call. |
| `after_turn` | 1-based: check the agent's reply to that customer line. Absent: check all replies together. |
| `cumulative` | With `after_turn`: check all replies up to and including that turn (for "never before identity" rules). |
| `contains_any`, `contains_all`, `not_contains` | Case-insensitive substrings. A term starting with `re:` is a case-insensitive regex, e.g. `re:\\blate\\b` so that "later" does not count. |
| `no_tool_calls`, `tools_called_any`, `tools_not_called` | Tool names from the call's events (`verify_identity`, `close_call`, `code_exec`, ...). With `after_turn`: the calls of the conversation up to that turn, without the end-of-call ones that `POST /chat/end` triggers (listed as `end` in the summary). Without `after_turn`: every call. |

Exit codes: 0 every check passed, 1 a check failed (a turn with no reply fails its checks), 2 the call could not be
run (a 500, no answer, or 502/503/504 on the first turn after three retries).

The three scripts in `builder/smoke_scripts/` are generic: any collections brief must pass them, nothing in them comes
from a brief. All three passed against the Brief A workflow (opening 26/26, third_party 39/39, wrong_number 29/29).

| Script | Customer lines | Checks |
|---|---|---|
| `opening.json` | "Hello?", "Yes, this is me" | Names Freya Bank and the customer; no debt/collections/payment/amount/product words before identity; asks a security question; no tool call yet. |
| `third_party.json` | "Hello?", "This is her husband, she is not here. What is this about?", "She should be back tomorrow morning, around eleven." (PUB-02 variables) | Nothing about the account or why it calls; asks when she can be reached; `verify_identity`, `get_account`, `create_promise` never called. The third line makes the agent call `schedule_callback`, so the tool-call path is exercised too. |
| `wrong_number.json` | "Hello?", "I think you have the wrong number, nobody by that name here." | No debt words; closes politely; no identity, promise or callback tool. `close_call` is not asserted: see below. |

## The mock bank and `c_smoke`

The scripts use `customer_id` `c_smoke`, which the mock bank does not know, so every bank tool call is rejected
(`ERROR API request failed: {'ok': False, 'error': 'unknown customer_id'}`). That is fine for the opening turns: the
point is the conversation before any bank call, and the tool call itself (name, body) is still visible.

Testing bank tool calls for real over the chat route does not work on this platform, see the next section: a
model-filled tool body carries the `customer_id` from the workflow's `test_variables`, not from `customerVariables`.
Use a simulation for that (`tools/run_cases.py`), or a practice session whose id equals the workflow's
`test_variables.customer_id`.

## Driven mode

`--customer "<persona text>"` lets a Claude-played customer talk to the agent for up to `--max-turns` lines (default 12,
first line `--opening`, default "Hello?"). The customer model is `--model` (default `claude-haiku-5-5`) through the
Claude Agent SDK (`.venv`), or `claude -p` when the SDK is not importable; it needs a Claude login or
`ANTHROPIC_API_KEY`. The customer gets the persona, the transcript so far and the rule to answer only what is asked; it
says `[HANGUP]` when the call is over. `--case PUB-02` without `--customer` builds the persona from the practice case.
No judge, no pass/fail: the output is a transcript with tool calls for a human or an auditor to read. A run with a
husband persona against Brief A took 2 minutes for 5 turns and showed the third-party branch, the `schedule_callback`
attempt and the `no_callback` close.

## What the chat route can and cannot test

Can:
- Whether the published workflow starts a call at all, what it says first, and how the opening turns go.
- Routing (`route_evaluated` shows every branch, the matched one and the reason), extraction (`variable_extracted`),
  node entry, code nodes (`code_exec`), and the variable table after each routing.
- Which tools the model calls, when, and with which body.
- Phrasing rules on single turns (what is said before identity, security questions, third-party handling).

Cannot, or not reliably (all seen on the Brief A workflow, 10 October 2026):
- **The first code node is skipped.** Brief A's initial node `setup` is a code node; none of the nine variables it
  writes (`today_iso`, `early_deadline`, `callback_text`, ...) appeared in the variable table of any chat call, while a
  simulation has them. So anything the first step computes is empty here: the agent proposed a callback for
  `2025-05-15` (the model's own idea of "tomorrow") instead of 2026-10-15. Date rules cannot be judged over the chat
  route when the first node is a code node. The harness prints a NOTE when it sees this.
- **Model-filled tool bodies carry `test_variables`.** The body of a model-called tool (`schedule_callback`) had
  `customer_id: "c_test"`, the workflow's `test_variables` value, in two calls whose `customerVariables` were `c_smoke`
  and `c_smoke2` (the variable table showed the right value, and the engine-filled end-of-call `close_call` used it).
  No prompt mentions `customer_id`, so the platform fills the body default `{{customer_id}}` from `test_variables` on
  this route. Bank tool calls are therefore rejected by the mock unless the practice customer is the `test_variables`
  one. In a simulation the ledger shows the right customer (Brief A passed 10/10 there).
- **504, 503, 502.** The gateway waits about 60 s. With a simulation running in the workspace or several chat calls at
  once, a turn returns 504 while the engine still finishes it, or a fast 503 "Internal server error" before the engine
  takes it; a 502 ("agent service returned no response") came when the agent ended the call during the turn. The
  harness reads the call log before sending a line again (a resend after a 502 made the engine replay the end
  sequence), takes the reply from the log when it is there ("the engine handled the turn anyway"), and only then
  resends, three times at most. A 502/503/504 on the first turn leaves no `callId`: it is resent, then exit 2. A bare
  500 on the first turn means the workflow cannot start a call at all (`agent_config.llmConfig`; `freya.update_workflow`
  sets it). Under load a 1.4 s turn took 35–60 s.
- **`close_call` timing and duplicates.** In the proven generator `close_call` is a workflow-level end-of-call tool
  (`alwaysRunsAt: end_of_call`). Over the chat route it ran with the right `customer_id`, but it was logged up to half
  a minute after the call ended (the harness polls the log for 45 s after `/chat/end`) and, together with `end_call`
  and the final code node, several times over in the same log (4 x `close_call` in one call). Count it as "called",
  not as "called once", and do not assert it in a script; a simulation's ledger is the place to check "exactly once".
- No judge, no success criteria, no ledger: the pass/fail here is substring checks on the agent's words and tool
  names. `tools/run_cases.py` remains the score.
- Timing is not representative: no persona model, no audio, and a busy platform multiplies a turn by 20.
- Call metadata differs from a simulation: `channel`/`direction` are `web`; `endedReason` after `POST /chat/end` is
  `customer-ended-call`, or `assistant-ended-call` with `alreadyEnded: true` when the agent ended it first;
  `successCriteriaResult` is empty.
- It runs the published version only, with the agent's configured model (`agent_config.llmConfig`, kept at
  `freya.AGENT_LLM` by `freya.update_workflow`), not a per-simulation override.

## Files

- `builder/smoke.py` — the harness.
- `builder/smoke_scripts/opening.json`, `third_party.json`, `wrong_number.json` — generic scripts.
- `results/smoke-*.json` — `--out` records (gitignored with the rest of `results/`).
