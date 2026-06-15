# MCP-UI: interactive folder/asset browser

Inline, interactive UI ([mcpui.dev](https://mcpui.dev/) / MCP Apps `io.modelcontextprotocol/ui`)
that lets a user **browse their folders and assets** through a rendered panel — in the web chat
(inline in the transcript) and in Claude Desktop. Design and rationale: **[ADR-0012](../adr/adr-0012-hand-authored-ui-tools-over-the-projection.md)**.

## What shipped

- **One hand-authored MCP tool, `browse(folder_id=None)`** (`backend/.../mcp_server.py`) layered
  over the ADR-0011 projection. Returns `[text summary, ui:// resource]`; data + RBAC come from the
  existing `/api/folders` + `/api/assets` (zero new authorization).
- **One shared renderer** `mcp_ui.render_browse` — the single source of UI truth for both hosts.
- **Web host:** the SPA detects the agent's `browse` tool *call* and renders the panel via the
  web-only **`GET /ui/browse`** proxy (reuses `render_browse`), in a sandboxed iframe
  (`frontend/src/components/ChatUIResource.tsx`). Drill-in clicks re-fetch `/ui/browse` directly —
  no agent turn.
- **Claude Desktop:** renders the `ui://` resource the MCP tool returns.

## Host capability matrix

| Capability | Web chat | Claude Desktop |
|------------|----------|----------------|
| Render the browse panel | ✅ | ✅ (native MCP Apps host) |
| Interactive drill-in | ✅ (direct `/ui/browse`) | ⏳ needs MCP Apps app-bridge in the guest HTML |
| Asset thumbnails | ⏳ web-only later (sandbox can't carry bytes) | ❌ (no backend origin in sandbox) |

## Open items / follow-ups

1. **Claude Desktop drill-in.** The guest HTML currently posts the simple
   `{type:"tool", payload:{toolName:"browse", params:{folder_id}}}` message (which our web host
   understands). For Desktop's *interactive* drill-in, the guest must speak the MCP Apps app-bridge
   JSON-RPC (`tools/call`). Spike pending: confirm what Desktop renders/round-trips today, then add
   the app-bridge emission (likely via `mcp-ui-server`'s MCP-Apps adapter) so one resource serves
   both hosts interactively.
2. **Thumbnails in the web host.** Pass short-lived signed URLs (`assets_get_url`) into the HTML so
   the sandboxed iframe can show image previews without backend credentials.
3. **Resume rendering.** Browse panels are live-only; a resumed session shows the prose but not the
   panel. Reconstruct panels from a session's `browse` tool-calls if we want them on resume.
4. **Streaming.** The chat still uses `/run` (non-streaming). Switching to `/run_sse` is an
   orthogonal UX upgrade (token-by-token text); the browse feature does not require it.
