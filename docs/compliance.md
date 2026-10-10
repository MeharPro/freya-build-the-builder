# Compliance and reproducibility check

Verified against commit `b10096e` (working tree clean) on 10 Oct 2026 by an adversarial verifier: every auditor
claim was re-checked against the files and the rule text; a clean `git clone` of the commit was exercised with the
system Python (3.14.7) for every offline part; the Claude Agent SDK was run with no credential at all to see what
the organisers would see. Line numbers are those of the commit above.

## The two questions

**Are we passing all the practice cases? No.** Under the final's rule ("3 per case. The case passes only when all 3
runs pass", docs/hackathon-site.md:164) the best agents stand at:

| Agent (slot) | Run (results/log.jsonl) | Result | Failed |
|---|---|---|---|
| Brief A v3, agent `7d100f1a` (`brief-a-v3`) | 15:17, organisers' simulator, 1 run | 9/10 | PUB-04 (judge: did not re-acknowledge being a digital assistant when asked "Am I talking to a robot?"; out/freya/a-v3-x1.json) |
| same | 15:40, `--reps 3` | **7/10** | PUB-01 2/3 (rep 1 closed `no_promise/refused`, no `create_promise` although the customer agreed to 420 today), PUB-04 2/3 (rep 2 no promise, slowest turn 62.2 s), PUB-07 2/3 (rep 3 closed `service_error`, never offered 2026-10-27 after the holiday, loop) — out/freya/a-v3-x3.json |
| Brief B v3, agent `24083493` (`brief-b-v3`) | 15:20, 1 run | 2/3 | PUB-12 (closed `no_promise/refused`, notes on p1,p2,p3; expected promise p1 510.00 2026-10-15 + notes p2,p3) — out/freya/b-v3-x1.json |
| Brief A v1, agent `d4bc2edb` (`brief-a`, the committed submission file) | 11:32 1 run; 12:15 `--reps 3` | 10/10; 10/10 | none under the default style; v2/v3 were built because people-like styles broke it (git 2a2a320: asks_back 4/10 on v2) |

Neither v3 agent has a committed trace: `.freya-agents.json` holds slots `brief-a-v3` / `brief-b-v3`, `traces/` holds
only `brief-a.*` and `brief-b.*` (git ls-files), both written by the 11:22/11:35 version of build.py (their first line
lacks the `cases=... runner=... budget=` fields that build.py:197 writes now).

**Does the builder follow the rules, and how do the organisers run it without your auth?** Structurally yes (table
below). Nothing in the repository carries your credentials: `env.sh`, `.freya-agents.json`, `.personas.json` are
gitignored (.gitignore:2-5); a scan of every tracked file for `fak_` keys, `sk-` keys, your actual FREYA_API_KEY and
your actual team key found only the three documented placeholders (docs/api.md:24, env.example:1,
tools/check_secrets.sh:6). The builder authenticates from environment variables only: `FREYA_API_KEY` /
`FREYA_BANK_TEAM_KEY` (build.py:192-193 refuses to start without them; freya.py:10 puts the key in the header) and,
for its own model calls, whatever Anthropic credential the Claude Code CLI finds (`ANTHROPIC_API_KEY` in the
environment, or a `claude login` in the runner's home directory). The Claude Agent SDK spawns the CLI bundled inside
its own wheel (`claude_agent_sdk/_bundled/claude`, subprocess_cli.py:255-260 and 341-354) with the inherited
environment (subprocess_cli.py:819-824). Your shell has neither `ANTHROPIC_API_KEY` nor `OPENAI_API_KEY` set
(env.sh exports only FREYA_API_KEY, FREYA_API_URL, FREYA_BANK_TEAM_KEY, FREYA_WORKSPACE_ID), so your runs use your
`claude login`; theirs will use theirs. Verified: with an empty HOME and no key, the SDK returns
`ResultError: Not logged in · Please run /login` at zero cost, so an organiser without a credential gets a run with
no agent (build.py:230-231 logs `ERROR in the agent run`, export then logs `no workflow saved for slot`), never a
run on your account.

## Organiser requirements, verified

Status: **OK** = verified compliant; **RISK** = compliant today but a concrete way to fail exists; **VIOLATION** =
not met; **UNVERIFIABLE** = cannot be checked from the repo.

| # | Requirement (quoted) | Status | Evidence after verification |
|---|---|---|---|
| 1 | "The builder must work alone. One command, a brief as input, a phone agent as output. No manual edits after it runs." (docs/hackathon-site.md:76; kit-README.md:84) | RISK | build.py:175-251 is one command: rules + cases (threads, :206-215) -> Claude with the skill (:225-227) -> lint (:234) -> audit (:235-238) -> export (:240) -> trace (:243). Form matches README.md:84 / site:206. Risk: the only committed build.py traces are from the pre-12:07 builder (git: v2 landed 95f11b8 at 12:07; traces/brief-a.log committed 1613396 at 11:35, brief-b in 95f11b8), and the best agents (`brief-a-v3`, `brief-b-v3`) came from hand-run generators out/gen_brief-a_v3.py / gen_brief-b_v3.py with no trace. There is no committed evidence yet that the current build.py yields a v3-quality agent inside the budget. |
| 2 | "They ... clone the repository at that commit, run the builder themselves on the same briefs and compare with your trace ... If their run scores clearly below yours, the entry is removed." (site:235) | RISK | Clean-clone test (this commit, system Python 3.14, no env): build.py exits "FREYA_API_KEY is not set" before touching traces; `import freyalib, policy, multiproduct, lint, spec_check, freya` OK; `python3 out/gen_brief-a_v3.py tools/openapi.json` writes 69 nodes; `lint.py` on it: 0 errors; multiproduct self-test 31/31; unit tests 32/32, 144/144, 29/29. Four rebuild risks remain: rows 17, 18, 19, 5. |
| 3 | "You may not write anything from a hidden brief into it: no rule, no value, no name." (site:78, :263; kit-README.md:73) | OK today | Hidden briefs open Sun 17:00 UTC (site:66); nothing can be in the repo yet. Every Brief A/B literal found is a kit file (all byte-identical to kit-archive/build-the-builder-v3.zip), a reference generator (out/gen_brief-a_v3.py:27 HOLIDAYS etc.), a test fixture (builder/tests/*, multiproduct.py:827), documentation, or a library default (see "Brief-specific defaults" below, which matter for site:77 "It has to read a brief it has never seen", not for :78). |
| 4 | "The phone agent may call only the tool API from the kit. A call to any other service fails the case." (site:261; kit-README.md:86) | OK | Tool URLs are built from the given API file only: freyalib.py:69-71 `base_url(api)` = `servers[0].url`, :163 `url = base_url/name`, :100 raises for a tool the file lacks; HEADERS carry only Content-Type (freyalib.py:54). Every URL in submission/*.json, out/brief-a_v3.workflow.json, out/brief-b_v3.workflow.json is `https://freya-bank-mock.freyavoice.workers.dev/v1/<tool>` (seven tools, grep). lint.py:971 errors on a tool that is not an operation of the file, :975-976 on a url that is not base + name, :727 on an undocumented handler. Gaps (not violations): build.py:234 ignores lint's exit code and exports anyway (:239-240); neither lint.py nor freyalib._check_code (:815-824, compile only) inspects imports inside code nodes/hooks; the sandbox's network policy is "Not documented" (docs/tools-and-code.md:507). |
| 5 | "Builder run time: 30 minutes per brief, including any test the builder runs on its own phone agent" (site:241; kit-README.md:89) | RISK | Default `--minutes 29` (build.py:176). Claude is stopped at `budget - 3` min at the latest (:226-227, `asyncio.wait_for`). Then lint up to 120 s with no guard (:234), then the audit runs whenever `elapsed < budget - 1` with a 360 s timeout (:235-238), then export. Worst case read from the trace's start (:197) to end (:243): about 26 + 2 + 6 = 34 min. Whether `wait_for` cancellation ends the CLI subprocess promptly was not executed. |
| 6 | "Workflows per workspace: 200. Update one in place instead of creating a new one per run." (site:242; kit-README.md:87) | OK | freya.py:36-47 creates once per slot, then `update_workflow` + publish (:49-64); SKILL.md:46 saves under the slot; build.py:160-166 exports that slot's id. `.freya-agents.json` is gitignored (.gitignore:4), so the organisers' clone creates one workflow per slot in *their* workspace on the first run and updates it afterwards. |
| 7 | "Do not probe or load-test the platform. One Freya key per team." (site:262) | OK | freya.py:10 reads one `FREYA_API_KEY`; env.sh holds one; no second key in any tracked file. The local simulator runs at most 3 chat calls in parallel (build.py:127, SKILL.md:53 says 2 for generated cases). |
| 8 | "Model the phone agent runs on: The Freya model set in freya.py. The same for every team. Do not change it" (site:244; kit-README.md:85) | OK | freya.py is byte-identical to the kit zip (cmp); `AGENT_LLM` at freya.py:84 untouched; build.py:198 only logs it. Also identical to the zip: tools/run_cases.py, tools/score.py, tools/openapi.json, public-test-set.json, both briefs, examples/*, docs/workflow-format.md, tools-and-code.md, api.md, env.example, VERSION, and docs/kit-README.md (= the zip's README.md). Only `.claude/skills/build-phone-agent/SKILL.md` differs (ours, as intended). |
| 9 | Trace: "Start and end time of the run / Every model call the builder made: which model, and what it was asked for in one line / What it created on Freya: workflow id, agent id, number of steps and tools / Any test it ran on its own phone agent, with the result" (site:222-227; kit-README.md:91) | RISK | build.py:197 start (ISO time with %z), :243 end + total seconds; :135 the build call with purpose, :143/:146 one line per assistant text or tool use with the model name, :85-86 copies every `model call:` line that rules.py (:225), cases.py (:36) and audit.py (:27) print to stderr; :151-152 PASS/FAIL/workflow_id lines from tool results; :170-171 `created on Freya: workflow_id=... agent_id=... | N steps (...), M tools`. Committed traces/brief-a.log (36 lines, 22 model-call lines, 1 created-on-Freya line, total 608 s, $1.65) and brief-b.log (50 lines, 39 model-call lines) satisfy the list but come from the older build.py (row 1). Gap: when a helper step times out (:83-84) its stderr is dropped, so that step's model calls are missing from the trace. |
| 10 | "Remove API keys before you commit." (site:229) | OK | build.py:44-52 `scrub()` masks `fak_…`, `sk-…` and the values of FREYA_API_KEY, FREYA_BANK_TEAM_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY on every trace line (:64) and jsonl record (:69); tools/check_secrets.sh is the pre-commit hook (.git/hooks/pre-commit execs it; not cloned, irrelevant for the organisers). Tracked-file scan: 0 real keys. Cosmetic: traces contain `/Users/karanvirkhanna/...` paths (brief-a.log 3, brief-b.log 3, brief-a.jsonl 9, brief-b.jsonl 12). |
| 11 | "Export each phone agent to a file with freya.export_workflow and commit the files. They load them into their own workspace, so what you export is what they score." (site:194; kit-README.md:75) | RISK | build.py:157-172 calls `freya.export_workflow` at the end of every run (:240) into submission/<slot>.workflow.json. BUT the committed submission/brief-a.workflow.json and brief-b.workflow.json are the v1 agents (46 / 48 nodes) and carry populated `test_variables` (`customer_id: c_test`, `now: 2026-10-14T11:00`, …), which SKILL.md:43 now forbids ("Never emit test_variables"); out/brief-a_v3.workflow.json has `test_variables: {}`. Not a hackathon-rule breach (practice slots are not scored), but the committed files do not match what the current builder produces. |
| 12 | Submission form: `run_command "python3 builder/build.py {brief_path} {tool_api_path}"`, workflows `submission/hidden-1.workflow.json`, traces `traces/hidden-1.log` (site:201-216) | OK | README.md:79-88 reproduces the form; repo URL = `git remote -v`; build.py:194 slot = brief file stem, so `briefs/hidden-1.md` -> submission/hidden-1.workflow.json (:165) and traces/hidden-1.log (:59); :184-187 accepts `<brief> <api>` in that order (and a non-`.json` API name via the positional fallback). Commit sha pending. |
| 13 | "Submit one builder trace per hidden brief." / "Submit one phone agent per brief, with the trace of the run that made it." (site:260, :193) | OK | One trace per slot per run (build.py:57-60); a timestamped copy keeps earlier runs (:246-250); the export happens inside the same run (:240), tying agent and trace. Pending Sunday execution. |
| 14 | "Do not edit a phone agent after the run." / "no manual edits" (site:193, :259; kit-README.md:84) | OK (process) | SKILL.md:62 "Never edit the agent on the platform by hand. Change the generator and save."; export reads the platform at the end of the run (build.py:166-167). Whether any workflow was ever edited in the dashboard cannot be seen from the repo; the v3 agents were saved by running generators. |
| 15 | "After the hidden briefs open you may fix a bug in your builder ... Adding the new brief's holiday dates or outcome names to your code or prompts is not [allowed]." (site:78; kit-README.md:73) | UNVERIFIABLE | Future process rule; recorded in CLAUDE.md (Hard rules) and README.md:25. Nothing to check today. |
| 16 | "Second tie-break: Shorter total build time, read from the builder's traces" (site:167) | OK | build.py:197/:243 start and end with `total N s`; every line carries `+elapsed s` (:64). |
| 17 | Reproducibility: Claude credentials on the organisers' machine (kit-README.md:36 "It needs a Claude login or ANTHROPIC_API_KEY") | OK, no fail-fast | build.py:106-136, rules.py:217-229, cases.py, audit.py and smoke.py:459 (driven mode only) all go through `claude_agent_sdk.query()`. The SDK (0.2.165, = PyPI latest; wheels for macOS arm64/x86_64, manylinux aarch64/x86_64, win_amd64, 98-110 MB each) prefers its bundled CLI (subprocess_cli.py:258) and falls back to PATH and `~/.local/bin/claude` (:264-301); it inherits `os.environ` minus CLAUDECODE (:819-824), so an exported `ANTHROPIC_API_KEY` or the runner's own login reaches it. Only `--setting-sources=project` is passed (:730; build.py:110), so the organisers' own `~/.claude` settings are excluded and the skill is read from the clone's `.claude/skills/build-phone-agent/SKILL.md` (the only file under `.claude/`). Verified behaviour without any credential: `Not logged in · Please run /login`, cost 0. build.py has no early check for this: rules/cases fail inside their 420 s steps, then the agent run logs an ERROR (:231). |
| 18 | Reproducibility: no machine-specific path or personal auth in the builder's self-test runner (site:235) | **VIOLATION (one line)** | builder/sim.py:30 `CLAUDE_CLI = os.environ.get("CLAUDE_CLI", str(pathlib.Path.home() / ".local/bin/claude"))`; :155 picks that CLI whenever `OPENAI_API_KEY` is unset; :203 runs it. On this Mac it is a symlink to `~/.local/share/claude/versions/2.1.268` (your personal install and login). Verified: with `CLAUDE_CLI=/nonexistent/claude` and no OpenAI key, `Provider.chat` raises `FileNotFoundError` (not caught by :205, which catches only `TimeoutExpired`), which sim.py:572-575 turns into `stop = "customer model failed"` on every case and :650-651 into `judge model failed`. build.py:116 forces the sim runner for generated cases (every hidden brief) and SKILL.md:49/:53 tells the agent to run sim.py, so on a machine without `~/.local/bin/claude` and without OPENAI_API_KEY the whole self-test phase is void and the organisers' trace diverges from yours. The build still produces an agent (lint, dry run, smoke scripts and audit need no model-played customer). The only home-path hit in builder/, tools/, freya.py, SKILL.md, the reference generators and README. |
| 19 | Reproducibility: README tells an organiser everything, in order (kit-README.md:19-29: `cp env.example env.sh`, `source env.sh`, `pip install claude-agent-sdk`) | RISK | README.md:30 says "`env.sh` (gitignored) holds the keys. The team key is already generated" — on a clone env.sh does not exist and no team key is generated; README never says `cp env.example env.sh`, never names FREYA_BANK_TEAM_KEY, mentions ANTHROPIC_API_KEY only at :37, and never mentions OPENAI_API_KEY, CLAUDE_CLI, BUILDER_MODEL or FREYA_WORKSPACE_ID (grep: one hit, :37); `source .venv/bin/activate` appears under "The loop" (:42), not Setup. |
| 20 | Reproducibility: dependency pinning (site:235) | RISK | requirements.txt:1 is `claude-agent-sdk` unpinned. Installed and PyPI-latest are both 0.2.165 today (PyPI JSON), so a clone today matches; build.py:109-113 (`skills=`, `setting_sources=`, `env=`), rules.py:226-229 (`output_format=json_schema`, `effort=`, `max_budget_usd`) depend on this release's option set. |
| 21 | Reproducibility: Python version (kit-README.md:16 "Python 3.10 or newer") | OK (not executed on 3.10) | `ast.parse(feature_version=(3,10))` accepts all 19 files in builder/, builder/tests/, tools/, freya.py and the v3 generators; grep for 3.11+/3.12 features (tomllib, ExceptionGroup, except*, datetime.UTC, typing.Self, TaskGroup, asyncio.timeout, StrEnum, itertools.batched, Path.walk, match, `type X =`, nested same-quote f-strings) found none; the only non-stdlib import anywhere is `claude_agent_sdk`. Local venv is 3.12.0; the clean-clone offline run above used 3.14.7. No 3.10 interpreter on this machine. |
| 22 | Reproducibility: state missing on a clone must not break the run | OK | Clone test: env.sh, .freya-agents.json, .personas.json, results/, .venv absent. freya.py:42-46 creates the workflow when the state file is absent; sim.py:736 and :775 create results/; run_cases.py:54-60 creates personas when .personas.json is absent; build.py:199 creates out/. The reference generators the skill names (SKILL.md:17) and builder/FREYALIB.md / MULTIPRODUCT.md are tracked (git ls-files). |
| 23 | Reproducibility: skill and settings come from the repo, not the author's machine (examples/agent_builder.py:25 "only this folder's settings, not your own") | OK | build.py:109-111 `cwd=ROOT, skills=["build-phone-agent"], setting_sources=["project"], allowed_tools=[Read, Write, Edit, Glob, Grep, Bash], permission_mode="dontAsk"`; ROOT from `__file__` (:36). rules.py:228 and smoke.py:461 use `setting_sources=[]`. sim.py runs `claude -p` from an empty scratch directory (:52-61) so the customer/judge never read CLAUDE.md. |
| 24 | "Models the builder may use: Any" (site:243); no OpenAI call unless the runner opts in | OK | OpenAI appears only in builder/sim.py: Provider.pick (:152-155) uses OpenAI only when `OPENAI_API_KEY` is set, else the Claude CLI. build.py makes no OpenAI call (:48 only scrubs the key). |
| 25 | "Can my builder open practice customers of its own? No. The practice bank serves the 13 cases" (site:291) | OK | Generated cases reuse the 13 mock customers through `mock_case` (cases.py:270); nothing creates customers. |

## Environment an organiser needs

Required (build.py:192-193 refuses to start without the first two):

| Variable | Value |
|---|---|
| `FREYA_API_KEY` | their workspace's key (freya.py:10) |
| `FREYA_BANK_TEAM_KEY` | any string of 16+ characters they make up (env.example:3; tools/score.py:12 sends it as `x-team-key`); used by the practice runners, by the mock bank, and checked at start |
| `ANTHROPIC_API_KEY` **or** a `claude login` in the runner's home | the builder's own model calls (build.py:30, rules.py:42, cases.py:35, audit.py:26); the key must have access to `claude-opus-5-5` (build.py:40, rules.py:51) |

Optional, with defaults:

| Variable | Default / effect | Where |
|---|---|---|
| `FREYA_API_URL` | `https://staging-app.freyavoice.ai` | freya.py:8 |
| `FREYA_WORKSPACE_ID` | first workspace of the key | freya.py:28 |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | when set, sim.py plays the customer/judge with OpenAI; otherwise the Claude CLI | sim.py:28, :155, :172 |
| `CLAUDE_CLI` | `~/.local/bin/claude` (see row 18) | sim.py:30 |
| `BUILDER_MODEL` | `claude-opus-5-5` | build.py:40, :108 |
| `RULES_MODEL`, `RULES_EFFORT` (`low`), `RULES_SAMPLE_MODELS` | rules.py:51-59 | |
| `CASES_MODEL`, `AUDIT_MODEL` | `claude-opus-5-5` | cases.py:697, audit.py:330 |
| `FREYA_AGENT_PROVIDER`, `FREYA_AGENT_MODEL`, `FREYA_SIM_CONCURRENCY`, `FREYA_BANK_HOST` | kit variables (organisers' own) | freya.py:84, :87; tools/score.py:7 |

Also: Python 3.10+, `pip install -r requirements.txt` (one package, ~100 MB wheel that bundles the Claude Code CLI),
network access to staging-app.freyavoice.ai and freya-bank-mock.freyavoice.workers.dev.

## How they reproduce it from a clean clone

`git clone <repo> && git checkout <commit>`; `cp env.example env.sh` and set `FREYA_API_KEY` to a key of their
workspace and `FREYA_BANK_TEAM_KEY` to any 16+ character string; export `ANTHROPIC_API_KEY` (or run `claude login`
once); `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`; `source env.sh && source
.venv/bin/activate`; then `python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json`. The run needs
no state from this machine: `.freya-agents.json` is absent so `freya.save_workflow` creates one workflow per slot in
their workspace and updates it on later runs; the skill is read from the clone's `.claude/skills/`; helper steps use
`sys.executable` (build.py:41) and the build agent runs with `cwd=ROOT`; outputs land in `out/`,
`submission/<slot>.workflow.json` and `traces/<slot>.log`. Two things differ from your runs unless fixed: the
simulator's customer/judge model fallback path (row 18) and whichever Anthropic credential and SDK version they
install (rows 17, 20). Nothing about your account, login, workspace id or key is read from the repository.

## Brief-specific defaults to fix before Sunday (ranked by impact on a never-seen brief)

These are allowed under site:78 (they are Brief A/B values, not hidden-brief values) but cut against site:77 / kit-README.md:80 ("build something that reads a brief, not something that knows this one").

1. **builder/sim.py:30** — the `~/.local/bin/claude` fallback (row 18). Resolve `CLAUDE_CLI` -> `shutil.which("claude")` -> the SDK's bundled binary (`pathlib.Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"`) -> the home path; or drive the customer/judge through `claude_agent_sdk.query()` as smoke.py:458-468 does. This is the one item that changes the organisers' rebuild.
2. **builder/policy.py:55-89 `DEFAULT_TEXTS`** carry Brief A/B sentences that the policy core speaks whenever a generator passes no override (merge at :947-949): `hardship` (:74, "connect you with our customer support team" = briefs/brief-a.md rule 32), `wrap_change` (:87, "mobile app" = rule 36), `too_much_floor` (:68, "The rest stays overdue." = rule 26), `paid` (:72, "one business day to appear" = rule 39), `one_by_one` / `question_all` (:70, :60 = Brief B rule 4), `human_first` / `notalk_first` (:75-76). Spoken unconditionally at :642, :796, :342, :616 (multi only), :588, :624/:788, :634. Make the brief-bearing keys required (raise in `Policy.__init__` when missing) or give them lint-flagged placeholders.
3. **builder/policy.py:942-946** numeric defaults `fail_max=2, human_limit=2, notalk_limit=2, wrap_turns=2` (Brief A rules 37/42/45) and :822 the fixed hardship state line "make no persuasion attempt and propose nothing yourself" (rule 32); freyalib.py:1033 `question_back_node(limit=2)` (rule 15). Make them keyword-required or spec-driven.
4. **builder/smoke_scripts/opening.json:6, third_party.json:6, wrong_number.json:6** require `"Freya Bank"` in the opening while SKILL.md:47 says "Fix failures in the generator": for a hidden brief naming another bank the first expectation fails on every script and a literal-minded build agent may add "Freya Bank" to the opening. `out/<slot>.spec.json` has no bank-name field (grep spec_check.py: none). Substitute the bank name and forbidden words from the spec, or drop that term.
5. **builder/multiproduct.py:450-470** `finalize_code(default_key="refused", paid_reason=None -> paid_key, order="product")` with the docstring admitting Brief A/B conventions (:11-14, :459 "Brief B's rule"); the `api=` enum check (:473-476) is optional. Make `paid_reason` and `order` required and `api` mandatory. (Older flow; policy.py is the default per SKILL.md:17.)
6. **builder/audit.py:124** judges "every holiday date, 12th/7th business day, 10:00-19:00, three wrong answers" — Brief A values in the audit prompt; reword generically.
7. **builder/cases.py:272** `now` defaults to the kit's practice date 2026-10-14T11:00; GROUPS (:291-310) enumerate Brief A families. Derive `now` from the spec's call-date range.
8. **builder/freyalib.py:20-34 and :118** docstring example literals (holiday 2026-12-25, 10:00-19:00, `date_of_birth`/`support`, a `test_variables` example that SKILL.md:43 forbids). Documentation only.
9. **Reference generators** out/gen_brief-a_v3.py / gen_brief-b_v3.py retype every Brief A value (HOLIDAYS :27 etc.) instead of loading `out/<slot>.spec.json` as SKILL.md:16 instructs; the never-seen-brief builds out/gen_brief-c.py:15 and gen_brief-d.py:19 imitated that (retyped holiday lists; neither uses `Policy(`, so DEFAULT_TEXTS leakage has never been exercised on a fresh brief). Rewrite the references to read the spec so the structure that gets copied is a spec lookup.
10. **build.py** guardrails: refuse to export (or write a loud line) when lint reports ERRORs (:234-240); cap lint/audit by the time left (row 5); fail fast when no Anthropic credential is present (row 17); add a brief-agnostic "foreign literal" check (dates, HH:MM, quoted sentences in out/<slot>.workflow.json must occur in the given brief or API file).

Housekeeping before submission: run the current build.py on brief-a and brief-a+brief-b, commit those traces and
exports (rows 1, 9, 11), score that agent with `--reps 3`, and tag the last pre-17:00 UTC commit on Sunday.

## Auditor claims refuted or corrected

- "traces/brief-a.log ... written by the pre-12:07 build.py" and "git 1613396 at 11:35": correct for brief-a; brief-b's trace was committed in 95f11b8 at 12:07 but produced 11:35-11:43 by the same older builder (header lacks `cases=`). Not refuted, sharpened.
- "Scan of all tracked files for the fak_ pattern ... 0 hits": a plain regex gives 3 hits, all placeholders (docs/api.md:24 `fak_your_key`, env.example:1, tools/check_secrets.sh:6). The substantive claim (no real key) holds.
- Line numbers off by a few: policy.py "40" -> :38 (the "nothing in this module names a holiday" sentence); `Policy.__init__` "945-947" -> :942-946; multiproduct `api=` check "466-468" -> :473-476; rules.py "never a default" :154 -> :152; cases.py "Never a check the brief does not require" :290 -> :285; hackathon-site practice customer ":289" -> :287. None changes a conclusion.
- "Not verified: whether DEFAULT_TEXTS actually leak in a fresh policy.py-based build": confirmed unverifiable and confirmed that gen_brief-c.py / gen_brief-d.py contain no `Policy(` call (grep: 0), so no fresh-brief build on the current architecture exists.
- "Only the macOS arm64 wheel inspected": PyPI lists manylinux aarch64/x86_64 wheels of 107-108 MB for 0.2.165 (same size class as the macOS wheels that carry the 236 MB binary), consistent with a bundled CLI on Linux; the Linux wheel content itself was not opened.
- "PyPI latest is 0.2.165": confirmed (PyPI JSON).
- "Python 3.10: grep found none": confirmed by `ast.parse(feature_version=(3,10))` on 19 files plus the offline clean-clone run on 3.14.7; still not executed on 3.10.
- Everything else in both findings lists was confirmed against the files; no "compliant" claim was found false.

## Not verifiable from the repo

- What the organisers' rebuild environment provides (Anthropic credential, a `claude` binary at `~/.local/bin`, SDK version at install time, OS).
- Whether `asyncio.wait_for` cancellation (build.py:227) ends the CLI subprocess promptly at the budget.
- The platform sandbox's network policy for code nodes (docs/tools-and-code.md:507 "Not documented").
- Whether any workflow was ever edited in the dashboard by hand.
- Behaviour on Python 3.10 and on Linux (not executed).
- Anything about the Sunday process (bug-fix-only rule, submission timing).
