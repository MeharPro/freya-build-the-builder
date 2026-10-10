# persona-2: persona robustness, round 2 (cloud worker, 10 Oct 2026, branch `cloud/persona-2`)

Brief-agnostic work on how customers talk: two generic persona smoke scripts, extra styles for the local simulator,
an opt-in digits gate for identity questions, and three generic agent bugs found by the organisers' simulator under
the `talkative` style and fixed in the library. Nothing from Brief A/B values entered the library; every fix is a
rule about speech, not about a bank.

## What changed

| Area | Change | Files |
|---|---|---|
| Smoke (Task 1) | `talkative.json` (small talk before each answer, a cut-off line with no answer at the second security question, then the answer) and `asks_back.json` ('why do you need that?' at a security question, 'which account is this about?' at the first payment question). Expectations hold for any collections brief: `verify_identity` called once per question with the case's value and `verified` true, no call on the cut-off line, `get_account` after identity, no close/transfer/promise on small talk or a question back, no sympathy phrase for small talk, no debt words before identity. | `builder/smoke_scripts/talkative.json`, `asks_back.json` |
| Smoke harness | `--practice` (opens a mock practice customer for `--case`, so bank tools answer for real), `--cases <file>` (generated cases), `--answers`, placeholders `{{answer1}}`/`{{answer1_raw}}`/`{{last_name}}`, a `tool` expectation (`count`, `values_in_order` compared on digits, `results_true`), and pre-action `api_call` events named by their endpoint (`get_account`). | `builder/smoke.py`, `builder/SMOKE.md` |
| Skill | Step 7 runs the two persona scripts on a practice customer whose identity passes. | `.claude/skills/build-phone-agent/SKILL.md` |
| Local simulator (Task 2) | `EXTRA_STYLES` (terse, rambling_corrects, pieces_identity, impatient, previous_question, volunteer, silent_turn, hangs_up_after_promise, final_like) in the kit's STYLES format, and `--styles <list\|kit\|extra\|all>` (`none` = the unstyled copy). Styled copies are `<id>[<style>]`, keep `mock_case` = the original mock customer (public cases: the case id), and the style is in every row, the transcript header (with the style text) and `results/log.jsonl`; a per-style summary names cases that pass unstyled but fail styled. | `builder/sim.py`, `builder/SIM.md` |
| Library (Task 3) | Opt-in `gated_digits_identity(...)` + `digits_from_spec(api, field)`: the question node has no tool and a `^[0-9]{N}$` extraction; `is_set AND != sentinel` routes to an api_request node that calls `verify_identity` with field and answer baked, then a code node writes a schema-valid sentinel and routes (all verified / verified / exhausted / unreadable / wrong, each wrong or unreadable answer re-entering the question with the brief's fixed line). Default stays prompt-driven. 6 exec tests. | `builder/freyalib.py`, `builder/FREYALIB.md`, `builder/tests/test_gated_identity.py` |
| Agent fix 1 (generic) | A day of the month said with a weekday wins: 'Monday the twenty-sixth' was resolved as the next Monday (19 October) and read back that way. | `builder/policy.py` `resolve_when`, test in `builder/tests/test_policy.py` |
| Agent fix 2 (generic) | `CUTOFF_CLAUSE` appended by `Policy` to every enum on the negotiate, confirm, hardship and wrap-up nodes: a cut-off line or small talk is the neutral value, even with words like stressed/busy/family/wedding ('I've been so stressed because my cousin's' was routed to hardship; strings of cut-off small talk became refusals). | `builder/freyalib.py` (`CUTOFF_CLAUSE`, `with_cutoff`), `builder/policy.py` |
| Agent fix 3 (generic) | `PERSONA_CONDUCT`: a line that stops mid-sentence gets 'Sorry, I think you were cut off. Please go on.'; at a payment proposal the amount and date are not repeated word for word (the judge counted four repeats of the floor as four offers). | `builder/freyalib.py` |
| Agent fix 4 (generic) | Words that stop on a bare tens word ('I can pay on the twenty') are a vague day: ask for the exact day; never the 20th and never the extractor's guess. | `builder/policy.py` `resolve_when`, test |

Tests: `test_policy.py` 32/32, `test_gated_identity.py` 6/6, `test_lint.py`, `test_normalise.py` pass. Lint of both v3
workflows: 0 errors, warnings unchanged (48 / 49).

## Smoke results (chat route, practice customers)

| Agent | Script | Case | Result |
|---|---|---|---|
| brief-a-v3 (main) | talkative | PUB-01 | 61/62: the only miss was the harness (pre-action `get_account` logged as `api_call`), fixed in smoke.py |
| brief-a-v3 (main) | talkative | PUB-05 | 62/62 |
| brief-a-v3 (main) | asks_back | PUB-03 | 32/32 |
| brief-b-v3 (main) | talkative | PUB-11 | 62/62 |
| brief-b-v3 (main) | asks_back | PUB-13 | 32/32 |
| brief-a-v3-p2 (fixed) | talkative | PUB-06 | 62/62 ("Please go on" on the cut-off line) |

No smoke failure came from the agent, so the v3 generators keep the prompt-driven identity form (Task 3's condition
for switching was not met). Ad-hoc chat checks on the fixed agent: two cut-off lines at the payment question stayed
`topic none / stance other` (no hardship, no refusal); 'Monday the twenty-sixth' became the holiday 26 October and the
next business day 27 October was offered; 'I can pay on the twenty' got 'Which exact day would that be?'.

## Organisers' simulator (tools/run_cases.py, Brief A/B public cases, one rep)

Agents: `brief-a-v3` = agent `7d100f1a` (current main, published by the main session at 20:24 UTC); `brief-b-v3` =
agent `24083493`. The fixes were published to two NEW slots, `brief-a-v3-p2` (workflow `71a962c4`, agent `458a5e90`)
and `brief-b-v3-p2` (workflow `32451af1`, agent `7148e3fe`), because the main session was running simulations on the
v3 agents at the same time and a republish would have changed the agent under its runs.

RESULTS_TABLE

## Failures, read from the transcripts (`freya.get_call(call_id)['messages']`)

FAILURE_TABLE

## Credits

RUNS_USED

## Not done / open

- The v3 slots (`brief-a-v3`, `brief-b-v3`) and `submission/` still hold main's version: whoever merges this branch
  should regenerate and republish them (the p2 slots are copies for measurement only).
- `talkative` is dominated by the persona model's truncation on some calls (PUB-04 rep: more than 20 cut-off lines in
  one call). The agent now asks the customer to go on and never acts on a cut-off line, but a customer who never
  finishes a sentence cannot be served; that is a persona artefact, not an agent bug.
- `corrects`, `pieces`, `in_words` were not re-run on v3 within this budget (v2 reference: 9/10, 9/10, 8/10).
- The extra local styles were not run beyond the one sanity check (OpenAI is closed; Claude provider limited to 5 calls).
- The gated identity helper has never run on the platform (opt-in, unused by any generator).
