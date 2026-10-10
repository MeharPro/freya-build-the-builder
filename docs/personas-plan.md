# Persona robustness: ranked plan

Synthesised 10 Oct 2026 from three reader audits (A: kit personas and the final's customer model; B: library, skill,
generators and built workflows; C: truncated in the hand-off, used only where A or B say the same) plus re-checks in
the code (marked RC). Every claim below carries its source. Nothing here names a bank value, a hidden-brief rule or a
holiday date; every fix is brief-agnostic and consistent with the Do-not list in `docs/research/sota-techniques.md:755-770`
and with `CLAUDE.md` (no first code node, no `test_variables`, no pre-hook that blocks a write by rewriting the request,
no runtime reviewer, no editing on the platform by hand).

## 1. Verdict

The architecture is persona-agnostic wherever it is deterministic (routes on tool results and extracted enums, a
read-back before every write, `what_to_do_next` on every tool result, dates computed in code), but every
persona-specific defence the library offers (`normalise_pre`, `latest_value_note`, `digit_extraction`,
`relative_days_code`, `builder/freyalib.py:1505-1600`) reaches no generated and no submitted workflow: zero
`_nz_main`, zero `validation_pattern`, zero "LAST value" across `out/*.py`, `out/*.workflow.json` and
`submission/*.json` (A, B), because the skill sentence that asks for it (`.claude/skills/build-phone-agent/SKILL.md:27`,
added 14:17 today) came after the two reference generators the skill tells Claude to copy
(`out/gen_brief-a_lib.py`, `out/gen_brief-b_lib.py`), which carry only prompt lines and `promise_pre` (B). No styled
run has ever been executed (RC: `results/log.jsonl`, 13 rows, every `"style": null`; `builder/build.py` has no style
step; the three smoke scripts contain no split number, no question back and no words-only value), so the 10/10 PUB-A
score on Freya and the 34/42 local extended score are unstyled, cooperative measurements and the styled pass rate is
simply unknown. By expected cost on hidden cases the hazards rank: a half number or words sent to `verify_identity`
on the digits field, which the mock counts as a wrong answer with no "unreadable" escape (A and B both probed it
today; `tools/openapi.json:37` gives the free path to the date field only); a question back at an identity question
counted as a refusal by a counter that never resets, so two such questions close the call (A, B); a self-correction
or a changed value at the read-back landing in a prompt-only negotiate node (observed misroute
`results/ext-a-v2/EXT-A-34.txt`); then talkative enum misfires, prompt-counted persuasion attempts and latency.
Not verifiable from the repo: the final's mode (the kit practice uses `mode: chat`, `freya.py:92`, and the site says
"text, not audio", `docs/hackathon-site.md:110`; the task's premise of audio/ASR is supported by no kit file), the
hidden harness's persona system prompt, whether a hidden customer carries one style or several, how the organisers'
ledgers treat a question back that lands on an identity question, and whether an 18.8 KB `pre_process_code` runs
within platform limits (never deployed).

## 2. Hazards ranked by expected cost on hidden cases

Fix types: **lib** = library default (freyalib/multiproduct), **skill** = skill sentence, **lint** = lint check,
**sim** = sim style/option, **meas** = measurement only. Effort S/M/L.

| # | Hazard | Where it bites in our architecture | Evidence (file:line) | Fix | Type | Effort |
|---|---|---|---|---|---|---|
| 0 | Nothing styled was ever measured; the local customer (gpt-5-mini) does not show the gemini habits seen on Freya (terse one-liners, digits and dates in words unprompted in 5 of 8 calls, 3 truncated turns) | Every pass rate we quote; the build's step 9 and the smoke step | RC `results/log.jsonl` (all `style` null); `builder/sim.py:33` PHONE_RULE, `:534` `persona_for(..., ctx.style)`; `builder/SIM.md:86-91`; A (8 fetched calls) | `--styles` in sim.py plus the extra styles of section 3; one `run_cases.py --style <x>` per kit style on the current agents; record style in `results/log.jsonl` and in the trace | sim + meas | S |
| 1 | Phone digits given in two parts ('pieces') or in words ('in_words', and gemini unstyled) reach `verify_identity` early or as words: every non-matching value on the digits field is a COUNTED wrong answer ('44', '', absent, `null`, int 44, 'four four seven one' all decrement `wrong_answers_left`); only the date field has the free "unreadable" path. One slip plus one scripted wrong answer ends the check on a two-wrong-answer brief | `ask_<digits>` node: prompt says "When they give four digits, call verify_identity" and the tool description "CALL it every time the customer gives four digits"; no "wait for all N" sentence; no extraction gate; `pre_process_code` cannot cancel a call (`docs/tools-and-code.md:395`: "Clean a value, or rewrite the whole request") | A and B mock probes today; `tools/openapi.json:37`; `out/gen_brief-a_lib.py:219`, `out/gen_brief-c.py:244`, `out/gen_brief-d.py:221`; `builder/freyalib.py:1584-1588` (`digit_extraction` unused), `:1590-1593` (`latest_value_note` unused) | 5.1: identity-tool helper that puts `latest_value_note(N)` + "never call with fewer than N digits or with words; ask for the rest" into BOTH the node prompt and the tool description, a `digit_extraction` gate, `n_digits` keep-last-N in the normaliser; smoke `pieces.json`; lint ERROR when a verify tool on a digits field lacks the sentence/gate | lib + lint + sim | M |
| 2 | The speech normaliser is built and tested but attached nowhere: words for an amount ('four hundred and twenty'), a date ('the sixteenth of October') or a time ('half past ten') pass through `promise_pre`/`PROMISE_PRE` to the mock, which rejects them ("amount must be a positive number", "date must be YYYY-MM-DD", "time HH:MM"); `promise_post` then orders a retry "with exactly the same values", which fails again, and `tool_failed_twice` routes to the service-error ending: wrong outcome AND lost promise | `create_promise`, `schedule_callback`, `verify_identity` tools of every generator; `promise_pre` only does `float(str(amount).replace(',',''))` and `date[:10]` inside try/except | RC grep: 0 `_nz_main` in `out/*.py`, `out/*.workflow.json`, `submission/*.json`; `builder/freyalib.py:567` `promise_pre`, `:555-562` `promise_post`, `:366-372` `tool_failed_twice`; `SKILL.md:27`; `out/gen_brief-a_lib.py:247`, `out/gen_brief-b_lib.py:228,236`; B mock probes | 5.2: `api_tool` attaches `normalise_pre` by default for model-filled fields of a known kind; `promise_pre` reports a still-non-numeric amount/non-ISO date via `what_to_do_next` instead of sending it; port the two reference generators; lint ERROR; deploy once and smoke 'four four seven one' to confirm the hook runs on the platform | lib + lint | M |
| 3 | 'asks_back' at an identity question ("why do you need that?", "which account is this about?") is extracted as `refused`; `decline_count` increments and never resets after a correct answer, so the persona's two questions landing on the two identity nodes close the call as declined/withheld although every answer follows ("The facts stay the same", `docs/kit-README.md:78`). The second question also invites disclosure before verification | `REFUSAL_DESC` on every identity node ("or ask what the call is about instead of answering it"), `fl.eq(refusal_*, 'refused', count_decline_*)`, `counter_code('decline_count', 2, ...)` which resets only the extraction flags | `out/gen_brief-a_lib.py:194-195, 211, 230-233`; `out/gen_brief-c.py:235, 253, 266, 272-276`; `out/gen_brief-d.py:212`; `builder/freyalib.py:792-800` `counter_code`; `results/ext-a-v2/EXT-A-11.txt:16-17`; `tools/run_cases.py:31` | 5.3: split the enum into `refused` / `question` / `none`; count `question` only when the brief says such a question counts (spec flag from `rules.py`); reset the decline counter in the verify post hook on any `ok: true`; one-sentence answer then re-ask in the common identity prompt; smoke `asks_back.json` | lib + skill + sim | M |
| 4 | 'corrects' ("the 21st, sorry, I mean the 20th") and a changed value at the read-back land in a prompt-only negotiate node: `latest()` keeps only the tokens after the marker, which do not parse alone, so month-less corrections stay raw; a read-back of the first value gets no "Yes, I confirm"; a change at the read-back was already routed to `new_plan`/transfer unstyled | NEGOTIATE node: attempts, floor, read-back, `create_promise` all prompt text; only `topic` enum and PROMISE_TR are code routes; `create_promise` body is model-filled | `out/gen_brief-a_lib.py:260-291, 310-311`; `builder/freyalib.py:1071-1081` `latest()`; `results/ext-a-v2/EXT-A-34.txt`; `docs/ext-a-v2-failures.md:13`; `tools/run_cases.py:29`; A and B normaliser runs ('the 21st, sorry, I mean the 20th' unchanged; '14 March 1988, sorry, 1989' unchanged, and the mock reads the FIRST date) | 5.4: a code-built confirm step (`offer_amount`/`offer_date` extraction, `confirm in {yes, no, change}`, `create_promise` reachable only from it with body baked from vars); normaliser patch: a bare day/month/year after the marker replaces that component of the value before it; tests for both organisers' literal examples | lib + skill + sim | L |
| 5 | 'talkative': small talk before the opening confirmation can be labelled `unclear` at 0.6 confidence; the second ask ends with `always(fin_unclear)`, so one more miss closes not_reached; `topic` enum ("hardship", "already_paid", "dispute") fires straight into terminals (`fin_paid`, `fin_dispute`) on chatter about work or other bills; the decoy "cousin's wedding on the 30th" is guarded by the read-back only | `opening`/`opening_retry` WHO_DESC and the `always` fallback; NEGOTIATE `topic` routes; `ext(conf=0.6)` with plain `eq` transitions, no confidence gate possible on routing | `out/gen_brief-a_lib.py:109-116, 131-146, 286-311`; `out/gen_brief-c.py:136-143, 171`; `builder/freyalib.py:391-393`; `results/ext-a-v2/EXT-A-01.txt:14-16` ('Yeah, go ahead' -> `customer`); `tools/run_cases.py:30` | 5.5: enum-description templates with labelled small-talk examples ("even after small talk"); topic descriptions "only when said about THEMSELVES as the reason they cannot pay; small talk about work, family events, weather or other bills is none"; `offer_date` defined as "the day they say they WILL PAY, never another date they mention"; smoke `talkative_opening.json` | lib + skill + sim | S |
| 6 | Persuasion attempts and repeated refusals are counted by the dialogue model only; already failing unstyled (offers repeated, attempts exceeded); a padded or repeating refusal makes it worse | NEGOTIATE step "uses one persuasion attempt ... when the allowed attempts are used up ... call transition_to_fin_refused"; exit is an `intent_tool`, no counter, no stance extraction | `out/gen_brief-a_lib.py:279-282, 307-309` (B cites a_v2 numbering); `results/ext-a-v2.json` EXT-A-17, EXT-A-25; `results/brief-a-v2-freya.json` PUB-06; `builder/freyalib.py:792` | 5.6: `stance` extraction + `counter_code('attempts_used', N)` writing the code-built next offer; lint WARN when a node's prompt says "attempt" and no transition routes on a counter | lib + lint | M |
| 7 | Latency: talkative turns lengthen the three model calls per turn; a median slowest turn above 10 s lowers a score and a long silence makes the customer hang up | Every conversation node; no evidence either way because no talkative run exists | `CLAUDE.md` (Things that bite); `docs/kit-README.md:100`; `tools/run_cases.py` slow-run warning (A) | Measure on Freya with `--style talkative`; if slow, trim prompt size (lint `--budget`) rather than add nodes | meas | S |
| 8 | A whole phone number ('my number is 0171 555 4471') becomes an 11-digit answer through `to_digits`, which the mock counts as wrong | Normaliser digits kind, once attached | `builder/freyalib.py:1172-1184` (B) | `n_digits` in the digits kind: keep the LAST N digits when more are given, leave shorter values alone; test in `builder/tests/test_normalise.py` | lib | S |
| 9 | Hang-up or silence mid-call: no `fin_*` node runs, so `close_call`'s `{{outcome}}`/`{{reason}}` are model-filled; the local simulator turns an empty customer line into "Hello?" so the platform's behaviour on an empty turn is unknown | `close_call_tool` var_map; conversation nodes keep the inactivity monitor | `builder/freyalib.py:184-202`; `docs/tools-and-code.md:562`; `builder/sim.py:241` `return s or "Hello?"` (B) | Setup code writes a stage default outcome/reason from the brief's table (generator parameter) that every stage overwrites; `pauses` style in section 3 | lib + sim | S |
| 10 | Same-sentence DOB correction: the mock reads the FIRST date in the string, so a corrected security answer where the second value is right is a counted wrong answer; the kit 'corrects' text exempts security answers, so this is a corner | Identity tool, date field | B mock probe ('14 March 1988, sorry, 1989' verified as 1988) | Covered by the normaliser component patch of 5.4 once attached (5.2); otherwise measurement only | lib | S |

Ranking rationale: rows 1-2 cost on two of the five kit styles AND on the unstyled gemini habit of saying digits in
words (A: 5 of 8 calls), across every verified case; row 3 costs on one style across every verified case whenever
both questions land at identity; row 4 on one style across every promise case; rows 5-7 are single-style, partial
exposure; rows 8-10 are corners.

## 3. Extra STYLES for `builder/sim.py`

All text is brief-agnostic, in the organisers' format (`tools/run_cases.py:27-33`, one "HOW YOU TALK:" paragraph
appended to the PERSONA), and keeps the facts of the case unchanged so the pass check stays ledger equality plus the
case's checks. `tools/run_cases.py` is a kit file and stays as shipped; sim.py extends the dict in memory.

```python
# builder/sim.py, after `from run_cases import STYLES, persona_for`
EXTRA_STYLES = {
    # the habits of Freya's persona model observed in the organisers' simulation (terse, words for digits, cut-off turns)
    "terse_words": "HOW YOU TALK: you answer in one short line, never more. You say dates, years and digits in words even when nobody asked you to, like 'nineteen October nineteen eighty-three' and 'four four zero one'. Once or twice in the call your sentence stops early, as if you were cut off, and you finish the thought only if the caller asks.",
    # two kit styles at once: the first half of a number, in words
    "pieces_words": "HOW YOU TALK: you give long numbers and dates in two parts and in words. Say the first half in words, stop, and give the rest in your next turn or when asked, like 'forty-four' and then 'seventy-one'. This replaces the rule about saying all of it in one turn.",
    # the kit's asks_back aimed at the security questions only
    "asks_back_identity": "HOW YOU TALK: each time the caller asks you a security question, before you answer you ask a short question back, like 'why do you need that?' or 'who are you again?'. Whatever the caller replies, you then give your answer.",
    # a non-answer turn at identity and a 'say that again' at the read-back
    "pauses": "HOW YOU TALK: once in the call, before you answer a security question, you reply only 'Hang on a second.' and give the answer in your next turn. Once more in the call, when the caller reads a payment back to you, you reply only 'Sorry, say that again?' and confirm only after the caller repeats it.",
    # the correction arrives in the NEXT turn, at the read-back, not in the same sentence
    "corrects_late": "HOW YOU TALK: the first time you say a payment day or amount, you say a slightly different one. When the caller reads it back, you say 'no, sorry, I meant' and give the right one, which is the one written above. Do this once in the call. Never do it with a security answer: those you say right the first time unless the text above says otherwise.",
    # talkative with a decoy amount instead of a decoy date
    "decoy_amount": "HOW YOU TALK: before most answers you add a sentence about your day. Once in the call you mention that you spent about a hundred and ninety on car repairs this week. It has nothing to do with any payment, and you never offer it as a payment amount.",
    # the same refusal, word for word, every time the caller asks again
    "repeats": "HOW YOU TALK: when you decline something, you say the same short refusal again every time the caller asks, in the same words, and add nothing. When you agree to something, you say it once, plainly.",
    # two kit styles combined
    "mixed": "HOW YOU TALK: you give long numbers and dates in two parts: say the first half, stop, and give the rest in your next turn or when asked (this replaces the rule about saying all of it in one turn). Also, twice in the call, before you answer, you ask a short question back, like 'why do you need that?'. Whatever the caller replies, you then give your answer.",
}
STYLES.update(EXTRA_STYLES)          # the same dict object run_cases.persona_for reads; the kit file is untouched
KIT_STYLES = ("pieces", "corrects", "talkative", "asks_back", "in_words")
```

The sim.py change that accepts them (sketch; `persona_for` already honours a per-case `style` field,
`tools/run_cases.py:45` `style = style or case.get("style")`):

```python
# argparse: keep --style (single, choices=sorted(STYLES) computed AFTER the update) and add
ap.add_argument("--styles", help="comma list, or kit | extra | all: run every selected case once per style, "
                                 "plus once unstyled, and report per style")
# after the case list is built
if a.styles:
    names = (KIT_STYLES if a.styles == "kit" else tuple(EXTRA_STYLES) if a.styles == "extra"
             else KIT_STYLES + tuple(EXTRA_STYLES) if a.styles == "all" else tuple(a.styles.split(",")))
    unknown = [s for s in names if s not in STYLES]
    if unknown: sys.exit("unknown style(s): %s" % ", ".join(unknown))
    cases = [dict(c, id=c["id"] + ("[%s]" % s if s else ""), style=s) for c in cases for s in (None,) + names]
# run_case / write_transcript / finish: use case.get("style") instead of ctx.style for the header and the row
# log line: "style": a.style or a.styles ; each row also carries row["style"] = case.get("style")
# summary: after the PASS/FAIL list print one line per style: "<style>: k / n passed; cases that pass unstyled but
# fail styled: <ids>" (the metamorphic reading of docs/research/sota-techniques.md:445-452: ledger equality is the
# signal, the judge verdict is kept for the checks)
```

Notes. The ids carry the style in brackets so transcripts do not overwrite each other. The unstyled copy is included
so the per-style line can say "passes unstyled, fails styled", which is the only reading that separates a style
hazard from a case the agent fails anyway. Concurrency stays 2 (the chat route answers 504 above that,
`SKILL.md:42`). `results/credits.log` (RC, 14:30 EDT line) says "STOP OpenAI usage", so local runs go through
`--provider claude` (`builder/sim.py:711`) until the user reopens OpenAI.

## 4. Measurement plan (cloud)

Agents: the Brief A agent (slot `brief-a`, the 10/10 PUB-A run) and the A+B agent (slot `brief-b`) scored on B's
cases only (`CLAUDE.md`: the practice set mixes two rule sets). Case sets: for the organisers' simulation
`public-test-set.json` (10 Brief A cases, RC); locally `tests/cases/brief-a-extended.cases.json` (the 42-case set of
`results/ext-a-v2.json`) and `tests/cases/brief-b-extended.cases.json`.

1. **Organisers' simulation, most faithful test.** `python3 tools/run_cases.py <brief-a agent_id> --brief A --reps 3 --style <s>` once per kit style (`pieces`, `corrects`, `talkative`, `asks_back`, `in_words`), run in the foreground one at a time (one simulation per workspace), 3-11 minutes each. It costs Freya credits: about 4 per 10-case run; the task's note says cap 50 with about 8 used, and `results/credits.log`'s last two lines (14:30 and 14:33 EDT) raise the allowance to USD 150 on Freya simulations and say to stop when the dashboard balance drops below 85.75; confirm which figure applies before the fifth run. Five styled runs at `--reps 3` is 15 simulation passes, roughly 60 credits; if that is too much, run `--reps 1` per style first (about 20 credits) and repeat only the styles that lose cases. Report per style: cases passed / 10, the failing case ids with the organisers' FAIL reason, the median slowest turn (the slow-run warning), and the call ids so the transcripts can be fetched with `freya.get_call`.
2. **Local, wide.** `python3 builder/sim.py brief-a --cases tests/cases/brief-a-extended.cases.json --styles all --concurrency 2 --provider claude --out results/brief-a-styles.json --transcripts results/brief-a-styles/` : 42 cases x (1 unstyled + 13 styles) = 588 calls, about 3 hours at concurrency 2 (ext-a-v2 took about 15 s per call); if too long, `--styles kit` first (252 calls). Same for `brief-b` on B's extended set. Report per style: passed / n, "passes unstyled, fails styled" ids, and the three model-call families that misfired (`[route]` lines in the transcripts: who/refusal/topic), so each loss maps to a hazard row above.
3. **Before and after each library change** (sections 5.1-5.6): the same command on the same cases and styles, paired, never against a remembered number (`docs/research/sota-techniques.md` T19). A change ships only when the styled pass count does not fall on any style and the unstyled count holds.
4. **Transfer check.** The builder's own output on an unseen brief (`tests/synthetic` C or D rebuilt by `builder/build.py`) with `--styles kit` on its extended cases, to make sure the fixes are library defaults the builder emits and not edits to a reference generator.
5. **Smoke on the platform for the hook.** After 5.2 lands: save the agent, then `builder/smoke.py` with turns 'four four seven one' and 'forty-four seventy-one' and assert the `verify_identity` body is '4471' (the hook has never run on the platform; B could not verify the 18.8 KB limit).

What a run cannot tell us: the final's mode (chat vs voice) and persona system prompt, whether hidden customers mix
styles, and how the organisers' expected ledgers treat a question back at an identity question under a brief whose
rule counts such a question as a refusal (A). The kit text "The facts stay the same" (`docs/kit-README.md:78`) is the
only statement, and the plan reads it as "the styled ledger equals the unstyled one".

## 5. Library and skill changes in priority order

Each item is brief-agnostic: it takes N, the date order, the wrong-answer limit, the refusal wording and the outcome
table from the brief/API through generator parameters, never from Brief A/B. None adds a runtime reviewer, a second
service, a blocking pre-hook, a capped promise, a `think` tool or a first code node.

### 5.1 Identity tool helper with a digits gate (hazard 1, 8) — lib + lint + sim, M
- `fl.identity_tool(api, field, question, n_digits=None, date_order='dmy', limit=..., hints=..., ...)`: wraps
  `api_tool(api, "verify_identity", baked={"field": field}, pre=fl.normalise_pre({"answer": "answer"}, date_order=...), post=fl.verify_count_post(...))`
  and, when the API description of the field gives a digit count (`tools/openapi.json:37` "four digits": parse the
  number word or digit with a regex over the field description; else the generator passes `n_digits`), appends to
  BOTH the tool description and the node's task text:
  `fl.latest_value_note(N)` + " Never call verify_identity with fewer than N digits or with words: say 'and the rest?' and wait, then join the parts."
- `normalise_pre` digits kind takes `n_digits`: when the joined digit string is longer than N keep the LAST N
  ("last four digits" semantics); when shorter leave it as is (the gate above keeps the call from happening).
- `fl.digit_extraction(name, N, desc)` added to the node's `extraction_schema` by the helper, with the task text
  "the extracted <name> is filled only when all N digits are in"; the prompt tells the model to call the tool
  when that variable is set. (`pre_process_code` cannot cancel a call, `docs/tools-and-code.md:395`, and an empty or
  absent answer is counted by the mock, so the gate must sit before the call.)
- Lint (`builder/lint.py`, `check_tools`, under `--rules`): ERROR when a `verify_identity` tool whose baked field is
  not a date has neither a digits `validation_pattern` extraction on the node nor the "fewer than" sentence in the
  tool description; WARN when an identity node's task text has no "in parts"/"wait for all" sentence.
- Smoke `builder/smoke_scripts/pieces.json`: turns "Hello?", "Yes, this is me", "44", "71"; expect
  `tools_not_called: [verify_identity]` after turn 3 and, after turn 4, a `verify_identity` call whose body `answer`
  matches `^[0-9]{4}$` (the smoke script format supports `tools_not_called`; a `body_matches` expectation is a
  small addition to `builder/smoke.py`).
- Tests: `builder/tests/test_normalise.py` negative cases ("44" unchanged, "" unchanged) and
  "my number is 0171 555 4471" -> "4471" with `n_digits=4`.

### 5.2 Normalisation as the `api_tool` default, and a non-numeric amount never retried (hazard 2, 10) — lib + lint, M
- In `fl.api_tool(...)`: when `pre` is not given, build `fl.normalise_pre({f: kind})` for every model-filled body
  field whose `_guess_kind` is one of `dob|date|amount|time|answer` (`builder/freyalib.py:1501-1513`), with
  `date_order` taken from a new module-level `fl.configure(date_order=..., relative_var=...)` the generator calls
  once from the brief; `pre=None` disables it explicitly; a given `pre` string is concatenated after the normaliser
  (the docstring at `freyalib.py:1540` already says the hooks are self-contained).
- `promise_pre`/`PROMISE_PRE` (and the multiproduct promise/note tools): after normalisation, if `amount` is still
  not a number or `date` not `YYYY-MM-DD`, do not touch the body (no URL/body rewrite that makes the bank reject it,
  per the Do-not list); instead the post hook's `what_to_do_next` says "The amount/date could not be read as a
  number/date. Do NOT retry: ask the customer to repeat it, read it back, then call create_promise again." and the
  `tool_failed_twice` route is preceded by a route on a `promise_unreadable` flag the post hook sets, so a words
  value never consumes the brief's single retry.
- Port `out/gen_brief-a_lib.py` and `out/gen_brief-b_lib.py` (the references the skill names at `SKILL.md:17`) and
  `builder/multiproduct.py` to the helpers, so Claude copies code that carries the hook.
- Lint ERROR (`--rules`): a conversation-node `api_call` tool with a model-filled field named `answer`, `amount`,
  `date` or `time` and no `_nz_main` in its `pre_process_code`.
- Skill sentence (replace `SKILL.md:27`): "Speech normalisation is on by default in `api_tool`; pass
  `fl.configure(date_order=..., relative_var=...)` once from the brief and never set `pre=None` on an identity,
  promise or callback tool."
- Tests: "<hundreds> and <tens>" amounts ("six hundred and thirty-seven and fifty"), digit-by-digit years
  ("one nine eight eight"), "half past ten" -> "10:30".

### 5.3 Question back is not a refusal; the decline counter resets on an answer (hazard 3) — lib + skill + sim, M
- `fl.refusal_extraction(name, question_counts=False)` template, description: "From the customer's LATEST message
  only: `refused` = they say they will not answer, do not want to talk, or hang up on the question; `question` = they
  ask something back instead of answering (why it is needed, who is calling, which account, what the call is about);
  `none` = they give an answer, part of an answer, or say anything else." When the brief says a question counts as
  declining (`rules.py` spec flag `question_counts_as_refusal: true`, quoted from the brief's own sentence), the
  generator routes `question` through the same counter; otherwise `question` goes to an `explain_<q>` passthrough
  that re-enters the ask node with a tts line built from the brief's permitted explanation.
- `verify_count_post` (`builder/freyalib.py:461`): on any `ok: true` result set `vars['decline_count'] = 0`
  (an answer, right or wrong, ends the refusal sequence; the wrong-answer counter is separate).
- Common identity prompt line (brief-agnostic, in ID_COMMON): "If they ask a question back, answer it in one
  sentence without naming the product, the amount or the reason for the call, then ask the same security question
  again."
- Skill step 4 sentence: "The refusal counter counts the brief's named deflection exactly (quote it in the enum
  description); a question the customer then answers is never a refusal unless the brief says so."
- Smoke `asks_back.json`: "Hello?", "Yes, this is me", "Why do you need that?", "<answer>" (the script's identity
  value), expect: no forbidden words after turn 3, the same security question re-asked, no `fin_*` route, and a
  `verify_identity` call after turn 4.

### 5.4 Confirm step before every write (hazard 4, 10) — lib + skill + sim, L
- Pattern `fl.offer_nodes(prefix, write_tool, ...)` generating: in the negotiate node two extraction entries
  `offer_amount` (number, min_confidence 0.6, "the amount the customer says they WILL PAY on this debt; the LAST
  value if they correct themselves") and `offer_date` (type date, "the day they say they WILL PAY; never another
  date they mention"); a code node `check_offer` that normalises both, validates against the calendar/floor
  variables the generator already computes, and writes `offer_ok` plus a `readback_text`; a conversation node
  `confirm_offer` whose on_enter tts is the read-back and whose extraction `confirm in {yes, no, change}` is
  described as "`change` = a different amount or date for THIS promise, NOT a request for a plan; `no` = they
  reject it"; `eq(confirm,'change')` back to negotiate with the flags reset, `eq(confirm,'yes')` to a node whose
  `create_promise` tool has `amount` and `date` baked as `{{offer_amount}}`/`{{offer_date}}` (the model never fills
  them). This is the T1 guard the Do-not list prefers over capping.
- Normaliser patch in `_NORM_SRC`: when the tokens after the last correction marker do not parse alone, parse the
  part before the marker and replace one component: a bare day number (ordinal or digits, 1-31) replaces the day, a
  month name the month, a 2/4-digit year the year; for times a bare number replaces the minutes; for digits a shorter
  group replaces the tail when `n_digits` is set. Tests: both organisers' literal examples
  ("the 21st, sorry, I mean the 20th" with a month in the earlier value; "14 March 1988, sorry, 1989").
- Skill sentence: "Every write tool is reached only from a confirm node whose read-back repeats the LAST value the
  customer gave, with weekday, day and month; the tool body for amount and date is baked from the extracted offer
  variables, never model-filled."
- Cases: generated case sets get a `corrects` and a `corrects_late` variant of every promise case (`builder/cases.py`
  writes a `style` field, which `persona_for` honours).

### 5.5 Enum descriptions that survive small talk (hazard 5) — lib + skill + sim, S
- `fl.who_desc(confirm_words, deny_words)` template: "`customer` = a yes or their own name anywhere in the
  message, even after small talk ('what a morning... yes, speaking'); `other` = <the brief's third-party words>;
  `unclear` = a question or a greeting with no yes." Filled from the brief's words (SKILL.md step 3).
- Topic descriptions (template sentence appended by `fl.topic_desc`): "only when the customer says it about
  THEMSELVES as the reason they cannot pay this debt; small talk about work, family events, weather or other bills
  is `none`."
- Keep the brief's second-ask closure but route it on `eq(who2,'unclear')` or `is_not_set(who2)` explicitly instead
  of a bare `always`, so the transcript shows why it closed.
- Smoke `talkative_opening.json`: "Hello?", "Sorry, awful day, traffic was terrible. Yes, this is me." must reach a
  security question.

### 5.6 Attempts counted in code (hazard 6) — lib + lint, M
- In negotiate: `fl.ext("stance", ["refusal", "offer", "none"], "From the LATEST message: `refusal` = they say they
  cannot or will not pay anything now and name no amount or day; `offer` = they name an amount or a day; `none` =
  anything else")`; `eq(stance,'refusal')` -> code node `count_attempt` running
  `counter_code('attempts_used', attempts_n, 'attempt_route')` and writing `vars['next_offer_text']` from the
  code-built attempt lines the generators already compute (`out/gen_brief-a_lib.py:99-102` pattern, values from the
  brief); `eq(attempt_route,'retry')` back to negotiate with the next offer as on_enter tts, `'close'` to the
  brief's refused ending. The model never decides how many attempts remain and never repeats a refused offer.
- Lint WARN (`--rules`): a conversation node whose task text contains "attempt" and no outgoing transition routes on
  a counter variable.

### 5.7 Builder and trace (hazard 0) — skill + build, S
- `SKILL.md` step 7: add `pieces.json`, `asks_back.json`, `talkative_opening.json` to the sequential smoke list
  (brief-agnostic expectations; adapt only where the brief's wording differs).
- `SKILL.md` step 9 / build.py: when a cases file exists and more than 8 minutes remain after the unstyled round,
  run `python3 builder/sim.py <slot> --cases <file> --styles kit --concurrency 2 --only <the five highest-value
  passing cases, one per style>` (the in-build mutation of `docs/research/sota-techniques.md:445-452`) and treat a
  "passes unstyled, fails styled" case like any FAIL; log the style in the trace line.
- `results/log.jsonl` rows gain `styles` (list) so the score history separates styled from unstyled runs.

### 5.8 Stage default for close_call (hazard 9) — lib, S
- `SETUP_CODE` extra: `vars['outcome'], vars['reason'] = <stage default from the brief's not-reached/unconfirmed row>`
  (generator parameter, read by `rules.py` from the outcome table); the verified stage's prepare node overwrites it
  with the brief's "no promise" default; every `fin_*` node overwrites it again. `close_call` then never depends on
  a model fill after a hang-up.

## 6. Verification and what happened next (added 10 Oct 19:00 UTC)

Two adversarial verifiers (code lens, rules-and-scoring lens) checked the plan. Corrections that stand:
- The default architecture is now `builder/policy.py` (v3 generators `out/gen_brief-a_v3.py`, `out/gen_brief-b_v3.py`): sections 5.4 (confirm step) and 5.6 (attempts in code) are implemented there. One real bug was found and fixed: the confirm node listed the topic routes before `confirm=change`, so a changed amount at the read-back could still become a restructuring transfer (fixed in `policy.py`, commit 0205826).
- The normaliser (`normalise_pre`, `digit_extraction`, `latest_value_note`) is still attached nowhere, including v3. The organisers' simulator shows the dialogue model converts words and parts on its own (pieces 9/10, corrects 9/10 on the v2 reference), so attaching it is not urgent; `n_digits` must keep the LAST N digits if it is ever attached.
- Hazard 1 (half numbers to `verify_identity`) is lower than ranked: pieces scored 9/10 on Freya.
- Section 5.3 as written would over-apply: a question back at an identity question counts as a deflection when the brief says so (Brief A rule 15 counts cumulatively, no reset). The library must not reset counters or reclassify questions on its own; the brief's definition goes first in the enum description.
- Section 5.8 (a staged default outcome for hang-ups) is not in any brief: dropped.
- The measurement plan's cost figures were guesses; the dashboard balance is the only credit reading (USD 235.75 at 18:33 UTC, floor 85.75).
- The hidden final uses text chat (site: "text, not audio"), so ASR-style noise is not a target; persona-model truncation is (seen on Freya: cut-off turns such as "I'm actually planning for my cousin's wedding on").

Measured on the organisers' simulator (v2 reference, Brief A public cases, one rep): pieces 9/10 (PUB-07: asked three times for the exact day), corrects 9/10 (PUB-07: the persona's cut-off "five hundred" was recorded as 500, a persona artefact), **talkative 5/10**: three calls closed `not_verified/declined` because small talk and cut-off turns at the second security question were read as refusals, one transferred to restructuring on "How much can I pay instead?", one said sympathy twice (once for a busy day).

Applied (commits ab94e05, 5b59d75): `PERSONA_CONDUCT` system-prompt lines via `assemble(..., conduct=True)`, `REFUSAL_NONE_CLAUSE` and `PLAN_REQUEST_CLAUSE` for the enum descriptions, used by both v3 generators and required by the skill. Still open: generic smoke scripts for small talk and a question back; extra simulator styles need `mock_case` handling in `sim.py` for the public cases (0 of 13 carry it).

### Later on 10 Oct (19:00-19:30 UTC), from the first v3 runs on the organisers' simulator
- v3 Brief A public x1: **9/10**. The miss: "Am I talking to a robot? I can pay on that" was accepted (stance accept -> code -> read-back tts) and the question was never answered. Fix: `Policy(asides=...)` (commit 97a8c70): an `aside` extraction on the negotiate/confirm/hardship/wrap-up nodes and the brief's answer prefixed in code to the spoken line.
- v3 Brief B public x1: **2/3**. PUB-12: the platform's `date`-type extraction resolved "tomorrow" with the REAL clock (11 October during a call set on 14 October); the agent said "Sunday 11 October has already passed" eight times, recorded nothing and noted all three products refused. Fix (commit 5dc92e4): `offer_when` (the customer's own words) extracted alongside `offer_date`, resolved in code against the call's `today_iso` (`resolve_when`: today, tomorrow, this/next weekday with the brief's rule, the 23rd, the sixth of November, in two weeks, vague periods); an extracted date before today with no words is treated as vague. This is a platform hazard for EVERY brief: never trust a date-type extraction for relative words.
- Open: a guard against repeating the identical spoken line more than twice (PUB-12 repeated the same sentence eight times before the loop cap); the next check of PUB-12 is the queued `brief-b-v3 public B x3` run (out/freya/b-v3-x3.json when it lands).
- v3 Brief A public **x3: 7/10** (pass^3), measured while the agent was being re-published (versions 6-8). The three misses: PUB-01 rep 1 "Saturday 10 October has already passed" eight times (the real-clock date for "today"; fixed in v8 by `resolve_when`); PUB-04 rep 2 a 62-second platform stall after "Yes, I confirm" (the node never routed, the platform spoke its Turkish filler "Bir saniye lütfen", the customer hung up: a slow-model incident of the kind the organisers discard and repeat); PUB-07 rep 3 the holiday date case looped into service_error (call log too large to fetch; the date fix is the likely cause). A second x3 pass on the fixed versions is queued (out/freya/a-v3-x3-fixed.json, b-v3-x3-fixed.json).
- Styled runs on the fixed v3 (organisers' simulator, one rep each): **talkative 9/10** (was 5/10 on v2), **asks_back 8/10** (was 4/10), **corrects 8/10**. The asks_back and corrects misses exposed two platform behaviours, both fixed in commits 2158ed4/6986b7e: (1) a code node's variable writes are schema-validated and silently rejected when invalid (our clears wrote '' into date/float variables and 'none' into enums without that member), so stale `offer_date`/`offer_amount` survived and re-fired the offer check: PUB-10 looped, PUB-06 recorded the stale 2125 instead of the agreed 637.50 floor; (2) `min_confidence` 0.6 discarded "Yes, I confirm." extracted at 0.59, so the read-back never routed to the record node. Clears now write the enum's own neutral member and sentinel values (1900-01-01, 0) that the core treats as empty; the confidence floor is 0.5. The in_words run and the final three-rep pass are the first fully on the fixed version.

### Hidden-path rehearsal (cloud, 20:16-20:45 UTC, `out/rehearsal-hidden.REPORT.md`)
`build.py` on Brief A under an unknown name: 21 min 15 s total, 20 generated cases (19 high confidence), agent's own run 14/19, export valid, trace complete except the killed sim's per-case lines. Pipeline defects found and fixed on main: the audit crashed on Linux (system prompt too large for the command line; now the context goes through the message and the digest prints the shared policy core once: 872 KB -> 159 KB); the generated-case run was wrapped in a `timeout` by the agent and lost its summary (sim.py now flushes per line and writes `--out` after every case; the skill says never to use `timeout` and to run the high-confidence identity and promise cases first); the simulator's Claude customer is Sonnet now, not Haiku (4 of 10 kit cases failed on Haiku going off script). Agent bugs the generated cases found on Brief A: the opening must be ONE sentence when the brief says "first sentence"; "ask once for another time" counted in the prompt; a human request at an identity question read as a refusal; "I don't know the exact day" read as a refusal instead of a vague offer. The skill now states all four; the v3 extended sweep and the Brief C transfer test (cloud, running) take the library side.
- 21:10 UTC: after the day-number fix, PUB-07 (with PUB-01 and PUB-04) passed **3 of 3** on the organisers' simulator (`out/freya/a-v3-pub07-x3.json`). Together with the clean three-rep run (9/10, PUB-07 the only miss) and Brief B's 3/3 twice, every one of the 13 practice cases now passes all three runs on the current v3 version. A final whole-set three-rep certification of both agents is planned once the v3 extended sweep and the Brief C transfer test have been merged.
