"""The web host's MCP-UI drill-in proxy (ADR-0012).

When a folder is clicked inside the rendered browse panel, the SPA fulfils the MCP-UI
action by calling this endpoint directly (not by re-prompting the agent — folder
navigation is deterministic and identity-scoped, so it shouldn't cost a model turn). It
forwards the caller's identity into a loopback `/api/*` fetch and reuses the SAME
`render_browse` the MCP `browse` tool uses, so both hosts can never diverge.

`include_in_schema=False` keeps `/ui/*` out of OpenAPI, and the MCP route maps' EXCLUDE
catch-all keeps it from becoming a tool — it is a web-only presentation seam, not API.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request

from ...config import get_settings
from ...mcp_ui import fetch_visible, render_browse
from ..auth import IAP_USER_HEADER, INTERNAL_VIEWER_HEADER

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)

_IDENTITY_HEADERS = (IAP_USER_HEADER, INTERNAL_VIEWER_HEADER)


@router.get("/browse")
async def browse(request: Request, folder_id: str | None = None) -> dict[str, Any]:
    """Render the browse UI resource for `folder_id` (None = root), scoped to the caller's
    visibility. Returns the embedded `ui://` resource block for `@mcp-ui/client` to mount."""
    settings = get_settings()
    base_url = settings.self_base_url or f"http://127.0.0.1:{settings.port}"
    forwarded = {h: request.headers[h] for h in _IDENTITY_HEADERS if h in request.headers}
    async with httpx.AsyncClient(base_url=base_url, headers=forwarded) as client:
        folders, assets = await fetch_visible(client)
    return render_browse(folders, assets, folder_id=folder_id).model_dump(mode="json")
