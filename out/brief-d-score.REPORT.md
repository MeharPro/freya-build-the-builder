# Brief D: scoring run (stopped by the user before any simulation)

Run: 2026-10-10, branch `cloud/brief-d-score` (from origin/main 252cb79). Slot `brief-d`, workflow
`de5f944a-d43d-4a7e-80fc-405ee4c53649`, agent `49ba465f-6ca5-4240-b4a7-c81502d3a8d8`, published version 2.

**The user stopped the run before step 3.** No further OpenAI usage is allowed. **No `builder/sim.py` round ran and no
OpenAI call was made in this run**, so `out/sim/brief-d/` does not exist and there are **no per-case results**
(0 of the 13 practice cases and 0 of the 30 extended cases were run). No `tools/run_cases.py` or Freya simulation ran either.

## What ran

| Step | Result |
|---|---|
| Keys | FREYA_API_KEY, FREYA_API_URL, FREYA_BANK_TEAM_KEY, OPENAI_API_KEY all set; `freya.workspace_id()` answered |
| Generate + lint (`--call-vars ... --rules ... --budget`) | 0 errors, 8 WARNs (`out/brief-d.lint.txt`) |
| `validate_workflow` dry run | `{"valid": true}`, both versions |
| `save_workflow('brief-d')` | v1 created, then v2 (after the opening fix) published |
| Smoke on v1 (`out/smoke/brief-d/v1/`) | opening 31/32, third_party 39/40, wrong_number 28/29. The one failure in each: the first line was "Hello. Am I speaking with Daniel Reyes?", without "This is the digital assistant of Kestrel Bank…" (see fix 1). Apart from that, the behaviour was correct: no debt words before identity, phone-digits question first, the relative was told only "a personal banking matter… when can she be reached", `schedule_callback` was called with 2026-10-15 11:00 (the rejection is the expected `c_smoke` unknown id), and the wrong number closed WN. |
| Smoke on v2 (`out/smoke/brief-d/*.txt`) | **not readable**: the platform answered 503 or 504 on every first turn (5 tries over about 15 minutes). The last run was killed when the user stopped the session. The agent config on the platform is intact (`llmConfig` present), so this looks like gateway load, not the workflow. Not verified. |

## Changes made (commit 1ee0e49)

1. **`fl.opening_conv` (new, in `builder/freyalib.py`, brief-agnostic, additive).** On the chat route the engine answers the
   customer's first line with the dialogue model, not the opening node's tts (seen on Brief C, confirmed here by the v1 smoke).
   So the helper repeats the opening line in the task ("If you have not spoken yet… your message is exactly …"). Existing
   signatures are unchanged. Checks: `builder/tests/*.py` pass; `multiproduct.py` 31/31; `compare_brief-a_lib` 193 pass, 0 fail;
   `compare_brief-b_lib` 545 pass, 0 fail; `compare_brief-a_v2` 5/5 with the same "2 unexpected" paths as on main
   (already there before this run).
2. **Hardship line as fixed text** (fixes the lint verbatim WARN R38). The `hardship` node's on_enter tts says "I am sorry to hear that." plus
   the single customer care offer. The extraction gains `offer` (the customer names a date or an amount, and this wins over decline). A
   named promise is therefore still recorded, not closed HSHP (ext-a-v2 bug EXT-A-28).
3. **Wrap-up turn after a recorded promise** (ext-a-v2 bugs EXT-A-31/35; tested by EXT-D-20). `finalize`'s promise route goes to
   `wrapup`. Its tts is "We will email you a confirmation of this arrangement. Is there anything else I can help you with?" The routes:
   - plan or lower instalments → `xfer_restructuring` (TRS)
   - a person → new `xfer_general` (TRH)
   - nothing else → `fin_promise` (whose farewell no longer repeats the email sentence)
   - anything else → answered (a change gets "it cannot be changed in this call"), with at most 2 such turns.
4. The read-back `topic` description now says that changing the date or the amount at the read-back is not `new_plan` (ext-a-v2 bug EXT-A-34).

The ext-a-v2 attempt-ladder bug (floor once "too much" was said) is covered in the per-product attempt line ("the amount in play").
That fix is in the prompt, not in code, and has not been tested.

## Lint WARNs left (8)

- The verbatim lines "I am Kestrel Bank's digital assistant.", "Shall I record that?" (R43/R60) and "I don't have that information." are mid-conversation replies
  with no node of their own. They are left in the prompts.
- `transfer_to_agent` before identity: deliberate. The brief says to give a person "straight away".
- The `setup` CAL_HELPERS sit outside try/except: known library behaviour.
- The `negotiate` prompt is 5.3k characters: not reduced.

## Not done

- Step 3: sim round 1 (13 cases) and ext1 (30 cases). Stopped by the user (no OpenAI). These need `--close-from-args`, because the kit
  mock rejects Brief D's close codes (PRM, HSHP, …), as it did Brief C's.
- Step 4: no transcripts, so no failure classification and no rounds 2–3.
- Step 5: `builder/audit.py` was not re-run on the changed workflow.
- Smoke on v2 (platform 503/504).
