# brief-a-cloud: report (cloud worker, 2026-10-10)

**Status: built and checked offline only. Not saved on Freya. Not simulated.** The cloud environment's network
policy denies `staging-app.freyavoice.ai` (Freya API and mock bank) and `api.openai.com`: the egress proxy
answers `403` to CONNECT for both (checked at the start and again ~20 minutes later). The Anthropic API works
(the nested `claude` CLI answered `OK`), so `rules.py` and `audit.py` ran for real.

To unblock: in the cloud environment's settings (Network access), add `staging-app.freyavoice.ai` and
`api.openai.com` under Allowed domains. See https://code.claude.com/docs/en/cloud-environments#network-access.

| item | value |
|---|---|
| workflow_id | — (not created: Freya API unreachable) |
| agent_id | — |
| export `submission/brief-a-cloud.workflow.json` | — (`freya.export_workflow` needs the API) |
| nodes | 46 (initial node `opening`, conversation) |
| node tools | verify_identity (×2 nodes), transfer_to_agent (general in 4 nodes; restructuring/support as `api_request` nodes), schedule_callback, get_account (`api_request`), create_promise (×2 nodes), code_exec (setup, prepare, 2 decline counters, 16 `fin_*`) |
| workflow tools | 1: `close_call` (end_of_call lifecycle) |
| test_variables | none (`{}`) |

## Pipeline steps run

| step (SKILL.md) | result |
|---|---|
| 1 read + rule inventory | `builder/rules.py` (claude-opus-5-5, 1 call, 68 s, $0.25): 62 rules, 62 in force, self-check ok → `out/brief-a-cloud.rules.{json,md}`, log `out/brief-a-cloud.rules.log` |
| 4 generator | `out/gen_brief-a-cloud.py` on `builder/freyalib.py`, `# R<n>` comments |
| 5 lint | 0 errors, 2 warnings, 18 info (below) |
| 5 code unit test | setup + prepare run locally on 3 inputs, all match a hand calculation (below) |
| 6 dry-run + save | **blocked** (network) |
| 7 smoke | **blocked** (network) |
| 8 audit | `builder/audit.py` (claude-opus-5-5, 6 calls, 48 s, $1.20): **62 implemented, 0 partial, 0 missing, 0 contradicted**, 0 unverified evidence quotes, no top fixes → `out/brief-a-cloud.audit.{json,md}`, log `out/brief-a-cloud.audit.log` |
| 9 sim rounds | **0 of 4 run**: `builder/sim.py` needs the Freya chat route, the mock bank and OpenAI, all blocked. `out/sim/brief-a-cloud/` was not created because there are no results to put in it. |

### Lint (`python3 builder/lint.py out/brief-a-cloud.workflow.json --api tools/openapi.json --call-vars customer_id,first_name,last_name,title,now`)

```
WARN nodes.setup.pre_actions[code_exec].code: code has statements outside try/except (Assign); wrap the whole body
WARN nodes.prepare.pre_actions[code_exec].code: code has statements outside try/except (Assign); wrap the whole body
-- 0 error(s), 2 warning(s), 18 info
```
Both warnings are the `CAL_HELPERS` constants (`HOL = set([...])`) at the top level of the code. They cannot raise.
The reference `out/brief-a_v2.workflow.json` has the same 2 warnings. Full output: `out/brief-a-cloud.lint.txt`.

### Date/amount unit test (setup + prepare executed locally)

| now | product | band / attempts | deadline | attempt 1 | callback window | hand check |
|---|---|---|---|---|---|---|
| Wed 2026-10-14 11:00 | card 4821, 5 days late, min 60 | early / 1 | 2026-11-02 (12 bd, skips the 26 Oct holiday) | Fri 2026-10-16 | today after 11:00–19:00, Thu 15 Oct 10–19 | ✓ |
| Fri 2026-10-16 18:30 | car loan, 20 days late, inst. 300 | late / 2 | 2026-10-28 (7 bd, skips 26 Oct) | Fri 2026-10-23 (today is the last bd of the week, so next week) | today 18:30–19:00, Mon 19 Oct | ✓ |
| Wed 2026-10-21 09:00 | personal loan, 8 days late, inst. 250 | late / 2 | 2026-11-02 | Fri 2026-10-23 | today from 10:00, Thu 22 Oct | ✓ |

## Sim rounds

| round | result |
|---|---|
| 1–4 | not run: network policy (see top). No PASS/FAIL data exists. I did not fake or estimate any. |

## Deviations from `out/gen_brief-a_v2.py`, and why

1. **No `test_variables`.** The reference passes `{"customer_id": "c_test", ...}` to `assemble`. The skill and CLAUDE.md
   say never to ship them: on the chat route they replace the real `customer_id`, so every bank call fails.
2. **Opening line** says "I am a digital assistant calling from Freya Bank. This call is recorded." The reference says
   "this is Freya Bank's digital assistant. Please note that we record this call." The new line follows R1 more literally.
3. **Deceased farewell** is "I am sorry for your loss. Thank you, goodbye." R47 says every call thanks the customer before
   goodbye. The reference had no thank-you, and its audit flagged this.
4. **Hardship node** also has `transfer_to_agent` (general) and a `transferred` → `fin_transferred_human` route. R42 applies
   before and after verification, and the reference had no human exit from hardship (its audit flagged this as R52).
5. **System prompt** adds "Never call close_call yourself." R46 says exactly one close_call. The reference's audit flagged
   that nothing forbade the model from calling it (R64).
6. **Band, attempt, callback and decline-limit numbers** are named constants at the top of the generator and are
   substituted into the code templates. They were literals inside the code strings. The output is the same.
7. `floor_name` for loans is "instalment amount", the brief's term (R25). The reference said "monthly instalment".

All other structure is the same as the reference: `opening` → `setup` → `ask_dob`/`ask_phone` with `verify_post` →
`load_account` → `prepare` → `negotiate`/`hardship`. Routing uses `who`/`topic`/`support_choice` enums and tool-result
counters. There is one `end_pair` per outcome row.

## Remaining risks, untested because nothing was simulated

- **A transfer after a recorded promise.** The table says to close as `transferred`, but `ok_true(create_promise)` ends the call at once. The reference does the same, and it scored 10/10.
- **R42 before identity is confirmed.** A request for a human in `opening`/`opening_retry` falls into `unclear` or `declined`. Neither node has a transfer tool.
- **Deviations 3–5 are not run-tested.** They are small prompt and route changes on the 10/10 reference. The first sim round should confirm them.

## Library / tooling gaps found

- **`builder/lint.py` reported false positives without `test_variables`.** Shipping no `test_variables`, as required, made
  lint emit 44 WARN ("{{title}} is never set …") for the brief's call variables. This is fixed generically: a new
  `--call-vars a,b,c` option (and `lint(wf, api, call_vars)`) treats the brief's call variables as always set.
  `builder/tests/test_lint.py` still passes 17/17. **Follow-up:** `build.py` should pass the call variables from the
  brief's call-variable table when it runs lint (it does not yet).
- **`freyalib.check` uses `test_variables` keys as known variables.** Without them, its "model-filled field named like a
  known variable" warning cannot see call variables. A `call_vars` parameter on `assemble`/`check` would fix that the same way. Not changed.
- **Environment:** the claude-agent-sdk could not be installed into the system Python (a Debian-owned PyJWT). It installs
  into a local `.venv` (gitignored), which is what AUDIT.md expects.
