# `e2e/` — Playwright evidence suite

Drives the **deployed** React app and proves two things end-to-end:

1. **Chat works** — a message typed into `/chat` is answered by the ADK agent through the FastAPI → sidecar proxy.
2. **Cost accounting works** — that turn is recorded in BigQuery (via the agent's `after_model_callback`) and surfaced on the `/admin` page; the test polls `/admin` until the call count rises and asserts the cheapest model (`gemini-2.5-flash-lite`) is itemised.

3. **Mobile layout holds up** (`tests/mobile-layout.spec.ts`) — under the `iphone-11` project (Playwright's `devices["iPhone 11"]`: WebKit, 414×715 CSS viewport, DPR 2, touch) every key route (`/`, `/chat`, `/assets`, `/admin`) is scanned for the classic mobile failure modes: no horizontal overflow, no element wider than the viewport, tap targets ≥ the WCAG 2.5.8 (AA) 24px floor (controls under the 44px AAA/HIG goal are reported as evidence), and reachable navigation. Each check uses `expect.soft` so one run reports *every* issue, with offender selectors attached as JSON. Per-route mobile screenshots are attached, and `toHaveScreenshot` baselines (in `tests/mobile-layout.spec.ts-snapshots/`) catch visual regressions.

Each test attaches a full-page **screenshot**; an HTML report is written to `playwright-report/`.

The two projects are isolated: `chromium` runs `chat.spec.ts` only, `iphone-11` runs `mobile-layout.spec.ts` only.

## Run

```bash
make -C e2e install            # bun install + chromium & webkit (webkit drives iPhone 11)
make -C e2e test               # full suite against Test (default); screenshots + report
make -C e2e mobile             # ONLY the iPhone 11 mobile-layout suite
make -C e2e update-snapshots   # (re)generate the mobile visual baselines
make -C e2e report             # open the HTML report
```

> Mobile visual baselines are platform-specific (`…-darwin.png`) and capture the
> current layout — regenerate them with `make -C e2e update-snapshots` after a
> deliberate layout change so the snapshot test gates real regressions.

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
