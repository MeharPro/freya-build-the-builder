# Rehearsal: the hidden-brief path (generated cases), 10 Oct 2026

**What ran:** `python3 builder/build.py briefs/rehearsal-a.md tools/openapi.json`. `rehearsal-a.md` is a byte-for-byte copy of
Brief A under a name that `detect_cases` does not recognise, so the run had no practice cases: `cases=None`, and
`builder/cases.py` wrote the practice set. Environment:
- `OPENAI_API_KEY` was empty, so `sim.py` used the Claude CLI: customer `claude-haiku-5-5`, judge `claude-sonnet-5-5`.
- The Freya keys were set, and the workspace was `1af69fb8-…`.
- The branch is `cloud/rehearsal-hidden`, cut from origin/main `f0150be`.

**Environment fixes before the run, none to the code:**
- The local `main` was 60 commits stale and had no `builder/cases.py`. I reset the branch to `origin/main`.
- `claude_agent_sdk` was missing. A system `pip install` failed on Debian's PyJWT, so I created `.venv` and installed
  `requirements.txt` there.
- No restart was needed.

## 1. Timing (wall clock, from `traces/rehearsal-a.log`)

| Phase | From → to (s) | Duration | Notes |
|---|---|---|---|
| rules (`rules.py`) | 0 → 87 | **87 s** | 9 model calls, $1.58: 60 rules (60 in force, 1 low confidence) + spec + conflicts |
| cases (`cases.py`), in parallel | 0 → 113 | **113 s** | 3 model calls, $0.74: 20 cases |
| cases-map + cases-check | 113 → 113 | <1 s | 76 brief references mapped; 20/20 pass the checker |
| build agent: read + "design" | 114 → 129 | 15 s | **Diffed the brief against `briefs/brief-a.md`, found it IDENTICAL, copied `out/gen_brief-a_v3.py` with `sed`** (see F1) |
| generate + lint (`--rules --budget`) | 129 → 134 | 5 s | 0 errors; warnings judged to follow the brief |
| dry run + save | 135 → 138 | 3 s | workflow `f523ddf6-…`, agent `753337bb-…` |
| smoke (3 scripts, sequential) | 141 → 271 | 130 s | opening 32/32, third_party 40/40, wrong_number 29/29 |
| generated cases, run 1 | 272 → 465 | **193 s wasted** | 0/20: `sim.py` could not find `/root/.local/bin/claude`, so no customer and no judge (F2) |
| diagnosis | 465 → 473 | 8 s | the agent found `/opt/node22/bin/claude` and set `CLAUDE_CLI` |
| generated cases, run 2 | 473 → 1259 | **786 s** | the agent's own `timeout 780` killed `sim.py`: no summary and no `--out`; 19/20 transcripts written, GEN-P-08 never ran (F3) |
| result recovery + final line | 1259 → 1271 | 12 s | grep of `# RESULT` lines: 14/19 |
| **repair round** | not run | 0 | 4.9 min left of the agent's budget (deadline 20:43:42); the skill requires ≥6 min |
| **audit (by the agent, skill step 8)** | not run | 0 | the agent skipped it |
| final lint (`build.py`) | 1271 → 1272 | 1 s | 0 errors, 45 warnings, 14 info. Run **without** `--rules` and `--call-vars`, so most warnings are false call-variable warnings |
| final audit (`build.py`) | 1272 → 1273 | 2 s | **crashed**: `CLIConnectionError … [Errno 7] Argument list too long` (F4) |
| export | 1273 → 1275 | 2 s | `submission/rehearsal-a.workflow.json` |
| **total** | | **1275 s = 21 min 15 s** | under 30 min; 465 s of the 29-min budget unused |

The 29-minute budget cut off nothing: `build.py` never reached its `wait_for` timeout. The agent's own `timeout 780` on
the sim run and the 6-minute rule for a repair round are what removed the repair round.

**Cost:** rules $1.58 + cases $0.74 + build agent $0.52 (13 turns) + audit $0 (crashed before any call) = **$2.84**,
plus the sim's Claude CLI calls, which the trace does not count: run 1 made 40 calls that all failed; run 2 made about
19 judge calls and about 100 customer calls. Model calls in the trace: 36 lines (9 rules, 3 cases, 1 agent session
with its tool calls, 5 audit batches).

## 2. Generated cases (`out/rehearsal-a.cases.json`)

20 cases: 12 control (`GEN-C-*`), 8 promise (`GEN-P-*`); confidence **19 high, 1 medium, 0 low**; 0 dropped, 0
repaired. 4 were trimmed for the 20-case cap: robot→restructuring, refuses-to-talk twice, a promise failure retry
(duplicate), and job loss with a floor offer. Holidays as the case writer read them: 26 Oct, 11 Nov, 26 Nov, 25 Dec,
1 Jan.

### The agent's own run (run 2, one rep) and my classification

| Case | Mock | Conf. | What it tests | Result | Reason | Class |
|---|---|---|---|---|---|---|
| GEN-C-01 | PUB-01 | high | "who is this", then "go ahead" → unclear | FAIL | judge: the recording notice is in the 2nd sentence, not the 1st | **agent bug, strict reading of rule 1** (the opening is two sentences: "…digital assistant. Please note that we record this call."). The kit judge passed the same opening. Cheap fix: one sentence. |
| GEN-C-02 | PUB-02 | high | relative on Friday evening: Monday holiday, Tuesday 10:00 | PASS | | |
| GEN-C-03 | PUB-05 | high | wife, two slots outside the window | FAIL | asked "another time?" twice | **agent bug, rule 7** ("ask once for another time"): the third-party node holds this in the prompt, with no counter in code |
| GEN-C-04 | PUB-03 | high | wrong number | PASS | | |
| GEN-C-05 | PUB-09 | high | son reports a death | PASS | | |
| GEN-C-06 | PUB-04 | high | three wrong answers | PASS | | |
| GEN-C-07 | PUB-06 | high | two deflections → declined | PASS | | |
| GEN-C-08 | PUB-02 | high | dmy swap, then "already paid" | PASS | | |
| GEN-C-09 | PUB-06 | high | scam question, then dispute | FAIL | not_verified/failed | **simulator artefact**: Haiku said 18 May three times; the identity is 17 May 1986. The scam answer was right. |
| GEN-C-11 | PUB-03 | high | insists on a human before verification | FAIL | not_verified/declined, no transfer | **agent bug, rule 42**: at `ask_dob` "I want a human" goes to the refusal enum (`refused`) → second refusal → declined. The identity nodes have no `human` value and no ask-once-then-transfer path, although the lint WARN noted `transfer_to_agent` is on those nodes |
| GEN-C-12 | PUB-07 | high | job loss, support accepted | PASS | | |
| GEN-C-13 | PUB-08 | high | illness, support declined | PASS | | |
| GEN-P-01 | PUB-01 | high | "this Saturday" → next business day, then restructuring | PASS | | |
| GEN-P-02 | PUB-04 | high | too much → floor, holiday in the window | PASS | | |
| GEN-P-03 | PUB-06 | high | read-back change to a Saturday after the deadline | PASS | | |
| GEN-P-04 | PUB-07 | **medium** | "when my salary comes", still no exact day → propose the deadline | FAIL | proposed Fri 16 Oct (ladder rung 1); "I don't know the exact day" counted as a refusal → refused | **agent bug, rule 21**: after the one exact-day question a non-answer must give the deadline. The `stance` enum makes it `refuse`, and `policy.py` keeps no "vague asked once" state. The brief settles this, so it is a deterministic route error, even though the case is medium. |
| GEN-P-05 | PUB-08 | high | below the floor + "next Friday" | PASS | | |
| GEN-P-06 | PUB-05 | high | late band, refuses everything | PASS | | |
| GEN-P-07 | PUB-03 | high | Friday call, ladder with a holiday | PASS | | |
| GEN-P-08 | PUB-10 | high | create_promise fails once | **not run** | killed by the timeout (the run-1 result is a no-customer artefact) | harness |

**Result: 14/19 passed.** Of the 5 failures, 4 are agent bugs that the brief settles (rules 1, 7, 21, 42) and 1 is a
simulator artefact. None was repaired, because there was no time (F3).

## 3. Kit practice cases, scored by me (`out/sim/rehearsal-hidden/pub.json`, Brief A, 1 rep, concurrency 2, 401 s)

| Case | Result | Reason | Class |
|---|---|---|---|
| PUB-01 | PASS | | |
| PUB-02 | FAIL (judge only; the ledger passed) | callback 15 Oct 11:00 "should be Monday 12th" | **simulator + judge artefact**. The call's `now` is Wed 14 Oct, so "tomorrow" = Thu 15 Oct and the agent was right. The customer persona is never told the call date: Haiku used the real clock ("Sunday the 11th"), and the judge believed the customer. |
| PUB-03 | FAIL | dispute instead of three wrong answers | **simulator artefact**: Haiku gave the true date of birth (from the persona's identity line) instead of the three scripted wrong ones |
| PUB-04 | FAIL | declined at the phone question | **simulator artefact**: Haiku role-swapped ("could you please answer the security question?", "please give me the last four digits") |
| PUB-05 | FAIL (judge only) | support offered twice | **agent bug, minor (rule 32, "offer" once)**: the customer answered the offer with a discount question; the hardship prompt answered it and repeated the offer. An offered-once flag in code, with the side question answered without re-offering, would pass. Borderline judge strictness. |
| PUB-06 | FAIL (ledger) | recorded 2125.10, expected the 637.50 floor | **agent bug, rule 27 / the amount classes**: the customer said "the minimum payment this Friday"; `offer_amount` took no number, the guard defaulted to the full amount, and the read-back and the write used 2125.10. The library default (`policy.py`) has no amount word `minimum`/`floor` (or `full`) that code turns into the product's floor. Brief-agnostic and high value: every hidden brief has a floor. |
| PUB-07 | FAIL | declined at the date-of-birth question | **simulator artefact**: Haiku refused the date of birth twice although the script says "Verified" |
| PUB-08 | PASS | | |
| PUB-09 | PASS | | |
| PUB-10 | PASS | | |

**Result: 4/10 raw.** Without the 4 simulator artefacts, **4/6**. The same generator scored 7/10 pass^3 on the
organisers' simulator (commit 84c166c), so the local Haiku customer is the larger source of noise here.

## 4. Export and trace checks

- `submission/rehearsal-a.workflow.json` exists and loads as JSON (`workflow_id`, `agent_id`, `updated_at`,
  `workflow`). It has 69 nodes and 6 tools; the initial node is `opening` (a conversation node); `test_variables` is
  `{}` (empty); there is no `agent_config`. The nulls in the file are platform-filled fields
  (`max_turn_transition`, `passthrough_default_transition`). The file is **1.0 MB**: each of about 20 policy nodes
  carries the same 41 KB `pre_actions` code.
- Trace items:
  - Present: start and end times; every model call with model and purpose (rules ×9, cases ×3, the agent session with
    each tool call, audit ×5); created on Freya (workflow id, agent id, version, steps, tools); smoke results; the
    run-1 sim results.
  - **Missing from `.log`:** the per-case results of run 2. They are only in `.jsonl`: `sim.py` was killed before it
    printed, and `build.py`'s result filter does not match the `# RESULT:` lines the agent grepped.
  - **Missing:** the sim's own customer and judge model calls; there is only a count line, and only for run 1.
  - **Misleading:** "audit: exit 1" with a stack trace and no coverage numbers.
- Keys: no `fak_`/`sk-` pattern and no literal key value in the traces, the export, the out files or the transcripts.
  `tools/check_secrets.sh` is clean.

## 5. Pipeline findings, ranked by expected cost on a hidden brief

1. **F4. The audit cannot run on a policy-architecture workflow on Linux (high: no coverage evidence at all).**
   `audit.py` puts the generator plus the workflow digest into the system prompt, and the SDK passes the system prompt
   to the CLI on the command line. Here the digest is 872 KB (the duplicated 41 KB policy code in about 20 nodes),
   and Linux limits a single argument to 128 KB (`MAX_ARG_STRLEN`), so the call fails with E2BIG before any model
   call. It would also be about 220k tokens even if it got through. Every v3-style build hits this, and the organisers
   rebuild on their own machine. Fix: dedupe identical code blocks in `workflow_digest` (print once, then "same code
   as node X"), cap the digest, and pass large text in the prompt over stdin, not in `system_prompt`. The agent also
   **skipped audit step 8** on its own, so even a working audit would only have run as the final evidence step.
2. **F3. The generated-case run uses the whole budget, so the repair round never happens (high: this is the one
   thing the hidden-brief path adds).** With the Claude CLI as customer, 19 cases at concurrency 2 took about 786 s
   (about 41 s of wall time per case). The agent wrapped the run in `timeout 780`, and the kill lost the summary, the
   `--out` file and GEN-P-08, because stdout is block-buffered to a pipe. The four real bugs it found (rules 7, 21,
   42, plus rule 1) stayed unfixed. Fixes:
   - `sim.py`: flush per line, write `--out` incrementally, and handle SIGTERM by writing what it has.
   - The skill: run the high-confidence promise and identity cases first (`--only`), or about 10 cases, so a repair
     round fits.
   - `build.py`: hand the agent a pre-run case set, or start the generated-case run itself right after the first save.
3. **F2. `sim.py` hardcodes `CLAUDE_CLI = ~/.local/bin/claude` (medium: 193 s plus a misleading 0/20 on any machine
   where the CLI is elsewhere).** Use `shutil.which("claude")` as the fallback. The agent recovered here; on Sunday a
   0/20 could have triggered a bogus repair.
4. **F5. Simulator noise from the Haiku customer (medium: it hides real results and tempts wrong repairs).**
   4 of 10 kit cases and 1 of 19 generated cases failed because the customer went off script: wrong or true dates of
   birth against the script, role swaps, a refusal although the script says "verified", the real clock for
   "tomorrow". Fixes: tell the customer persona the call date from `variables.now` ("Today is Wednesday
   14 October 2026"), and use `claude-sonnet-5-5` as the CLI customer for the identity-heavy cases. The judge should
   resolve relative dates from `now` and not from the customer's claim.
5. **F6. Brief-agnostic agent gaps the generated cases exposed (medium-high; they will recur on hidden briefs because
   they live in the library and the reference generator):**
   - **No amount word for "the minimum" → floor (`policy.py`)** (PUB-06): the guard falls back to the full amount and
     records the wrong amount. A ledger failure on every brief with a floor.
   - **A request for a human during identity is counted as a refusal** (GEN-C-11): add a `human` value to the refusal
     enum, with ask-once-then-transfer, wherever the brief allows a transfer before verification.
   - **A vague date with no answer to the exact-day question becomes a refusal** (GEN-P-04): add policy state
     `vague_asked`, and on a non-answer propose the deadline when the brief says so.
   - **"Ask once for another time" for the third party lives in the prompt** (GEN-C-03): move it to a counter in code,
     like the identity counters.
   - **The opening sentence carries the recording notice in a 2nd sentence** (GEN-C-01): `lint --rules` could check
     "first sentence contains X" when the brief says "first sentence".
   - Hardship re-offers support after a side question (PUB-05).
6. **F1. The rehearsal could not test generation: the agent diffed the brief against the kit's Brief A and copied
   the reference generator (low on Sunday, high for what this rehearsal measured).** Generating a generator from an
   unseen brief, in 15 s, is NOT what was measured. On Sunday the agent must write it from scratch, which will take
   many minutes (not measured here). The time left for testing will be correspondingly smaller, which
   makes F3 worse. For the record, the copy also means that this agent's rules are Brief A's, which is correct here
   only because the text is identical. Next rehearsal: use a synthetic brief (`tests/synthetic/brief-c.md` or
   `brief-e`) under an unknown name, or perturb Brief A (dates, limits, names) so a diff fails.
7. **F7. The final lint in `build.py` runs without `--rules` and `--call-vars` (low):** 45 warnings, mostly false
   call-variable warnings, so the trace's "evidence" lint is noise. Pass the same flags the skill uses.

## 6. Time wasted (seconds)

| Item | s |
|---|---|
| Generated-case run 1 without a customer or judge (F2), plus diagnosis | 201 |
| Generated-case run 2: summary, `--out` and GEN-P-08 lost to the kill (F3); the run itself was needed but was ~2× too long for the budget | ~786 (of which about 40 s for GEN-P-08 produced nothing) |
| Budget left unused after the agent stopped: no repair round (6-min rule) | 292 (agent), 465 (build) |
| Audit: crashed after 2 s (F4); the agent's own audit never ran | 0 spent, but the whole audit step was lost |

## 7. Verdict

**Not ready for Sunday yet.** The plumbing works end to end: rules and cases ran in parallel, the cases passed the
checker, the agent was saved early, smoke tests passed, and a valid agent was exported in 21 min. The
generated-case path also proved it is worth having: it found four real, brief-settled agent bugs that the kit's
cases do not exercise. But on a hidden brief, three things must change first:

1. **Make the audit run** (F4: dedupe and cap the digest, keep large text off argv). As it stands, a hidden-brief
   build has no rule-coverage check at all.
2. **Make the generated-case run fit beside generation** (F3, F2): `shutil.which` for the CLI, `sim.py` that flushes
   and writes partial results, a smaller first case set, and the case date in the customer persona (F5). Otherwise
   the repair round, the reason this path exists, never runs once the agent also has to write the generator.
3. **Fix the floor-word gap in `policy.py`** ("the minimum" → floor) and **add a `human` route during identity**
   (F6). Both are brief-agnostic library defaults that fail the ledger.

Then rerun this rehearsal on a brief the builder cannot diff against (F1).
