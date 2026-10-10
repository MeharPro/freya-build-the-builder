# Policy as code: report (branch `cloud/policy-as-code`, 10 Oct 2026)

**Status: library, tests, both v3 generators, lint, dry runs, saves and docs are done. Validation was NOT completed:
all sims were stopped on the user's order (no OpenAI use). There are no v3 PASS numbers.**

## What changed

| File | Change |
|---|---|
| `builder/policy.py` (new) | Policy-as-code module (T1, T2, T3, T20, T22, T26). A single core holds per-product state in string variables written only by code; every policy code node runs the core with one event and routes on `route`. It contains the offer guard (`check_offer` / `accept_offer`: weekend_or_holiday, after_deadline, below_floor, above_full, before_today, vague, plus a loop exit), the stance counter (`count_refusal`, `too_much`; the attempt ladder is precomputed per product, it switches to the floor once "too much" was said, skips offers already refused, and offers the floor once), the human / no-talk / paid / dispute / hardship events, the code-built read-back (`confirm_node`: confirm yes/no/change; change goes back through the guard and is read back again, never to a transfer), the record and note loops (`create_promise` / `add_note` run in `api_request` nodes entered only from a confirmed read-back; the read-back values are baked in and asserted by `promise_assert_pre`; failures are retried up to `fail_max`), the wrap-up node after a recorded promise, finalize (closing precedence) and `state_line`, which is first in every negotiation/confirm/hardship/wrap-up prompt. No bank values: every sentence and value is a parameter. `freyalib` signatures are unchanged. |
| `builder/tests/test_policy.py` (new) | 30 exec tests: weekend, holiday, before today, after both deadlines, amounts at/below/above the floor and the full amount, both problems at once, vague twice, the ladder after "too much" (EXT-A-18), floor once, hardship with and without a named offer (EXT-A-28, PUB-05), read-back change/no (EXT-A-34), record retry/fail twice (PUB-10), wrap-up change/human (EXT-A-31/35), human/no-talk counters, multi-product all-today / one date across deadlines (PUB-13) / one-by-one with notes (PUB-12) / one date for all after one-by-one started (PUB-11) / closing order, empty vars, platform safety. **30/30 pass.** |
| `out/gen_brief-a_v3.py` + `out/brief-a_v3.workflow.json` | Brief A on the policy module, 67 nodes. Conversation-first, no `test_variables`; the opening prompt quotes the opening line (the chat route replaces an initial tts with a model turn). |
| `out/gen_brief-b_v3.py` + `out/brief-b_v3.workflow.json` | Brief A+B (one to three products, notes) on the same module, conversation-first (the old lib port started on a code node), 69 nodes. |
| `out/brief-b.rules.json/.md` (new) | Brief B inventory from `builder/rules.py` (74 rules, 68 in force). It was needed for the B lint command and did not exist before. |
| `builder/FREYALIB.md` | New section "Policy as code". |
| `.claude/skills/build-phone-agent/SKILL.md` | Steps 2–4: the v3 generators are the references; the payment part is policy as code by default (negotiate → check_offer → confirm, counters in code, `state_line` first, wrap-up after a recorded promise). No bank values. |

How the five ext-a-v2 agent bugs are fixed by construction:

1. **EXT-A-18:** the `full_or_floor` rung reads `too_much_<pid>`.
2. **EXT-A-28:** the hardship node sends a named offer to `check_offer` and then the read-back. It closes as `hardship` only when the customer declines with no named offer.
3. **EXT-A-31:** after a recorded promise, a wrap-up node takes the customer's next turn. A human request gets one "can I help?" and then a transfer to `general`. `outcome` was already set, so the close code becomes `transferred/human`.
4. **EXT-A-35:** in wrap-up, a change request gets the mobile-app sentence and the promise stays unchanged.
5. **EXT-A-34:** at the read-back, a new value is `confirm = change` → guard → read back again. The `new_plan` description says a different amount or date is not a plan request.

## Checks that ran

- `python3 builder/lint.py out/brief-a_v3.workflow.json --api tools/openapi.json --call-vars customer_id,first_name,last_name,title,now --rules out/brief-a.rules.json --budget`: **0 errors**, 4 warnings:
  - the setup node keeps freyalib's `CAL_HELPERS` outside its try block (this predates v3);
  - `transfer_to_agent` before verification gives the expected T6 warning for the human-request transfer;
  - negotiate has 5 extraction variables.
- The same command for brief-b (`--rules out/brief-b.rules.json`): **0 errors**, the same 4 warnings (negotiate has 6 extraction variables).
- `freya.validate_workflow` dry run: valid for both.
- Saved: `brief-a-v3` = workflow `9cf0839d-66c4-4f9f-91df-8f9f2698b2d1` (agent `7d100f1a-7799-42ef-9d12-ff74aa69ff13`, version 3); `brief-b-v3` = workflow `403d8b8b-fbdc-4100-b6db-37dad14fd5d6` (agent `24083493-68b9-4c7d-86d1-914ffa24b18c`).
- One local sim on brief-a-v3 (`--only PUB-01,PUB-06`, before the 3-rep run): **2/2 PASS**. PUB-06 went:
  1. "too much" → floor offered today with "The rest stays overdue";
  2. a named offer for Friday → guard ok → code-built read-back;
  3. yes → `create_promise {amount 637.5, date 2026-10-16}` from the api node → the text-message sentence in wrap-up;
  4. "that's all" → `close_call promise`.

  This confirms that the api-node write path works on the platform.

## Before / after PASS tables

| Set | v2 (before) | v3 (after) |
|---|---|---|
| Brief A public, 3 reps | 10/10 (earlier sessions) | **not measured**: run 1 got HTTP 503 on every first chat turn from 18:12 UTC (0/10, all "no call was started": an infrastructure error, not an agent result); the run was stopped |
| Brief A extended (42) | 34/42 (`docs/ext-a-v2-failures.md`) | **not run** |
| Brief B public, 3 reps | — | **not run** |
| Brief B extended | — | **not run** |

`out/sim/v3/a/` holds the run-1 transcripts of the 503 failures, kept only as evidence of the outage. A direct probe
afterwards got HTTP 403 "error code: 1010": the probe used urllib's default User-Agent, which the gateway's bot
filter blocks. That is an artefact of the probe, not a finding about the agent.

## Not done

- TASK 3 validation (3 reps A/B, extended A/B, up to two repair rounds): stopped on the user's order. There are no
  per-case extended results, so EXT-A-18/28/31/34/35 are fixed by construction and covered by unit tests, but not
  confirmed on the platform.
- `submission/brief-a-v3.workflow.json` and `submission/brief-b-v3.workflow.json` were not exported, because the
  agents are unvalidated.
- EXT-A-17, EXT-A-25 and EXT-A-01 are case or judge artefacts, as `docs/ext-a-v2-failures.md` says, and were left
  as they are.

## Next steps when sims are allowed again

Rerun the TASK 3 commands as written in the task: `sim.py brief-a-v3 --brief A --reps 3 --concurrency 2 ...`,
then the extended sets. Watch for these risks:
- the `offer_date` extraction of "next Friday" (EXT-A-20);
- the `offer_for` mapping in multi-product calls;
- a stale enum when extraction returns nothing (the code clears every routed enum after each policy step).

Export the submissions after a green run.
