For the newest archive integration and current evidence, read [docs/CURRENT-REVIEW.md](docs/CURRENT-REVIEW.md). Earlier notes below describe the initial hardening pass.

# Build readiness

The ZIP is the starting implementation, including its historical workflows and
traces. Scores described in those files are historical claims, not scores measured
by the current changes. Winning depends on the hidden benchmark; no offline test
can guarantee a rank.

## Run locally

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 -m unittest discover -s builder/tests -v
source env.sh
.venv/bin/python builder/build.py briefs/brief-a.md tools/openapi.json --preflight
.venv/bin/python builder/build.py briefs/brief-a.md tools/openapi.json
.venv/bin/python builder/build.py briefs/brief-a.md briefs/brief-b.md tools/openapi.json
```

`--preflight` checks local files, API shape, credential presence and SDK compatibility.
It does not prove authentication, model availability or a benchmark score. The Claude
CLI can use an authenticated subscription login; a new Anthropic key is not required
when that login works. A read-only model probe on October 10 reported that the local
OAuth session had expired and could not be refreshed, despite `claude auth status`
reporting a login. Reauthenticate before a live build.

## Changes to the base

- Required stages fail with a nonzero exit code. A failed model run cannot export
  an old saved workflow. Prior attempts are preserved under gitignored `build-history/`.
- Validate local and exported workflows, including conversation-first entry and
  the absence of `test_variables`. Publish the current candidate before exporting.
- Audit the exported representation. Every active rule must be implemented with
  no explicitly unverified evidence. Unresolved candidates stay outside `submission/`.
- Use one monotonic time budget, bounded helper calls and process-group cleanup.
  Reserve five minutes after generation for final checks. Serialize builds in this
  workspace to avoid artifact and simulation conflicts.
- Hash briefs, API, generator, workflow, export, audit and traces in a per-run
  manifest. Preserve full helper output in the redacted JSONL trace.
- Reject omitted required tool fields, handle changed numeric enum values and
  absent `customer_id` fields, accept non-identifier failure reason strings, and
  reject invalid business calendars.
- Require correction-aware confirmation and forbid silently changing the amount
  or date after the customer confirms. Expand the builder's boundary checks and
  repeated-test guidance.

The phone-agent model and supplied bank briefs/API/scorer remain as shipped.

## Evidence needed before claiming readiness

1. Run A and A+B through the complete builder with fresh traces.
2. Score A against A cases and A+B against B cases. Repeat three times; inspect
   failures and call transcripts rather than trusting one green run.
3. Exercise conversation styles, changed-calendar synthetic briefs, and the
   changed-schema fixture. Synthetic expectations are useful diagnostics, not an
   official leaderboard score.
4. When hidden briefs open, run the builder on each brief/API pair and inspect the
   validated manifests. Keep the exact matching exports and traces. Do not hand-edit
   either phone agent or encode hidden policy values into builder source.

The live event page lists hidden briefs opening **October 11 at 1 p.m. Toronto time**
and submission closing **October 11 at 4 p.m. Toronto time** (17:00 and 20:00 UTC).
See [the official challenge](https://www.freyavoice.ai/hackathon).

`--no-rules --no-audit` is a development escape hatch, recorded as unaudited in the
manifest. It is not evidence of policy coverage. Model audits and static tests
cannot replace live scoring of the generated phone agents.

## Validation in this workspace

`python3 -m unittest discover -s builder/tests -q`: **69 tests passed**.
`python3 -m compileall -q builder`: passed. Live Freya scores are not yet measured.

## Rule-inventory integrity

Reviewing [τ^τ-Bench](https://arxiv.org/pdf/2609.04611) prompted an additional
inspection of the extraction stage. The runner now rejects numbered requirements
still missing after gap-fill. Rule normalization rejects duplicate identifiers,
unknown/self/cyclic overrides, and competing replacements without an explicit
override chain. Seven regression tests cover these cases; the bundled 64-rule
inventory remains valid. Lexical token warnings alone remain diagnostic because
dates or identifiers can be metadata rather than obligations. These checks do not
prove that all unnumbered requirements were extracted correctly.
