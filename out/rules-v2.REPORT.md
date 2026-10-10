# rules.py v2: report (cloud run, 10 Oct 2026)

Branch `cloud/rules-v2`. What changed: `builder/rules.py` now does T13 (3 samples in different document orders + USC merge),
T14 (dated-decision resolution), T15 (chain-of-verification), a deterministic stale-value pass, and compiles a structured
spec (T28). `builder/spec_check.py` holds the spec schema and validates it against the tool API file. The build prompt
(`builder/build.py`) and the skill now point Claude at `out/<slot>.rules.conflicts.md` (resolve first) and
`out/<slot>.spec.json` (pass values into the generator, don't retype them). `tests/compare_inventory.py` grades an
inventory against a reference list (evaluation only; the builder never runs it). Full documentation: `builder/AUDIT.md` §1.

All runs: `claude-opus-5-5` through the Claude Agent SDK; effort `low` for extraction, merge and verification, default for
T14. No Freya or OpenAI calls.

## Results

| | Brief A | Brief A + B | Brief D (raw material) |
|---|---|---|---|
| command | `rules.py briefs/brief-a.md` | `rules.py briefs/brief-a.md briefs/brief-b.md` | `rules.py tests/synthetic/brief-d.md` |
| sample sizes A / B / C | 58 / 56 / 59 | 75 / 73 / 73 | 101 / 101 / 100 |
| rules after merge (in force) | 60 (60) | 77 (70) | 117 (101) |
| confidence high / medium / low (all rules) | 55 / 3 / 2 | 69 / 6 / 2 | 85 / 15 / 17 (+2 low after checks) |
| low confidence, in force | 2 | 2 | 14 |
| T14 decision blocks | 1 | 7 | 12 |
| T15 values checked: ok / mismatch | 21 / 0 | 21 / 0 | 29 / 3 (all 3 in rules T14 had superseded) |
| stale values flagged | 0 | 0 | 1 (R43 `HARD`) |
| items in `conflicts.md` | 1 | 3 | 12 |
| `spec_check` errors / warnings | 0 / 0 | 0 / 0 | 0 / 0 |
| self-check (numbered rules, dates, tokens) | ok | ok | ok after 1 gap-fill (`wrong_answers_left`) |
| model calls | 9 | 9 | 11 |
| wall time | **78 s** | **102 s** | **171 s** |
| cost | **$0.96** | **$1.28** | **$2.41** |

Time per stage (D): 6 extraction calls in parallel 82 s ($1.30), merge 41 s ($0.42), gap-fill 6 s ($0.16), T14 + T15 in
parallel 42 s ($0.54). Brief A: extraction 38 s, merge 19 s, T14 + T15 21 s.

**Against the target (about 2 min, $1-2 per brief):** met on A and A+B. Brief D is over, at 171 s and $2.41. It is a
150-line raw-material pack with 100+ rules per sample, and output tokens set the wall time. Earlier configurations on D:

| D configuration | wall | cost | notes |
|---|---|---|---|
| 3 samples, 1 call each, default effort | 350 s | $3.58 | 104-116 rules per sample, 240 s per call |
| 3 samples, 1 call each, effort low, compact output | 223 s | $2.39 | about 140 s per call; 20-30k output tokens, little thinking |
| 3 samples x 2 calls (split by parts), effort low | 171-223 s | $2.42-3.15 | about 75-80 s per call; one 146 s outlier in one run |
| same, Sonnet 5.5 for samples B and C | 190 s | $2.68 | not cheaper (longer answers); 29 low-confidence rules instead of 10-17, so not adopted |

`--samples 1 --split 1 --no-verify` is roughly v1 (one call, about $0.3) if a build is ever short of time.

## Brief D vs the hand-written rationale (64 rules in force)

Graded by `tests/compare_inventory.py out/brief-d.rules.json --ref tests/synthetic/brief-d.rationale.md --section "## Rule inventory"`
(one independent Opus call; output in `out/brief-d.compare.json`):

- **61 covered, 3 partial, 0 missed. 1 wrongly in force.**
- **Partial (3):**
  - Rationale 22: the closure list is right, but the memo's "Monday 26 October is a normal business day" is in R108, which T14 marked `not_policy` (it treated the bridge-day rumour as the statement). This changes nothing in `spec.json`: 26 Oct is not in the holidays.
  - Rationale 62: nothing says the other tools may be repeated. The rationale infers this; the brief does not say it.
  - Rationale 64: the memo's override of code list v3 is stated only through the individual changes.
- **Wrongly in force (1):** R43, the email's "close as no promise with the hardship code from the list (HARD in v3)", still carries `HARD`. The new stale-value pass catches it:
  - The memo rule that replaced code-list row 7 names HARD in its text and drops it from its values, so R43 gets `confidence: low` and `stale_values: ["hard"]`.
  - It is listed first in `brief-d.rules.conflicts.md`.
  - Its outcome row is left out of `spec.json`, whose only hardship-declined code is `HSHP`.

  Before that pass existed, a previous run had shipped `HARD` and `HSHP` side by side in the spec.
- **All six memo changes reach `spec.json`:**
  - Band S: 5th business day and 2 attempts.
  - Band F: 21 calendar days, adjusted to the previous business day.
  - Over 45 days: `same_as` S.
  - Credit card floor: `multiple`, factor 2 × `minimum_payment`, `cap_to_full`. Loans: `instalment_amount`.
  - Holidays: 2026-10-30, 11-20, 12-24, 12-25, 12-28 and 12-31.
  - Callback: 09:00-18:00, today or the next 2 business days.

  The other values match the rationale too:
  - identity order phone_last4 then date_of_birth, `max_wrong_answers` 2;
  - ladder: attempt 1 in play on the next business day (F and S), attempt 2 S-only floor on the latest date;
  - all 17 outcome codes plus HSHP, and the 5 note reasons;
  - 11 verbatim lines; the 7 forbidden words.
- **T14 call range:** from 2026-10-14 (go-live), open-ended. The memo takes effect on the first call date, so the old versions are superseded rather than kept, which is correct; `timeline` is not needed.
- **The 11 single-sample (low-confidence) rules are all real brief content**, for example "Thank the customer and say goodbye", "Am I speaking with {first_name} {last_name}?" and the CP-7 4.5 table rows. Low confidence here comes from how the samples split rules, not from hallucinations. The union kept them, which is the point of T13.

## Brief A vs the v1 inventory (64 rules)

Graded both ways with `tests/compare_inventory.py --ref-json` (output in `out/brief-a.compare.json`):

- **v2 covers 62 of v1's 64 rules, with 2 partial and 0 wrongly in force.** The partials are API detail rules (the `get_account` product fields; the `schedule_callback` field list and HH:MM format) that v2 folds into other rules.
- **v1 covers all 60 of v2's rules.** v2 has 1 extra rule in force.
- **All 47 numbered rules are cited** (self-check).
- **`spec.json` matches the brief:**
  - holidays: 5;
  - bands: early 1-7, 12th business day, 1 attempt; late 8-45, 7th business day, 2 attempts;
  - floors: card `minimum_payment`, loans `instalment_amount`;
  - callback: 10:00-19:00, today or the next 1 business day;
  - identity: DOB then phone, 3 wrong answers;
  - outcomes: 16 rows; verbatim lines: 5.
- **Conflicts (1 item):** the `verify_identity` API rule (an unreadable answer is not counted; phone is four digits) was found by only one sample.

## Brief A + B

- **7 Brief A rules are superseded by Brief B**, each with a deciding quote:
  - B2 → A17 (statement of the debt)
  - B4 → A28 (first ask)
  - B7 → A34 (read-back)
  - B8 → A's "Brief A never uses `add_note`"
  - B10 → A41 (restructuring)
  - B11 → A37 (retries)
  - B closing → A's outcome table
- **B1, B3, B5, B6, B9, the second half of B10 ("no notes on any transfer") and the "Brief B is Brief A with..." preamble** are new rules with no override, so the Brief A rules they extend stay in force. v1 listed 10 overrides; v2 lists 7 and keeps the A rule in force where B only adds.
- **`spec.json` differs from Brief A's in two ways:**
  - it gains the 5 `add_note` note reasons;
  - it loses A28's verbatim "Can you make this payment today?", because B4 replaces the first ask.

  Open point: for a single-product call the builder may still want A28's sentence. The inventory does not flag this, because B4 does supersede A28.
- **Conflicts (3 items):**
  - two rules were found by only one sample: A1's forbidden words and A32's "still names a date";
  - the samples disagree on two values: whether "the product" belongs in the forbidden-words list, and how complete the Brief B closing table is.

## False alarms found and fixed during the runs

- **T15 compared against quotes.** A quote can carry a replaced value ("(HARD in v3)"), which let a stale rule pass. T15 now compares against the verifier's own statement of the value in force.
- **T15 needed number words.** "The next business day" vs `days_ahead_business: 1`, "fifth" and "twice" now count as numbers. `min_days` is not checked because it is derived from the previous band's `max_days` plus 1; `spec_check` checks contiguity instead.
- **T15 answered only part of a table.** Questions now say "give ALL of them (17 outcomes)".
- **T14 warned when no candidate in a block was in force,** even when the replacing rule was in force in another block. That warning is gone.
- **The self-check flagged sample values from an "Example" column** (`Daniel`, `c_4f2a...`), which forced a useless gap-fill call. Those tokens are now ignored.
- **`spec_check` flagged an "over 45 → treat as S" band as having no deadline.** Bands now have `same_as`.

## Brief-agnostic check

- **No brief-specific values in the code.** A grep of `rules.py` and `spec_check.py` finds no value from any brief; the only brief names left are file-name examples in a `source` description.
- **`spec_check` reads its enums from the API file it is given.** Run against Brief E's changed API (`tests/synthetic/brief-e.openapi.json`), Brief A's spec gets 24 errors, which is correct: different outcome, field and product enums.

## Open points

- **Brief D is over the time and cost target** (171 s, $2.41). To get under it:
  - a third split (9 calls in flight; watch rate limits);
  - a deterministic pre-grouping before the merge call, which takes 41 s on D;
  - or 2 samples on large briefs.
- **No other model family was tried for T15** (T16b). Using an OpenAI verifier when `OPENAI_API_KEY` is set would be the next step.
- **The `spec.json` path has not been through a full build.** Nothing here ran `build.py` end to end, because this task allowed no Freya calls. The skill now tells Claude to load `spec.json` into the generator, but `out/gen_*` reference generators do not do it yet.
- **`out/brief-a.audit.json` is stale.** It still refers to the v1 rule ids; rerun `audit.py` before using it.
- **Every run differs a little** (D merged sizes across 4 runs: 107-121 rules), and T14's judgements vary at the edges. Examples are the 26 Oct sentence above and which memo rule stands for the code-list change.

## Files

- **Brief A:** `out/brief-a.rules.{json,md,log,meta.json}`, `.rules.conflicts.md`, `.spec.json`, `.compare.json`
- **Brief A + B:** `out/brief-ab.rules.{json,md,log,meta.json}`, `.rules.conflicts.md`, `.spec.json`
- **Brief D:** `out/brief-d.rules.{json,md,log,meta.json}`, `.rules.conflicts.md`, `.spec.json`, `.compare.json`
- **Code:** `builder/rules.py`, `builder/spec_check.py`, `tests/compare_inventory.py`
- **Docs:** `builder/AUDIT.md` §1, `.claude/skills/build-phone-agent/SKILL.md` step 1, `builder/build.py` (build prompt)
