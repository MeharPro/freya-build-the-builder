# Current review — 10 October 2026

All 433 files from `freya-build-the-builder-main (3).zip` were imported. Previous local versions were preserved under gitignored `build-history/before-newest-import-20261010/`. `newest-import-manifest.json` records the original archive hashes and active overlays; it is an import receipt, not a score.

## Official material

Read the complete live hackathon page: Overview, Data, Evaluation, Submit, Leaderboard, Rules and FAQ. A fresh capture is saved as `hackathon-live-20261010.md`. Downloaded the version 3 kit from its live Data link and compared every file. The official core files matched byte for byte on import. The builder skill is customised, and the client now has a generic polling fix: a completed iteration is accepted even while its parent status lags; workspace waiting and polling are bounded. The phone-agent model and official scorer/test expectations remain unchanged. `official-kit-verification.json` records the comparison.

Hidden briefs open Sunday 11 October at **1 p.m. Toronto time**; submission closes at **4 p.m.** (17:00 and 20:00 UTC). Each of 60 cases must pass every one of its three repetitions. Scores come from the submitted exports, with ledger, conversation-policy and honesty checks; top builders are rebuilt. No score or win can be guaranteed in advance.

## Imported work and integration

The updated archive supplies policy as code, structured and dated policy extraction, speech normalisation, identity gates, independent case generation, extended and synthetic fixtures, platform docs, reference generators and historical failure analysis. Those are now in the workspace. The active runner retains the local reliability work and uses the new libraries and skill.

Fixed API schema drift: no invented `customer_id` field, no omitted required fields, numeric enum validation, safe quoted failure reasons and valid workweek/holiday requirements. Strengthened rule inventory integrity and numbered-rule coverage after gap-fill. Removed a public-bank-name assumption from generic smoke assertions and public-bank numeric examples from the audit prompt. Actual exports are checked through an in-memory view that ignores known optional null defaults added by Freya, without modifying export bytes. Candidates and tool fields remain strict. The workflow library now omits empty test variables; the export gate rejects nonempty overrides and tolerates harmless empty platform defaults.

The runner refuses failed or stale submissions, publishes the current validated candidate, audits the actual export, preserves full redacted helper output even on timeout, archives spec/case/audit sidecars, serialises builds and writes success manifests. The runner also checks that source, instructions and practice expectations remain unchanged during generation and before success, including detecting added helper files. All helper processes have bounded timeouts; the final checks share the same monotonic budget. Generated-case tooling remains available for diagnostics. A never-seen API does not automatically inherit the public mock bank’s schema or a trustworthy generated score.

## Rule compliance

| Requirement | Current evidence / remaining obligation |
|---|---|
| Automatic generation and unchanged exports | Runner publishes and exports inside the run; hidden agents must be built with it, with no later manual edits |
| Trace and reproducibility | Start/end, model calls, helper output and export ids are recorded; manifests bind inputs and artifacts; actual hidden runs remain pending |
| Supplied bank API only | API tools are checked against the supplied schema/URL; lint rejects network/process clients and dynamic execution in workflow code/hooks |
| Fixed phone-agent model | Official phone-agent model configuration is unchanged; only simulation polling is adjusted; builder models are configurable |
| Time and workspace limits | Maximum 30 minutes, one workspace lock, stable workflow slots; official practice simulations run sequentially |
| Secrets | Approved seven-day key saved only in owner-readable gitignored `env.sh`; staged-secret check reports filenames without exposing matching keys |
| Hidden policy contamination | No hidden brief is available yet; after release only generic bug fixes, with no hidden names/values/rules inserted into builder source |
| Synthetic data and team limits | Practice data is synthetic; registration and team membership need the participant’s confirmation |
| Final submission | Two matching exports/traces and a commit are still required after hidden briefs arrive; nothing has been emailed or submitted |

## Reproducibility and measured checks

A clean checkout without `env.sh`, `.freya-agents.json`, `.personas.json`, `.venv`, results or build history passed **69 unittest checks** and compilation. Separately: **32 policy scenarios**, **144 normalisation cases**, **6 identity-gate checks**, **31 multi-product checks**, and independent re-derivation of the extended A/B expectations passed. Both regenerated v3 practice reference workflows passed local validation and Freya server dry run; their actual platform exports also passed validation and use experimental-5.

A reviewer supplies their own `ANTHROPIC_API_KEY` and Freya/team credentials. No Karan account or interactive Claude login is required. Verified the SDK’s bundled CLI selects an environment API key with an empty configuration directory; this was a configuration-only check using a dummy key, with no paid model request. Local builder-model access is currently unset/signed out, so a full fresh model-driven build has not been measured here. The Freya key authenticates successfully. Public reference agents have been published in practice slots for official baseline testing; these are not current submission-runner outputs.

Historical scores and claims in imported reports, traces and submission files belong to the source archive. They do not certify the current builder. Official baseline logs are saved under `results/context-validation/`, with structured rows in `results/current-a-reps3.json` and `results/current-b-reps3.json`. Brief A passed all 10 cases in all three fresh repetitions (30/30 calls), counting both ledger and conversation checks. Median slowest turns were 4.9, 7.3 and 10.4 seconds; no slow run was discarded. Brief B’s old reference failed PUB-12 by recording all products despite consent to only one. The failure and transcript are retained. Redundant old repetitions were stopped and the second old simulation paused. Its in-flight PUB-12 call eventually ended with a failure after repeated incorrect read-backs; the other two runs ended before corrected testing began. The shared policy library now narrows offers to their positive product scope, extracts scope again at confirmation, and reopens other unrecorded agreements after a partial confirmation. Corrected Brief B (practice version 3) passed all three cases in all three fresh repetitions (9/9 calls), including the correct refusal notes. Its median slowest turns were 11.2, 14.1 and 6.0 seconds; no slow run was discarded. The exact measured values and artifact hashes are in practice-baseline-20261010.json. Together the reference agents passed all 13 public cases across three repetitions (39/39 calls). These reference-generator results do not measure a fresh model-driven builder or the hidden cases.
