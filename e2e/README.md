# `e2e/` — Playwright evidence suite

Drives the **deployed** React app and proves two things end-to-end:

1. **Chat works** — a message typed into `/chat` is answered by the ADK agent through the FastAPI → sidecar proxy.
2. **Cost accounting works** — that turn is recorded in BigQuery (via the agent's `after_model_callback`) and surfaced on the `/admin` page; the test polls `/admin` until the call count rises and asserts the cheapest model (`gemini-2.5-flash-lite`) is itemised.

Each test attaches a full-page **screenshot**; an HTML report is written to `playwright-report/`.

## Run

```bash
make -C e2e install            # bun install + chromium
make -C e2e test               # against Test (default); screenshots + report
make -C e2e report             # open the HTML report
```

Target another environment with `BASE_URL`:

```bash
make -C e2e test BASE_URL=https://agentic-webapp-67piswzbeq-ts.a.run.app   # dev
```

## Environments

| Env  | Automated here?           | Why |
|------|---------------------------|-----|
| dev  | ✅ (set `BASE_URL`)        | no IAP |
| test | ✅ (default)               | no IAP |
| prod | ❌ verified manually        | IAP-locked to a single human Google account — no headless identity by design |

Local-run only (not wired into CI) by decision — see the suite header comment.
