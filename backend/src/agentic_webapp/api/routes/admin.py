"""Admin API over the LLM bookkeeping inventory. Read-only aggregates + recent
records for the admin panel. Behind IAP in prod, so only admins reach it."""

from collections import defaultdict
from typing import Annotated, Any

from agentic_core.database import LlmUsageManager
from agentic_core.models import LlmUsageRecord
from fastapi import APIRouter, Depends

from ..deps import get_llm_usage_manager

router = APIRouter(prefix="/api/admin", tags=["admin"])

UsageDep = Annotated[LlmUsageManager, Depends(get_llm_usage_manager)]


@router.get("/usage")
async def usage_summary(manager: UsageDep, limit: int = 1000) -> dict[str, Any]:
    """Aggregate token/cost usage overall and by model + user."""
    records = await manager.list(limit=limit)
    totals: dict[str, Any] = {"calls": 0, "total_tokens": 0, "est_cost_usd": 0.0}
    by_model: dict[str, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "total_tokens": 0, "est_cost_usd": 0.0})
    by_user: dict[str, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "total_tokens": 0, "est_cost_usd": 0.0})

    for r in records:
        for bucket in (totals, by_model[r.model_id], by_user[r.user_id]):
            bucket["calls"] += 1
            bucket["total_tokens"] += r.total_tokens
            bucket["est_cost_usd"] += r.est_cost_usd

    def _round(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "est_cost_usd": round(d["est_cost_usd"], 6)}

    return {
        "totals": _round(totals),
        "by_model": {k: _round(v) for k, v in by_model.items()},
        "by_user": {k: _round(v) for k, v in by_user.items()},
    }


@router.get("/usage/records", response_model=list[LlmUsageRecord])
async def usage_records(manager: UsageDep, limit: int = 100) -> list[LlmUsageRecord]:
    """Most-recent itemised usage records."""
    return await manager.list(limit=limit)
