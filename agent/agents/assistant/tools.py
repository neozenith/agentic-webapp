"""The agent's one local tool: `attach_asset`.

Listing assets and recording extractions are NOT here — they're MCP tools served by the kernel
(see mcp.py / ADR-0011), so the business logic and its RBAC live in the main server. What stays
local is the turn-scoped directive to SHOW the model an image: `attach_asset(asset_id)` marks an
asset for the current turn; the actual inline injection happens in the before_model_callback
(attachments.attach_referenced_assets), scoped to the turn so stale attachments don't leak. The
generic OpenAPI→MCP bridge can't carry image pixels, so this multimodal path is deliberately not
an MCP tool — it fetches via the backend's RBAC-checked content endpoint instead.
"""

from __future__ import annotations

import logging
from typing import Any

from google.adk.tools.tool_context import ToolContext

from . import assets_client
from .attachments import note_tool_attachment

log = logging.getLogger(__name__)


def _invocation_id(tool_context: ToolContext) -> str:
    ictx = getattr(tool_context, "_invocation_context", None)
    return getattr(ictx, "invocation_id", "") or ""


async def attach_asset(asset_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Attach a stored asset (a photo/scan/PDF, e.g. a receipt or an odometer) so you can SEE
    it this turn. Pass the asset_id from assets_list or from the user's message. The image
    becomes visible to you; use it to read details from the document.
    """
    if not asset_id:
        return {"status": "error", "detail": "asset_id is required"}
    note_tool_attachment(tool_context.state, _invocation_id(tool_context), asset_id)
    return {
        "status": "attached",
        "asset_id": asset_id,
        "preview_url": assets_client.preview_url(asset_id),
        "note": "The asset's contents are now visible to you in this turn.",
    }
