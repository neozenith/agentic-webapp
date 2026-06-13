"""Agent tools for working with stored assets and recording analytics.

Three function tools, registered on root_agent:
  - list_assets()            — discover stored assets (id, filename, type, size, date,
                               preview_url). The preview_url is a same-origin link the model
                               can hand back to render the image in chat.
  - attach_asset(asset_id)   — mark an asset to be shown to the model THIS turn. The actual
                               inline injection happens in the before_model_callback
                               (attachments.attach_referenced_assets), scoped to the current
                               turn so stale attachments from earlier turns don't leak in.
  - record_extraction(...)   — persist structured details to the analytics store via the
                               backend-agnostic AnalyticsManager (in-memory locally,
                               Firestore/BigQuery when configured).

Assets are sourced from the backend's AssetService (GCS) — the single source of truth — and
never ADK's artifact store (ADR-0006).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from google.adk.tools.tool_context import ToolContext

from agentic_core.database import AnalyticsManager, build_analytics_database_from_env
from agentic_core.models import ExtractionRecord

from . import assets_client
from .attachments import note_tool_attachment

log = logging.getLogger(__name__)

_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")
# Analytics is its own backend (BigQuery in cloud, in-memory locally) — separate from the
# operational Firestore stores (sessions, assets). See AnalyticsManager.
_ANALYTICS = AnalyticsManager(build_analytics_database_from_env())


# --- list_assets ------------------------------------------------------------------------


async def list_assets(tool_context: ToolContext) -> dict[str, Any]:
    """List stored assets the user can reference (id, filename, content type, size, date,
    preview_url). Only assets the user owns or that are shared with them are returned.

    Assets can share a filename (phone cameras reuse names), so identify a specific one by
    its asset_id, and prefer the most recent when the user describes a new photo. The
    preview_url is a link you can embed in a markdown image to show it in chat.
    """
    assets = await assets_client.list_assets(viewer_id=_viewer_id(tool_context))  # pragma: no cover — live HTTP
    return {"assets": assets, "count": len(assets)}  # pragma: no cover — live HTTP to backend


# --- attach_asset (records the asset for the current turn; injection in the callback) ----


def _invocation_id(tool_context: ToolContext) -> str:
    ictx = getattr(tool_context, "_invocation_context", None)
    return getattr(ictx, "invocation_id", "") or ""


def _viewer_id(tool_context: ToolContext) -> str | None:
    """The chat user's pseudonymous id — passed to the backend so asset visibility is
    scoped to them (it equals the asset owner_id minted from the same identity)."""
    ictx = getattr(tool_context, "_invocation_context", None)
    return getattr(getattr(ictx, "session", None), "user_id", None)


async def attach_asset(asset_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Attach a stored asset (a photo/scan/PDF, e.g. a receipt or an odometer) so you can SEE
    it this turn. Pass the asset_id from list_assets or from the user's message. The image
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


# --- record_extraction ------------------------------------------------------------------


def _parse_fields(fields_json: str) -> dict[str, Any]:
    """Best-effort parse the model-supplied JSON payload into a dict (never raises)."""
    if not fields_json:
        return {}
    try:
        parsed = json.loads(fields_json)
    except (json.JSONDecodeError, TypeError):
        return {"raw": fields_json}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


async def record_extraction(asset_id: str, doc_type: str, fields_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Persist structured details extracted from an asset to the analytics store.

    Args:
      asset_id: the source asset the details came from.
      doc_type: a short kind label, e.g. "fuel_receipt", "odometer", "invoice".
      fields_json: a JSON OBJECT string of the extracted key/values, e.g.
        '{"vendor":"Shell","total":"82.50","currency":"AUD","date":"2026-06-10"}'.
    """
    fields = _parse_fields(fields_json)
    ictx = getattr(tool_context, "_invocation_context", None)
    session = getattr(ictx, "session", None)
    record = ExtractionRecord(
        extraction_id=uuid4().hex,
        asset_id=asset_id,
        doc_type=doc_type,
        user_id=getattr(session, "user_id", None) or "anonymous",
        session_id=getattr(session, "id", None) or "unknown",
        fields=fields,
        model_id=_MODEL,
        created_at=datetime.now(timezone.utc),
    )
    await _ANALYTICS.record_extraction(record)
    log.info("analytics recorded: %s doc_type=%s fields=%d", record.extraction_id, doc_type, len(fields))
    return {"status": "recorded", "extraction_id": record.extraction_id, "doc_type": doc_type, "fields": fields}
