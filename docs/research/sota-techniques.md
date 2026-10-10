# State-of-the-art techniques for the builder and the phone agents it builds

Research worker note, Saturday 10 October 2026 (cloud session; no Freya or OpenAI calls were made). Written for the
person who improves `builder/`, the skill and the library before Sunday 17:00 UTC.

**What this is about.** We ship a builder (Claude Code + `builder/freyalib.py` + `builder/multiproduct.py` + the
`build-phone-agent` skill) that turns one brief and one tool API file into a Freya workflow in under 30 minutes, with
no practice cases. Each turn of the phone agent is three calls on a fixed shared model: extraction → routing →
dialogue. It is scored on 60 hidden cases × 3 reps, all 3 must pass (ledger exact AND judge happy), with customers
who split numbers, correct themselves, talk off-topic, ask questions back and say amounts and dates in words.

**How the evidence was gathered and how far to trust it.** The egress proxy blocked arxiv.org, export.arxiv.org,
alphaxiv, huggingface, openreview and most vendor docs (DNS failure or 403 on CONNECT). The numbers below therefore
come from:
- **[R]**: read directly. The Anthropic engineering blog; the `sierra-research/tau-bench` and
  `sierra-research/hyper-tau-bench` GitHub repos (the leaderboard JSON was read from a clone); the PolicyGuard and
  PolicyGuide READMEs.
- **[S]**: search-engine extracts of the paper's abstract or body. Probably right, but not checked against the tables.
- **[V]**: vendor claim.
- **[M]**: the researcher's prior knowledge of a well-known paper, not re-checked in this session.

Where sources disagree, both numbers are given. Every claim carries a link; check a number before quoting it outside
this repo.

---

## 0. Ten facts that should drive every decision

1. **pass^3 is unforgiving.** Per-case reliability p becomes p³: 0.80 → 0.51, 0.90 → 0.73, 0.95 → 0.86, 0.98 → 0.94.
   On τ-bench retail, GPT-4o tool-calling falls from pass^1 0.604 to pass^4 0.383; airline falls from 0.420 to 0.200
   ([tau-bench leaderboard](https://github.com/sierra-research/tau-bench) [R];
   [Yao et al. 2024, arXiv 2406.12045](https://arxiv.org/abs/2406.12045)). Moving p from 0.90 to 0.97 on every case
   is worth more than fixing one hard case.
2. **External, state-aware enforcement gives the largest measured gains on τ-style tasks.** Two examples:
   - PolicyGuide compiles the policy into a workflow graph with a gate on writes. τ²-bench, GPT-5.4, mean pass^4
     0.42 → 0.62; telecom 0.25 → 0.675 ([arXiv 2608.19861](https://arxiv.org/abs/2608.19861),
     [repo](https://github.com/erjui/PolicyGuide) [R mechanism / S numbers]).
   - STAGE puts deterministic control in code with policy-scoped nodes: up to +55 points pass^3 on τ²-telecom
     ([arXiv 2608.22538](https://arxiv.org/abs/2608.22538) [S]).

   Our architecture is already of this kind. The remaining gains come from moving the last decisions still left to
   prompts into code, routes and tool gating.
3. **Argument-only guards miss most rules.** Most airline policy rules depend on the dialogue or on an earlier read,
   not only on the arguments of the call ([PolicyGuard, arXiv 2606.29225](https://arxiv.org/abs/2606.29225) [S]).
   A guard must read the state (what was offered, refused or confirmed), not only the body of `create_promise`.
4. **A wrong guard hurts.** A gate that is wrong on some state pushed a 35B agent below its no-gate baseline
   ([arXiv 2609.25686](https://arxiv.org/abs/2609.25686) [S]). Gate only what code can decide exactly from the brief.
5. **ττ-bench: reading the records decides the score, and build time does not.**
   - Codex + GPT-5.6-terra built in 30 minutes and scored 18.0. Claude Code + Opus 5 built in 216 minutes and scored
     23.9. The expert reference scored 82.2 ([hyper-tau-bench leaderboard JSON](https://github.com/sierra-research/hyper-tau-bench) [R]).
   - The gap is almost all in banking_knowledge (5.9 against 79.8), where developers opened fewer than 80 of about
     1,700 files.
6. **Self-authored probes miss held-out branches.** In ττ-bench's worked example, all ten of a developer's own probes
   passed, yet two-fifths of the held-out suite failed on policy branches those probes never reached. The submission
   scored 59.7% against an 85.8% ceiling ([ττ-bench, arXiv 2609.04611](https://arxiv.org/abs/2609.04611) [S]).
7. **The "one hint doubled the score" result is a single probe.** In a telecom probe, the hint "route by intent,
   review tool calls" took one developer from 31% to 67%. No task, model or run count is reported, so treat it as
   exploratory (ττ-bench, search extract [S]).
8. **Many instructions in one prompt fail together.** Following all of n instructions ≈ p^n. With 10 instructions,
   GPT-4o followed all of them about 15% of the time ([Curse of Instructions, ICLR 2025](https://openreview.net/forum?id=R6q67CDBCH) [S]).
   Instruction-following decays early and steeply on non-reasoning models, mostly through omissions, with a primacy
   bias ([IFScale, arXiv 2507.11538](https://arxiv.org/abs/2507.11538) [S]). The fixed serving model is a fast model:
   keep each node's prompt to a handful of rules.
9. **Self-correction is the hardest speech phenomenon.**
   - On Full-Duplex-Bench-v3, the best system passes fewer than 59% of self-correction scenarios. Overall it reaches
     tool accuracy 88.7 but argument accuracy 71.6, so slot values break more often than tool choice
     ([arXiv 2604.04847](https://arxiv.org/abs/2604.04847) [S]).
   - Disfluent questions cut F1 from 89.6 to 61.6, because models latch onto the first entity mentioned
     ([Disfl-QA, arXiv 2106.04016](https://arxiv.org/abs/2106.04016) [S]).
10. **LLM simulators are too cooperative.**
    - Swapping the user model moves τ-retail success by up to 9 points
      ([Lost in Simulation, arXiv 2601.17087](https://arxiv.org/abs/2601.17087) [S]).
    - Simulated non-buyers show half the real resistance (25.1% → 13.5%)
      ([arXiv 2606.20708](https://arxiv.org/abs/2606.20708) [S]).
    - 24.4% of successful simulated episodes contain premature disclosure by the user
      ([UserProxyBench](https://www.opentrain.ai/papers/userproxybench-evaluating-llm-user-simulators-for-agent-benchmarks-and-training--arxiv-2609.38043/) [S]).

    So our `sim.py` pass rate overestimates the hidden score unless we add uncooperative personas.

---

## 1. Policy-following conversational agents (τ-bench, τ²-bench, τ-Knowledge, SOPBench, SOP-Bench)

### T1. Policy as code: gate the write tool on code-checked state (offer guard) — **P0**
- **Source.** Three related systems:
  - PolicyGuide ([arXiv 2608.19861](https://arxiv.org/abs/2608.19861), 2026): policy compiled into a frozen workflow
    graph, step check at every user turn, one-shot gate on writes.
  - ToolGuard ([arXiv 2507.16459](https://arxiv.org/abs/2507.16459), IBM, EMNLP 2025 Industry): policy compiled into
    per-tool Python guards.
  - Blueprint First ([arXiv 2508.02721](https://arxiv.org/abs/2508.02721), 2025).
- **Effect.**
  - PolicyGuide, mean pass^4 on τ²-bench with GPT-5.4: 0.42 → 0.62.

    | Domain | ReAct | PolicyGuide |
    |---|---|---|
    | Airline | 0.46 | 0.62 |
    | Retail | 0.575 | 0.725 |
    | Telecom | 0.25 | 0.675 |

    The abstract gives a telecom baseline of 0.19.
  - ToolGuard, τ²-airline pass^4: 0.46 → 0.52 (third-party re-run).
  - Blueprint First: +10.1 points pass^1 on τ-bench. [S]
- **What we do today.** `negotiate` (in `out/gen_brief-a_v2.py`) is one large prompt. The model checks the date
  against the calendar, the amount against the floor, decides whether the read-back was confirmed, and only then calls
  `create_promise`. `promise_pre` only casts types; `multiproduct.promise_pre_code` silently caps the date and amount.
  The cap protects the ledger but can contradict what was read back to the customer, which the judge sees.
- **Apply (freyalib + skill + reference generators).**
  1. Add `fl.offer_guard(...)`. In the negotiation node, extract `offer_date` (`type: "date"`), `offer_amount`
     (`float`) and `offer_kind` (enum `exact|vague|none`), with `min_confidence` around 0.6.
  2. Add a transition `is_set(offer_date) or is_set(offer_amount)` → code node `check_offer`. It computes, from the
     brief's parameters, `offer_verdict ∈ {ok, weekend_or_holiday, after_deadline, below_floor, above_full, vague}`
     and `offer_text`, a finished sentence ("Saturday 17 October is not possible; the next business day is Monday
     19 October."). It then clears the extracted variables and routes `ok` → `confirm_<pid>`, anything else back to
     `negotiate`. The prompt there reads `{{offer_text}}`.
  3. Only `confirm_<pid>` carries the `create_promise` tool. Its tts on_enter reads the code-built read-back and asks
     the brief's confirmation question, and it extracts `confirm ∈ {yes, no, change}`. The tool is made available
     only when `confirm == yes` is routed (or the tool description says to call it immediately). `change` goes back
     to `check_offer`.
  4. `promise_pre` asserts `body == (pending_pid, offer_amount_ok, offer_date_ok)`, the values code approved, instead
     of capping.
- **Expected impact.** This addresses the hardest practice families: dates (PUB-04, PUB-07), amounts (PUB-06) and
  multi-product (PUB-12, PUB-13). On a 30-customer hidden brief perhaps a third of cases go through a counter-offer.
  Estimate +3 to +6 cases per brief through better p on those cases.
- **Cost.** About 2–3 hours of library work plus a port of both reference generators, and about 1 minute of builder
  time per build, since it is parameterised like `products_facts_code`.
- **Risk.**
  - Date extraction converts "next week" into a concrete date (`docs/workflow-format.md`, Extraction schema). The
    `offer_kind` enum must catch vague periods first, and the guard must treat `vague` before reading the date.
  - Extra node hops add latency.
  - A loop between `check_offer` and `negotiate` needs a counter exit.
  - Port behind `compare_*` checks before relying on it.

### T2. Attempt and refusal counters in code, not in the prompt — **P0**
- **Source.**
  - StateFlow, states with deterministic transitions ([arXiv 2403.11322](https://arxiv.org/abs/2403.11322), COLM 2024):
    +13% on InterCode-SQL and +28% on ALFWorld over ReAct, at 3–5× lower cost [S].
  - Task-state gate ([arXiv 2609.25686](https://arxiv.org/abs/2609.25686)): a 235B model's pass^1 went 0.39 → 0.54
    when state decided writes [S].
  - ARQ ([arXiv 2503.03669](https://arxiv.org/abs/2503.03669)): the largest gain was on "re-applying a guideline
    later in the call" [S].
- **Apply (freyalib, multiproduct, skill step 3).**
  - Extract `stance ∈ {refuse, too_much, offer, accept, other}` each turn in `negotiate`.
  - `stance == refuse` → `count_refusal` code node (the existing `counter_code`). It increments
    `attempts_used_<pid>`, writes `next_offer_text` from the brief's attempt ladder (precomputed in `prepare`), and
    routes `exhausted` → the refused fin (or the per-product note in multi-product briefs).
  - Remove "count your attempts" from the prompt. The prompt only says "Say: {{next_offer_text}}".
  - Same for "said twice they do not want to talk" and "declines the security questions twice".
- **Impact.** Removes the `intent_tool("fin_refused", ...)` judgement, the single most model-dependent exit. That
  improves p on the refusal, hardship-decline and persuasion families: +2 to +4 cases per brief.
- **Cost.** About 1–2 hours of library work; no build-time cost.
- **Risk.**
  - The extractor misclassifies "I can't pay all of it" as `refuse` instead of `too_much`. The enum descriptions must
    come from the brief's own definitions: rule 29 says a proposed date or amount is never a refusal.
  - Double counting when routing runs again after a tool result: reset `stance` in the counter code.

### T3. Canonical facts reach the model as finished text (input reformulation / ARQ) — **P1**
- **Source.**
  - IRMA ([arXiv 2508.20931](https://arxiv.org/abs/2508.20931), EMNLP 2025 Findings): each step's input is rewritten
    with the relevant constraints, a memory of the task state and tool suggestions. pass^5 rose 12.7–16.1% over
    function calling and ReAct on τ-bench [S]. The paper's abstract and body give different gaps.
  - Attentive Reasoning Queries ([arXiv 2503.03669](https://arxiv.org/abs/2503.03669), Parlant, 2025): 90.2% against
    86.1% (CoT) and 81.5% (direct) on 87 scenarios, GPT-4o, 5 runs [S].
- **Apply (freyalib `what_next_post`, prepare code).**
  - Every code node and hook already writes facts. Add one variable, `state_line`, rewritten by every counter, guard
    and hook. For example: "Product 2 of 3: personal loan. Offers already refused: full amount today, full amount on
    Friday 16 October. Next allowed offer: floor 120.00 on Thursday 22 October. Nothing recorded yet."
  - Put `{{state_line}}` first in the negotiation `task_message` (primacy, see T20) and in `what_to_do_next`.
- **Impact.** Fewer repeated or forbidden offers (brief A rule 31) and fewer wrong product references in multi-product
  calls: +1 to +3 cases per brief.
- **Cost.** About 1 hour. A slightly longer prompt.
- **Risk.** A stale `state_line` if one writer forgets to update it. Generate it in one helper called by every writer.

### T4. "Think" scratchpad with domain examples — **P2 (phone agent), P0 (builder)**
- **Source.** Anthropic, "The think tool" (2025, [blog](https://www.anthropic.com/engineering/claude-think-tool)) [R].
  - Airline pass^1: baseline 0.332, think alone 0.404, extended thinking 0.412, think + optimised prompt with domain
    examples 0.584. The article text says 0.370 → 0.570, +54%.
  - Airline pass^5: 0.100 → 0.340.
  - Retail pass^1: 0.783 → 0.812.
  - Most of the gain came from the domain-specific examples. The December 2025 update recommends extended thinking
    over a think tool in most cases.
- **Phone agent.** We cannot change the serving model, and every extra tool call is a full model turn of latency
  (CLAUDE.md: a median slowest turn above 10 s lowers the score). A `code_exec` think tool exists
  (`docs/tools-and-code.md`, `code_exec` as a tool), but T1–T3 deliver the same "check the rules before acting"
  deterministically. → P2. Do not add it unless a transcript shows the agent acting without checking.
- **Builder.** The builder model (Claude, `build.py`) should get the think-tool lesson: worked examples of the
  mapping. Add one compact worked example to `SKILL.md` step 3 showing one rule traced to its code node, route, hook
  and prompt sentence (taken from a synthetic brief, not A/B values). Also run the builder with extended thinking on;
  that is already the case with Opus 5.5 by default, so verify it in `ClaudeAgentOptions`.

### T5. Native tool calling, no ReAct text reasoning in the dialogue call — **keep (no change)**
- **Source.** τ-bench leaderboard [R]. Airline gpt-4o pass^1: tool calling 0.420, Act 0.365, ReAct 0.325. Pass^4:
  0.200, 0.140, 0.160.
- **Apply.** Freya already uses native tool calls. Do not add "think step by step before answering" lines to
  `task_message`. They add latency and showed no gain in this harness.

### T6. Tool availability is policy: each write tool lives only in the node that may write — **P0 (lint check)**
- **Source.**
  - SOP-Agent ([arXiv 2501.09316](https://arxiv.org/abs/2501.09316)): the model chooses only among the current node's
    out-edges and tools [S, self-made benchmark].
  - SOP-Bench ([arXiv 2506.08119](https://arxiv.org/abs/2506.08119)): with a bloated tool registry, agents call the
    wrong tool almost always [S].
  - PolicyGuide's one-shot gate (T1).
- **Apply (`builder/lint.py`).** Add a deterministic check. No write tool (`create_promise`, `add_note`,
  `schedule_callback`, `transfer_to_agent`) may appear in any node reachable from the initial node without passing
  through the identity-verified route, except where the inventory allows it: callbacks before identity, a human
  transfer during identity. The allowed pre-verification tools come from `rules.json` categories `third_party` and
  `identity`. Emit ERROR otherwise.
- **Impact.** Prevents the worst class of failure (a write before verification, or debt disclosure) that a generator
  bug could introduce on a hidden brief. Mostly insurance; perhaps 0–2 cases.
- **Cost.** About 1 hour. No build time.
- **Risk.** False positives when a brief legitimately allows a tool early. Make the allow-list come from the
  inventory, and WARN rather than ERROR for tools the inventory does not mention.

### T7. Pre-execution LLM reviewer of tool calls — **Do NOT (on the phone agent); P1 as a build-time audit**
- **Source.**
  - PolicyGuard ([arXiv 2606.29225](https://arxiv.org/abs/2606.29225)): τ²-airline pass^4 +6 to +12 points [S].
  - Reinforced Agent ([arXiv 2604.27233](https://arxiv.org/abs/2604.27233)): τ²-bench with GPT-4o 48.7 → 55.8 [S].
    A reasoning-model reviewer fixed three errors for every correct call it broke.
- **Why not on the phone agent.** A runtime reviewer is another model service, but the phone agent may call only the
  bank's tool API ("A call to any other service fails the case"). It also adds latency.
- **Apply at build time instead.** `builder/audit.py` already plays this role statically, and T15 adds a transcript
  reviewer over the self-tests.

### T8. Constrained tool arguments (enums, schemas) — **keep; extend to validation_pattern** — **P0 (small)**
- **Source.**
  - XGrammar-2 ([arXiv 2601.04426](https://arxiv.org/abs/2601.04426)): constrained decoding removes malformed calls
    on BFCL [S].
  - "Brief Is Better" ([arXiv 2604.02155](https://arxiv.org/abs/2604.02155)): constraints do not fix valid but wrong
    arguments [S].
  - Freya docs: enum on the leaf plus the values listed in the description (`docs/tools-and-code.md`, Constrain
    model-filled parameters).
- **Apply.** `api_tool` already copies enums from the spec. Add three things:
  1. Product ids never model-filled. They are baked from `pending_pid` (multiproduct does this).
  2. `validation_pattern` + `max_retries: 2` on digit-like extractions (T13).
  3. In `lint.py`, an ERROR when a model-filled field has an enum in the spec but not in the workflow.
- **Impact.** Insurance against schema drift on the hidden tool API, which can change fields and enums (kit README).
  0–2 cases.
- **Cost.** Under 1 hour.
- **Risk.** Low.

### T9. Few-shot exchanges inside node prompts — **P1**
- **Source.**
  - The think-tool examples (T4) carried most of that gain.
  - StateFlow: rewriting examples to follow the workflow alone gave +7% [S].
  - Retell recommends "transition finetune examples" for misfiring transitions ([docs](https://docs.retellai.com/build/conversation-flow/transition-condition) [V]).
- **Apply (skill step 3).** For each extraction enum whose misclassification changes the outcome (`who`, `topic`,
  `stance`, `confirm`), have the builder write 3–5 short labelled examples into the enum `description`. They must be
  drawn from the brief's own wording: "Only 'yes', 'that's me', 'speaking' counts". Put them in extraction
  descriptions rather than the dialogue prompt, so routing gets them and the dialogue model does not parrot them.
- **Impact.** Better routing on edge phrases. +1 to +2 cases.
- **Cost.** Builder tokens only.
- **Risk.**
  - Examples leaking A/B content. The skill must say "from this brief only".
  - Longer extraction prompts add latency.

---

## 2. Agent-building meta-systems: what transfers to a 30-minute single-shot build

### T10. Do not run search-based agent optimisation at build time — **Do NOT**
- **Source.** Every one of these needs a scored validation set and 10²–10⁴ evaluations:
  - ADAS ([arXiv 2408.08435](https://arxiv.org/abs/2408.08435)): +13.6 F1 on DROP; about 25–30 iterations on about
    128 validation examples [M].
  - AFlow ([arXiv 2410.10762](https://arxiv.org/abs/2410.10762)): +5.7% average, about 20 MCTS iterations × 5 runs [M].
  - AgentSquare ([arXiv 2410.06153](https://arxiv.org/abs/2410.06153)): about +17% [M].
  - Darwin Gödel Machine ([arXiv 2505.22954](https://arxiv.org/abs/2505.22954)): SWE-bench 20 → 50%, over weeks of
    compute [M].
  - MaAS, OPRO, Promptbreeder, MIPROv2 ([M]).
- **Why.** Hidden briefs have no cases, so our self-generated cases are the only signal, and they encode our blind
  spots (fact 6). A search would overfit to them. The ττ-bench leaderboard also shows that 7× more build time bought
  only +6 points (fact 5).

### T11. Use the offline equivalent: library priors and an FSM skeleton (MetaAgent) — **already done; keep investing**
- **Source.** MetaAgent ([arXiv 2507.22606](https://arxiv.org/abs/2507.22606), ICML 2025) builds a finite-state
  multi-agent system from the task description alone, with no training data. It is comparable to hand-designed
  systems [S].
- **Apply.** `freyalib` + `multiproduct` is exactly this. Spend the remaining pre-Sunday time making the library
  cover more brief variations (T1, T2, T13, T14) rather than making the builder smarter at writing prompts. Every
  decision moved into a parameterised helper is a decision the builder cannot get wrong on Sunday.

### T12. One or two reflective repair rounds on rich traces (GEPA / TextGrad-style) — **P1 (already in skill step 9; extend to no-case briefs)**
- **Source.**
  - GEPA ([arXiv 2507.19457](https://arxiv.org/abs/2507.19457), ICLR 2026) reflects on natural-language traces. It
    beats GRPO by 6–10% on average with up to 35× fewer rollouts, and beats MIPROv2 by more than 10% [S]. It still
    needs about 100–500 evaluations.
  - On a simplified τ-bench, GEPA took Gemini 2.5 Flash from 73.9 to 82.6 (retail) and from 65.3 to 79.2 (airline)
    ([arXiv 2605.14443](https://arxiv.org/abs/2605.14443) [S]).
  - Coding agents used as prompt optimisers match GEPA on τ²-retail: 40.0 against 39.2
    ([arXiv 2609.26261](https://arxiv.org/abs/2609.26261) [S]).
- **Apply (`build.py`, skill step 9).** When no cases file is given, the skill stops at smoke and audit. Add a step:
  run the generated rule-branch cases (T16) through `sim.py` once. Claude reads each failed transcript and maps the
  failure to a rule id. It fixes the generator only when the failure is a deterministic agent error (wrong route, a
  missing tool, a wrong fact in a code-built line), not when the expected ledger itself is uncertain. At most 2
  rounds.
- **Impact.** Catches generator bugs that lint and audit cannot see, such as a route that never fires or a hook that
  throws. +1 to +4 cases per brief, mostly on brief-specific branches.
- **Cost.** About 6–10 minutes of the 30, at roughly $1–3 for simulator and judge calls.
- **Risk.**
  - Chasing simulator noise. Mitigation: fix only failures that reproduce, or whose cause is visible in the engine
    events.
  - Running out of time. Save before the round (already the rule).

---

## 3. Specification recovery from unstructured and conflicting records

### T13. Rule inventory by self-consistency: sample 3, union, flag minority rules — **P0**
- **Source.**
  - Self-consistency ([Wang et al. 2022, arXiv 2203.11171](https://arxiv.org/abs/2203.11171)): +17.9 points on
    GSM8K, with most of the gain in the first 5–10 samples [M].
  - Universal Self-Consistency ([arXiv 2311.17311](https://arxiv.org/abs/2311.17311)): the model itself picks or
    merges free-form outputs [M].
  - ττ-bench: shallow reading is failure mode #1 (fact 5).
- **Apply (`builder/rules.py`).**
  1. Run the extraction call 3× in parallel (`asyncio.gather`), with different document orders: forward, reverse,
     and memo first.
  2. Merge with one USC-style call: "union these inventories; a rule present in only one is kept with
     `confidence: low`; where values differ, list both".
  3. The existing deterministic self-check (every numbered rule cited, every ISO date and every backticked token
     present) runs on the merged result.
  4. Low-confidence or conflicting rules go into a short `out/<slot>.rules.conflicts.md` that the skill tells Claude
     to resolve first by re-reading the source sentence.
- **Impact.**
  - Highest value on the raw-material hidden brief (mail + extract + memo + code list), where one missed or
    superseded rule fails a whole case family.
  - It also guards the clean brief against a single unlucky extraction.
  - Estimate +1 to +4 cases on the raw brief.
- **Cost.** Wall time about 90 s instead of 60–75 s (parallel), at roughly $0.75–1.00 instead of $0.25–0.30.
- **Risk.** Union adds spurious rules from hallucinated samples. These are flagged low-confidence and must quote a
  source sentence (T15) to survive.

### T14. Dated-decision resolution as an explicit multiple-choice step — **P0**
- **Source.**
  - evolveQA ([arXiv 2510.19172](https://arxiv.org/abs/2510.19172)): models give outdated answers to open questions,
    but pick the current one when shown the dated options side by side [S].
  - HoH ([arXiv 2503.04800](https://arxiv.org/abs/2503.04800)): outdated passages pull models to wrong answers even
    when the current evidence is present [S].
  - ττ-bench evidence generator ([hyper-tau-bench repo](https://github.com/sierra-research/hyper-tau-bench),
    `src/tau2/hyper/transformations/`) [R]:
    - It plants decision arcs `superseded* → final_current`, with statuses `proposal | rejected | superseded | final_current`.
    - It plants distractors that look current (`distractor_current`).
    - It plants "open gaps" where the final ruling never lands.
- **Apply (`builder/rules.py`, second pass).**
  - For every rule topic that has more than one candidate statement (same category, overlapping values), emit a block
    containing:
    - the topic;
    - each candidate, with its document, date, author role and status words ("proposal", "we decided", "from
      <date>", "effective");
    - the `now` of the calls, if the brief gives it, since an effective-from date after `now` is not yet in force.
  - Ask one call: "Which is in force for calls on/after the effective date? Answer with the candidate id and the
    quoted deciding sentence; proposals, rejected options, discussion and distractors decide nothing; if the latest
    discussion never decided, the last decided rule stays in force."
  - Store `in_force`, `superseded_by` and `deciding_quote`.
- **Impact.** Directly targets the raw-material brief's "memo that changes it". One wrong choice typically fails 3–8
  cases (a deadline, a floor or a holiday affects many customers). Estimate +2 to +6 cases on that brief.
- **Cost.** One extra call, about 30–60 s.
- **Risk.**
  - Effective dates relative to the call date: the hidden cases run "on several calendar days". If a memo takes
    effect mid-range, both rules may be needed, with code choosing by `now`.
  - The skill must say so, and the generator must then put both versions in code keyed on `today`.

### T15. Chain-of-Verification on every value-bearing rule — **P0 (merged with T13/T14 output)**
- **Source.** CoVe ([arXiv 2309.11495](https://arxiv.org/abs/2309.11495), 2023): draft → verification questions
  answered independently, without the draft in view → revise. Wikidata list precision 0.17 → 0.36; long-form
  FActScore 55.9 → 71.4 [M]. Atomic-fact checking: FActScore ([arXiv 2305.14251](https://arxiv.org/abs/2305.14251)) [M].
- **Apply (`builder/rules.py`, deterministic + one call).**
  - For each rule with `values`, generate the question "Quote the exact sentence(s) that set <value>". Example
    values: holidays, band thresholds, deadline formula, floor field per product, attempt ladder, callback window,
    max wrong answers, identity order, outcome/reason table.
  - Answer in a fresh call that sees only the brief, not the inventory.
  - Compare deterministically: numbers and dates must match exactly, and the quote must be found verbatim in the
    brief (string search).
  - Mismatches go into `rules.conflicts.md`.
- **Impact.**
  - Wrong numbers are the cheapest catastrophic error: a holiday or an off-by-one business-day rule fails every date
    case.
  - Estimate +1 to +3 cases per brief, more on the raw brief.
- **Cost.** One call, about 40 s, about $0.20.
- **Risk.** Low. False alarms cost Claude a re-read.

### T16b. Second-model cross-examination of the inventory — **P2**
- **Source.** LM vs LM cross-examination ([arXiv 2305.13281](https://arxiv.org/abs/2305.13281)): factual-error
  detection around F1 0.8 [M].
- **Apply.** Run T15's verification with a different model family (OpenAI, when `OPENAI_API_KEY` is present, as
  `sim.py` does).
- **Value.** Marginal over T13–T15. Do it only if time allows.

---

## 4. Coverage-driven test generation and pass@3 stability

### T16. Rule-branch test cases generated from the inventory (IntellAgent-style) — **P0**
- **Source.**
  - IntellAgent ([arXiv 2501.11067](https://arxiv.org/abs/2501.11067), 2025;
    [code](https://github.com/plurai-ai/intellagent)) [S]:
    - A policy graph, with random walks over co-occurring policies.
    - Generated events (user goal plus database state), simulated dialogues, and a critic per policy.
    - Pearson 0.98 (airline) and 0.92 (retail) with τ-bench, from purely synthetic data.
    - Success falls as the number of combined policies rises.
  - τ²-bench's compositional task generator, with functional pre- and post-conditions per subtask
    ([arXiv 2506.07982](https://arxiv.org/abs/2506.07982)) [S].
  - ττ-bench fact 6: held-out failures sit on branches the probes never reached.
- **Apply (new `builder/cases.py`, called from `build.py` right after `rules.py`, in parallel with the Claude build).**
  1. One model call, separate from the building agent (independent author, CLAUDE.md "Self-authored tests"), with the
     inventory and the brief.
  2. It emits 12–20 cases in `public-test-set.json` shape (persona script, call variables, mock product data if the
     practice bank can serve it), one per rule branch:
     - every outcome/reason row;
     - each identity failure path;
     - each date class (weekend, holiday, after deadline, vague, "next <weekday>");
     - each amount class (below floor, at floor, too much);
     - each special topic;
     - multi-product mixes;
     - plus 3–4 pairwise combinations (hardship + date, correction at read-back, transfer after a promise).
  3. **Constraint.** The mock bank serves only PUB-01..13 (FAQ), so generated cases must reuse those customers' data
     (the call variables and accounts of PUB-xx). They are re-scripted against the hidden brief's rules, as
     `tests/synthetic/brief-c.cases.json` does by hand.
  4. Expected ledgers are computed by the case-writer model with the brief's arithmetic; date maths goes through the
     same deterministic calendar code (CAL_HELPERS) given the brief's holidays. They are marked
     `expected_confidence`.
  5. The building agent never sees the rationale; it gets only the cases file.
- **Impact.**
  - This is the only thing that tests a hidden brief's own branches before submission.
  - ττ-bench and IntellAgent suggest it is where the held-out losses are.
  - Estimate +2 to +6 cases per brief, through bugs found in T12's repair round.
- **Cost.**
  - Builder time: about 1–2 minutes to generate (parallel with the build).
  - About 5–8 minutes to run 15 cases × 1 rep at `--concurrency 5` through `sim.py`.
  - About $2–4.
- **Risk.**
  - Wrong expected ledgers send Claude to "fix" correct behaviour. Mitigations:
    - fix only on deterministic evidence (engine events);
    - compute dates in code;
    - test `cases.py` before Sunday on briefs C, D and E against their hand-verified case files.
  - The mock serves only PUB customers, so new product mixes are impossible; reuse PUB-11..13 for multi-product.
    Check the practice-session API before relying on it.

### T17. Metamorphic speech mutations of passing cases — **P1**
- **Source.**
  - MORTAR, multi-turn metamorphic testing ([arXiv 2412.15557](https://arxiv.org/abs/2412.15557)): more than 150% more
    bugs per test case than single-turn metamorphic testing [S].
  - LLMORPH: an 18% average failure rate across 36 relations, but only about 62% of flagged violations were true
    positives [S].
- **Apply (`builder/sim.py`).**
  - Add `--mutate`. Each case that passed is re-run with one style drawn from `pieces | corrects | in_words |
    talkative | asks_back`; these already exist in `run_cases.STYLES`.
  - The metamorphic relation is **ledger equality**: same promises, notes, callbacks and outcome. It needs no judge,
    so there is no judge noise and the false positives LLMORPH warns about are avoided.
  - In-build: mutate only the 5 most valuable passing cases (one per style).
- **Impact.** The hidden customers use all five styles, so this tests exactly that distribution. +1 to +3 cases.
- **Cost.** About 3 minutes in-build; unlimited before Sunday.
- **Risk.** Low; it reuses the organisers' style text.

### T18. Uncooperative, non-disclosing simulator personas — **P1**
- **Source.**
  - Sim2Real gap for user simulators ([arXiv 2603.11245](https://arxiv.org/abs/2603.11245), COLM 2026; 451 humans,
    31 simulators): simulators are too cooperative, which makes an "easy mode" [S].
  - Customers who never walk away ([arXiv 2606.20708](https://arxiv.org/abs/2606.20708)): resistance halved
    (25.1 → 13.5%) [S].
  - UserProxyBench: premature disclosure in 24.4% of successful episodes [S].
  - τ²-bench: script-constrained users cut simulator errors from 40% to 16% [S].
- **Apply (`builder/sim.py` persona suffix).**
  - Add one line: "Never volunteer a fact before you are asked for it. Answer only the question asked. If the
    script says you refuse, refuse plainly and do not soften it."
  - Keep the organisers' persona text otherwise. Freya's simulator is `gemini-3-flash-preview` (`builder/SIM.md`), so
    we should not drift far from it.
  - Add `--customer-model` diversity (two models), so a case passes only if both pass.
- **Impact.** It does not improve the agent directly; it removes the optimism bias of our measurement, so we fix the
  right things. Indirect +1 to +2 cases.
- **Cost.** Minutes of coding.
- **Risk.** Over-adversarial personas break cases the organisers' simulator never would. Keep it to the
  non-disclosure line.

### T19. Measure pass^3 properly before Sunday: clustered, paired, enough reps — **P0 (process)**
- **Source.**
  - τ-bench unbiased pass^k estimator per task: C(c,k)/C(n,k) ([arXiv 2406.12045](https://arxiv.org/abs/2406.12045)).
  - Anthropic, "Adding error bars to evals" ([blog](https://www.anthropic.com/research/statistical-approach-to-model-evals),
    [arXiv 2411.00640](https://arxiv.org/abs/2411.00640)) [R]: cluster by case (clustered SE can be more than 3× the
    naive SE); paired differences between builds on identical cases cut variance by the correlation between them.
  - Rule of three: 0 failures in n trials bounds the failure rate at 3/n (95%).
  - "Deterministic" LLM settings still vary up to 15% between runs ([arXiv 2408.04667](https://arxiv.org/abs/2408.04667)) [S].
- **Apply.**
  1. In `sim.py`/`run_cases.py` output, print per case c/n and the estimated pass^3 = C(c,3)/C(n,3) with n ≥ 5
     reps for cases that matter.
  2. Compare two library versions on the same cases, styles and customer model (paired), never against a number from
     yesterday.
  3. Before Sunday: run synthetic briefs C and D, built by `build.py` end to end, with 5 reps at
     `--style talkative` and `corrects`. Any case below 5/5 is a p < 0.95 case and worth a fix.
  4. In-build: 1 rep over many branches (T16) beats 3 reps over few. Reps are for development, not for the 30-minute
     run.
- **Impact.** Stops us shipping changes that look good on one lucky run (FAQ: "My score dropped and I changed
  nothing").
- **Cost.** Development time and credits only; nothing in the build.
- **Risk.** None.

### T20. Make behaviour deterministic where the brief is deterministic — **P0 (principle; T1, T2, T13 are its instances)**
- **Source.**
  - τ²-bench: constraining with tools and state cut simulator errors 2.5× [S].
  - PolicyGuide and STAGE (fact 2).
  - Temperature 0 is not deterministic (T19).
  - Curse of Instructions: all-instruction success ≈ p^n (fact 8).
- **Apply (skill, Rules).** Add a sentence to `SKILL.md`: "Every rule whose outcome can be computed from the call
  variables, tool results and extracted enums must be decided in code or a route; a prompt may only phrase what code
  decided." Make `audit.py` report, per rule, `where_kind ∈ {code, route, hook, tts, prompt}`, and list prompt-only
  rules that could be code-decided as `partial`.
- **Impact.** Raises p uniformly. This is the mechanism behind T1 and T2.
- **Cost.** Audit prompt change (minutes).
- **Risk.** Over-mechanising conversational rules ("one short sentence of sympathy") gives robotic text. Those stay
  in prompts.

---

## 5. Robustness to human-like speech

### T21. Normalise numbers and dates in code hooks, and let the latest value win — **P0**
- **Source.**
  - NeMo ITN ([arXiv 2104.05055](https://arxiv.org/abs/2104.05055)): production inverse text normalisation is
    rule-based because neural ITN makes catastrophic errors ("one hundred and twenty three dollars" → $23) [S].
  - Disfl-QA: models latch onto the first entity; −28 F1 (fact 9).
  - Full-Duplex-Bench-v3: self-correction is the hardest category for every system, and argument accuracy (71.6)
    trails tool accuracy (88.7) (fact 9).
- **Apply (freyalib).**
  - `normalise_pre(fields)`: a pre-hook snippet for `verify_identity`, `create_promise` and `schedule_callback`, with
    no imports beyond `re`, `json` and `datetime` (sandbox). It does four things:
    1. Number words → digits ("four four seven one", "forty-four seventy-one", "oh" → 0).
    2. Strips spaces, dashes and "dollars".
    3. Month names → ISO dates. A numbers-only date is read in the order the brief's rule says (a generator
       parameter, e.g. `dmy`).
    4. Amounts in words → float ("four hundred and twenty point five").
  - Prompt line in identity nodes (generated): "If the customer gives the digits in parts, wait for all N digits and
    join them; if they correct themselves, use the LAST value they gave."
  - Extraction: `validation_pattern` (`^[0-9]{N}$`, with N from the API description) + `max_retries: 2` for digit
    answers when extracted.
- **Impact.** The hidden customers split numbers ("463…" then "51"), correct themselves and say amounts in words by
  design (event site). Each of these hits identity (every verified case) and the promise amount (every promise case).
  A failure there fails the case. Estimate +2 to +5 cases per brief.
- **Cost.** About 2 hours with unit tests; no build cost (library helper). Test it with a table of 40 utterances.
- **Risk.**
  - Converting something the model already got right; idempotent code (digits stay digits) avoids this.
  - A wrong date order: it must come from the brief, not from Brief A.
  - Never `{{` in hooks; `fl.check` already enforces it.

### T22. Confirm by read-back, generated by code, before every write — **P0 (part of T1)**
- **Source.**
  - IVR and VoiceXML practice: explicit confirmation for critical slots.
  - Shin et al., ICSLP 2002 ([link](https://www.isca-archive.org/icslp_2002/shin02_icslp.html)): errors that surface
    through implicit confirmation are recovered less often and more slowly.
  - Sagawa et al. 2004 ([link](https://www.isca-archive.org/interspeech_2004/sagawa04_interspeech.html)): explicit
    confirmation is preferred when errors occur.
  - Brief A rule 34 requires it anyway.
- **Apply.** T1's `confirm_<pid>` node. The read-back sentence is built in code from the guarded values (product
  words, `fmt(amount)`, weekday day month), so what the customer hears is exactly what will be written. This also
  removes "read-back says 420, tool writes 42.0" mismatches.
- **Impact.** Included in T1. It also helps the judge (T24).
- **Cost and risk.** See T1.

### T23. Off-topic and questions back: global interrupt nodes with a `__previous__` return — **P1**
- **Source.**
  - Rasa CALM repair patterns (digress, clarify, chitchat as default meta-flows,
    [arXiv 2402.12234](https://arxiv.org/abs/2402.12234)) [S].
  - Bland and Retell global nodes take precedence ([docs](https://docs.bland.ai/tutorials/pathways) [V]).
  - The Freya docs support global nodes with `__previous__` (`docs/workflow-format.md`, Global nodes; `fl.check`
    validates them).
- **Apply (freyalib, skill).**
  - For brief rules that apply "at any time": robot/AI question, scam question, request for a human, "is the call
    recorded", "how did you get my number". For each, decide between:
    - (a) a system-prompt line, which is today's approach and good enough when the answer is one sentence and the
      conversation simply continues;
    - (b) a global node only when the rule changes state, e.g. "ask once whether you can help, transfer on the
      second request", which needs a counter.
  - Rule of thumb for the skill: a counter or a tool means a global node; otherwise a system-prompt line.
- **Impact.** The "asks_back" and "talkative" styles. +0 to +2 cases.
- **Cost.** About 1–2 hours.
- **Risk.**
  - Global nodes fire from anywhere, including during the third-party flow, where nothing may be disclosed. The
    condition must exclude pre-verification states.
  - Returning with `__previous__` can re-run `on_enter` tts. Check `first_only` semantics on a smoke script first.

---

## 6. Judged conversation checks: maximise agreement with the judge

The judge (`gemini-3-flash-preview` on Freya, per `builder/SIM.md`) reads the transcript against case-specific checks
("never says recorded when the tool failed", "does not disclose the debt to a relative").

### T24. Verbatim lines as fixed text, plus a deterministic verbatim-coverage check — **P0**
- **Source.**
  - Parlant strict canned responses ([docs](https://next.parlant.io/docs/concepts/customization/canned-responses) [V]).
  - Pipecat `tts_say`, Retell and Bland static text, Dialogflow CX flows for "explicit control over agent responses"
    ([docs](https://cloud.google.com/dialogflow/cx/docs/concept/generative)) [V].
  - TICK/CheckEval: judges evaluate checklist items literally
    ([arXiv 2410.03608](https://arxiv.org/abs/2410.03608), [arXiv 2403.18771](https://arxiv.org/abs/2403.18771)) [S].
- **Apply (`builder/lint.py --rules`).**
  - For every string in `rules.json` → `verbatim`, assert that it appears verbatim in some tts `on_enter`, terminal
    farewell or code-built text in the workflow. A substitution placeholder such as `{{title}}` may stand in for a
    braced field.
  - ERROR if it is missing. A missing verbatim sentence fails every case whose checks include it. Today this is only
    checked by the LLM audit, which is not exhaustive.
- **Impact.** +1 to +3 cases per brief. These are cheap, total failures.
- **Cost.** About 1 hour.
- **Risk.** None.

### T25. Forbidden-word lint before identity is verified — **P0**
- **Source.**
  - The brief (rule 1: no "collections", "debt", "payment" or product before verification).
  - CALM ([arXiv 2410.02736](https://arxiv.org/abs/2410.02736), ICLR 2025): judges react to surface cues [S].
  - AgentRewardBench ([arXiv 2504.08942](https://arxiv.org/abs/2504.08942)): LLM judges over-report success, but are
    literal on explicit violations [S].
- **Apply (`builder/lint.py --rules`).**
  - Collect the forbidden-before-verification words from the inventory (category `opening` or `disclosure`; the
    builder should put them in `values.forbidden_words`).
  - Scan every tts text, farewell and **prompt** of nodes reachable before the verified route, including the
    third-party nodes and their farewells.
  - A prompt may mention them only in a "never say X" clause: the regex skips quoted words after "never" or "do not".
    Prompts quoting the words remain a WARN, because the dialogue model sometimes repeats them.
- **Impact.** Insurance against a total-failure class across all third-party, identity-failure and decline cases.
  +0 to +2 cases.
- **Cost.** About 1 hour.
- **Risk.** False positives on legitimate words ("I will call back"). Keep it a WARN for prompts and an ERROR for spoken text.

### T26. Say what was and was not done, in words the checks use — **P1**
- **Source.**
  - Judge checklists are literal (TICK, CheckEval).
  - The organisers' Honesty check ("never says recorded when the call failed", event site Evaluation).
  - AgentRewardBench: LLM judges over-report success when the agent claims it; rule checks under-report (above).
  - The flip side: a missing explicit statement can make a judge mark "did not inform the customer".
- **Apply (skill + generators).**
  1. Every `fin_*` farewell states the outcome in the brief's own terms. Examples: "I have not recorded a promise
     today." "Your callback is booked for Thursday 15 October at 11:00." "I could not record your promise because of
     a technical problem."
  2. `what_next_post` failure texts tell the model the exact honest sentence to say.
  3. Never use "recorded", "booked" or "confirmed" in any text reachable before the matching `ok_true` route.
     T25's scanner gets a second word list for this.
  4. Avoid filler that could trigger a check: "I understand your financial difficulty" when the customer did not
     mention one counts as unrequested hardship talk.
- **Impact.** +1 to +2 cases.
- **Cost.** Skill text.
- **Risk.** Longer farewells. Keep them to two sentences.

### T27. Simulate the judge with a checklist, chain of thought and majority vote in `sim.py` — **P1**
- **Source.**
  - TICK: checklist judging raised agreement 46.4 → 52.2%, with CoT plus a majority vote raising it further [S].
  - CheckEval: about +0.10 correlation with humans [S].
  - MT-Bench: GPT-4 judge agreement above 80%, equal to human–human ([arXiv 2306.05685](https://arxiv.org/abs/2306.05685)) [M].
- **Apply (`builder/sim.py`).** The judge answers each check separately (`[{check, pass, quote}]`) with a 2-of-3 vote
  when `--judge-votes 3`. Report which check failed. Also use T16's generated checks.
- **Impact.** Better diagnosis, so the right fix. Indirect.
- **Cost.** 3× judge tokens. Cheap with gpt-5-mini.
- **Risk.** Our judge is not Freya's. Treat a disagreement as a reason to read the transcript, not as truth.

---

## 7. Hidden-brief generalisation, prompt size, workflow-engine specifics

### T28. Build from a structured spec (inventory → parameters), not free-written prompts — **P0 (direction)**
- **Source.**
  - Rasa CALM: logic as flows, with the LLM only emitting commands ([arXiv 2402.12234](https://arxiv.org/abs/2402.12234)) [S].
  - Salesforce Agent Script compiles to an agent graph ([blog](https://developer.salesforce.com/blogs/2025/10/introducing-hybrid-reasoning-with-agent-script)) [V].
  - Sierra ADLC: deterministic guardrails as code ([blog](https://sierra.ai/blog/agent-development-life-cycle)) [V].
  - NOMOS ([arXiv 2610.11030](https://arxiv.org/abs/2610.11030)): static checks alone repair or reject 37% (airline)
    and 13% (retail) of generated policy gates [S].
  - PolicyLR ([arXiv 2408.14830](https://arxiv.org/abs/2408.14830)): precision 0.91 and recall 0.88 compiling policy
    into atomic formulae [M].
- **Apply.**
  - Extend `rules.json` `values` to a fixed schema the generator consumes directly:
    `calendar{business_weekdays, holidays}`, `bands[]`, `floors{product_type: field}`, `attempt_ladder[]`,
    `callback{open, close, same_day, days_ahead}`, `identity[{field, order}]`, `max_wrong`,
    `outcomes[{outcome, reason, when}]`, `verbatim[]`, `forbidden_words[]`.
  - Add `builder/spec_check.py`, which validates that schema deterministically.
  - The skill then tells Claude to *pass these values* into `SETUP_CODE`, `products_facts_code` and `end_pair` rather
    than retyping them. Retyping is where transcription errors enter, and T15 cannot check what Claude retypes.
  - Keep Claude for what does not fit the schema: free-text rules, unusual brief structure.
- **Impact.** Fewer transcription errors; faster builds (the second tie-break). +1 to +3 cases per brief.
- **Cost.** About 3–4 hours. Risky to do in full before Sunday, so do the schema for calendar, bands, floors and
  outcomes first.
- **Risk.**
  - A hidden brief may not fit the schema (a band by amount instead of days late, a product type we never saw).
    Every field needs a "free-text fallback" path where Claude writes code instead.
  - The schema must never contain A/B defaults.

### T29. Short per-node prompts, critical rules first, history kept but facts restated — **P1**
- **Source.**
  - IFScale: primacy bias, and omission is the dominant error ([arXiv 2507.11538](https://arxiv.org/abs/2507.11538)) [S].
  - Lost in the Middle: about 75.8% with the answer at position 1 against about 53.8% in the middle, GPT-3.5
    ([arXiv 2307.03172](https://arxiv.org/abs/2307.03172)) [S].
  - LongLLMLingua: +21.4% on NaturalQuestions at 4× compression ([repo](https://github.com/microsoft/LLMLingua)) [S].
  - Vapi: do not make one node per question; split at policy and tool boundaries
    ([docs](https://docs.vapi.ai/workflows/legacy-migration)) [V].
- **Apply.**
  - `lint.py` WARN when a conversation node's `task_message` plus facts exceed about 2,500 characters, or has more
    than about 15 imperative lines. `negotiate` in `gen_brief-a_v2.py` is about 4,000 characters including FACTS.
  - Skill: order every node prompt as (1) `{{state_line}}` (T3), (2) the 3–5 rules that decide this node, (3)
    conduct rules, (4) the calendar and fact tables last.
  - Remove from prompts any rule that a route or code already enforces (T1, T2). Saying it twice costs attention.
- **Impact.** Raises p on long multi-product calls. +0 to +2 cases.
- **Cost.** About 1 hour.
- **Risk.** Removing a sentence that was silently load-bearing. Do it A/B-paired (T19).

### T30. Latency budget: keep the routing and extraction calls tiny — **P1**
- **Source.**
  - Voice latency budgets of about 800 ms to first audio, with the LLM the largest variable stage
    ([Soniox](https://soniox.com/wiki/voice-agent-latency-budget) [V]).
  - The kit: a slow model lowers scores, with a warning above a median slowest turn of 10 s (kit README).
  - Amazon hybrid intent detection: keep label sets small per router ([arXiv 2410.01627](https://arxiv.org/abs/2410.01627)) [S].
- **Apply (`lint.py`).**
  - WARN when a node has more than 4 extraction variables, an enum with more than 7 values, or more than 8
    model-judged (`intent`) transitions.
  - Prefer deterministic conditions; `fl.eq` and `is_set` need no model call.
- **Impact.** Fewer "customer-ended-call" losses on slow days. 0–2 cases.
- **Cost.** 30 minutes.
- **Risk.** None.

### T31. Spend the build budget on reading, not on more architecture search — **P0 (process)**
- **Source.** ττ-bench leaderboard [R]:
  - A 30-minute build scored 18.0 against 23.9 at 216 minutes, so build time is a weak lever.
  - Builds that asked the client 0, 1 or 2 questions scored 5, 15 and 25% on tasks where the reference scored 95–100%.
  - Built agents used only 0.38–0.76× of their serving budget.
- **Apply (`build.py`).**
  - Start `rules.py` (T13–T15) and `cases.py` (T16) concurrently, then the Claude build. That gives Claude a verified
    inventory instead of making it the only reader.
  - Our "client" is the brief itself. The analogue of asking the client is T14/T15's targeted questions answered from
    the brief by a fresh context.
- **Impact.** Enables T13–T16 within 30 minutes.
- **Cost.** Parallelism only.
- **Risk.** Rate limits on the builder model; keep it to 3–4 concurrent calls.

---

## Top 10 to implement now (ranked by expected score gain per hour before Sunday 17:00 UTC)

| # | Technique | Where | Why it ranks here |
|---|---|---|---|
| 1 | **T21 Normalise numbers and dates in code; the latest value wins** | `freyalib.normalise_pre`, identity and promise tools, skill line | Hits every verified case under the hidden speech styles; self-correction is the top measured speech failure (<59%, −28 F1) |
| 2 | **T2 Attempt and refusal counters in code** | `freyalib.counter_code` + multiproduct ladder + extraction `stance` | Removes the most model-dependent exit; deterministic state raises pass^k (StateFlow, task-state gate +0.15 pass^1) |
| 3 | **T1 + T22 Offer guard and code-built read-back; `create_promise` only in a confirm node** | `freyalib.offer_guard`, multiproduct, reference generators | The largest measured family of gains (PolicyGuide +0.20 pass^4); targets dates, amounts and multi-product |
| 4 | **T14 Dated-decision resolution, multiple-choice style** | `rules.py` second pass | The raw-material brief is half the score; one wrong "rule in force" fails whole families |
| 5 | **T15 CoVe verification of every value + T13 3-sample inventory** | `rules.py` | Cheap insurance against wrong holidays, bands and floors; about +1 min, about +$1 |
| 6 | **T24 + T25 Verbatim-coverage and forbidden-word lints from the inventory** | `lint.py --rules` | Deterministic, about 2 h total, guards total-failure classes |
| 7 | **T16 Rule-branch cases from the inventory by an independent writer** | new `builder/cases.py`, `build.py` | The only test of hidden-brief branches; ττ-bench: held-out failures sit on unprobed branches |
| 8 | **T12 One reflective repair round on those cases (no-case briefs too)** | skill step 9, `build.py` prompt | Turns T16 into fixes; at most 2 rounds, fixes only on deterministic evidence |
| 9 | **T19 Paired, clustered pass^3 measurement on briefs C/D with 5 reps** | `sim.py` output + dev process | Prevents shipping noise; target per-trial p ≥ 0.95 per case |
| 10 | **T3 + T29 `state_line` first in every node prompt; short node prompts** | freyalib hooks/code, skill, `lint.py` length WARN | Cheap attention fix on a fast fixed model (IRMA +12–16 pass^5, ARQ +4–9) |

Suggested order of work given about 24 hours:
1. (6) and (5): small, deterministic, independent.
2. (1) and (2): library helpers with unit tests, then a port of `gen_brief-a_lib` / `gen_brief-b_lib` and
   `compare_*`.
3. (3).
4. (7) and (8).
5. (9) continuously.
6. (10) last.

Freeze the library by about Sunday 12:00 UTC and run the full builder on C, D and E twice.

## Do NOT do

| Don't | Why |
|---|---|
| Put any rule, value, name, date, outcome or sentence from Brief A/B (or a hidden brief after 17:00) into `freyalib`, `multiproduct`, the skill or the schema defaults | Organisers' rule; a reviewer checks the commit. T28's schema must have no A/B defaults. `multiproduct` "Defaults" are already A/B conventions: make sure the skill overrides every one from the brief |
| A runtime reviewer LLM, retrieval service, or any HTTP call other than the brief's tool API inside the phone agent (T7) | "The phone agent may call only the tool API from the kit. A call to any other service fails the case" |
| A pre-hook that "blocks" a write by rewriting the URL or body to make the bank reject it | It is still a ledger entry (a failed or extra call), and redirecting the URL is a call to another service. Gate by tool availability and routes instead (T1) |
| Silently cap or alter a promise to a value the customer did not hear | Ledger and transcript disagree; the judge fails Honesty. Replace capping by T1's guard; keep caps only as a last-resort safety net that also rewrites the read-back |
| ADAS, AFlow, AgentSquare, DGM, OPRO, MIPRO or GEPA-scale search during the 30-minute build (T10) | Needs labels and 10²–10⁴ evaluations; overfits our self-written cases; build time is the second tie-break |
| Fine-tuning, RL, or changing `AGENT_LLM`; relying on extended thinking or temperature in the phone agent | The serving model is fixed for every team; "deterministic" settings still vary up to 15% |
| Probing the platform: hunting for hidden cases, extra practice sessions, load tests, multiple simulations in parallel, a second Freya key | Rules ("Do not probe or load-test"); ττ-bench saw 17–42% of runs try cheating-adjacent probes, none succeeded |
| Weakening a self-test, judge or expected ledger to make a build pass; mocking a failing endpoint | ττ-bench: "cannot raise the held-out score; it only hides the failure from the developer" |
| Editing the phone agent on Freya by hand, or exporting a workflow that did not come from the traced run | Disqualifying; the top entries are rebuilt from the commit |
| Shipping `test_variables`, or a first code node | CLAUDE.md: breaks the chat route; tests would then measure a different agent |
| Many reps of few cases inside the build | 3/n bound: 10 clean reps still allow 30% failure. Use 1 rep over many branches in-build; reps belong to development (T19) |
| Putting the whole brief in every node prompt, or runtime retrieval of the brief | IFScale, Lost in the Middle; τ-Knowledge shows retrieval-grounded policy at 25.5% pass^1 ([Sierra](https://sierra.ai/blog/tau-knowledge)) |
| Adding a `think` tool or "reason step by step" to the phone agent | Each tool call is a model turn of latency; ReAct-style text reasoning underperformed native tool calls on τ-bench (T4, T5) |
| Over-fragmenting into one node per question | Latency and lost context (Vapi migration guidance); split at policy and tool boundaries |

## Sources (all links cited above)

**τ-family benchmarks:**
- [τ-bench](https://arxiv.org/abs/2406.12045) and its [leaderboard repo](https://github.com/sierra-research/tau-bench)
- [τ²-bench](https://arxiv.org/abs/2506.07982)
- [τ-Knowledge](https://sierra.ai/blog/tau-knowledge)
- [τ-Voice](https://arxiv.org/abs/2603.13686)
- [ττ-bench](https://arxiv.org/abs/2609.04611) and its [repo](https://github.com/sierra-research/hyper-tau-bench)

**Policy guards and state:**
- [PolicyGuide](https://arxiv.org/abs/2608.19861) and [PolicyGuard](https://arxiv.org/abs/2606.29225)
- [ToolGuard](https://arxiv.org/abs/2507.16459)
- [Task-state gate](https://arxiv.org/abs/2609.25686)
- [STAGE](https://arxiv.org/abs/2608.22538)
- [Blueprint First](https://arxiv.org/abs/2508.02721)
- [StateFlow](https://arxiv.org/abs/2403.11322)
- [ARQ](https://arxiv.org/abs/2503.03669)
- [IRMA](https://arxiv.org/abs/2508.20931)
- [Reinforced Agent](https://arxiv.org/abs/2604.27233)
- [SOP-Agent](https://arxiv.org/abs/2501.09316)

**SOP benchmarks:**
- [SOPBench](https://arxiv.org/abs/2503.08669)
- [SOP-Bench](https://arxiv.org/abs/2506.08119)

**Think tool:**
- [Anthropic think tool](https://www.anthropic.com/engineering/claude-think-tool)

**Meta-systems and prompt optimisers:**
- [ADAS](https://arxiv.org/abs/2408.08435)
- [AFlow](https://arxiv.org/abs/2410.10762)
- [AgentSquare](https://arxiv.org/abs/2410.06153)
- [DGM](https://arxiv.org/abs/2505.22954)
- [MetaAgent](https://arxiv.org/abs/2507.22606)
- [GEPA](https://arxiv.org/abs/2507.19457)
- [Prompting policies](https://arxiv.org/abs/2605.14443)
- [Coding agents as prompt optimisers](https://arxiv.org/abs/2609.26261)

**Spec recovery and verification:**
- [Self-consistency](https://arxiv.org/abs/2203.11171)
- [USC](https://arxiv.org/abs/2311.17311)
- [CoVe](https://arxiv.org/abs/2309.11495)
- [FActScore](https://arxiv.org/abs/2305.14251)
- [LM vs LM](https://arxiv.org/abs/2305.13281)
- [evolveQA](https://arxiv.org/abs/2510.19172)
- [HoH](https://arxiv.org/abs/2503.04800)
- [NOMOS](https://arxiv.org/abs/2610.11030)
- [PolicyLR](https://arxiv.org/abs/2408.14830)

**User simulation and testing:**
- [IntellAgent](https://arxiv.org/abs/2501.11067)
- [MORTAR](https://arxiv.org/abs/2412.15557)
- [Sim2Real user simulation](https://arxiv.org/abs/2603.11245)
- [Lost in Simulation](https://arxiv.org/abs/2601.17087)
- [Simulated Customers Never Walk Away](https://arxiv.org/abs/2606.20708)
- [UserProxyBench](https://www.opentrain.ai/papers/userproxybench-evaluating-llm-user-simulators-for-agent-benchmarks-and-training--arxiv-2609.38043/)
- [Error bars for evals](https://www.anthropic.com/research/statistical-approach-to-model-evals)
- [Non-determinism of deterministic settings](https://arxiv.org/abs/2408.04667)

**Speech robustness and normalisation:**
- [Full-Duplex-Bench-v3](https://arxiv.org/abs/2604.04847)
- [Disfl-QA](https://arxiv.org/abs/2106.04016)
- [NeMo ITN](https://arxiv.org/abs/2104.05055)
- [Shin 2002](https://www.isca-archive.org/icslp_2002/shin02_icslp.html)
- [Sagawa 2004](https://www.isca-archive.org/interspeech_2004/sagawa04_interspeech.html)

**LLM judges:**
- [MT-Bench judge](https://arxiv.org/abs/2306.05685)
- [CALM judge biases](https://arxiv.org/abs/2410.02736)
- [TICK](https://arxiv.org/abs/2410.03608)
- [CheckEval](https://arxiv.org/abs/2403.18771)
- [AgentRewardBench](https://arxiv.org/abs/2504.08942)

**Instruction load and prompt length:**
- [IFScale](https://arxiv.org/abs/2507.11538)
- [Curse of Instructions](https://openreview.net/forum?id=R6q67CDBCH)
- [Lost in the Middle](https://arxiv.org/abs/2307.03172)
- [LLMLingua](https://github.com/microsoft/LLMLingua)

**Intent routing and constrained decoding:**
- [Rasa CALM](https://arxiv.org/abs/2402.12234)
- [Intent detection hybrid](https://arxiv.org/abs/2410.01627)
- [XGrammar-2](https://arxiv.org/abs/2601.04426)
- [Brief Is Better](https://arxiv.org/abs/2604.02155)

**Vendor docs:**
- [Retell transitions](https://docs.retellai.com/build/conversation-flow/transition-condition)
- [Vapi migration](https://docs.vapi.ai/workflows/legacy-migration)
- [Parlant canned responses](https://next.parlant.io/docs/concepts/customization/canned-responses)
- [Dialogflow CX generative](https://cloud.google.com/dialogflow/cx/docs/concept/generative)
- [Bland pathways](https://docs.bland.ai/tutorials/pathways)
- [Salesforce Agent Script](https://developer.salesforce.com/blogs/2025/10/introducing-hybrid-reasoning-with-agent-script)
- [Sierra ADLC](https://sierra.ai/blog/agent-development-life-cycle)
- [Soniox latency budget](https://soniox.com/wiki/voice-agent-latency-budget)
