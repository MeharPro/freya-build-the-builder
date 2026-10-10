# Rule inventory and coverage audit

Two Claude-powered helpers for the builder. Both run on the Claude Agent SDK in `.venv` (no tools, structured JSON output,
model `claude-opus-5-5`), work as a CLI and as a function, write their output file plus a Markdown rendering next to it,
and print a one-line summary on stdout. Progress and every model call go to stderr as
`model call: <model> | purpose: ...`, so a caller can copy them into a trace.

```
source .venv/bin/activate          # or prefix the commands with .venv/bin/python
```

## 1. `builder/rules.py`: rule inventory of a brief (v2)

```
python3 builder/rules.py <brief.md> [<brief2.md> ...] --api <tool_api.json> --out out/<slot>.rules.json
python3 builder/rules.py briefs/brief-a.md --api tools/openapi.json --out out/brief-a.rules.json
python3 builder/rules.py briefs/brief-a.md briefs/brief-b.md --api tools/openapi.json --out out/brief-ab.rules.json
options: --samples 1|2|3 (default 3)   --split N (parallel calls per sample, default 2)   --no-verify (skip T14/T15)   --model
env:     RULES_MODEL (default claude-opus-5-5), RULES_EFFORT (default low for extraction/merge/verification),
         RULES_SAMPLE_MODELS ("m_A,m_B,m_C"; default: the main model for all three)
```

```python
import sys; sys.path.insert(0, "builder")
from rules import extract_rules
rules = extract_rules(["briefs/brief-a.md"], "tools/openapi.json", "out/brief-a.rules.json")   # returns the list
```

Outputs, next to `--out`:

| file | content |
|---|---|
| `<slot>.rules.json` | the inventory, one entry per rule (fields below) |
| `<slot>.rules.md` | the same, grouped by category, with confidence / verification / supersession flags and deciding quotes |
| `<slot>.spec.json` | the structured spec compiled from the `values` of the rules in force (T28; schema in `builder/spec_check.py`) |
| `<slot>.rules.conflicts.md` | everything doubtful, to resolve FIRST by re-reading the source sentence (the skill says so) |
| `<slot>.rules.meta.json` | model, samples, calls, seconds and cost per stage, counts |

Fields of a rule:

| field | meaning |
|---|---|
| `id` | `R01`, `R02`, ... in document order (order of sample A) |
| `source` | `brief-a.md rule 6`, `brief-d.md CP-7 4.1 table`, `memo item 3`, `openapi.json /close_call` |
| `category` | one of `opening, third_party, identity, disclosure, dates, amounts, persuasion, hardship, confirmation, recording, special, multi_product, closing, wording, other` |
| `topic` | snake_case name of the policy point without any value; an old statement and the one that changes it share it |
| `text` | the rule, one or two sentences, numbers / dates / enum values quoted exactly |
| `verbatim` | sentences the agent must say word for word (`[]` if none) |
| `values` | a PARTIAL SPEC: only the spec keys this rule sets (`calendar`, `bands`, `floors`, `attempt_ladder`, `callback`, `identity`, `max_wrong_answers`, `outcomes`, `note_reasons`, `forbidden_words_before_verification`, `text`) |
| `overrides` | id of the earlier rule this one replaces, else `""` |
| `in_force` / `superseded_by` | `false` + the replacing id when a later decided rule changes it |
| `doc`, `doc_date`, `author_role`, `status`, `status_words` | where the statement is, its date, and whether it is `decided` or a `proposal` / `discussion` / `rejected` / `distractor` / `unclear` |
| `confidence`, `samples` | `high` (all 3 samples), `medium` (2), `low` (1, or failed verification, or a stale value); which samples found it |
| `alternatives`, `value_difference` | when the samples disagree on a value: the other members' values and what differs |
| `not_policy` | T14 judged it a proposal / discussion / distractor |
| `deciding_quote`, `deciding_quote_found` | T14's quoted deciding sentence, and whether it occurs verbatim in the brief |
| `effective_from`, `effective_until` | a decision with an effective date; `effective_until` on an older version kept in force because the change takes effect inside the range of call dates (key the code on `now`) |
| `verification` | T15: `{status: ok / mismatch / quote_not_found / not_found / no_answer, missing, verifier_value, quotes[{quote, in_force, found}]}` |
| `stale_values` | values a later rule replaced that this rule (in force) still carries |

Pipeline (techniques T13, T14, T15, T28 of `docs/research/sota-techniques.md`):
1. **T13 self-consistency.** The brief files are cut into parts (on `---`, else on `## ` headings); each part gets its header
   date. Three samples read the parts in three orders: forward, reverse, latest-dated first (memo first; undated files: the
   last file first). Each sample is written by `--split` (2) parallel calls that list the rules of one half of the parts
   while seeing all of them (cross-half `overrides` are written as a source and resolved by `resolve_ref`), so 6 calls run
   at once. One merge call (USC style) returns only groups of ids (`members`, `best`, `values_differ`, `difference`); the
   union is built deterministically: best member's text and values, `confidence` by the number of samples, differing values
   (the model's judgement or numbers/dates that conflict both ways) kept as `alternatives`.
2. **Self-check** (unchanged): every numbered rule cited, every ISO date and `backticked` token present (tokens that occur only
   in an "Example" column are ignored); one gap-fill call when something is missing.
3. **T14 and T15 in parallel.**
   - T14: candidate blocks = rules linked by `overrides`, by the same `topic`, or by the same structured entity (callback,
     wrong-answer limit, holidays, a band name, a floor's product type, an attempt number), max 8 per block, plus every single
     statement that is not `decided`. One call gets the documents and the blocks (document, date, author role, status words,
     values per candidate) and returns `in_force` / `superseded` / `not_policy` per candidate with the deciding quote and
     effective date, plus the plausible range of call dates. Applied deterministically; a superseded rule whose successor
     takes effect after the earliest call date stays in force with `effective_until` (both versions kept).
   - T15: for every rule in force with checkable values (numbers except order/attempt/min_days, ISO dates, HH:MM, codes,
     outcomes, fields), a question built from its source, topic and spec keys only ("give ALL of them (17 outcomes)"),
     never the value. Fresh calls (30 questions each) see only the brief and the API. The rule's atoms must all occur in the
     verifier's own statement of the value in force (number words and "the next day" count as numbers); at least one quote
     must occur verbatim in the brief. Anything else lowers the rule to `confidence: low`.
4. **Stale values** (deterministic): a value the superseded rule had, that its replacement names in its text but no longer has
   in its values, is stale wherever another rule in force still carries it (flagged; outcome rows with a stale reason are
   left out of the spec).
5. **T28 spec.** `values` of the rules in force are merged in order (API-sourced rules first, so the brief wins): holidays
   united, bands merged by name or range, floors per product type, ladder per attempt, callback field by field, identity
   per field, outcomes per (outcome, reason), note reasons per reason, verbatim from the rules' `verbatim`. Two rules in
   force that set different values are listed as merge conflicts (the later one is used). With effective dates inside the
   call range, `timeline` holds one spec per period. `spec_check.check` validates it; problems go to the conflicts file.

`builder/spec_check.py out/<slot>.spec.json --api <api>` validates a spec by itself: weekdays, ISO holidays, bands
(integers, min <= max, contiguous, deadline type/n/adjust, `same_as` names a band), floors (product types and fields from the
API's `get_account` schema, percent/factor), ladder (1..n, amount enum, band names, enough steps for every band's attempts),
callback (HH:MM, open < close, some day allowed), identity (API field and hint enums, order 1..n), `max_wrong_answers`,
outcomes (API outcome enum, reason enum when the API has one, every API outcome used), note reasons (API enum). Exit 1 on ERROR.

Measured (10 Oct, `claude-opus-5-5`, effort low except T14; details in `out/rules-v2.REPORT.md`):

| brief | rules (in force) | low confidence in force | conflict items | calls | wall time | cost |
|---|---|---|---|---|---|---|
| Brief A | 60 (60) | 2 | 1 | 9 | 78 s | $0.96 |
| Brief A + B | 77 (70; 7 A rules superseded by B) | 2 | 3 | 9 | 102 s | $1.28 |
| Brief D (mail + policy + memo + code list) | 117 (101) | 14 | 12 | 11 | 171 s | $2.41 |

Against the hand-written Brief D inventory (64 rules in force, graded by `tests/compare_inventory.py`): 61 covered, 3
partial, 0 missed, 1 wrongly in force (the email's "hardship code (HARD in v3)", flagged by the stale-value pass and kept
out of `spec.json`). The spec matches every memo change (Band S 5th business day and 2 attempts, card floor 2 x minimum
payment capped at the overdue amount, Founders' Day closure, callback to 18:00, HSHP). v1 for comparison: one call,
60-86 s, $0.25-0.30, no confidence, no verification, no spec.

## 2. `builder/audit.py`: coverage audit of a workflow against the inventory

```
python3 builder/audit.py --rules out/<slot>.rules.json --workflow out/<slot>.workflow.json --generator out/gen_<slot>.py --out out/<slot>.audit.json
python3 builder/audit.py --rules out/brief-a.rules.json --workflow out/brief-a.workflow.json --generator out/gen_brief-a.py --out out/brief-a.audit.json
python3 builder/audit.py ... --digest-only            # print the workflow digest that is sent to Claude, no model call
```

Options: `--batch N` rules per model call (default 12), `--parallel N` calls in flight (default 3), `--model`,
`--generator ""` to audit a workflow without its generator. `--workflow` accepts the plain workflow or the export format
(`{"workflow": {...}}`, i.e. `submission/<slot>.workflow.json`).

```python
from audit import audit
report = audit("out/brief-a.rules.json", "out/brief-a.workflow.json", "out/gen_brief-a.py", "out/brief-a.audit.json")
```

Output `out/<slot>.audit.json`:

```
{"rules": [{"id": "R13", "status": "implemented|partial|missing|contradicted|superseded",
            "where": "third_party.task_message + setup code: callback_text", "evidence": "<one line quoted from the prompt/code>",
            "fix_hint": "<one concrete change, '' when implemented>"}, ...],
 "summary": {"implemented": n, "partial": n, "missing": n, "contradicted": n, "superseded": n, "total": n},
 "top_fixes": [{"id", "status", "rule", "why", "fix"}],        # the 5 most important gaps, most important first
 "meta": {"model", "seconds", "cost_usd", "calls", "batches", ...}}
```

`out/<slot>.audit.md` renders the summary table, the top fixes, the contradicted / missing / partial rules with evidence,
and a table of all rules.

What the script does:
1. Builds a **workflow digest** instead of sending the raw JSON (93 KB for Brief A, mostly repeated tool definitions):
   system prompt, deduplicated tool definitions (description, body fields with defaults / enums / descriptions,
   pre/post-process code, response mapping), then every node with its on_enter line, task_message, tools, code, extraction
   enums with descriptions, transitions in order with their conditions rendered as text, and terminal farewell. 46 KB for
   Brief A. The generator source (41 KB) is sent as well, so the auditor sees how values are computed.
2. Sends the rules in force in batches of 12, each batch one model call with the same context (primer on how a Freya
   workflow works + generator + digest in the system prompt, the batch of rules in the user prompt), up to 3 in parallel.
   Each judgement must point at a line (`evidence`), and a `fix_hint` is required for anything not implemented. Superseded
   rules are not audited; they are listed with status `superseded`.
3. One small call ranks the gaps (contradicted > missing > partial) into `top_fixes` with a concrete fix each. No gaps,
   no call.

Measured on Brief A (64 rules, 46-step workflow, the 10/10 generator): **run 1: 58 implemented, 6 partial, 0 missing, 0 contradicted (7 calls, 69 s, $0.95); run 2: 60 implemented, 4 partial (7 calls, 57 s, $0.34)**; 62 of 64 judgements identical between the runs, and all evidence quotes were found verbatim in the digest or generator. The partials are real but minor gaps of `gen_brief-a.py`: the hardship node has no human-transfer tool (R52, found both runs), no restructuring route and no "said twice they do not want to talk" exit (R51, R55, found in run 1 only; R51 is arguably what Brief A rule 32 wants, "this rule comes before rules 30 and 41"), a recorded promise ends the call at once so no transfer can follow it (R57), the deceased farewell has no thank-you (R59), and nothing forbids the model from calling the global `close_call` tool itself (R64).

## Cost and time per run

| run | model calls | wall time | cost |
|---|---|---|---|
| `rules.py` v2 Brief A (3 samples x 2 calls, merge, T14, T15) | 9 | 78 s | $0.96 |
| `rules.py` v2 Brief A + Brief B | 9 | 102 s | $1.28 |
| `rules.py` v2 Brief D (raw material: mail, policy, memo, code list) | 11 (incl. 1 gap-fill) | 171 s | $2.41 |
| `rules.py` v1 Brief A / A + B (one call; `--samples 1 --split 1 --no-verify` is close to it) | 1 | 60-86 s | $0.25-0.30 |
| `audit.py` Brief A (64 rules, 6 batches of 12, 3 in parallel, + 1 ranking call), first run | 7 | 69 s | $0.95 |
| `audit.py` Brief A, second run minutes later (prompt-cache hits on the shared context) | 7 | 57 s | $0.34 |

Costs are what the SDK reports (`ResultMessage.total_cost_usd`), billed to the Claude login on this machine or to
`ANTHROPIC_API_KEY` when it is set in the environment. Both scripts cap each model call at $6 (`max_budget_usd`).
Running the audit with `--parallel 1` is slower (about 3x) but the shared system prompt then hits the prompt cache,
which lowers the cost of the later batches.

## Using them inside a build

Within the 30-minute build budget, a sensible order is: `rules.py` right after reading the brief (1.5-3 minutes), build the
workflow, then `audit.py` (about 3-4 minutes) and fix the `top_fixes` before the practice run. The audit is a static
check: it finds rules the prompts, routes and code do not cover; it does not replace a simulation.
