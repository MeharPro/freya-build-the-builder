# Generated rule-branch cases: `builder/cases.py`

Hidden briefs come with no practice cases. `cases.py` is an **optional local diagnostic case writer**: separate model
calls read a brief and write up to 20 scenarios in `public-test-set.json` shape. A separate call helps expose the
builder's blind spots, but may use the same underlying model and may share its mistakes. The building agent should
not write the cases or read their rationale. These cases correspond to research technique T16; the proposed repair
round and parallel case writing are T12 and T31 (`docs/research/sota-techniques.md`). They are not current behavior of
the submission runner and do not establish a score on the organisers' unseen customers.

```bash
source .venv/bin/activate
python3 builder/cases.py --brief <brief.md> [<brief2.md>] --api <tool_api.json> [--rules out/<slot>.rules.json] --out out/<slot>.cases.json
python3 builder/cases.py --check out/<slot>.cases.json --api <tool_api.json>         # deterministic checker again
python3 builder/cases.py --map-rules out/<slot>.cases.json --rules out/<slot>.rules.json   # brief refs -> inventory ids
# evaluation of the case writer itself (not used by the build):
python3 builder/cases.py --brief b.md --api api.json --rules r.json --scenarios hand.cases.json --out out/x.replay.cases.json
python3 builder/cases.py --compare out/x.replay.cases.json hand.cases.json
```

Outputs:

| File | Content | Who reads it |
|---|---|---|
| `<out>` | The cases: `id`, `mock_case`, `brief`, `family`, `level`, `title`, `variables` (with `now`), `identity`, `products`, `faults`, `third_party`, `script`, `expected`, `checks`, `rule_ids`, `expected_confidence` | `builder/sim.py`, the building agent |
| `<out stem>.rationale.md` | The calendar and the business-day ladders for each `now`, the outcome rows covered, and the derivation of every case: each expression and its value, and the reason for its confidence | humans only. The skill tells the building agent not to open it. |
| `<out stem>.meta.json` | The calendar, the outcome rows, the checker's report (`dropped`, `rejected_then_repaired`, `trimmed_to_20`), and the model, cost and time | `--check`, the trace |

## How it works

1. **Two model calls in parallel** (`CASES_MODEL`, default selected by the configured builder provider, no tools,
   JSON schema output; this reuses `rules.py`'s `ask_json_async`). One call writes the conversation-control branches: opening, third party,
   identity failures, special topics, and **one case per non-promise outcome/reason row**. The other writes the
   promise branches: date classes, amount classes, persuasion per band, read-back changes, the promise-service fault,
   multi-product mixes, and 3-4 pairwise combinations.
   Each call receives:
   - the brief(s);
   - the API digest;
   - the rule inventory, if one was given;
   - the 13 mock customers as data only (names, identity, products, faults: no Brief A/B script, expectation or check);
   - a weekday sheet.
2. **No model arithmetic for dates.** The model returns the brief's calendar (business weekdays and holidays). Every
   date it writes is an expression, such as `addbd(today, 9)`, `next_bd(d('2026-10-17'))`,
   `weekday_in_week(today + days(7), 'Friday')` or `lastbd_of_week(today)`. The script evaluates each expression
   with `freyalib.CAL_HELPERS`, exec'd with that calendar. This covers the promise dates, the deadlines, the
   callbacks and the `[[...]]` date placeholders in scripts. Amounts can be expressions too, such as
   `ceil(0.4 * product('p1')['past_due'])`. A holiday that does not appear in the brief's text is dropped. If the
   two calls disagree on the calendar, the disagreement is reported.
3. **Deterministic checker**, run on every case:
   - `mock_case` is one of PUB-01..13, and `variables`/`identity`/`products`/`faults` are copied from
     `public-test-set.json`, because the mock answers with its own data;
   - `now` is well formed;
   - `outcome`, transfer `queue` and note `reason` are in the API file's enums;
   - every product id exists for that customer;
   - every promise date is a business day under the brief's calendar, not before today, and not after the deadline
     the case states for that product;
   - the amount is positive (a warning above `past_due`);
   - callbacks are `HH:MM` and later than `now`;
   - the weekday of every "Monday 19 October" written in a script is right;
   - a one-product brief does not use the multi-product customers PUB-11..13.
4. **At most one repair call.** It runs only when the checker rejected a case or an outcome row has no case. The
   checker's findings go back to the model together with the uncovered rows. Cases that still fail are dropped and
   listed in `meta.dropped`.
5. **Trim to 20.** The cases kept first are those that are the only case of their outcome row. The rest are taken
   round-robin across the two writers, with low-confidence cases last.

`expected_confidence` is set by the case writer:
- `high`: the brief fixes every ledger value, and the script leaves no choice.
- `medium`: one value depends on an ambiguous sentence or on a delicate persona instruction.
- `low`: the brief can be read two ways.

When a case file is explicitly supplied to the building agent, the skill's step 9 says to change the generator only
for deterministic agent errors, never merely because a `low` or `medium` expectation disagrees.

## Current relationship to the build (`builder/build.py`)

The current runner runs `rules.py` and then the builder model. It **does not invoke `cases.py`**, and it has no
`--gen-cases` or `--no-gen-cases` options. For a brief without a supplied cases file, its prompt calls for lint, dry
run, smoke and audit only. The skill contains a generated-case procedure, but the runner does not create or name the
file that would activate it. `--map-rules` and `--check` are manual `cases.py` commands; they do not run as submission
gates. The historical parallel-build design described in earlier notes was removed from the active path.

Use the script before hidden release to diagnose public or synthetic briefs. Do not manually splice its outputs into
a hidden agent after release: the phone agent must still come from the submitted builder's automatic run. If the
runner gains an optional generated-case step, first prove that the hidden API fields can be exercised by the fixed
practice mock, keep generation and tests inside the 30-minute budget, preserve expectations and failures in the trace,
and do not treat a generated score as official.

## Historical case-writer measurements (10 Oct, Brief A and synthetic Brief C)

| Run | Calls | Time | Cost | Result |
|---|---|---|---|---|
| Brief A, `--rules out/brief-a.rules.json` | 3 (2 + repair/gap) | 127 s | $0.65 | 20 cases, 18 high / 2 medium, 15/16 outcome rows (service_error is unreachable with the mock), 0 dropped |
| Brief C, `--rules out/brief-c.rules.json` | 3 (2 + gap) | 141 s | $1.04 | 20 cases, 17 high / 3 medium, 16/17 rows (system_fault is unreachable), 0 dropped |
| Replay of the 52 hand-verified Brief A cases (PUB A + EXT-A) | 5 | 97 s | $1.40 | **52/52** expected ledgers equal |
| Replay of the 40 hand-verified Brief C cases (C practice + EXT-C) | 4 | 85 s | $1.28 | **40/40** expected ledgers equal |

The comparison and a hand check of every generated case are in `out/cases-gen.REPORT.md`. These are case-writer
experiments with their then-current model and prices, not timings or costs of the current OpenAI build path.

## Limits

- **The mock serves only PUB-01..13.** Identity answers, products, `days_late` and the single fault (PUB-10's first
  `create_promise` fails) are fixed. Some branches therefore cannot be reached:
  - a service-error row whose brief retries more often than the fault fails (Brief A `service_error`, Brief C
    `system_fault`);
  - a band that no mock customer's `days_late` falls into;
  - a product type or floor field the mock does not have.
  The rationale lists such rows as NOT COVERED. The hidden tool API may also change field names and allowed values;
  this script cannot assume the public mock can exercise them.
- **Expectations are a model's reading of the brief.** Dates are exact (they are computed in code), but the branch
  the model picks can be wrong where the brief is ambiguous. That is why the confidence field exists, and why
  step 9 fixes only failures that the engine events prove.
- **Scripts depend on the simulator following them.** A case that needs the persona to give a numeric date (to
  trigger `day_month_swapped`) or to stay silent is marked `medium`.
- **`tools/run_cases.py` (the kit) cannot run these files.** It opens practice sessions by case id. Use
  `builder/sim.py`.
- **The replay agreement is an upper bound.** The hand-written scripts are explicit, so writing an expected ledger
  for a given script is easier than inventing the scenario and its ledger. The fresh cases were checked by hand
  instead (see the report).
- The SDK prints `Unknown child process pid N, will report returncode 255` when parallel calls finish. This is
  harmless: every result arrived.
