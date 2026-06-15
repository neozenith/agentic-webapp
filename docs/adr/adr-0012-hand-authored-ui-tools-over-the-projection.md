# ADR-0012: A narrow hand-authored UI-tool layer over the MCP projection (MCP-UI)

**Status:** Accepted · implemented

## Context

ADR-0011 made the MCP server a **pure projection** of the OpenAPI spec (`FastMCP.from_openapi`,
zero hand-written tools) — its whole virtue is that it *can't drift* from the API. But we want
users to **browse their folders and assets through a rendered UI**, inline in the web chat and
in Claude Desktop, with interactive drill-in (click a folder → it opens). That capability is an
`io.modelcontextprotocol/ui` resource (HTML in a sandboxed iframe; the [MCP-UI](https://mcpui.dev/)
/ MCP Apps pattern), which is **not expressible as an OpenAPI operation** — a `GET /api/folders`
returns JSON, not an interactive panel. So "browse" cannot come from the projection; it needs a
hand-authored tool. That is a deliberate, bounded exception to ADR-0011 — the same shape of
exception ADR-0011 already carved out for multimodal image injection (which also can't cross the
generic OpenAPI→MCP bridge).

A second forcing constraint is the **two hosts differ**. Claude Desktop is a native MCP Apps host
(its client advertises the `io.modelcontextprotocol/ui` extension), so it renders a UI resource
returned by a tool directly. The web SPA is **not** a host — and its agent path makes it worse:
the chat agent (ADK/Gemini) consumes the MCP server-side, so a UI resource returned to the model
would have to survive ADK's tool-result serialization to reach the browser. We do not want the web
surface to depend on that internal behaviour.

## Decision

Add a **single hand-authored tool, `browse`**, registered on the FastMCP server *after*
`from_openapi` (it wins no collisions because it shares no name with any `{tag}_{verb}` op), and a
shared renderer, with three properties that keep the ADR-0011 invariants intact:

1. **It reuses the API for data + RBAC, adding none.** `browse` fetches the caller's folders and
   assets through the **existing** `/api/folders` + `/api/assets` over the same loopback httpx
   client, so the per-request identity-forwarding hook (`_forward_identity`) scopes visibility
   exactly as every projected tool does. `mcp_ui.render_browse` (a pure function) turns those into
   the `ui://` HTML resource. The tool returns **`[short_text_summary, ui_resource]`** — the text
   is what the model reads; the resource is what the host renders. Verified: a viewer's `browse`
   shows only their folders, an admin's shows all.

2. **The web host renders off the tool *call*, not the tool *result*.** The SPA detects that the
   agent invoked `browse` (the `functionCall` ADK reliably surfaces) and fetches the panel from a
   web-only **`GET /ui/browse`** proxy that reuses the *same* `render_browse` with the caller's
   identity. So the web surface never depends on ADK forwarding the embedded resource, and both
   hosts converge on one renderer. `/ui/*` is `include_in_schema=False` and matches the MCP route
   maps' `EXCLUDE` catch-all, so it is neither an API operation nor a tool (test-asserted).

3. **Interactive drill-in is a deterministic, agent-free round-trip on the web.** Clicking a folder
   posts an MCP-UI action; the SPA fulfils it by re-fetching `/ui/browse?folder_id=…` and swapping
   the sandboxed iframe — folder navigation shouldn't cost a Gemini turn. The agent stays in the
   loop only for the initial "show my files" turn. In Claude Desktop the host re-invokes the MCP
   `browse` tool itself; both paths land in `render_browse`.

## Consequences

- **The projection still can't drift for everything else.** Exactly one hand-authored tool exists;
  every other `/api/*` route remains an auto-projected tool. New API routes still become tools for
  free.
- **One renderer, one RBAC, two hosts.** `render_browse` is the single source of UI truth; the MCP
  tool and the `/ui/browse` proxy are two entry points to it, so the surfaces can't diverge.
- **Host-capability boundary, documented not hidden.** The web host gets full interactive drill-in
  now (we control the iframe + `postMessage`). Claude Desktop renders the panel; *interactive*
  drill-in there requires the guest HTML to speak the MCP Apps app-bridge JSON-RPC (`tools/call`)
  rather than the simple `postMessage` we emit — a clearly-scoped follow-up, not a silent gap.
- **Thumbnails are web-only.** Asset *bytes* still can't cross into a sandboxed iframe with no
  backend origin/credentials (the same wall ADR-0011 hit), so v1 renders type icons, not
  thumbnails, in both hosts; same-origin thumbnails are a later web-only enhancement.
- **New dependencies:** `mcp-ui-server` (Python, emits the `ui://` resource). The web host needs no
  client library — a minimal sandboxed-iframe component suffices for the surface we control.

## Lens

When a capability genuinely can't be expressed through your auto-generated contract, **add the
smallest possible hand-authored exception and make it reuse the contract underneath** (here:
fetch through `/api/*` so RBAC is inherited, render through one shared function so the surfaces
can't diverge) — rather than letting the exception grow its own data path or its own authorization.
And when one consumer of a feature is a richer host than another, **render off the most reliable
signal each host gives you** (a tool *call* the agent always emits, vs. a tool *result* whose
forwarding is an internal detail) instead of forcing every host through the most fragile path.
