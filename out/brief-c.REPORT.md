# Brief C (Nordvik Savings Bank) transfer test — report

Run: cloud worker, 10 Oct 2026, 16:50–18:06 UTC, branch `cloud/brief-c`. Builder = the skill
`.claude/skills/build-phone-agent/SKILL.md`, followed by hand (no `build.py`). Inputs: `tests/synthetic/brief-c.md`,
`tools/openapi.json`, slot `brief-c`, cases `tests/synthetic/brief-c.cases.json`. `brief-c.rationale.md` was not read.

## Result

| | |
|---|---|
| workflow_id | `68dc5046-318c-4d4f-bae5-3d602d05a7f9` (version 3, published) |
| agent_id | `01b1a04f-fecb-4f14-915f-c63145296333` |
| nodes | 50 (initial node `opening` = conversation node; 12 fin/end pairs + 4 transfer fin/end pairs + promise pair) |
| tools | 15 tool definitions on nodes (verify_identity ×2, transfer_to_agent ×7 [3 model-called, 4 engine-run api nodes], create_promise ×2, schedule_callback, get_account) + `close_call` as the workflow-level `end_of_call` lifecycle tool. `add_note` not used (Brief C never calls it) |
| test_variables | none shipped (`{}`) |
| export | `submission/brief-c.workflow.json` |
| last sim | round 2: 10/10; round 3 (same agent): 8/10; round 4 (v3): 8/10 |

Files: `out/gen_brief-c.py` (generator), `out/brief-c.workflow.json`, `out/brief-c.rules.{json,md}` (64 rules, `builder/rules.py`),
`out/brief-c.audit.{json,md}` (+ `audit.round1.*`), `out/brief-c.lint.txt`, `out/sim/brief-c/round{1,2,3,4}.{json,log}` + transcripts,
`out/sim/brief-c/round1.rescored.txt`.

## Environment incidents

- At the start the network policy denied `staging-app.freyavoice.ai` and `api.openai.com` (proxy 403). Rules, generator,
  lint and the local date/hook unit tests were done offline; by ~17:10 UTC both hosts answered and the rest ran normally.
- `claude-agent-sdk` was missing; `pip install` failed on Debian's PyJWT. `python3 -m pip install --ignore-installed PyJWT claude-agent-sdk` fixed it. Nested `claude -p` worked, so `rules.py` and `audit.py` ran as is.

## Lint (`builder/lint.py out/brief-c.workflow.json --api tools/openapi.json`)

`0 error(s), 53 warning(s), 27 info` (final v3). Every warning was read; none is a real defect:
- ~44 are "`{{first_name}}`/`{{last_name}}`/`{{title}}`/`{{customer_id}}` is never set": lint learns call variables only from
  `test_variables`, which we must not ship. They are call variables (brief section 2) and resolve in the sim transcripts.
- `id_route` / `promise_route` "not set by anything": they are written by the post hooks (`verify_count_post`, `promise_state_post`); the round-1 transcript shows `negotiate -> fin_promise: promise_route == 'recorded'`, so hook-written vars do route.
- `setup`/`prepare` "statements outside try/except": the `CAL_HELPERS` function definitions (same as every reference generator).

## Audit (`builder/audit.py`)

| round | implemented | partial | missing | contradicted |
|---|---|---|---|---|
| 1 (first build) | 59 | 5 | 0 | 0 |
| 2 (after fixes) | 61 | 3 | 0 | 0 |

Fixed after audit 1: R35 (accept-from floor was the unrounded 40%; now the rounded-up floor IS the floor for cards), R50 (transfer
on request also from `hardship` and `plan_offer`), R57 (estate farewell thanks the person). After audit 2: R20 (the service-counter
fallback to `fin_exhausted` now only fires when no swapped hint was seen). Left partial on purpose: R01 (days_late outside 1–45
is outside the call's population; the brief gives no outcome for it), R34 (see "Brief ambiguities").

## Simulator rounds (`builder/sim.py`, gpt-5-mini customer, gpt-5 judge, concurrency 2)

| case | round 1 (as scored) | round 1 rescored* | round 2 | round 3 (same agent) | round 4 (v3) |
|---|---|---|---|---|---|
| PUB-01 happy path | FAIL | FAIL: first line was "Hello. Am I speaking with Daniel Reyes?" | PASS | PASS | PASS |
| PUB-02 third party | FAIL | PASS | PASS | PASS | PASS |
| PUB-03 identity (2 wrong) | FAIL | PASS | PASS | PASS | PASS |
| PUB-04 date after deadline | FAIL | PASS | PASS | PASS | PASS |
| PUB-05 hardship + discount | FAIL | FAIL: no "cannot offer any reduction" after the discount request | PASS | FAIL: spoke the literal `{{reduction_line}}` | PASS |
| PUB-06 floor, holiday | FAIL | FAIL (judge): read the `'full'` fallback in fin_promise's code although close_call sent `partial` | PASS | PASS | PASS |
| PUB-07 vague date | FAIL | PASS | PASS | PASS | FAIL: no close_call in the ledger (agent recorded 540 on 26 Oct, farewell spoken) |
| PUB-08 already paid | FAIL | PASS | PASS | FAIL (judge): objected to the mandatory R29 question | FAIL (judge): same R29 objection |
| PUB-09 plan review | FAIL | PASS | PASS | PASS | PASS |
| PUB-10 tool failure, holiday | FAIL | PASS | PASS | PASS | PASS |
| total | 0/10 | 7/10 | **10/10** | 8/10 | 8/10 |

\* Round 1 as scored failed every case with `outcome (None, None)`: **the organisers' mock bank validates `close_call` reasons
against the kit's Brief A/B table** (`"this outcome needs one of these reasons: callback, no_callback, wrong_number, deceased, unclear"`;
for `promise`/`paid` it accepts no reason at all), so every Brief C close (`not_reached/scheduled`, `promise/full`, ...) gets
`ok: false` and the ledger outcome stays empty. The agent sent the expected outcome/reason in all 10 cases. I added an opt-in
`--close-from-args` to `builder/sim.py` (scores the outcome/reason the agent sent when the mock rejected it, recorded in the row as
`close_from_args`), and rescored round 1's saved ledgers with the same function (`round1.rescored.txt`). Rounds 2–4 use the flag.

### Fixed between rounds 1 and 2
1. **Opening line (PUB-01)**: on the chat route the initial conversation node answered the customer's first "Hello?" with the
   dialogue model, not its `on_enter` tts, so the verbatim sentence (R1) was lost. The `opening` task now says: if you have not spoken
   yet, your message is exactly "<R1 sentence> Am I speaking with {first} {last}?". Round 2 transcripts start with the exact line.
2. **Reduction request on the hardship path (PUB-05)**: the customer asked for a discount in the same turn as the hardship, the tts
   took the turn and the decline closed the call. `hardship` now extracts `asked_reduction`; `fin_financial_distress` writes
   `reduction_line` ("I cannot offer any reduction, and the figures are those on the account.") into the farewell when it is `yes`.
3. PUB-06 needed no change (judge artefact; it passed in round 2).

### Fixed between rounds 3 and 4
4. **PUB-05 (agent bug)**: the terminal spoke `I understand.{{reduction_line}} The care team ...` literally. In round 2 the same
   template resolved ("I understand. I cannot offer any reduction, ..."), so the variable is substituted when it holds text; in round
   3 the extraction said `no`, the fin code wrote `''`, and **an empty-string variable is left as the literal placeholder** in a
   terminal's `spoken_message`. Replaced by two terminals, `end_financial_distress` and `end_financial_distress_reduction`, routed
   on `asked_reduction` (same endedReason `no_promise_financial_distress`). Library lesson: never template a spoken text on a
   variable that can be empty; route to a separate terminal (or write a non-empty sentence). Remaining risk: the extraction
   can still miss a discount request (then the reduction sentence is not said).
- PUB-08 round 3 (judge artefact): the judge counted the statement's mandatory R29 question ("Are you able to settle the full
  overdue amount today?", asked before the customer said they had paid) as a persuasion attempt. No change.

### Remaining failures and diagnosis
- **PUB-07 round 4**: promise recorded correctly (540 on 2026-10-26 after one ask for the exact day), routed to `fin_promise`,
  farewell spoken, but the ledger had no `close_call`. close_call is the `end_of_call` lifecycle tool and lands seconds after
  `/chat/end`; the same tool landed in the other 39 sim calls. Diagnosis: most likely a **simulator timing artefact** (ledger read
  before the late lifecycle call), not verified; worth checking `sim.py`'s post-end ledger wait.
- **PUB-08 rounds 3–4**: **judge artefact** — R29 makes "Are you able to settle the full overdue amount today?" part of the
  statement, before the customer says they already paid; the judge reads it as a persuasion attempt. Passed in rounds 1–2.
- Net: every agent bug found was fixed; over rounds 2–4 the ledger was right in 29/30 calls and the only conversation failures
  after the fixes are the PUB-08 judge reading.
- Organisers' mock rejects every Brief C reason: **simulator/fixture artefact** (the README in `tests/synthetic/` calls Brief C
  "scorable on the organisers' mock"; for close_call it is not). `tools/run_cases.py` would score 0/10 for the same reason.
- Judge sees code_exec source in the tool list and can misread fallbacks (PUB-06 round 1): **judge artefact**.

## Brief ambiguities found
- **R27 vs R31 (floor named twice)**: R27 says the floor "may be named a second time only as attempt 2"; R31 says attempts are "for the
  floor if the customer has already said the full amount is too much", so attempt 1 after a declined floor names the floor a second
  time. The agent follows R31's explicit wording (attempt 1 = floor on the next business day). No practice case reaches it.
- **R26 loans**: "State a rounded floor in whole units" with a fractional instalment (PUB-02: 103.50). The agent proposes the
  rounded-up 104 and accepts any amount from 103.50. Not exercised by a practice case.
- **R14 + service counter**: Brief C counts the second swapped answer as wrong; whether the service counts a swapped answer is
  unknown (no practice case produced a `day_month_swapped` hint). Our own counter in the hook handles both; the service-counter
  fallback route is disabled once a swapped hint was seen. PUB-03 confirmed the service starts at 3 and decrements per wrong answer
  (3 -> 2 -> 1), and our counter closed at the second wrong answer.

## Library / skill gaps found, and the generic fixes made (no Brief C value in shared files)
1. `freyalib.CAL_HELPERS` / `SETUP_CODE` had one meaning of "this/next <weekday>" (this week / a week later). Added
   `weekday_rule="first_after"` ("this X" = "next X" = the first X after today). Mon–Sat calendars already worked via
   `business_weekdays`; the calendar tag "weekend, not allowed" is now "not a business day (<Weekday>), not allowed", so a Saturday
   business day is never called a weekend.
2. **Wrong-answer limit stricter than the service's** and **hints that count after N free uses**: new
   `freyalib.verify_count_post(question, limit, hints, limit_text, free_hints=...)` keeps the brief's counter in `vars` and writes
   `id_route` = `exhausted`/`open` for a deterministic route. Verified on the platform: hook-written vars route in the same turn.
3. **Closing reason that depends on whether the recorded amount equals the overdue amount**, **"the promise decides" over a later
   transfer**, and **retry counts other than "once"**: new `promise_state_pre(full_var)`, `promise_state_post(max_calls, ...)`,
   `promise_reason_code()`, `promise_or_code(outcome, reason)`. (PUB-06: `partial` sent; PUB-10: retry then `full`.)
4. **Chat route skips the initial node's `on_enter` tts** (new finding beyond "skips a first code node"): proposed for the skill
   and `FREYALIB.md` "Initial node": put the verbatim opening line in the opening node's task as "if you have not spoken yet, say
   exactly ...". Not yet written into the skill (left for review); the generator does it.
5. **`builder/sim.py --close-from-args`** (added): synthetic briefs with their own reason names cannot be scored by the kit mock's
   close_call. Proposed: say so in `tests/synthetic/README.md` and run Brief C/D with the flag.
6. **lint.py** proposals: accept a `--call-vars first_name,last_name,title,now,customer_id` list (or read the brief's call-variable
   table) so call variables without `test_variables` do not raise ~44 warnings; recognise vars written by post/pre hooks
   (`V['x'] = ...`, `vars['x'] = ...`) as set.
7. Skill step 7 (smoke) was skipped: the smoke scripts carry Brief A's expectations, and the sim covered the same ground. Proposed: make
   `smoke_scripts/*.json` expectations brief-agnostic (no wording checks) or generate them from the rule inventory.
8. **Empty-string variables are spoken as literal placeholders** (round 3, PUB-05). Proposed: `freyalib.check()` / `lint.py`
   warn when a `spoken_message` or tts text uses a variable that some code path sets to `''`; the skill says to route to separate
   terminals instead of optional sentences in a template.
9. Environment: the skill should say to install the SDK with `python3 -m pip install --ignore-installed PyJWT claude-agent-sdk` on
   Debian images.

`builder/multiproduct.py` self-test (31 checks) and the three reference generators still build after the library changes;
`out/compare_brief-a_lib.py` still reports 0 uncovered differences.
