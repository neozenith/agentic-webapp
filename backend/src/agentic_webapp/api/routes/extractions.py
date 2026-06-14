"""Record a structured extraction against an asset — the WRITE side of the analytics
warehouse, centralised in the kernel so the agent (and any client) records via the API/MCP
instead of writing analytics itself. Read lives in routes/analytics.py (admin/analytics-gated);
the write is gated only by **asset visibility** — you may record against an asset you can see,
which is exactly what the chat agent does on a user's behalf. Identity comes from `auth.viewer`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from agentic_core.access import accessible_folder_ids, asset_visible
from agentic_core.database import AnalyticsManager, FolderManager, GroupManager
from agentic_core.models import ExtractionRecord
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...services import AssetService
from ..access import viewer_ctx
from ..deps import get_analytics_manager, get_asset_service, get_folder_manager, get_group_manager

router = APIRouter(prefix="/api/extractions", tags=["extractions"])

AnalyticsDep = Annotated[AnalyticsManager, Depends(get_analytics_manager)]
ServiceDep = Annotated[AssetService, Depends(get_asset_service)]
FolderDep = Annotated[FolderManager, Depends(get_folder_manager)]
GroupDep = Annotated[GroupManager, Depends(get_group_manager)]


class RecordExtractionRequest(BaseModel):
    asset_id: str
    doc_type: str
    fields: dict[str, Any] = {}
    model_id: str | None = None
    session_id: str | None = None


@router.post("", response_model=ExtractionRecord, status_code=201)
async def record(
    body: RecordExtractionRequest,
    request: Request,
    analytics: AnalyticsDep,
    service: ServiceDep,
    folders: FolderDep,
    groups: GroupDep,
) -> ExtractionRecord:
    """Record an extraction for an asset the caller can see (404 otherwise — don't leak existence).
    `user_id` is the caller's pseudonymous id, never client-supplied (server-authoritative)."""
    meta = await service.get(body.asset_id)
    viewer_id, is_admin, group_ids = await viewer_ctx(request, groups)
    accessible = accessible_folder_ids(
        await folders.list(), viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids
    )
    if meta is None or not asset_visible(
        meta, viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids, accessible_folders=accessible
    ):
        raise HTTPException(status_code=404, detail="asset not found")
    extraction = ExtractionRecord(
        extraction_id=uuid4().hex,
        asset_id=body.asset_id,
        doc_type=body.doc_type,
        user_id=viewer_id or "anonymous",
        session_id=body.session_id or "unknown",
        fields=body.fields,
        model_id=body.model_id,
        created_at=datetime.now(timezone.utc),
    )
    return await analytics.record_extraction(extraction)
