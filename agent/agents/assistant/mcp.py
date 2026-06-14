"""The agent's business-logic tools ARE the core API's MCP server.

Instead of bespoke HTTP tools, the agent connects to the backend's `/mcp` (the secure kernel)
and lets it own asset listing, extraction recording, and RBAC. Identity flows PER REQUEST: the
chat user's pseudonymous id — the ADK session `user_id` — is forwarded as the internal viewer
header, so the kernel scopes visibility and records extractions to that user (the same RBAC the
SPA and CLI get). This keeps the sidecar thin and centralises business logic in the main server.

Not handled here: multimodal image injection (showing the model a receipt's pixels) stays a
`before_model_callback` in attachments.py — the generic OpenAPI→MCP bridge can't carry image
bytes (FastMCP decodes tool results as text), so that one path fetches via the kernel's
RBAC-checked content endpoint instead. See ADR-0011.
"""

from __future__ import annotations

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from .assets_client import BACKEND_BASE_URL

# Internal header the backend trusts for the agent's on-behalf calls (backend api/auth.py).
INTERNAL_VIEWER_HEADER = "X-Viewer-User-Id"
MCP_URL = f"{BACKEND_BASE_URL.rstrip('/')}/mcp/"

# Least privilege: the chat agent surfaces only the kernel tools it needs. Admin/analytics
# tools exist on the MCP but aren't exposed here (and RBAC would 403 them for a chat user).
_TOOL_FILTER = ["assets_list", "assets_get", "extractions_record"]


def identity_headers(ctx: ReadonlyContext) -> dict[str, str]:
    """Forward the chat user's pseudonymous id (ADK session user_id) so the kernel scopes
    RBAC to them. Empty when there's no identity (the kernel then treats it as anonymous)."""
    user_id = ctx.user_id
    return {INTERNAL_VIEWER_HEADER: user_id} if user_id else {}


def build_mcp_toolset() -> McpToolset:
    """The kernel's MCP as the agent's toolset, scoped per request to the chat user."""
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
        header_provider=identity_headers,
        tool_filter=_TOOL_FILTER,
    )
