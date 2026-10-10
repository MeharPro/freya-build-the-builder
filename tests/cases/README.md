# Extended practice cases (Brief A, Brief B)

The 13 practice cases cover only a few rules. These files add 56 scored cases that cover every rule family of Brief A
and the multi-product rules of Brief B. The mock bank serves only the practice customers `PUB-01`..`PUB-13` (fixed
identity answers, products, `days_late`, faults), so each case reuses one of them through `mock_case` with its own
script, expected ledger and checks; some cases change `variables.now` (see `builder/SIM.md`, "Extended cases").

| File | What |
|---|---|
| `brief-a-extended.cases.json` | 42 cases `EXT-A-01`..`EXT-A-42` (6 of them on other call dates) |
| `brief-b-extended.cases.json` | 14 cases `EXT-B-01`..`EXT-B-14` (multi-product PUB-11..13, plus single-product customers under Brief B's note rules) |
| `brief-a-extended.rationale.md`, `brief-b-extended.rationale.md` | Derivation of every expected value, business-day ladders, what the fixed customers cannot test |
| `_gen_cases.py` | Writes both case files (mock data copied from `public-test-set.json`, expectations hand-written) |
| `verify_cases.py` | Independent re-derivation: own calendar code, recomputes every promise/callback, checks floors, deadlines, the outcome table, notes and the closing rule |

Run (local simulator only: `tools/run_cases.py` does not know `mock_case` or the `now` override):

```bash
source env.sh
python3 builder/sim.py <workflow> --cases tests/cases/brief-a-extended.cases.json --concurrency 2
python3 builder/sim.py <workflow> --cases tests/cases/brief-b-extended.cases.json --concurrency 2 --out results/sim-ext-b.json --transcripts results/ext-b/
python3 builder/sim.py <workflow> --cases tests/cases/brief-a-extended.cases.json --only EXT-A-09,EXT-A-41 --verbose
python3 tests/cases/verify_cases.py .          # after editing a case
```

Run Brief A cases against a Brief A agent and Brief B cases against a Brief B (or A+B) agent: the two rule sets differ
on notes. These files are test data for the developers; the builder never reads them.

---

# Extended practice cases (Briefs C and D)

More scored cases for the synthetic briefs, on top of the practice scripts in `tests/synthetic/`. Never read by the builder at run time.

The organisers' mock bank serves only the practice customers PUB-01..PUB-13 (fixed identity answers, products, `days_late`, and PUB-10's first `create_promise` failure). A case here reuses one of them through `mock_case` (e.g. `"PUB-03"`) with its own script, expected ledger and checks, so its `id` can be unique. Some cases also override `variables.now` (another call date; the mock enforces no date rule); every expected value of such a case is computed for that date.

| File | Brief | Cases | Rationale |
|---|---|---|---|
| `brief-c-extended.cases.json` | C (Nordvik, `tests/synthetic/brief-c.md`) | 30: `EXT-C-01`..`25` at 2026-10-14 11:00, `26`..`30` at other dates | `brief-c-extended.rationale.md` |
| `brief-d-extended.cases.json` | D (Kestrel, after the memo, `tests/synthetic/brief-d.md`) | 30: `EXT-D-01`..`25` at 2026-10-14 11:00, `26`..`30` at other dates | `brief-d-extended.rationale.md` |

Schema: as `tests/synthetic/brief-c.cases.json` (`id`, `brief`, `family`, `level`, `title`, `variables`, `identity`, `products`, `script`, `expected`, `checks`, `faults`) plus `mock_case`, and `third_party: true` on third-party cases. `identity`, `products` and `faults` are copied from the mock customer and are informative only: the mock decides them.

Run (local simulator over the chat route; needs `mock_case` support in `builder/sim.py`):

```bash
python3 builder/sim.py <workflow> --cases tests/cases/brief-c-extended.cases.json --concurrency 2
python3 builder/sim.py <workflow> --cases tests/cases/brief-d-extended.cases.json --concurrency 2 --only EXT-D-01,EXT-D-16
```

`tools/run_cases.py` opens practice sessions by case id, so it cannot run these files as shipped.
