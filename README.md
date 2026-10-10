# Build the Builder — Freya × Y Combinator hackathon

Weekend of 10–11 October 2026.

**The task.** Write a *builder*: one command that reads a bank's brief (a Markdown specification for late-payment calls) plus the bank's tool API file, and creates a *phone agent* (a Freya workflow) with no manual edits. On Sunday the organisers publish two briefs nobody has seen. The phone agents the builder creates from them are scored by simulated customers: score = cases passed / 60, no partial credit, every case runs 3 times and must pass all 3.

Everything the organisers published is in this repo:

| Where | What |
|---|---|
| [docs/hackathon-site.md](docs/hackathon-site.md) | The event site: overview, data, evaluation, submission format, rules, FAQ |
| [docs/kit-README.md](docs/kit-README.md) | The kit's own README (kit version 3). Read it in full |
| [briefs/](briefs/) | Brief A (47 rules, one product) and Brief B (up to three products, builds on A) |
| [tools/openapi.json](tools/openapi.json) | The bank's seven tools: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call` |
| [public-test-set.json](public-test-set.json) | The 13 practice customers with scripts, expected ledger and conversation checks |
| [docs/workflow-format.md](docs/workflow-format.md), [docs/tools-and-code.md](docs/tools-and-code.md), [docs/api.md](docs/api.md) | The Freya workflow format, tools/code nodes/hooks, and the REST calls a builder needs |
| [examples/](examples/) | The organisers' base agent (2 steps, 4 tools, passes ~2/13) and example builder |
| [kit-archive/](kit-archive/) | The original kit zip, untouched |

## Timeline (UTC)

| When | What |
|---|---|
| Sat 10 Oct 10:00 | Kit and keys. Build against the 13 practice cases, as often as you like |
| Sun 11 Oct 17:00 | Hidden briefs open. Run the builder once per brief. Only bug fixes allowed, nothing from a hidden brief may go into the code or prompts |
| Sun 11 Oct 20:00 | Submission closes: the JSON form (see below) by mail to the address in the kit email |

## Setup

1. `cp env.example env.sh` (gitignored) and fill in the three variables the builder needs: `FREYA_API_KEY` (sign in at https://staging-app.freyavoice.ai, open **API keys**, create one, `fak_...`), `FREYA_API_URL` (`https://staging-app.freyavoice.ai`) and `FREYA_BANK_TEAM_KEY` (your team key for the mock bank). Claude access for the builder's model calls: either `ANTHROPIC_API_KEY` in the environment or `claude auth login` on the machine (the SDK bundles the Claude Code binary). No OpenAI key is needed: the local simulator plays the customer and judge with Claude.
2. `source env.sh`
3. Python 3.10+. The kit itself is standard library only. The builder uses the Claude Agent SDK, installed in `.venv`:
   ```bash
   uv venv && uv pip install -r requirements.txt && source .venv/bin/activate
   # or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   (Debian images: add --ignore-installed PyJWT)
   ```
   It also needs a Claude login (Claude Code) or `ANTHROPIC_API_KEY`.

## Rebuilding with your own model credentials

A reviewer does not need Karan’s account or a personal Claude login. Set `ANTHROPIC_API_KEY` in the process environment (from your own secret store), alongside your own `FREYA_API_KEY` and a new `FREYA_BANK_TEAM_KEY` of at least 16 characters. Install the pinned requirements and run the command below. The SDK supplies its CLI; an interactive login is optional for local development. A clone contains no credentials, workspace state or team key.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Set ANTHROPIC_API_KEY, FREYA_API_KEY and FREYA_BANK_TEAM_KEY through your secret store.
.venv/bin/python builder/build.py briefs/brief-a.md tools/openapi.json --preflight
.venv/bin/python builder/build.py briefs/brief-a.md tools/openapi.json
```

`BUILDER_MODEL`, `RULES_MODEL`, `AUDIT_MODEL` and `CASES_MODEL` select the builder’s models. The credential must have access to the selected models. `OPENAI_API_KEY` is optional for the local simulator; otherwise it uses the same Anthropic access. The phone-agent model is unchanged. Preflight checks configuration presence, not whether a supplied key has credits or model access.

The runner rejects failed stages, stale exports, invalid tool definitions and unresolved audits. It archives prior attempts and writes a manifest tying each successful export to its input and trace hashes. Generated case tooling is imported for experiments; the submission runner does not automatically treat fabricated cases as official practice cases for unseen schemas. Historical practice exports and reports in this archive are reference material, not validated outputs of the current runner.

## The loop

```bash
source env.sh && source .venv/bin/activate

# 1. put the organisers' base agent on Freya and score it (prints workflow_id and agent_id)
python3 -c "import freya,json; print(freya.save_workflow('base', json.load(open('examples/base-agent.json'))))"
python3 tools/run_cases.py <agent_id> --brief A          # 3 to 11 minutes; one simulation at a time per workspace

# 2. run OUR builder (writes out/<slot>.workflow.json, submission/<slot>.workflow.json, traces/<slot>.log)
python3 builder/build.py briefs/brief-a.md tools/openapi.json
python3 builder/build.py briefs/brief-a.md briefs/brief-b.md tools/openapi.json     # Brief B builds on A: pass both

# 3. score the way the final does: 3 reps, people-like talk, saved call ids
python3 tools/run_cases.py <agent_id> --brief A --reps 3 --style talkative --out results/run.json
python3 tools/run_cases.py <agent_id> --brief B --only PUB-11,PUB-12,PUB-13
```

`run_cases.py` prints PASS/FAIL per customer with the tool calls made and the reason for a failure. `--style` is one of `pieces`, `corrects`, `talkative`, `asks_back`, `in_words`. A failed call's transcript: `freya.get_call(call_id)["messages"]` (call ids are in `--out`).

## Layout

```
builder/build.py        OUR builder: the submission entry point (brief(s) + tool API in, phone agent + trace out)
.claude/skills/         the skill(s) the builder runs Claude with. This is where the builder's knowledge lives
freya.py                API client. save_workflow() creates once then updates in place and publishes. export_workflow() writes the submission file
tools/run_cases.py      practice scorer (ledger + judge). tools/score.py: the ledger check
tools/check_secrets.sh  staged-file credential check: run before committing
out/                    workflow JSON the builder writes
submission/             exported phone agents, one per brief (what is scored)
traces/                 one trace per builder run (committed; keys scrubbed)
results/                run_cases.py outputs (gitignored). results/log.jsonl is the score history
env.sh                  keys (gitignored)
```

## Submission (Sunday before 20:00 UTC)

1. Enable `set -o pipefail`, then run `python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.console.log` (same for hidden-2). The builder itself writes `traces/hidden-1.log` and `submission/hidden-1.workflow.json`. Re-running is allowed; submit one agent per brief with the trace of the run that made it. Never edit a phone agent after the run.
2. Stage the exported workflows, matching traces and code, run `bash tools/check_secrets.sh`, then commit. A failed check must be fixed before committing.
3. Push, then mail this form to the address in the kit email:
   ```json
   {
     "team": "<team name>",
     "repo": "<your-repository-url>",
     "commit": "<sha>",
     "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
     "workflows": { "hidden-1": "submission/hidden-1.workflow.json", "hidden-2": "submission/hidden-2.workflow.json" },
     "traces":    { "hidden-1": "traces/hidden-1.log",              "hidden-2": "traces/hidden-2.log" }
   }
   ```

## Rules that decide the ranking

- Only the phone agents are scored. Rank = score; ties broken by total promised amount on passed cases, then shorter build time (from the traces), then earlier submission.
- The builder must work alone: one command, a brief in, a phone agent out. Top entries are rebuilt by the organisers from the commit and reviewed by an agent that reads the trace against the code. A hand-edited agent is removed.
- Nothing from a hidden brief may be written into the builder: no rule, value, name, holiday date or outcome name. Fixing a parser crash is fine.
- The phone agent runs on the model fixed in `freya.py` (`AGENT_LLM`). Do not change it. The builder may use any model.
- 30 minutes of build time per brief, tests included. 200 workflows per workspace: update in place. One simulation at a time per workspace. One Freya key per team.
- The phone agent may call only the kit's tool API. All data is synthetic.
