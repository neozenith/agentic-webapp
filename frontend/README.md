# `frontend/` — agentic-webapp React SPA

Vite + React + TypeScript single-page app, **served in production by the FastAPI
backend** (built into the backend image; FastAPI serves `dist/` + a client-routing
fallback). Same-origin calls reach the backend APIs and the proxied agent.

Pages: **Home**, **Chat** (talks to the ADK agent via the backend proxy), **Admin**
(token/cost usage from `/api/admin/usage`).

## Local dev

```bash
make -C frontend install
make -C backend dev-cloud      # backend on :8080 (proxies the agent); or `make -C backend dev`
make -C frontend dev           # Vite on :5173, proxies /api + agent paths to :8080
```

Open http://localhost:5173. In production it's one origin (the backend serves this).

## Build

```bash
make -C frontend build         # -> dist/  (the backend image bundles this)
```
