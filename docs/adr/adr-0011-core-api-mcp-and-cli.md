# ADR-0011: The core API is the hub; MCP, CLI, and agent are interfaces to it

**Status:** Accepted · implemented

## Context

The FastAPI backend (`/api/*`) is the system's real surface area: assets, folders, groups,
admin bookkeeping, analytics, and identity — each already RBAC-gated by the IAP-email identity
(ADR-0004) resolved through one engine (`rbac.py` + `api/auth.py`). Until now only two clients
reached it: the React SPA and the ADK agent (via bespoke per-tool code).

We want every consumer — SPA, a scriptable CLI, an MCP server for LLM tooling, and the agent —
to be an interchangeable **interface** to that one API, and we want RBAC to be demonstrable
identically across all of them (the same persona, the same allow/deny). The risk to avoid is a
second authorization implementation per surface, which inevitably drifts.

## Decision

Treat the API as a **hub** and add two thin spokes, both forwarding identity into the existing
RBAC engine rather than re-implementing it:

1. **MCP server, mounted in the main app** (`mcp_server.py`, FastMCP 3.x). Built from the live
   OpenAPI spec via `FastMCP.from_openapi(...)` and mounted at `/mcp`. It calls the API over
   **loopback HTTP** (not in-process `ASGITransport`) so a tool call traverses the exact same
   middleware + RBAC as any external client. A per-request httpx event hook copies the caller's
   identity header (`X-Goog-Authenticated-User-Email`, or the agent's `X-Viewer-User-Id`) —
   read from FastMCP's `get_http_headers()` — onto the downstream call. Route maps expose only
   `/api/*` as tools (admin/analytics included — RBAC 403s them per persona; that asymmetry *is*
   the demonstration), excluding the SPA fallback, the agent reverse-proxy, byte-stream content
   endpoints, and `/mcp` itself.

2. **A Python CLI** (`cli/`, stdlib argparse, httpx-only runtime) that drives `/api/*` and
   forwards a chosen persona via `--as <email>`. It enforces nothing locally; the server decides.

OpenAPI is given stable `{tag}_{verb}` operation ids (`assets_list`, `admin_users`, …) via a
`generate_unique_id_function`, so MCP tool names and any generated clients are predictable. The
agent reverse-proxy routes are marked `include_in_schema=False` (a passthrough, not API ops).

A testing harness (`scripts/mcp_harness.py` + `agent/harness/mcp_agent.py`) points an ADK agent,
`claude -p`, and `codex exec` at `/mcp` as a persona, proving the MCP works with real
subscription LLMs and that RBAC holds there too.

## Consequences

- **One RBAC implementation.** Requirements "simulate RBAC on the API" and "…on the MCP" are the
  same code path; the MCP added zero policy logic. Verified live: a viewer is denied `admin_users`
  over the CLI, the in-process MCP client, `claude -p`, and `codex` with the identical message.
- **The MCP stays in sync with the API for free** — it's a projection of the OpenAPI spec
  (`mcp_server.py` is ~17 statements for 26 tools), so new `/api/*` routes become tools
  automatically.
- **Two costs we accepted:** (a) a loopback hop per MCP tool call (negligible locally; in Cloud
  Run the process calls `127.0.0.1:$PORT`, itself); (b) FastMCP's streamable-HTTP transport must
  have its lifespan nested into the app's lifespan (wired via `app.state.mcp_app`) or it 500s.
- **CLI tests boot the real backend** in-process (no mocks) so RBAC is exercised end-to-end.
- **Harness transport facts (verified 2026-06):** `claude -p` takes HTTP MCP + custom headers via
  `--mcp-config`; **codex 0.139 supports streamable-HTTP MCP natively** (`config.toml`
  `http_headers`, injectable inline with `-c`) — no `mcp-remote` bridge — but needs
  `--dangerously-bypass-approvals-and-sandbox` to run tools non-interactively, and inline `-c`
  (not an isolated `CODEX_HOME`) so its login is preserved.

## Lens

When several surfaces need the same authorization, **make one component authoritative and have
the others forward identity into it** — never re-encode the policy per surface. Prefer wrapping
an existing contract (the OpenAPI spec → MCP tools) over hand-authoring a parallel one: the
projection can't drift. And when you choose a transport, prefer the one that **traverses the
real boundary** (loopback HTTP through the actual middleware) over the in-process shortcut, so a
test or a tool exercises what production does.
