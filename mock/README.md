# freya-bank-mock

Cloudflare Worker that mocks the Freya Bank voice test environment: the seven statement/debt services of `2026-10-01-service-contract.md`, served from `test-customers.json` (34 synthetic customers, 617 recorded answers). Each `POST /voice/v1/<service>` returns the recorded body and status for the looked-up customer / card / week; unknown ones get the contract's 404 (or 400 `INVALID_ARGUMENTS_ERROR`), `{{template}}` values get the first customer's entry, and the one delayed entry waits 12 s. Also `GET /health` and `GET /` (route list). No secrets, no real data.

- Run locally: `cd mock && wrangler dev --port 8787`
- Verify (all entries + behaviour checks): `node verify.mjs http://localhost:8787`
- Deploy: `cd mock && wrangler deploy`, then `node verify.mjs https://freya-bank-mock.mehar-144.workers.dev`

Deployed URL: https://freya-bank-mock.mehar-144.workers.dev (e.g. `POST /voice/v1/cards.list` with `{"data":{"customerNo":"90000001","aiFlow":"CardOps"},"call":{"ani":"...","lang":"tr"}}`).
