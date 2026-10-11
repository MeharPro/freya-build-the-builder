# Final run procedure

Official source: [Freya hackathon](https://www.freyavoice.ai/hackathon), captured in `hackathon-live-20261010.md` and rechecked against the live page on 11 October. On Sunday 11 October, hidden briefs arrive at **17:00 UTC / 13:00 Toronto**; submission is due before **20:00 UTC / 16:00 Toronto**. Each brief is one Markdown file with its own API file. The organisers supply no hidden practice cases.

## Before release

Keep a committed, tested builder revision and record its SHA. Before release, prioritize a successful fresh public-A build with its audit, a fresh multi-product B build, then a raw-material rehearsal. Recheck the public cases over three repetitions where time permits: a case counts only if all three pass. A reference generator's 39/39 public calls does not establish what the automatic builder produces.

Use one team workspace and one Freya API key. Confirm registration, team membership (at most two), the submission recipient in the kit email, and an accessible Git remote/reviewer access. As of the last local check, this checkout had **no Git remote**; a local commit alone cannot satisfy the repository URL requirement. Keep keys in gitignored, owner-readable `env.sh`. Reviewers supply their own Freya and builder-model credentials; no author's personal Claude login is needed.

## Run each brief sequentially

From the repository root, replace the two input paths below with the supplied files. The output slot is the Markdown filename without its extension.

```bash
source env.sh
export BUILDER_PROVIDER=openai
python3 builder/build.py path/to/brief.md path/to/api.json --preflight
python3 -u builder/build.py path/to/brief.md path/to/api.json --minutes 29
```

For Claude, select `BUILDER_PROVIDER=claude`, install `requirements.txt` and supply Anthropic access. Do not use `--no-rules` or `--no-audit` for the final build. Do not run simultaneous builds or external tests while a timed build is active.

The runner owns generation, available tests, repair, publication, export and trace. A zero exit code plus `submission/<slot>.manifest.json` records completion. A failed run removes its submission export; inspect the dated trace and rejected candidate instead of submitting an older file under the new trace. All testing inside a build counts against the same 29-minute budget. The current runner does **not** automatically create independent practice cases for hidden briefs. Its audit and smoke checks cannot establish a hidden score; the optional case writer relies on the fixed public mock customers and may not fit a changed hidden API.

After release, builder fixes must remain generic and contain no hidden policy rule, value or name. Phone-agent changes must come from a new automatic run. Select the export and trace from the same run; do not edit or re-export a different remote version afterwards. The JSONL trace and success manifest record the builder-source hashes; the manifest also records the Git commit and whether the source was dirty at run start. **After any builder-source change, rerun both hidden briefs from the final revision** so the submitted commit can reproduce both agents.

## Prepare the entry

Preserve both exports, manifests and their exact log/JSONL traces. Check each manifest’s hashes and compare each trace's `source_hashes` with the final builder files. Stage the complete code and artifacts, run `bash tools/check_secrets.sh`, commit, and confirm the commit is reachable by organisers at the submitted repository URL. The submission form needs the team name, repository URL, SHA, reproducible run command, two workflow paths and two trace paths. Send it to the address in the participant's kit email before 20:00 UTC. No entry has been sent by this assistant.

A successful audit is evidence of coverage, not a hidden score. The official score requires each case to pass all three repetitions, including ledger correctness, conversation policy and honesty. Keep failed and incomplete practice runs in the record.
