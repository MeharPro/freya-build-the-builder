# cases-gen: generated rule-branch cases, compared with the hand-written sets

Branch `cloud/cases-gen`, 10 Oct 2026. No simulations were run (no Freya or OpenAI calls). Every number below comes
from Claude calls through the Agent SDK, from the deterministic checker, and from hand derivation.

## Bottom line

- **Expected ledgers agree on every case: 92/92.**
  - Method: the case writer was given only the hand-written cases' scenarios (`--scenarios`: mock customer, `now`,
    title, script). It never saw their expected ledgers or checks. It computed its own ledgers, which were then
    compared field by field (`--compare`: outcome, reason, promises, notes, callbacks, transfers).
  - Brief A: **52 / 52** (10 organisers' practice cases + 42 EXT-A).
  - Brief C: **40 / 40** (10 synthetic practice cases + 30 EXT-C).
  - No disagreements, so nothing needed diagnosing as generator-wrong, hand-written-wrong or ambiguous. Two
    expectations that are hard to pin down were flagged on their own, as low/medium confidence (below).
- **Fresh cases are correct on every case: 60/60 hand-checked.** These are the cases `cases.py` invents itself, the
  ones the build will use.
  - Sets checked: Brief A (twice: the first prompt version and the final one) and Brief C (with the inventory, and
    without it as in `build.py`).
  - I re-derived every expected ledger from the brief: band, deadline ladder, floor, attempt dates, callback window,
    outcome row and precedence. I found no wrong expectation.
  - Where a generated case uses the same customer and branch as a hand-written case, the ledgers are identical
    (table below). Where the scenario differs, the shared derived facts match the hand-written ones (deadlines,
    floors, holiday shifts).
- Cost and time per brief: 2 parallel calls + 1 repair/gap call, **127-152 s, $0.65-1.04**. All 80 generated cases
  passed the deterministic checker (0 dropped). One Brief A case was rejected by the checker and fixed in the repair
  call.
- The comparison is an upper bound, and the replay is the weaker test of the two. The hand-written scripts are
  explicit, so computing a ledger for a given script is easier than inventing a scenario and its ledger. The hand
  check of the fresh cases covers the harder task.

## 1. Replay against the hand-verified sets

```
python3 builder/cases.py --brief briefs/brief-a.md --api tools/openapi.json --rules out/brief-a.rules.json \
    --scenarios out/cases-eval/brief-a.reference.cases.json --out out/cases-eval/brief-a.replay.cases.json
python3 builder/cases.py --compare out/cases-eval/brief-a.replay.cases.json out/cases-eval/brief-a.reference.cases.json
```

| Set | Cases | Calls | Time | Cost | Agreement | Confidence the writer gave |
|---|---|---|---|---|---|---|
| Brief A (`public-test-set.json` brief A + `tests/cases/brief-a-extended.cases.json`) | 52 | 5 (batches of 12, 4 in flight) | 97 s | $1.40 | **52/52** | 46 high, 5 medium, 1 low |
| Brief C (`tests/synthetic/brief-c.cases.json` + `tests/cases/brief-c-extended.cases.json`) | 40 | 4 | 85 s | $1.28 | **40/40** | 40 high |

The ledgers matched in every case. Where the writer gave less than high confidence, its reasons point at real
fragility in the hand-written cases. These are notes for whoever maintains those files; none of them is a
disagreement.

| Case | Writer's doubt | Diagnosis |
|---|---|---|
| EXT-A-01 (low) | The script's "Yeah, go ahead": "yeah" can be heard as a yes, which counts as confirmation under rule 3. | **Genuinely ambiguous wording in the hand-written script.** The expected `unclear` is right only if "Yeah, go ahead" is not taken as a yes. Suggest "Go ahead." without the "Yeah". |
| PUB-02 (medium, organisers' case) | "Around eleven" has to become exactly `11:00`. | Persona/agent risk, not a ledger question. |
| PUB-04 (medium, organisers' case) | The script does not say which amount she accepts. The full amount follows only because the agent proposes it first. | Correct by rule 24. |
| EXT-A-28 (medium) | Under rule 32's last sentence, a promise she names herself overrides the hardship close. | Correct, as the hand-written case says. |
| EXT-A-41, EXT-A-42 (medium) | "Can't pay today" followed by a date or a vague period could be taken as a flat refusal (rule 30) before the date is handled. | Correct by rule 29 ("a date ... is never a refusal"). This is a real trap for agents, and it is worth keeping. |

## 2. Fresh cases: `out/brief-a.cases.json`, `out/brief-c.cases.json`

```
python3 builder/cases.py --brief briefs/brief-a.md --api tools/openapi.json --rules out/brief-a.rules.json --out out/brief-a.cases.json
python3 builder/rules.py tests/synthetic/brief-c.md --api tools/openapi.json --out out/brief-c.rules.json   # 68 rules, 96 s, $0.35
python3 builder/cases.py --brief tests/synthetic/brief-c.md --api tools/openapi.json --rules out/brief-c.rules.json --out out/brief-c.cases.json
```

| Run | Time | Cost | Cases | Confidence | Outcome rows covered | Checker |
|---|---|---|---|---|---|---|
| Brief A (final) | 127 s | $0.65 | 20 | 18 high / 2 medium | 15/16 | 0 dropped; 1 rejected then repaired; 5 valid cases trimmed by the cap of 20 |
| Brief A (first prompt version, not kept) | 160 s | $0.96 | 20 | 16 / 4 | 12/16 | 0 dropped. This run led to the "one case per non-promise row" rule and the gap-fill call. |
| Brief C (with the inventory) | 141 s | $1.04 | 20 | 17 / 3 | 16/17 | 0 dropped |
| Brief C without the inventory (the `build.py` path), then `--map-rules` | 126 s | $0.77 | 20 | 19 / 1 | 16/17 | 0 dropped; 69 brief references mapped to inventory ids (results/, not committed) |

The uncovered rows cannot be reached with the mock bank. Brief A `no_promise/service_error` needs two
`create_promise` failures, and Brief C `no_promise/system_fault` needs three, but PUB-10 fails only once. The case
writer said so itself in GEN-C-14 (C) and GEN-C-15 (A, first run).

Branches covered (final Brief A set):
- the opening (a question uses the first ask, then unclear);
- third party: callback at the 19:00 window edge, two slots outside the window, wrong number, death;
- identity: three wrong answers across both questions, a deflection twice, a swapped day and month (not counted)
  followed by "already paid";
- dispute: "closed and paid off" is a dispute, not paid;
- restructuring;
- a human requested before verification;
- hardship accepted, and hardship declined;
- dates: "this Saturday" moved to Monday, then a transfer after the promise; a Friday call with "next Monday" on the
  26 October holiday; a date after the deadline with the deadline refused, then attempt 2 accepted;
- amounts: a vague period with the deadline proposed, and an amount below the floor;
- persuasion: a Friday call where attempt 1 moves to next week; floor refused, then the single attempt refused;
- a read-back change onto a holiday;
- two callback slots outside the window (gap-fill case).

Brief C adds:
- business Saturdays and the Friday 16 October holiday;
- the 40%-rounded-up floor;
- an amount above what is owed, recorded as the full amount;
- "next Friday" defined as the first one after today;
- hardship taking precedence over a plan request;
- a read-back change to a Sunday;
- the amber band's single attempt.

### Generated cases that match a hand-written scenario (same customer, same branch)

| Generated | Hand-written | Generated ledger | Hand-written ledger | Verdict |
|---|---|---|---|---|
| A GEN-C-01 (PUB-01, question then "Hello?") | EXT-A-01 | not_reached/unclear | not_reached/unclear | same |
| A GEN-C-10 (PUB-09, lower instalments) | PUB-09 | transferred/restructuring, [restructuring] | same | same |
| A GEN-C-11 (PUB-01, human, insists) | EXT-A-30 | transferred/human, [general] | same | same (generated: before verification; hand-written: after) |
| A GEN-P-07 (PUB-07, holiday 26 Oct → 27 Oct) | PUB-07 | promise 540 on 2026-10-27 | promise 540 on 2026-10-27 | same |
| C GEN-C-05 (PUB-09, death) | EXT-C-04 | not_reached/estate | same | same |
| C GEN-C-07 (PUB-07, wrong phone + swapped date + already paid) | EXT-C-05 | paid/self_reported | same | same |
| C GEN-C-12 (PUB-02, hardship → care team) | EXT-C-17 | transferred/care_team, [support] | same | same |
| C GEN-P-01 (PUB-02, Saturday 17 Oct) | EXT-C-09 | promise/full 310.5 on 2026-10-17 | promise/full 310.5 on 2026-10-17 | same |

### Generated cases on the same customer with a different script (ledgers differ by design; shared facts compared)

| Generated | Closest hand-written | Shared fact | Agrees |
|---|---|---|---|
| A GEN-C-02 callback 2026-10-14 19:00 (PUB-02) | PUB-02 callback 2026-10-15 11:00 | Callback window today/next business day, 10:00-19:00 inclusive | yes |
| A GEN-P-02 400 on 2026-10-27, now 23 Oct (PUB-04) | EXT-A-41 1250 on 2026-11-04, now 23 Oct | Late deadline from 23 Oct = 2026-11-04 (across the 26 Oct holiday) | yes |
| A GEN-P-03 260 on 2026-10-23 (PUB-05) | EXT-A-21 780 on 2026-10-23 | Late deadline 2026-10-23; floor = instalment 260 | yes |
| A GEN-P-04 103.5 on 2026-10-23 (PUB-02) | EXT-A-23 310.5 on 2026-10-23 | Late deadline 2026-10-23; floor 103.5 | yes |
| A GEN-P-01 420 on 2026-10-19 (PUB-01) | EXT-A-20 420 on 2026-10-23 | Early deadline 2026-11-02 | yes |
| C GEN-C-02 callback 2026-10-17 10:00 (PUB-02) | PUB-02 callback 2026-10-15 11:00 | Window = today + 2 business days (15 Oct, 17 Oct; 16 Oct is a holiday), 09:00-18:00 | yes |
| C GEN-P-04 851 on 2026-10-14 (PUB-06) | PUB-06 851 on 2026-10-17 | Card floor ceil(0.4 × 2125.10) = 851 | yes |
| C GEN-P-06 146 on 2026-10-17 (PUB-10, fault) | EXT-C-25 200 on 2026-10-19 | Green band, deadline 2026-10-26, Saturday 17 Oct is a business day | yes |
| C GEN-P-02 declined_offer (PUB-05) | EXT-C-22 declined_offer | Amber band: 1 attempt, deadline 2026-10-20 | yes |

The other generated cases have no hand-written counterpart on the same customer. For example:
- A GEN-P-05: a Friday 16 Oct call where attempt 1 is 2026-10-23;
- A GEN-P-06: a Friday call, late band, both attempts refused;
- the first-version Brief A GEN-P-07: now 2026-12-18, where attempt 1 is Thursday 24 Dec because 25 Dec is a holiday;
- C GEN-P-05: now Monday 19 Oct, where "next Friday" is 23 Oct, which is also the amber deadline, and 1300 is
  recorded as 1250;
- the C no-inventory GEN-C-02: now Thursday 15 Oct, where the window is Saturday 17 and Monday 19 Oct.

I re-derived each of these by hand from the brief, and all are correct. In the comparison sense these are new
branches that the hand-written sets do not test.

### Things the checker caught or that needed design changes

- In the first Brief A run, 4 non-promise outcome rows had no case. Since then the control writer must cover every
  non-promise row, and the repair call writes a case for any row still uncovered. In the final run, only the
  unreachable `service_error` row is still uncovered.
- The cap of 20 originally favoured the control writer, which wrote 15 cases, so 3 promise-branch cases were cut. The
  trim now goes round-robin between the writers, after first keeping the only case of each outcome row.
- In the final Brief A run, the checker rejected one case and the repair call fixed it. The log line is
  `repair 1 rejected case(s), add 2 uncovered outcome row(s)`. The rejected case was evidently GEN-C-03 (the
  `no_callback` callback case): its row was uncovered at that moment, and the repaired version appears among the
  trimmed cases. That run predates the `meta.rejected_then_repaired` field, which now records the findings.

## 3. What changed in the build

- `builder/build.py`:
  - `rules.py` and `cases.py` run in two threads (`cases.py` without the inventory, as an independent reader); then
    `--map-rules` and `--check` run.
  - When the brief has no practice cases, the generated file is the practice set, and the runner is forced to
    `sim.py`.
  - The builder prompt says the cases are generated (rules for using them; do not read the rationale), and states
    the minutes left and the clock time to stop by.
  - New flags: `--no-gen-cases` and `--gen-cases`.
  - The trace lock is now thread-safe.
- `.claude/skills/build-phone-agent/SKILL.md` step 9 adds the repair round for generated cases (T12):
  - save first;
  - run `sim.py` at concurrency 2;
  - read every failed transcript and map it to a rule id;
  - fix only deterministic agent errors visible in the events and tool calls;
  - never fix on a low/medium-confidence expectation or when the simulator went off script;
  - at most 2 rounds, each with at least 6 minutes left;
  - report unfixed failures in the final line.
- `build.py` was syntax-checked but not run end to end here, because it needs the Freya keys. The `cases.py` paths it
  calls (no inventory, `--map-rules`, `--check`) were each run.

## Files

- `builder/cases.py`, `builder/CASES.md`
- `out/brief-a.cases.json` (+ `.rationale.md`, `.meta.json`), `out/brief-c.cases.json` (+ same), `out/brief-c.rules.json` (+ `.md`)
- `out/cases-eval/`: the reference sets used for the replay, the replayed files with their rationale, and the meta files
