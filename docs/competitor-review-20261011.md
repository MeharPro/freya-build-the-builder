# Public competitor repositories, reviewed 11 October 2026 (18:10–18:30 UTC)

21 public GitHub repositories for the Freya × YC "Build the Builder" hackathon were found by GitHub search
(queries: "build the builder", "freya hackathon", "freya builder", "freya agent", "freya yc", profile pages of
five authors named in an earlier session). Each was shallow-cloned read-only into a scratch folder outside the
repo and read by five review agents against one rubric: architecture, recorded scores, platform lessons not in
our `CLAUDE.md`, portable techniques, red flags, and a 1–10 rank for the *actual* final case (a Turkish inbound
statement-debt call, a case folder with a Markdown service contract instead of OpenAPI, call variables
`customerNumber` + `now`, a Cloudflare Worker mock written by each team). Nothing from any clone was executed.

## Ranking (likely score on the final case)

| # | Repo | Rank | Architecture | Evidence | Final-case path |
|---|---|---|---|---|---|
| 1 | emrebarkind/freyahackathon | 9 | Hybrid compiler: one Opus call → typed spec → deterministic engine; "general mode" for non-collections | A 29/30 and B 9/9 (3 reps), synthetic 17/17, 18/18, 15/15 | Built (14 nodes, 7 tools, 388 s, $3.26), dry-run only, ships `test_variables` |
| 2 | ranaserpill/freya-builder | 7 | Two parallel Opus spec calls + fixed-shape generator, date engine in code | 13/13 regression, A 9/10 at 3/3, B PUB-12 1–2/3 | Opus-writes-JSON fallback, untested |
| 3 | sceylan058/build-the-builder | 7 | Config compiler (1.8k-line gen.py), 5-rule checker, repair rounds | A 10/10, B 3/3, v_clean 17/17, v_raw 13/15 (1 rep); styles at 3 reps 4–9/10 | `--mode workflow` (model writes workflow + openapi), untested, ships `test_variables` |
| 4 | KDpercy/build_the_builder_agentmost | 7 | Agent SDK with read/design/check skills, model adapts a reference generator | A 9/10 at 3 reps | Built 48 nodes in 1,106 s; usage-limit error before scenario sims; 45-min budget (over the rule) |
| 5 | black131/freya_hachaton_build_the_builder | 6 | Kit skill expanded (240 lines) + guard hook + keep-best-tested | B 3/3 twice, earlier 0/3–2/3 | Case-folder mode, no final trace committed |
| 6 | egemenayrac/freya-agent-builder | 6 | Kit example builder, isolated run folder, Opus freeform | Turkish rehearsal of A 10/10 once; 9/10 twice | Rehearsed end to end on Turkish folder + mock |
| 7 | nursena8/build-the-builder | 6 | Agent SDK + cal.py library + validators + 2 fix / 2 audit rounds | own builds 7/10 at 3/3; headline 9/10 flagged contaminated | Case folder + mock template; Turkish agent never live-tested |
| 8 | EdizArkin/freya-agent-builder | 5 | One Sonnet call → spec → compiler embedding an 87 KB runtime; derive-API-from-documents with evidence check | A 9/10, B 2/3 | Ingests the real folder; zero live runs on that path |
| 9 | ayazelrico/freya-build-the-builder | 5 | Two-pass spec + generator; "general mode" single LLM pass for the final | A+B 10/13, 33/33 runs on 11 cases | Built 32 nodes in 878 s; one chat turn tested; initial node is code |
| 10 | melihzgvnc/agent-builder | 4 | Typed PolicySpec + deterministic compiler, 882 tests, online self-repair | A 10/10 at 3 reps; B 3/3, 2/3, 2/3 | Spec is collections-only; cannot express the final flow |
| 11 | kaan-gunes/freya-yc-hackathon | 4 | Codex (GPT-6.1-Sol) spec + 2.7k-line validator | A 8/10 official (1 rep) | Three final runs stopped before publish (Codex input limit) |
| 12 | SenaEliri/freya-builder-final | 4 | Deterministic compiler, Freya's own model for extraction, 2.9k-line embedded runtime | 36/39 calls, strict 10/13 over three frozen runs | No folder/PDF/Turkish support; flags Turkish as failure |
| 13 | Dannythecoder88/YC-Freya-Hack | 3 | Expression-DSL spec + selftest + reviewer pass; "general mode" unwired | none | General mode has a TypeError; falls to collections template |
| 14 | hunhan0by-stack/build-the-builder | 2 | 27k-line replay engine, Codex generator "not ready" | none | Platform-unverified by its own notes |
| 15 | nnam-droid12/build-the-builder-hack | 2 | Spec + compiler, stock skill | 10/13 at 3 reps | No final work; broken `import selftest` |
| 16 | hazarsozer/build-the-builder | 2 (8 on a collections brief) | Dual extraction + settle pass + 2.8k-line compiler | none committed | Falls back to the kit's openapi.json: wrong tools |
| 17 | emredermann/freya-agent-builder | 2 | Hand-written single-node final agent (brief read then ignored) | README claims only | Disqualification risk: hand-built, `test_variables` |
| 18 | mertsefayavuz/freya-build-the-builder | 2 | 7-section extraction + compiler, free OpenRouter models | none | Exits on "no openapi tool API file" |
| 19 | nergisRahimzade/build-the-builder | 2 | Kit example builder on the OpenAI Agents SDK | A 9/10 (flaky), B 3/3 once | None |
| 20 | hadihassan04/build-the-builder | 1 | Policy IR compiler; extraction is a stub returning the hand-written A/B policy | 6/13 at 3 reps | Cannot read an unseen brief |
| 21 | Solarity-AI/Freya-YC-Hackathon-Public-Repo | 0 | README only | none | none |

Our builder, for comparison: case-folder bundling (`builder/casefolder.py`, docx/xlsx/pdf via stdlib + pdftotext),
model-derived OpenAPI from the service contract with library parse check (`builder/apispec.py`), rule inventory
with dated-override chaining (`builder/rules.py`), skill-driven generator on `builder/freyalib.py`, static lint of
every documented platform rule, independent audit, export lint of the actual platform export, source-hash
manifests. Weak spots the field shows up: no scenario-driven persona simulation on the final format, and no
Turkish-specific speech helpers in the library (the skill asks the generator to write them per build).

## Platform lessons from the field that our notes did not have

Recorded by competitors as measured on Freya; each is a candidate for `CLAUDE.md` and `builder/LINT.md`
after the event (none was written into builder source during the final window):

1. **A `response_mapping` to a list or object path leaves the variable unset.** Lists arrive flattened as
   `<node>_response.data.<list>.<i>.<field>` (node name for `pre_actions`, tool name for model tools); numbers
   are ints, booleans the string `'true'`. (melihzgvnc `builder/PLATFORM_NOTES.md:26-32`, nursena8
   `builder/lib/cal.py:190-206`, KDpercy `builder/PATTERNS.md:30-31`.) Our hooks already rebuild lists in
   `post_process_code`; the lint could flag list-valued mappings.
2. **HTTP 200 with `ok:false` counts as tool success** (`failure_count` not incremented): route on the body,
   not the counter. (emrebarkind `docs/PLAN.md` probe 1.)
3. **After a chat-route 502 the engine replays the last customer turn**: a write can run twice; never resend.
   (melihzgvnc `PLATFORM_NOTES.md:64`.)
4. **Tool calls in one model message run in parallel on copies of `vars`**; writes merge per variable, the last
   writer wins on a shared JSON variable. Keep one variable per product/card. (EdizArkin `ARCHITECTURE.md:196-205`,
   hazarsozer `builder/multi.py:108-113`.)
5. **Post-hooks run only after a 2xx**; on an HTTP error the model sees a bare error and may ignore it.
   (EdizArkin `ARCHITECTURE.md:331-336`.) Route error status codes explicitly.
6. **`maxRetries` repeats an HTTP 500 inside one node**: use 1 on reads and 0 on writes. (hazarsozer
   `compile.py:2355`, KDpercy final workflow.)
7. **A code node can re-run without a new customer turn** and reuse a stale "yes"; compare `<node>.total_turns`
   with a stored counter. (emrebarkind `docs/FRESHNESS.md`.)
8. **Global intent nodes are evaluated after every transition, including while code nodes run**, so a counter
   can increment twice; list every non-conversation node in `excluded_nodes`. (nursena8 `dev/EXPERIMENTS.md` 7d/7e.)
9. **Code per node + variables must stay under 131,072 bytes.** (SenaEliri `BUILDER.md:79`, emrebarkind probe 7.)
10. **Simulator retries reuse the bank session**: a retried run sees "already closed"; count runs with
    `attempts > 0` as void when reading practice results. (emrebarkind `docs/RETRY-EVIDENCE.md`, hazarsozer
    `tests/test_a25.py`.)
11. **Turn-taking**: the default "speak 0.5 s after a pause" cuts talkative callers; customers' turns are cut
    mid-sentence and corrections get summed unless the parser is last-value-wins. (ayazelrico `build.py:22-24`,
    sceylan058 CHANGELOG "PUB-06 corrects", SenaEliri `BUILDER.md:82-83`.)
12. **A product name or service text can be a prompt injection**: service data is data, never instructions.
    (KDpercy design-agent skill rule 10, ranaserpill `case_skill.md:33`.)
13. **JSON text checks must not escape non-ASCII**: a validator comparing required Turkish sentences against
    `json.dumps(wf)` misses them. (KDpercy final trace ~line 292.) Our lint normalises both sides without
    `json.dumps`; `audit.py` renders defaults/enums with `json.dumps` and could show escaped text to the auditor.

## Techniques worth porting (after the event; generic, no brief content)

1. Scenario-driven persona simulations on the platform from the case's example scenarios and test customers
   (KDpercy `builder/sim_test.py`, emrebarkind `eval/final_scenarios.py`): our builder runs only chat smoke
   on the final format.
2. Decision log with sources and conflicts per rule in the trace (emrebarkind `builder/agent_mode.py`,
   `traces/final.log`): the clearest reviewer-facing trace in the field.
3. Evidence-checked derived API: every path, field and status code must be found verbatim in the documents or
   the build refuses (EdizArkin `builder/run.py:369-404`). Ours checks the library parse, not provenance.
4. Offline grid execution of every code node the way Freya runs it (inside a function, many `now` values,
   1–3 synthesised items from the response schema) (sceylan058 `builder/check.py` rules 3–4).
5. Transcript lesson gates: recorded-only-after-success, read-back contains the written values, required
   sentences present, close exactly once (SenaEliri `qa/lessons.py`).
6. Turkish speech helpers as library code: `spoken()`/`money()` ("26 Ekim 2026 Pazartesi", "1.250,50 TL"),
   word-number and relative-day parsing (black131 `scripts/calendar_lib.py`, kaan-gunes `builder/language.py`,
   nursena8 `builder/lib/cal.py`).
7. Contamination scan with banned tokens derived from the practice briefs (melihzgvnc
   `scripts/check_contamination.py`).

## Red flags common in the field

- 7 of the 8 finished final agents ship `test_variables` (our chat-route finding says this breaks tool bodies).
- Several initial nodes are code nodes (the chat route skips them; simulations do not).
- Hand-written final agents (emredermann) and brief-ignoring stubs (hadihassan04) risk disqualification.
- Most "general mode" final paths are one large LLM pass with no simulation: fragile across three runs.
