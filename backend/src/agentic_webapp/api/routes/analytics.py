"""Analytics API over the AnalyticsManager warehouse (BigQuery in cloud, in-memory
locally). Read-only: list extractions + a summary that doubles as a lightweight semantic
layer (the field keys discovered per doc_type). The Analytics page explores this; Plotly
dashboards can be layered on the same data later."""

from collections import defaultdict
from typing import Annotated, Any

from agentic_core.database import AnalyticsManager
from agentic_core.models import ExtractionRecord
from fastapi import APIRouter, Depends

from ..deps import get_analytics_manager

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

AnalyticsDep = Annotated[AnalyticsManager, Depends(get_analytics_manager)]


@router.get("/extractions", response_model=list[ExtractionRecord])
async def extractions(manager: AnalyticsDep, limit: int = 200) -> list[ExtractionRecord]:
    """Most-recent extraction records."""
    return await manager.list_extractions(limit=limit)


@router.get("/summary")
async def summary(manager: AnalyticsDep, limit: int = 1000) -> dict[str, Any]:
    """Per-doc_type counts plus the set of field keys seen for each — a discovered schema
    (semantic layer) over the free-form extraction payloads."""
    records = await manager.list_extractions(limit=limit)
    counts: dict[str, int] = defaultdict(int)
    fields: dict[str, set[str]] = defaultdict(set)
    for r in records:
        counts[r.doc_type] += 1
        fields[r.doc_type].update(r.fields.keys())
    by_doc_type = [
        {"doc_type": doc_type, "count": counts[doc_type], "fields": sorted(fields[doc_type])}
        for doc_type in sorted(counts)
    ]
    return {"total": len(records), "by_doc_type": by_doc_type}
