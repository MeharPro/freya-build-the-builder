# Generated rule-branch cases: `builder/cases.py`

Hidden briefs come with no practice cases. If the building agent wrote its own tests, they would share its blind spots
(CLAUDE.md, ττ-bench: "tests that cannot fail"). `cases.py` is an **independent case writer**: separate model calls
that read the brief and write 12-20 practice cases in `public-test-set.json` shape. The building agent never writes
them, and it never reads their rationale. These cases are research technique T16. The repair round that uses them is
T12, and running them alongside `rules.py` is T31 (`docs/research/sota-techniques.md`).

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

1. **Two model calls in parallel** (`CASES_MODEL`, default `claude-opus-5-5`, no tools, JSON schema output; this
   reuses `rules.py`'s `ask_json_async`). One call writes the conversation-control branches: opening, third party,
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

The skill uses it in step 9: the generator is changed only for deterministic agent errors, and never because a
`low` or `medium` expectation disagrees.

## In the build (`builder/build.py`)

`rules.py` and `cases.py` run at the same time, in threads. `cases.py` reads the brief itself (an independent reader)
and cites the brief's own rule numbers. Once both have finished, `--map-rules` turns references such as "rule 13"
into the inventory ids whose `source` cites them, and `--check` runs. When the brief has no practice cases (a hidden
brief), the generated file becomes the practice set in the builder prompt. The prompt also says:
- the cases were generated and carry `expected_confidence`;
- the runner is `sim.py` at concurrency 2 (only `sim.py` knows `mock_case` and the `now` override);
- step 9's repair-round rules apply;
- how many minutes are left, and the local clock time to stop by.

Options:
- `--no-gen-cases` skips the generation.
- `--gen-cases` generates the cases even when a cases file exists. They are then offered as an extra set.

Wall time: about 2-2.5 minutes, in parallel with the 1.5-2 minutes of `rules.py`, so about 1 minute is added to the
critical path. Cost: about $0.65-1.05 per brief.

## Measured (10 Oct, Brief A and synthetic Brief C)

| Run | Calls | Time | Cost | Result |
|---|---|---|---|---|
| Brief A, `--rules out/brief-a.rules.json` | 3 (2 + repair/gap) | 127 s | $0.65 | 20 cases, 18 high / 2 medium, 15/16 outcome rows (service_error is unreachable with the mock), 0 dropped |
| Brief C, `--rules out/brief-c.rules.json` | 3 (2 + gap) | 141 s | $1.04 | 20 cases, 17 high / 3 medium, 16/17 rows (system_fault is unreachable), 0 dropped |
| Replay of the 52 hand-verified Brief A cases (PUB A + EXT-A) | 5 | 97 s | $1.40 | **52/52** expected ledgers equal |
| Replay of the 40 hand-verified Brief C cases (C practice + EXT-C) | 4 | 85 s | $1.28 | **40/40** expected ledgers equal |

The comparison and a hand check of every generated case are in `out/cases-gen.REPORT.md`.

## Limits

- **The mock serves only PUB-01..13.** Identity answers, products, `days_late` and the single fault (PUB-10's first
  `create_promise` fails) are fixed. Some branches therefore cannot be reached:
  - a service-error row whose brief retries more often than the fault fails (Brief A `service_error`, Brief C
    `system_fault`);
  - a band that no mock customer's `days_late` falls into;
  - a product type or floor field the mock does not have.
  The rationale lists such rows as NOT COVERED.
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
