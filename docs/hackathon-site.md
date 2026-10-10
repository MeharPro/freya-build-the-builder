# Build the Builder | Freya × Y Combinator — the event site, captured

Source: https://www.freyavoice.ai/hackathon (tabs Overview, Data, Evaluation, Submit, Leaderboard, Rules, FAQ).
Captured Saturday 10 October 2026, morning, before any run. Re-read the live site for changes.

- Register on YC: https://events.ycombinator.com/AI-FDE-Build-the-Builder26
- Kit: https://www.freyavoice.ai/hackathon/build-the-builder-v3.zip (version 3; a copy is in `kit-archive/`). The kit has a version number in its file name and at the top of its README; it goes up when the kit changes.
- Platform: https://staging-app.freyavoice.ai (sign in with the account the organisers mailed; API keys are under "API keys" in the dashboard)
- Public platform docs: https://docs.freyavoice.ai (personas, simulations, calls; workflow creation is only in the kit's `docs/`)

---

## Overview — What this is

A bank has customers who are late on a payment. It wants to phone each of them, check who is on the line, say what is owed and record when they will pay. On Freya, software makes that call instead of a person.

Example piece of one call:

> Phone agent: Your credit card has 420 dollars past due. Can you pay today?
> Customer: Not today. I can do it on Friday.
> Phone agent: 420 dollars on Friday the sixteenth. Do you confirm?
> Customer: Yes.
> → `create_promise 420.00 2026-10-16` recorded in the bank's system

The last line is what the bank's system keeps. The organisers check that record, and they check the conversation.

That software does not know the bank's rules by itself. Someone has to read the bank's specification and build the caller to follow it: never mention the debt before the identity check, never accept a promise on a holiday, say nothing to a relative. Today a person does this by hand, and one bank takes days.

**The question of this hackathon: can a program do that work instead?**

### Three words

| Word | Meaning |
|---|---|
| Phone agent | The software that talks to the customer. It lives on Freya as a workflow: steps, prompts and tools |
| Brief | The bank's specification for these calls: who to ask for, how to check identity, which payment dates are allowed, how to close the call |
| Builder | The program you write. It reads a brief and creates the phone agent. Nobody edits the phone agent by hand |

**You write the builder. They score the phone agent it creates.**

Pipeline of one run:

```
Brief (policies, tool API docs, practice customers)
  → Your builder (reads the brief, creates the phone agent, tests and improves it)   ← the part you write
  → Phone agent (a workflow on Freya: conditional routes, tool calls)
  → Their benchmark (simulated customers talk to the phone agent; they read the bank's records)
  → score = cases passed / cases run
```

A new brief goes in, a different phone agent comes out, no edits by hand.

### How the weekend goes

1. Download the kit from the Data tab. Two briefs, the bank's tool API, thirteen practice customers, the Freya workflow reference and a small working builder.
2. Run the sample builder. It creates a phone agent on Freya in your workspace.
3. Test that phone agent. Simulated customers talk to it in text. You see which ones it handled correctly and why the others failed.
4. Write your own builder and repeat steps 2 and 3 as often as you like.
5. On Sunday they publish briefs you have not seen. Same kind of call, different rules: other identity questions, other limits and deadlines, another outcome table, another calendar. The seven tool names stay the same. Their fields and allowed values can change.
6. You run your builder once on each new brief and submit the phone agents it created, your code and the builder's trace.
7. They test those phone agents on customers nobody has seen. The share they handle correctly is your score.

| Milestone | Time (UTC) | Note |
|---|---|---|
| Start | Sat 10:00 | kit and keys; build against the 13 practice cases |
| Hidden briefs open | Sun 17:00 | run your builder |
| Close | Sun 20:00 | submit |
| Results | after review | |

The three hours between 17:00 and 20:00 are for running the builder and fixing bugs, not for tuning it to the new briefs.

### What counts

- Only the phone agents are scored. Your rank comes from their score. They also rerun the builders of the top entries to verify them. Build time is the second tie-break.
- A customer counts as handled when the bank's records are right afterwards and the conversation followed the brief. There is no partial credit.
- The builder must work alone. One command, a brief as input, a phone agent as output. No manual edits after it runs.
- The final briefs are hidden so that a builder tuned to the two public briefs does not win. It has to read a brief it has never seen.
- After the hidden briefs open you may fix a bug in your builder. You may not write anything from a hidden brief into it: no rule, no value, no name. Fixing a crash on a table your parser did not expect is allowed. Adding the new brief's holiday dates or outcome names to your code or prompts is not.
- Calls are in English. The phone agent gets the date and time of the call as a variable, `now`. Every date rule uses it.
- Every phone agent runs on the same Freya model. Your builder may use any model or coding agent you like.

### Inside a phone agent

A phone agent on Freya is a workflow. Each step has its own prompt and tools. Conditional routes decide which step takes the conversation next. Calculations such as business days can run as code instead of being left to the model. How many steps, which routes and which tools is the design problem the builder solves.

---

## Data — Thirteen practice cases and the kit

Everything is synthetic. The bank, the customers, the debts and the payments do not exist.

To run the kit you need a Freya API key. Create one in your Freya workspace under API keys.

| File | What it is |
|---|---|
| `briefs/brief-a.md` | Freya Bank's specification for customers who are late on one product. 47 rules |
| `briefs/brief-b.md` | The extra rules for customers with up to three products. Builds on Brief A |
| `tools/openapi.json` | The bank's tool API that the phone agent calls. Seven tools: verify_identity, get_account, create_promise, add_note, schedule_callback, transfer_to_agent, close_call |
| `public-test-set.json` | The thirteen cases: who the customer is, what they do and what the bank's records must show afterwards |
| `docs/` | The Freya workflow format, tools and code nodes, and the API calls a builder needs. Written for a program to read |
| `freya.py` | A small client for the Freya API. Creates a workflow once and updates it on later runs. Standard library only |
| `examples/base-agent.json` | An example phone agent: two steps, four tools. The same one that is in your workspace. A place to start, not a good score |
| `examples/agent_builder.py` | An example builder on the Claude Agent SDK with one skill. Claude reads the brief, builds the agent, tests it and fixes what fails |
| `env.example` | The two keys you set: your Freya API key, and a team key you make up for the practice bank |
| `tools/run_cases.py` | Runs the practice cases against your phone agent and prints pass or fail per case, with the reason |

### How one case runs

```
Simulated customer (follows the case script; text, not audio)
   ⇄ conversation ⇄  The phone agent (your builder made)
                        → tool calls →  Mock bank API (identity, debts, promises; they host it)
                                           → Ledger (every call and its result)
                                              → Scorer (pass or fail per case: final state + transcript)
```

The mock bank API stands in for the bank's own systems. The phone agent calls it to check identity, read the debt and record a promise. They host it, so they can see what was really recorded. The scorer reads that record, not what the phone agent says it did. You pick a team key, and your practice sessions and their records belong to that key.

### Practice cases

Ten cases use Brief A and three use Brief B. Every case runs on Wednesday 14 October 2026 at 11:00, so the dates are fixed. Full scripts and checks are in `public-test-set.json`.

| Case | Brief | Family | What happens | Level |
|---|---|---|---|---|
| PUB-01 | A | Happy path | Confirms identity and pays the full amount today | easy |
| PUB-02 | A | Third party | A relative answers | medium |
| PUB-03 | A | Identity | Three wrong answers | medium |
| PUB-04 | A | Dates | Wants a date after the deadline | medium |
| PUB-05 | A | Hardship | Lost his job, declines the support team | medium |
| PUB-06 | A | Amounts | Full amount is too much, accepts the floor | hard |
| PUB-07 | A | Dates | A vague period, then a holiday | hard |
| PUB-08 | A | Already paid | Says she already paid | medium |
| PUB-09 | A | Restructuring | Asks for a new payment plan | medium |
| PUB-10 | A | Tool failure | The promise service fails on the first call | hard |
| PUB-11 | B | Multi-product | Three products, one date for all | medium |
| PUB-12 | B | Multi-product | Promises one product, refuses two | hard |
| PUB-13 | B | Multi-product | One date for both, but the deadlines differ | hard |

---

## Evaluation — One number: the share of hidden cases passed

A case is one simulated customer. It passes only when three checks all pass. There is no partial credit.

The bank's API does not enforce the brief. It records a promise on a holiday or below the minimum without complaint. Keeping the rules is the phone agent's job.

| Check | Question | Example |
|---|---|---|
| Outcome | Is the ledger in the right state? | Promise on the right product, date and amount, recorded once |
| Policy | Did it stay inside the brief? | No debt read before the identity check, no date past the limit |
| Honesty | Did it tell the customer the truth? | Never says "recorded" when the tool call failed |

Outcome is read from the bank's records. Policy and honesty are read from the transcript by a judge model, against the checks listed in each case.

A correct refusal counts. When the customer disputes the debt, the passing outcome is a recorded dispute and no promise. A phone agent that pushes for a promise anyway fails.

### The final benchmark

| Item | Value |
|---|---|
| Hidden briefs | 2. One is a clean specification. The other is raw bank material: a mail, a policy extract, a memo that changes it, a code list |
| Customers per brief | 30, with one to three products, on several calendar days |
| How customers talk | Like people: a number said in two parts ("463..." then "51"), corrections, talk about other things, a question back, amounts and dates in words |
| Repetitions | 3 per case. The case passes only when all 3 runs pass |
| Score | cases passed / 60 |
| First tie-break | Total promised amount recorded on the cases that passed |
| Second tie-break | Shorter total build time, read from the builder's traces |
| Third tie-break | Earlier submission time |

### Score yourself

The kit includes the scorer. Point it at a phone agent and it runs the practice cases and prints, for each one, the tool calls the phone agent made and why it failed.

```
$ python3 tools/run_cases.py <agent_id> --brief A

PASS PUB-01 easy   Happy path   | verify > verify > get_account > promise > close_call
FAIL PUB-04 medium Dates        | verify > verify > get_account > promise > close_call
       - promises [('p1', 1250.0, '2026-10-27')], expected [('p1', 1250.0, '2026-10-23')]
...
5 / 10 passed
```

The printout shortens two tool names: verify is verify_identity and promise is create_promise.

A ten-case run takes 3 to 11 minutes. One simulation runs at a time per workspace, and a team has one workspace. The same phone agent can pass a case in one run and fail it in the next, so run more than once before you trust a score: `--reps 3` counts a customer only when every run passes, as the final does.

---

## Submit — Two phone agents, one commit and the builder's trace

- On Sunday at 17:00 UTC they send two hidden briefs to every team. Each comes with its own tool API file.
- Run your builder on each brief and keep everything it prints. You may run it more than once. Submit one phone agent per brief, with the trace of the run that made it. Do not edit a phone agent after the run.
- Export each phone agent to a file with `freya.export_workflow` and commit the files. They load them into their own workspace, so what you export is what they score.
- Before 20:00 UTC, send the form below to the address in your kit email.

```
$ python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log
```

```json
{
  "team": "your-team-name",
  "repo": "https://github.com/you/your-builder",
  "commit": "9f2c1ab",
  "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
  "workflows": {
    "hidden-1": "submission/hidden-1.workflow.json",
    "hidden-2": "submission/hidden-2.workflow.json"
  },
  "traces": {
    "hidden-1": "traces/hidden-1.log",
    "hidden-2": "traces/hidden-2.log"
  }
}
```

### The builder's trace

A trace is the record of one builder run: what it read, what it decided and what it created. One per hidden brief. Commit the files to your repository.

| In the trace | Why |
|---|---|
| Start and end time of the run | Build time breaks ties between equal scores |
| Every model call the builder made: which model, and what it was asked for in one line | Shows how the builder works, not only what it produced |
| What it created on Freya: workflow id, agent id, number of steps and tools | Ties the phone agent you submit to this run |
| Any test it ran on its own phone agent, with the result | A builder that checks its own work is the point of the exercise |

Plain text is fine. There is no required format. **Remove API keys before you commit.**

If you built your builder with a coding agent such as Claude Code or Codex, you may also share those session logs. Optional. The top three teams talk their approach through with the organisers, and a log is the easiest way to show it.

### How they verify

They test the phone agents you submitted. For the top ten teams they also clone the repository at that commit, run the builder themselves on the same briefs and compare with your trace. Every trace is also read by a reviewer agent that checks it against the submitted code and the phone agent it claims to have created. If their run scores clearly below yours, the entry is removed. This catches phone agents that were edited by hand.

### Limits

| Limit | Value |
|---|---|
| Builder run time | 30 minutes per brief, including any test the builder runs on its own phone agent |
| Workflows per workspace | 200. Update one in place instead of creating a new one per run |
| Models the builder may use | Any. You pay for your builder's own model calls |
| Model the phone agent runs on | The Freya model set in freya.py. The same for every team. Do not change it |
| Practice simulations | 1 running at a time per workspace |

---

## Leaderboard

Empty at capture time: "Nothing is scored yet. Results appear here after the hidden benchmark has run and the top entries are verified." Columns: Rank, Team, Score, Passed, Promised amount, Submitted.

---

## Rules

- Enter solo or as a team of two.
- You submit a builder. A hand-built phone agent on its own is not a valid entry.
- The phone agents for the hidden briefs must come out of the submitted commit with no manual edits.
- Submit one builder trace per hidden brief. An entry without traces is not ranked.
- The phone agent may call only the tool API from the kit. A call to any other service fails the case.
- Do not probe or load-test the platform. One Freya key per team.
- You may fix your builder after the hidden briefs open. Nothing from a hidden brief may be written into it. A reviewer checks the commit for that.
- All data is synthetic. Do not bring real customer data.

### Prizes

| Place | Prize |
|---|---|
| First | YC interview |
| Second | AirPods |
| Top three | Final interview with Freya |
| Prize pool | $3,000 in Freya credits |

---

## FAQ

**I did not get the login mail.** Look in spam first (Outlook, Hotmail and some university addresses were filtered). Otherwise reply to them and they send it again.

**Where is the kit?** Data tab, "Download the kit". Unzip it and read README.md first.

**Where do I get a Freya API key?** Sign in with the account they mailed, open API keys in the dashboard and create one. Put it in env.sh as `FREYA_API_KEY`.

**Teammate has no account / two workspaces.** Work in one workspace. Its owner invites the teammate from Workspace settings. (Not relevant for a solo entry.)

**A test call in the dashboard never passes identity.** The workspace has one practice customer for dashboard test calls. Answer as that customer: date of birth 14 March 1988, last four digits 4471. After a call has closed, the same customer starts fresh once it has been idle for 5 minutes. `run_cases.py` opens a fresh customer for every case, so it is not affected.

**How many workflows can a workspace hold?** 200. Still, update your workflow in place instead of creating a new one per run.

**Can my builder open practice customers of its own?** No. The practice bank serves the 13 cases PUB-01 to PUB-13 only. To check a phone agent on a brief with no cases, talk to it with `POST /api/v2/chat/message` (see docs/api.md).

**Do the hidden briefs come with practice cases?** No. Each comes with its tool API file only.

**Is the raw-material brief one file?** Yes. Each hidden brief is one Markdown file, with its own tool API file next to it. `{brief_path}` is that one file.

**May I use code I wrote before the event?** Yes. Nothing from the hidden briefs may be in your builder, and the phone agents must come out of your builder with no edits by hand.

**Is the score taken from the phone agent we submit, or from their rebuild?** From the phone agents you export and submit. They rebuild only the top entries, to check that the submitted phone agent really came out of your builder. Model output varies from run to run, so they do not expect an identical workflow. They look at its structure and its score.

**My score dropped and I changed nothing.** The simulated customers and your phone agent are language models, so runs differ. A run also suffers when the model is busy: `run_cases.py` prints the slowest agent turn per call. Run again, and use `--reps 3` before you trust a number.

**Something else?** Reply to the login mail. It reaches them.
