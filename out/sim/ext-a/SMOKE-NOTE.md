# Smoke run of the extended-case support (10 Oct 2026, cloud worker)

Command: `python3 builder/sim.py 4045179c-42e8-436d-9fe2-c21c616c71fc --cases tests/cases/brief-a-extended.cases.json --only EXT-A-01,EXT-A-02 --concurrency 1 --out out/sim/ext-a/smoke.json --transcripts out/sim/ext-a/smoke/`

Result: both cases FAIL before any call: `harness: URLError: Tunnel connection failed: 403 Forbidden`. The cloud
environment's network policy denied the CONNECT to `staging-app.freyavoice.ai` (and to the mock bank and OpenAI);
the agent was never reached. This is an environment limit, not a result about the agent or the cases. Re-run the
command from a machine with network access.

What was verified offline instead: `run_case` opened the practice session with `{"case": "PUB-01"}` for EXT-A-37 and
sent `now = 2026-10-16T11:00` in `customerVariables` (stubbed `http`/`Chat`); `persona_for` builds every new case.
