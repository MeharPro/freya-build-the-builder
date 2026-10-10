# Freya public docs (saved copies)

Saved on 10 October 2026 from https://docs.freyavoice.ai and the staging server, for offline reading. The kit's own `docs/api.md`, `docs/workflow-format.md` and `docs/tools-and-code.md` are the primary reference for workflow creation (which the public docs do not cover); these files cover the rest of the API.

| File | What |
|---|---|
| `llms.txt` | Index of every public docs page (each is fetchable as `<url>.md`) |
| `llms-full.txt` | The guides in full. API reference pages in it are one-line stubs; see below |
| `openapi.json` | The staging server's full API spec (2.7 MB, 96 paths), from https://staging-app.freyavoice.ai/api/openapi.json. It has the simulation, persona, chat and version routes that the docs-site copy lacks. Its `servers` entry names production; the hackathon uses `https://staging-app.freyavoice.ai` (see `env.sh`) |
| `openapi-builder-subset.json` | Only the paths a builder needs (chat, simulations, personas, workflow, versions, call, workspaces, api-keys, agents) with the schemas they reference |
| `api-reference/*.md` | The rendered reference page (request/response schema) for the endpoints `freya.py` and `run_cases.py` use, plus the chat route for turn-by-turn testing |
