# builder/sim.py — a local simulator over the chat route

`builder/sim.py` runs the practice customers against a **published** phone agent without a Freya simulation. Each
case is one call over `POST /api/v2/chat/message` (one turn at a time, no simulation queue, so cases run in parallel in
a thread pool), with a model-played customer that follows the organisers' persona text, and is then scored exactly
like `tools/run_cases.py`: the mock bank's ledger (`tools/score.py: score_ledger`) plus a judge model that reads the
transcript against the case's `checks`. Standard library only. It never edits a workflow.

```bash
source env.sh
python3 builder/sim.py brief-a                                   # all Brief A+B cases in public-test-set.json, 5 at a time
python3 builder/sim.py brief-a --brief A --reps 3 --out results/sim-a.json
python3 builder/sim.py e33a51fa-5e74-4f66-80a5-01113ce944d8 --only PUB-01,PUB-02 --concurrency 2 --verbose
python3 builder/sim.py brief-b --brief B --style talkative --customer-model gpt-5-mini --judge-model gpt-5
```

| Option | Meaning |
|---|---|
| `<workflow>` | A workflow id, or a slot name from `.freya-agents.json` (`brief-a`, `brief-b`, `base`). |
| `--cases`, `--brief A\|B`, `--only PUB-01,PUB-02`, `--reps N`, `--style <pieces\|corrects\|talkative\|asks_back\|in_words>` | As in `run_cases.py`. With `--reps > 1` a case passes only when every rep passes. |
| `--styles <list\|kit\|extra\|all>` | Every selected case once per style (comma list; `none` adds the unstyled copy; `kit` = the five kit styles, `extra` = `EXTRA_STYLES`, `all` = both). A styled copy is `<id>[<style>]`, keeps the original mock customer (`mock_case`, else the original id) and the expected ledger; rows, transcripts (header `[style: ...]` + the style text) and `results/log.jsonl` carry the style; the summary prints one line per style with the cases that pass unstyled but fail styled. `--style` also accepts the extra styles. |
| `--concurrency 5` | Cases run in parallel (thread pool). See "504 under load" below before going above 5. |
| `--max-turns 30` | Customer lines per call at most. |
| `--out results/sim.json` | A JSON record shaped like `run_cases.py`'s (`final`, `rows`, `all_rows`; rows have `id`, `pass`, `failed`, `tools`, `customer_id`, `call_id`, `transcript`, `judge`, `stop`). |
| `--transcripts results/transcripts/` | One `<case>.txt` (and `.json`) per case: customer/agent lines, tool calls in place, the ledger and the judge's verdict. `-rN` suffix with reps. |
| `--customer-model`, `--judge-model`, `--provider openai\|claude` | OpenAI chat completions (urllib, `OPENAI_API_KEY`; defaults `gpt-5-mini` / `gpt-5`) or the Claude CLI `claude -p` (used when the key is missing; defaults `claude-haiku-5-5` / `claude-sonnet-5-5`). The CLI runs from an **empty scratch directory**: run from the repo, Claude Code loads `CLAUDE.md`, `.claude/` settings and skills into the session, so the customer and the judge would read the builder's scoring rules and the known chat-route bugs (verified 10 Oct: asked to quote any project instruction, `claude -p` from the repo returned the CLAUDE.md heading, from an empty directory `NONE`). The runs described under "Chat route findings" predate this fix; their ledger failures stand on their own, their judge verdicts were produced with that extra context. |
| `--opening "Hello?"` | The customer's first line. The chat route needs a user message to produce the agent's opening (see below). |
| `--verbose` | Print every turn as it happens, prefixed with the case id. |

Output: the same lines as `run_cases.py` (`PASS/FAIL <id> <level> <family> | <tool chain>`, then `       - <reason>` per
failure), `n / N passed`, a cost line (chat turns, model calls, ledger polls), one line appended to `results/log.jsonl`
with `"runner": "sim"` (so it can be told apart from the organisers' scorer), and the `--out` JSON.

## Extra styles (`EXTRA_STYLES` in sim.py)

Brief-agnostic paragraphs in the organisers' format, appended to the kit's `STYLES` in memory (`tools/run_cases.py`
stays as shipped): `terse` (one short line, digits and dates in words, one cut-off sentence: the habits of the
organisers' persona model), `rambling_corrects` (small talk + a wrong payment value corrected at the read-back),
`pieces_identity` (security answers in two parts, in words), `impatient`, `previous_question` (answers the previous
question once), `volunteer` (all security answers at once, says what they can pay unasked), `silent_turn` ('...' once,
'say that again?' at a read-back), `hangs_up_after_promise`, `final_like` (short lines, one split number, one question
back, amounts and dates in words). Use them with `--provider claude` while OpenAI is closed; one sanity check ran on
10 Oct (`--only PUB-01 --style terse --max-turns 4`: 4 model calls, style and mock customer recorded, the call cut by
the 4-turn cap).

## One case, step by step

1. `POST /v1/practice/sessions {"case": mock_case or id}` on the mock bank opens a fresh practice customer; its `variables`
   (`customer_id`, `first_name`, `last_name`, `title`, `now`) are the call's `customerVariables` (a case's own `variables.now` replaces `now`).
2. The customer's persona is `run_cases.persona_for(case)['prompt']` (the organisers' `PERSONA` template, `STYLES`,
   third-party handling) plus one line: `You are on a phone call. Reply with ONLY your next spoken line.` The
   conversation is kept as alternating messages (customer = `assistant`, agent = `user`); for the CLI it is
   serialised as `You:` / `Agent:` lines.
3. `POST /api/v2/chat/message {workflowId, message: "Hello?", customerVariables}` starts the call and returns the
   agent's opening line; every later turn is `{callId, message}`. After every agent turn the mock ledger is polled
   (a poll that fails, times out or answers without `calls` keeps the previous ledger and is counted as a ledger
   error; it never aborts the call). A first turn that answers 502/503/504 or nothing is sent again after 15 s, up to
   3 times, each time with a **fresh practice customer**: the engine may have created a call for the failed attempt
   and there is no `callId` to end it with, so the orphan's later `close_call` must not land in this case's ledger.
   The transcript notes the earlier customer ids. A bare 500 on the first turn is not retried (the workflow cannot
   start a call): the case stops at once, with one ledger read, no 30 s wait and no judge call.
4. The call stops when, checked in this order after every turn: the ledger shows a `close_call`; the agent ended the
   call (`endedByAgent: true` in the response, or, after a 502/504, an `end_call`/`call_ended` event in the call log:
   `stop` says which); the reply is empty twice in a row; three turns in the call got a 5xx or no answer **and** no
   reply could be recovered from the call log (a recovered 504 under load does not count); the customer said goodbye
   twice; `--max-turns` is reached. Then `POST /api/v2/chat/end {callId}`. A harness error mid-call (an exception
   outside the model and mock calls) also ends the call, and the case is still fetched, scored and judged, with
   `stop: harness error: ...` and a `harness: ...` failure.
5. `GET /api/v2/call/{callId}` gives the full transcript with the engine events (tool calls with args and results,
   routes, node entries). It does serve the chat route's `callId`; if it ever does not, the harness's own log plus the
   ledger's calls are used instead (`transcript_source` says which).
6. `score_ledger(case, ledger)` checks the bank records; the judge gets `All of these are true:` + the checks (the
   organisers' `successCriteria` wording), the transcript with tool events in place (it is told that the customer's
   first line, `--opening`, is them picking up the phone), and the tool list, and must answer
   `{"outcome": "pass"|"fail", "reason": "..."}`. Parsing is strict: a JSON object with `outcome` (fenced or not), an
   `outcome: pass|fail` field, or the bare word `pass`/`fail`; prose that merely contains the words is no verdict
   (an earlier fallback read "I cannot pass judgment" as a pass). With no verdict the judge is asked once more for the
   JSON object; still none -> `fail` with `no verdict`. Judge failures are appended as `conversation: ...`, like
   `run_cases.py`. The cost line counts judge retries and ledger errors when there were any.

## Extended cases: `mock_case` and a different `now`

The mock bank serves exactly the practice customers `PUB-01`..`PUB-13` (fixed identity answers, products, `days_late`,
faults: PUB-10's first `create_promise` fails). The customer's script, the expected ledger and the checks are ours, so a
case file may reuse a mock customer with a new script under its own id. Two optional case fields:

| Field | Effect |
|---|---|
| `mock_case: "PUB-03"` | The practice session is opened with `{"case": case["mock_case"]}` instead of the case's `id`, so ids can be unique (`EXT-A-07`). Copy `variables` (names, title), `identity`, `products` and `faults` from that mock case: the mock answers with its own data, whatever the case file says. |
| `variables.now` | Sent in `customerVariables` instead of the session's `now`. The mock enforces no date rule, so another call date is a valid test as long as every expected date is recomputed for it. |

Case sets: `tests/cases/brief-a-extended.cases.json`, `tests/cases/brief-b-extended.cases.json` (see `tests/cases/README.md`).
`tools/run_cases.py` (kit file) knows neither field: run extended cases with `sim.py` only.

## How it differs from the organisers' simulation

| | `tools/run_cases.py` (Freya simulation) | `builder/sim.py` (chat route) |
|---|---|---|
| Who plays the customer | Freya's persona model (`gemini-3-flash-preview`), one simulation per run | Your model: OpenAI `gpt-5-mini` or Claude `haiku` via the CLI, same persona text |
| Who judges | Freya's analysis model (`gemini-3-flash-preview`) on the run's `successCriteria` | Your model: `gpt-5` or `sonnet`, same criteria wording, plus the explicit tool list |
| Concurrency | One simulation per workspace; a second run waits ("another simulation is running") | None of that: no simulation object, no queue. Cases run in a local thread pool. The mock bank's practice sessions are per team key and independent of simulations, so nothing waits. |
| Agent model | Per-simulation overrides (`AGENT_LLM`) | The agent's configured `agent_config.llmConfig` (kept at `AGENT_LLM` by `freya.update_workflow`) |
| Who speaks first | The agent (phone call) | The customer must send a line first; "Hello?" makes the agent produce its opening (see below) |
| Timing | Representative; a slow run is discarded | Not representative: no audio, no persona model on Freya's side, and a busy gateway turns a 2 s turn into a 504 |
| Cost | Freya simulation credits | Chat turns on Freya (cheap) + your own model calls (printed at the end) |
| Call metadata | `endedReason` = the terminal's function name | `endedReason` is `customer-ended-call` after `/chat/end` even when the agent reached its end node |
| Score | The score that counts | A practice score: scores vary run to run on both sides. Use `run_cases.py` before trusting a number. |

## Chat route findings (observed on the Brief A workflow, `e33a51fa-5e74-4f66-80a5-01113ce944d8`, a 10/10 agent in `run_cases.py`)

Test: `python3 builder/sim.py brief-a --only PUB-01,PUB-02 --concurrency 2` (Claude CLI fallback, no `OPENAI_API_KEY`),
run twice on 10 Oct 2026 (the second time after the harness fixes of points 5 and 6). Both cases FAILED both times
(run 2: `FAIL PUB-01 ... | close_call` outcome `not_verified/failed`; `FAIL PUB-02 ... | close_call`; 41 chat turns, 41
model calls, 383 s), and every failure traces back to the chat route, not to the agent, which passed the same two cases
10/10 and 3/3 reps in `run_cases.py` the same day. The request/response pairs:

**1. The agent's opening line comes back as the reply to a first customer message.** A phone call starts with the
agent, but the chat route needs a `message`. `"Hello?"` works:

```
POST /api/v2/chat/message
{"workflowId": "e33a51fa-...", "message": "Hello?",
 "customerVariables": {"customer_id": "c_96d56796-c5c", "first_name": "Maria", "last_name": "Costa", "title": "Ms", "now": "2026-10-14T11:00"}}
-> 200 {"response": "Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with Ms Costa?",
        "callId": "7350a421-202b-411e-99dc-4e5d770d93ec", "messageId": "msg_..."}      (33.9 s; the other call's first turn took 57.9 s)
```

The call log shows `route_evaluated setup -> opening (always)` and `node_enter opening`: the initial node is routed
through and the first conversation node's `on_enter` TTS is the response. `{{title}} {{last_name}}` were resolved from
`customerVariables` (Ms Costa, although the workflow's `test_variables` say Mr Reyes). **No agent line ever contained
`{{`**, so prompts and TTS do get the call variables.

**2. The first code node is routed through but its code never runs.** `setup` (the initial node, a code node whose
`pre_actions` compute `today_iso`, `today_text`, `callback_text`, `weekday_table`, `early_deadline`, ...) produced no
`function_call_start code_exec` event, while the later code node `fin_no_callback` did (`[tool] code_exec -> HTTP 200`).
The `variable_table` of every `route_evaluated` event in both calls holds `customer_id`, `now`, `first_name`, ... but
none of the nine variables `setup` writes. Consequence in PUB-02: the model had no computed "tomorrow" and invented one:
`schedule_callback body={"date": "2025-05-15", "time": "11:00", ...}` (the case's `now` is 2026-10-14). In a simulation
the same workflow passes PUB-02, so the first code node runs there. `sim.py` prints this as a NOTE at the end of a run.

**3. Tool bodies on conversation nodes take `customer_id` from the workflow's `test_variables`, not from the call.**
The workflow carries `"test_variables": {"now": "2026-10-14T11:00", "title": "Mr", "last_name": "Reyes", "first_name": "Daniel", "customer_id": "c_test"}`
(the only place the string `c_test` occurs). Every tool defined under a conversation node's `tools` with
`body.properties.customer_id.default = "{{customer_id}}"` was sent with `c_test`:

```
function_call_start  verify_identity   body={"field": "date_of_birth", "answer": "1988-03-14", "customer_id": "c_test"}   (PUB-01, twice)
function_call_error  verify_identity   "API request failed: {'ok': False, 'error': 'unknown customer_id'}"
function_call_start  schedule_callback body={"date": "2025-05-15", "time": "11:00", "customer_id": "c_test"}           (PUB-02, six times)
function_call_error  schedule_callback "API request failed: {'ok': False, 'error': 'unknown customer_id'}"
```

while the global `close_call` tool (`alwaysRunsAt: ["end_of_call"]`, same `default: "{{customer_id}}"`) was sent with
the real id: `close_call body={"reason": "failed", "outcome": "not_verified", "customer_id": "c_7ac9c4e6-271"} -> 200 {"ok": true}`.
The engine's variable table held the real id throughout (`customer_id = c_7ac9c4e6-271` in `route_evaluated.variable_table`),
so the call variables arrived; only the templating of conversation-node tool defaults preferred `test_variables`.
The earlier smoke run (`results/smoke-third_party.json`, call variables `customer_id: c_smoke`) shows the same `c_test`.
**Until this is solved, the ledger half of the score cannot be earned over the chat route for a workflow that ships
`test_variables` with a `customer_id`**: the mock rejects every identity/account/promise/callback call, the agent
reports a technical problem, and the ledger ends `not_verified`/`no_callback`. The conversation half (routing, what is
said before identity, third-party handling, the judge's checks) is still exercised.
Experiment for the generator design (needs a workflow edit, not done here): publish the workflow without
`test_variables` (or without `customer_id` in it) and check whether the tool body then takes the variable table's
`customer_id`. If it does, the builder should not emit `test_variables`. If it does not, a code node placed AFTER the
opening node could copy `vars['customer_id']` into a name absent from `test_variables` for the tool defaults to use.

**4. Undocumented engine events.** Besides the documented `node_enter`, `route_evaluated`, `function_call_start/complete`
and `error`, the chat calls carried `function_call_error` (a 4xx from the tool API: there is then NO
`function_call_complete`), `function_call_complete_deferred`, `tool_call_routing`, `variable_extracted`,
`turn_completed` (with `responseText`), `conversation_resumed` and `call_ended`. `sim.py` reads `function_call_error`
as the tool's result so the judge sees the failure.

**5. The turn in which the agent ends the call has so far always come back as a 502 or 504, never as a 200 with
`endedByAgent: true`.** Observed on the Brief A workflow first (PUB-02, turn 11, two calls in parallel):
`POST /chat/message {"callId": ..., "message": "Tomorrow morning around eleven is the only time ..."}` -> `502 error code: 502`
after 65 s, while the call log shows the turn fully processed: `node_enter fin_no_callback`, `code_exec`, `end_call ->
success Call ended`, `close_call -> 200 {"ok": true}`, and the farewell "Thank you for your help. Goodbye." as an
assistant message. Then on the `brief-a-v2` workflow (`4045179c-...`, `results/brief-a-v2-sim.json`, 10 cases at
concurrency 5, transcripts in `results/transcripts-v2/`): the agent-ending turn answered 502 in 7 cases and 504 in 3,
the reply and the end were recovered from the call log 6 to 7 s later every time, and no turn of any run (the
two brief-a runs, 59 turns on brief-a-v2) carried `endedByAgent: true` in a 200 response. So this is not a one-off under load, but it
is also only two workflows on one day; the harness handles both outcomes and the `stop` field now says which one was
seen (`ended by the agent (endedByAgent in the response)` vs `ended by the agent (end_call in the call log after HTTP
502)`). Note for readers of the older results files: their `stop` label `ended by the agent (endedByAgent)` was
written for both cases and in every one of them the end came from the call log after a 502/504.
A first version of the harness re-sent the line on 502: the engine processed it again each time (four identical user
messages, the end node ran four times, three `close_call`s, the later ones answered `{"ok": false, "error": "the call
is already closed"}`). **A line is now never re-sent mid-call**; after a 502/504 the reply is read from the call log
and an `end_call`/`call_ended` event there, or a `close_call` in the ledger, ends the loop.

**6. `close_call` at `end_of_call` lands after `POST /chat/end`, asynchronously.** PUB-01: `/chat/end` at ~238 s into
the call, `close_call -> 200 {"ok": true}` at 249.9 s. A ledger read 2 s after `/chat/end` still said "not closed". The
harness now polls the ledger for up to 30 s after `/chat/end` until a `close_call` appears.

**7. 504 under load.** With two calls in parallel, 3 of the first 4 turns answered 504 after 60 s while the engine had
finished the turn in 2 to 7 s (the reply was in the call log 6 to 7 s after the 504). The gateway, not the agent, is the
bottleneck; `--concurrency` above 2 or 3 will mostly add 504s and 60 s waits. Timing from the chat route says nothing
about the agent's speed in a simulation.

**8. `GET /api/v2/call/{callId}` does serve the chat route's `callId`** (the transcript with every event; `endedReason`
is `customer-ended-call` after `/chat/end` even when the agent ended the call). The fallback to the harness's own log
was never needed.

What this means for the generator: a workflow whose practice score should be readable over the chat route needs (a) no
`test_variables` with a `customer_id` (to be verified, point 3), and (b) nothing it depends on computed in the initial
node (point 2): either the opening conversation node first and the setup code node second, or date facts computed
later in the flow. Both are testable in minutes with `sim.py` once a workflow is published; the ledger score from
`run_cases.py` remains the one that counts.
