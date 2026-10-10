# Brief D (Kestrel Bank, raw material pack) — cloud build report

Run: 2026-10-10, 16:57–17:15 UTC, branch `cloud/brief-d`. Inputs: `tests/synthetic/brief-d.md`, `tools/openapi.json`, slot `brief-d`, cases `tests/synthetic/brief-d.cases.json` (13).

## Headline: built and checked offline only, because Freya and OpenAI were blocked

This environment's network policy denies both hosts the run needs. The egress proxy answers **403 to CONNECT** for:

- `staging-app.freyavoice.ai` (FREYA_API_URL): `freya.workspace_id()`, `validate_workflow`, `save_workflow`, `export_workflow`, the chat route.
- `api.openai.com`: the customer and judge models in `builder/sim.py`.

All four keys were set. The calls failed at the proxy, not on authentication. So these steps **could not run**, and I did not fake their results:

| Step | Status |
|---|---|
| dry run + `save_workflow` (workflow_id, agent_id) | **not run**: no workflow_id / agent_id exists |
| smoke (opening / third_party / wrong_number) | **not run** |
| sim rounds 1–4 on the 13 cases | **not run**: no `out/sim/brief-d/**` |
| `submission/brief-d.workflow.json` (export) | **not produced**: export needs the platform |

Fix: in the cloud environment settings (Network access), add `staging-app.freyavoice.ai` and `api.openai.com` to Allowed domains and keep "Allow package managers" ticked. Then re-run this routine. Generation is deterministic, so the next run can start directly at step 6 (dry run + save).

Everything that runs locally was done: the rule inventory and coverage audit (nested Claude works), the generator, lint, executed unit tests of every code node and hook against the 13 cases' data, and the A/B equivalence proofs after the library changes. `brief-d.rationale.md` was **not** read: no sim round took place, so the condition for reading it was never met.

## What was built

- Generator: `out/gen_brief-d.py` (on `builder/freyalib.py` + `builder/multiproduct.py`). Every value comes from brief-d.md, and `# R…` comments name the source item or section.
- Workflow: `out/brief-d.workflow.json`. It has **50 nodes**: 8 conversation, 3 api_request, 22 code (17 `fin_*`, setup, prepare, finalize, 2 decline counters), 17 end_call. **13 node tools** (verify_identity ×2, transfer_to_agent ×5, create_promise ×2, add_note ×3, schedule_callback) plus 3 engine calls (get_account and 2 transfers) and **1 workflow tool** (`close_call`, end_of_call lifecycle). The initial node is `opening` (a conversation node). `test_variables` is `{}`, the same shape as the agent verified on the chat route.
- Workflow id / agent id: **none** (save blocked, see above).

### Rule in force (memo over CP-7 over email over code list v3)

| Topic | Superseded | In force (applied) |
|---|---|---|
| Band S latest date | 7th business day | **5th business day** (memo 1) → 21 Oct for a 14 Oct call |
| Band S attempts | 3 (final-offer repeat) | **2** (memo 2); Band F 1 |
| Card floor | minimum_payment | **min(2 × minimum_payment, past_due)** (memo 3); loans instalment_amount |
| Closure days | CP-7 4.3 list | + **Fri 30 Oct (Founders' Day)** (memo 4); 26 Oct a normal day |
| Hardship-declined code | HARD | **HSHP** (memo 5), outcome no_promise |
| Callback window | 09:00–17:00 | **09:00–18:00 included**, today after now + next 2 business days (memo 6) |
| Band F latest date | — | 21 calendar days; not a business day → last business day **before** |
| Closed day named | — | nearest business day **before** (4.6); a date after the latest date → the latest date |
| Every close | — | carries a code, PRM and AP included (no reason is dropped) |

`rules.py` marked all 9 superseded rules (R17, R40, R67, R68, R69, R72, R77, R89, R92) with their memo overrides.

### Architecture

`opening` (verbatim "This is the digital assistant of Kestrel Bank. Please note that this call is recorded. Am I speaking with {first_name} {last_name}?") → `setup` (dates, callback window, F/S latest dates, attempt-1 date, vague-period date, the 4.7 weekday table, default close codes) → `ask_phone` → `ask_dob` (phone first; the **second wrong answer on either question** ends the check: `verify_post(stop_left=("1","0"))` plus a route on `wrong_answers_left ∈ {1,0}` → IDF; the `day_month_swapped` hint is not counted; a second decline → IDD; identity-service HTTP failures → not_verified/SVC) → `load_account` → `prepare` (per-product band, floor, latest date, attempt ladder, tagged calendar, statement; no products → no_promise/SVC) → `negotiate` (create_promise / add_note with text / transfer general; routes to hardship / restructuring / ALL_DONE) → `finalize` (promise > all paid AP > SVC > HSHP > DSP > RF) → `fin_*` → `end_*`. Third party: personal-banking line, a callback inside the window, one nearest-slot proposal, then CBK, NCB, WN or DEC.

## Lint

`python3 builder/lint.py out/brief-d.workflow.json --api tools/openapi.json --call-vars customer_id,first_name,last_name,title,now`

```
WARN nodes.setup.pre_actions[code_exec].code: code has statements outside try/except (Assign); wrap the whole body
-- 0 error(s), 1 warning(s), 27 info
```

The one warning is known library behaviour (FREYALIB.md: SETUP_CODE keeps CAL_HELPERS outside its try). Without `--call-vars` lint printed 45 false warnings, one per call-variable placeholder. See library gap 5.

## Offline unit tests (executed code, not inspection)

- `out/unit/brief-d_dates.py`: runs the setup and prepare code of the workflow JSON on all 13 cases' variables and products (output in `out/unit/brief-d_dates.out`). I checked the results against my own reading of the brief: the latest dates (F 4 Nov, S 21 Oct), floors (PUB-06 1275, PUB-12 card 306 / loan 440), attempt 1 on Thu 15 Oct, attempt 2 = floor on 21 Oct, the vague-period proposal Fri 16 Oct, "this/next Friday" = 16 Oct, and the callback slots (today after 11:00, 15 and 16 Oct, 09:00–18:00). For PUB-13 the calendar offers Thu 29 Oct for the card on 30 Oct and the loan's own latest date, 21 Oct. All 13 cases: setup ok, prepare ok.
- `out/unit/brief-d_hooks.py`: **27/27 pass**. It covers:
  - the promise pre hook (30 Oct → 29 Oct, a Saturday → Friday, a date past the latest date → the latest date, an amount above past_due → past_due);
  - the promise post hook (fail, fail, ok → recorded on the 3rd try; 3 fails → a service_error note);
  - the verify hook (first wrong → ask again, left 1 → FAILED, hint → not wrong);
  - finalize precedence (7 mixes), the close codes (PRM, HSHP, AP, IDF), and the close_call pre hook keeping PRM.

## Audit (`builder/audit.py`, Claude)

| run | implemented | partial | missing | contradicted | superseded |
|---|---|---|---|---|---|
| 1 (first build) | 84 | 4 (R48, R54, R79, R88) | 0 | 0 | 9 |
| 2 (after fixes) | 84 | 4 (R52, R53, R65, R88) | 0 | 0 | 9 |

Fixed after run 1:

- **R48**: add_note was added to the hardship node, so a 3rd create_promise failure there can note service_error, plus a done route.
- **R54**: the identity steps now say "this will only take a moment" once.
- **R88**: default close codes are set in setup (not_reached/UNC) and after get_account (no_promise/RF), so a hang-up still closes with a code.
- **R79**: documented, not gated. The memo applies from the first call of the campaign (go-live 14 Oct), so no campaign call uses the pre-memo values.

Fixed after run 2:

- **R53**: transfer_to_agent (general) and the transferred route were added to hardship and hardship_notes.
- **R65**: "Thank you" was added to the WN, DEC and UNC farewells.

Left open:

- **R52**: a plan request *inside* hardship is not routed to restructuring. The hardship rule says no plan is on the table, so this is a brief ambiguity.
- **R88 residue**: a hang-up *before* the first customer turn has no close vars yet. Seeding them before `opening` would need `test_variables`, which must not ship.

The audit was not re-run after the run-2 fixes.

## Sim rounds

None (blocked). Practice PASS/FAIL table: **not available**.

### Pre-sim risk list (what I would check first in round 1)

1. **Does the mock decrement `wrong_answers_left` on a `day_month_swapped` hint?** If it does, a hint followed by one wrong answer would hit left = 1 and close IDF too early. Fix if so: count wrong answers in the verify post hook (`vars`) instead of trusting `left`.
2. **PUB-07**: "the week after next" must not be extracted as `new_plan` (more time). I tightened the extraction description, but this is model-dependent.
3. **PUB-08 / PUB-01**: the verbatim sentences ("Payments made today…", "We will email you a confirmation…") are said by the farewell. In the paid case the model also says the sentence when it is told, so the customer hears it twice. That is harmless, but a judge could object.
4. **PUB-11 / PUB-13**: one read-back for several products and "Shall I record that?". The prompt carries this, so it depends on the dialogue model. The promise pre hook enforces the dates either way (latest-date cap, then closure day moved back).
5. **PUB-12**: refused notes must state the attempt count and the last offer. The field description says so, but the ledger only checks the reason.

## Library / skill gaps found and the generic fixes (made in this run)

Every change is generic: no Brief D value is in a shared file. Checks after the changes: `python3 builder/multiproduct.py` 31/31; `compare_brief-a_lib` 0 fail; `compare_brief-a_v2` 5/5; `compare_brief-b_lib` 545 pass 0 fail (same as main).

1. **Closed day → business day BEFORE** (Brief A/B moved it after). `CAL_HELPERS` gains `prev_bd(d)`. `products_facts_code(..., closed_day_move="before")` makes the calendar offer the business day before a weekend or closure day, per product, and a product's own deadline when the day is past it. The default `"after"` leaves A/B output unchanged.
2. **Deadline in calendar days moved back to the previous business day**: `prev_bd(today + timedelta(days=N))` in SETUP extra. The helper is generic; the formula stays in the generator.
3. **Stricter wrong-answer limit than the service**: `verify_post(..., stop_left=("1","0"))`. The default `("0",)` emits byte-identical code, so the A/B proofs are unchanged.
4. **Closed-day safety net in the promise hook**: `promise_pre_code(snap_closed="before"|"after", holidays=..., business_weekdays=...)` moves a non-business date after the deadline cap.
5. **Lint false positives without test_variables**: `lint.py --call-vars a,b,c` (and `lint(wf, api, call_vars)`). The skill step 5 now passes the brief's call variables. Before this fix a correct no-test_variables workflow produced 45 WARNs.
6. **Up to three tries of create_promise**: already supported by `promise_post_code(max_fails=3)`. MULTIPRODUCT.md now says that `max_fails` = total tries.
7. **Closing precedence over note reasons**: already supported (`finalize_code(order="precedence", paid_reason=...)`).
8. **Notes with required text**: handled in the generator with `add_note` `text` kept (not omitted), made required, and described per reason.

Not yet fixed, proposed:

- **(a)** `close_call_tool(fallback=("not_reached", "<code>"))`, so the close never drops the reason when the close vars are unset. This needs an A/B-identical default.
- **(b)** `SETUP_CODE` should put CAL_HELPERS inside its try (clears the last lint WARN; changes the A/B setup text, so update the compare scripts too).
- **(c)** Name the `fin_*` close variables something other than `reason`, which collides with add_note's model-filled `reason`. Make `close_outcome`/`close_code` the library default in `end_pair` / `close_call_tool`, with an A/B compare update.
- **(d)** `audit.py` is non-deterministic between runs (it found a different set of partials each time). Consider running it twice and taking the union, or caching per rule.
- **(e)** The skill should say what to do when the network blocks Freya: build and test offline, notify, and never fake save/sim results. This run followed that path by hand.

## Files committed

`out/gen_brief-d.py`, `out/brief-d.workflow.json`, `out/brief-d.rules.{json,md,stdout,stderr}`, `out/brief-d.audit.{json,md,stdout,stderr}`, `out/brief-d.lint.txt`, `out/unit/brief-d_{dates,hooks}.{py,out}`, `out/brief-d.REPORT.md`. Generic edits: `builder/freyalib.py`, `builder/multiproduct.py`, `builder/lint.py`, `builder/FREYALIB.md`, `builder/MULTIPRODUCT.md`, `.claude/skills/build-phone-agent/SKILL.md`.
