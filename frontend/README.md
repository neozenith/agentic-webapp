# `frontend/` — agentic-webapp React SPA

Vite + React + TypeScript single-page app, **served in production by the FastAPI
backend** (built into the backend image; FastAPI serves `dist/` + a client-routing
fallback). Same-origin calls reach the backend APIs and the proxied agent.

Pages: **Home**, **Chat** (talks to the ADK agent via the backend proxy),
**Sessions**, **Assets** (a folder-style GCS asset browser), and **Admin**
(token/cost usage from `/api/admin/usage`). Styled with Tailwind CSS v4 + shadcn/ui;
navigation is a collapsible left sidebar.

## Local dev

The fastest path is the **root** `make dev`, which uses [`concurrently`](https://www.npmjs.com/package/concurrently)
(declared in this `package.json`'s `dev` script) to boot the whole stack — agent +
backend + this Vite server — under one supervisor. `--kill-others` means Ctrl-C (or
any one process exiting) tears all three down together. A preflight first checks
creds and tells you how to authenticate if any are missing:

```bash
make install        # once — installs every subproject (this frontend included)
make dev            # concurrently: agent :8081 + backend :8080 + Vite :5173 (Ctrl-C stops all)
# or, cloud-integrated via containers:
make dev-docker     # docker compose (agent + backend); SPA served by backend at :8080
make clean-ports    # kill any stray process still holding :8081 / :8080 / :5173
```

To run just this SPA against an already-running backend:

```bash
make -C frontend install
make -C frontend dev-frontend-only   # Vite on :5173, proxies /api + agent paths to :8080
```

Open http://localhost:5173. In production it's one origin (the backend serves this).

## Build

```bash
make -C frontend build         # -> dist/  (the backend image bundles this)
```
