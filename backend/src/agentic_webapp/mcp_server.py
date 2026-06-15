"""Mount the core API as MCP tools — the MCP is just another *interface* to /api/*.

The server holds no RBAC of its own. It wraps the app's OpenAPI spec and calls the API back
over loopback HTTP, forwarding the caller's identity header per request, so the SAME engine
(`api.auth.iap_email` / `require_area` / `agentic_core.access` visibility) decides what each
persona may do — identical to the SPA and the CLI. An MCP client picks a persona by setting a
header on its connection:

  * `X-Goog-Authenticated-User-Email` — a human persona (claude -p, codex, the ADK harness);
  * `X-Viewer-User-Id` — the agent acting on a signed-in user's behalf (already pseudonymised).

FastMCP exposes the incoming request's headers via `get_http_headers()` (a per-request
contextvar); the httpx event hook copies the identity header onto each downstream API call.
"""

from __future__ import annotations

from typing import Any

import httpx
import mcp.types as mcp_types
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.providers.openapi import MCPType, RouteMap
from fastmcp.tools import ToolResult

from .api.auth import IAP_USER_HEADER, INTERNAL_VIEWER_HEADER
from .mcp_ui import browse_summary, fetch_visible, render_browse

# Identity headers forwarded from the MCP client to the core API. Lower-cased because
# get_http_headers() returns lower-cased keys; httpx header keys are case-insensitive.
_FORWARD_HEADERS = frozenset({IAP_USER_HEADER.lower(), INTERNAL_VIEWER_HEADER.lower()})

# Only the core API is tool-shaped. First match wins (FastMCP evaluates in order):
#   1. asset byte-streams (content/{key}, {id}/content) — raw bytes, not a useful tool;
#   2. everything else under /api/* — a tool (incl. admin/analytics, which RBAC then 403s
#      per persona: that asymmetry IS the point of RBAC-over-MCP);
#   3. anything else (SPA fallback, agent reverse-proxy, /mcp, /health) — excluded.
_ROUTE_MAPS = [
    RouteMap(pattern=r"^/api/assets/.*content", mcp_type=MCPType.EXCLUDE),
    RouteMap(pattern=r"^/api/.*", mcp_type=MCPType.TOOL),
    RouteMap(pattern=r".*", mcp_type=MCPType.EXCLUDE),
]


async def _forward_identity(request: httpx.Request) -> None:
    """httpx request hook: copy the MCP client's identity header onto the API call so RBAC
    resolves the impersonated persona. Per-request (contextvar) — concurrent callers don't bleed."""
    for key, value in get_http_headers().items():
        if key.lower() in _FORWARD_HEADERS:
            request.headers[key] = value


def _register_ui_tools(server: FastMCP[Any], client: httpx.AsyncClient) -> None:
    """Hand-authored UI tools layered over the OpenAPI projection (ADR-0012). They run inside
    the FastMCP request context, so `_forward_identity` carries the caller's persona on any
    /api/* fetch they make — inheriting RBAC exactly like a projected tool."""

    @server.tool
    async def browse(folder_id: str | None = None) -> ToolResult:
        """Browse the user's folders and assets as an interactive UI panel. Returns a short
        text summary for the model plus an embedded io.modelcontextprotocol/ui resource for
        the host to render (HTML in a sandboxed iframe; clicking a folder drills in). Pass a
        folder_id to open that folder (omit for the root)."""
        folders, assets = await fetch_visible(client)
        summary = browse_summary(folders, assets, folder_id)
        ui = render_browse(folders, assets, folder_id=folder_id)
        return ToolResult(content=[mcp_types.TextContent(type="text", text=summary), ui])


def build_mcp(app: FastAPI, *, base_url: str) -> FastMCP[Any]:
    """An MCP server exposing the app's /api/* operations as tools, calling back into the
    running app over loopback HTTP with per-request identity forwarding. Plus a narrow,
    hand-authored UI-tool layer (ADR-0012) that returns MCP-UI resources."""
    client = httpx.AsyncClient(base_url=base_url, event_hooks={"request": [_forward_identity]})
    server = FastMCP.from_openapi(
        openapi_spec=app.openapi(),
        client=client,
        name="agentic-webapp",
        route_maps=_ROUTE_MAPS,
    )
    _register_ui_tools(server, client)
    return server
