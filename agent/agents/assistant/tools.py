"""Agent tools for working with stored assets and recording extractions.

Three tools, registered on root_agent:
  - list_assets()            — discover stored assets (id, filename, type, size, date).
  - AttachAssetTool          — attach_asset(asset_id): make an asset's image/PDF visible
                               to the model THIS turn by injecting it inline. The bytes are
                               re-fetched from the backend (GCS) on demand and NEVER saved to
                               ADK's artifact store — our AssetService is the single source of
                               truth (ADR-0006), which keeps the agent stateless / scale-to-zero
                               safe and the asset view coherent with the web Asset Manager.
  - record_extraction(...)   — persist structured details to the analytics store via the
                               shared, backend-agnostic ExtractionManager (in-memory locally,
                               Firestore/BigQuery when configured).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from agentic_core.database import ExtractionManager, build_database_from_env
from agentic_core.models import ExtractionRecord

from . import assets_client

log = logging.getLogger(__name__)

_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")
_EXTRACTIONS = ExtractionManager(build_database_from_env())

# Session-state key holding the asset_ids the model has attached this session. Stored in
# tool_context.state, so it persists in the Firestore session and survives a cold start
# (the images themselves are re-fetched from GCS, never persisted locally).
_ATTACHED_KEY = "_attached_asset_ids"


# --- list_assets ------------------------------------------------------------------------


async def list_assets() -> dict[str, Any]:
    """List stored assets the user can reference (id, filename, content type, size, date).

    Call this to discover what assets exist before attaching one to read it.
    """
    assets = await assets_client.list_assets()  # pragma: no cover — live HTTP to backend
    return {"assets": assets, "count": len(assets)}  # pragma: no cover — live HTTP to backend


# --- attach_asset (transient inline injection; no artifact persistence) ------------------


def _is_injectable(mime: str | None) -> bool:
    """True if Gemini accepts this MIME type as inline data (image/audio/video/pdf)."""
    m = (mime or "").split(";", 1)[0].strip().lower()
    return m.startswith(("image/", "audio/", "video/")) or m == "application/pdf"


def _add_attached(state: Any, asset_id: str) -> list[str]:
    """Append asset_id to the session-state attach list (dedup), return the new list."""
    ids = list(state.get(_ATTACHED_KEY, []))
    if asset_id not in ids:
        ids.append(asset_id)
    state[_ATTACHED_KEY] = ids
    return ids


class AttachAssetTool(BaseTool):
    """Attaches a stored asset's bytes to the model inline, sourced from our AssetService
    (GCS via the backend) — modelled on ADK's LoadArtifactsTool but deliberately NOT using
    ADK's artifact store. The asset is re-fetched and injected per request (stateless)."""

    def __init__(self) -> None:
        super().__init__(
            name="attach_asset",
            description=(
                "Attach a stored asset (a photo/scan/PDF, e.g. a receipt) so you can SEE its "
                "contents and read details from it. Pass the asset_id from list_assets or from "
                "the user's message. After attaching, the asset's image is visible to you."
            ),
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"asset_id": types.Schema(type=types.Type.STRING)},
                required=["asset_id"],
            ),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        asset_id = args.get("asset_id", "")
        if not asset_id:
            return {"status": "error", "detail": "asset_id is required"}
        _add_attached(tool_context.state, asset_id)
        return {
            "status": "attached",
            "asset_id": asset_id,
            "note": "The asset's contents are now visible to you in this turn.",
        }

    async def process_llm_request(  # pragma: no cover — live HTTP + model injection; covered by e2e
        self, *, tool_context: ToolContext, llm_request: Any
    ) -> None:
        # Register the function declaration so the model can call attach_asset.
        await super().process_llm_request(tool_context=tool_context, llm_request=llm_request)
        # Inject every currently-attached asset inline, re-fetched from GCS (nothing persisted).
        attached = tool_context.state.get(_ATTACHED_KEY, [])
        for asset_id in attached:
            try:
                data, mime = await assets_client.fetch_content(asset_id)
            except Exception:  # noqa: BLE001 — a missing asset must not break the reply
                log.warning("attach_asset: could not fetch %s", asset_id)
                continue
            if not _is_injectable(mime):
                continue
            llm_request.contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=f"Attached asset {asset_id}:"),
                        types.Part.from_bytes(data=data, mime_type=mime),
                    ],
                )
            )


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
      doc_type: a short kind label, e.g. "fuel_receipt", "invoice".
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
    await _EXTRACTIONS.record(record)
    log.info("extraction recorded: %s doc_type=%s fields=%d", record.extraction_id, doc_type, len(fields))
    return {"status": "recorded", "extraction_id": record.extraction_id, "doc_type": doc_type, "fields": fields}
