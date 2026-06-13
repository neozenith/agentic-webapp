"""Admin API over the LLM bookkeeping inventory plus group management. Read-only usage
aggregates + recent records, and full CRUD over custom user groups. Behind IAP in prod,
so only admins reach it."""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from agentic_core.database import GroupManager, LlmUsageManager
from agentic_core.models import Group, LlmUsageRecord
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ... import rbac
from ...config import get_settings
from ...identity import mask_user_id
from ..deps import get_group_manager, get_llm_usage_manager

router = APIRouter(prefix="/api/admin", tags=["admin"])

UsageDep = Annotated[LlmUsageManager, Depends(get_llm_usage_manager)]
GroupDep = Annotated[GroupManager, Depends(get_group_manager)]


class CreateGroupRequest(BaseModel):
    name: str
    member_emails: list[str] = []


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    add_member_emails: list[str] = []
    remove_member_ids: list[str] = []


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


@router.get("/users")
async def users(manager: UsageDep, limit: int = 5000) -> list[dict[str, Any]]:
    """Per-user roll-up: distinct sessions, calls, tokens, and cost — most expensive first."""
    acc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "total_tokens": 0, "est_cost_usd": 0.0, "sessions": set()}
    )
    for r in await manager.list(limit=limit):
        b = acc[r.user_id]
        b["calls"] += 1
        b["total_tokens"] += r.total_tokens
        b["est_cost_usd"] += r.est_cost_usd
        b["sessions"].add(r.session_id)
    # Enrich each pseudonymous user_id with email + name when we know it (test personas +
    # configured prod user_roles); unknown ids get nulls.
    directory = rbac.directory(user_roles=get_settings().rbac_user_roles)
    rows = [
        {
            "user_id": user_id,
            "email": directory.get(user_id, {}).get("email"),
            "name": directory.get(user_id, {}).get("name"),
            "sessions": len(b["sessions"]),
            "calls": b["calls"],
            "total_tokens": b["total_tokens"],
            "est_cost_usd": round(b["est_cost_usd"], 6),
        }
        for user_id, b in acc.items()
    ]
    rows.sort(key=lambda x: x["est_cost_usd"], reverse=True)
    return rows


@router.get("/users/{user_id}/sessions")
async def user_sessions(user_id: str, manager: UsageDep, limit: int = 5000) -> list[dict[str, Any]]:
    """Per-session roll-up for one user (calls, tokens, cost, last activity), newest first."""
    acc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "total_tokens": 0, "est_cost_usd": 0.0, "last_timestamp": ""}
    )
    for r in await manager.list(limit=limit):
        if r.user_id != user_id:
            continue
        b = acc[r.session_id]
        b["calls"] += 1
        b["total_tokens"] += r.total_tokens
        b["est_cost_usd"] += r.est_cost_usd
        ts = r.timestamp.isoformat()
        if ts > b["last_timestamp"]:
            b["last_timestamp"] = ts
    rows = [
        {
            "session_id": session_id,
            "calls": b["calls"],
            "total_tokens": b["total_tokens"],
            "est_cost_usd": round(b["est_cost_usd"], 6),
            "last_timestamp": b["last_timestamp"],
        }
        for session_id, b in acc.items()
    ]
    rows.sort(key=lambda x: x["last_timestamp"], reverse=True)
    return rows


# --- Group management (admin-only; mirrors the asset/folder sharing principals) ---


@router.get("/groups", response_model=list[Group])
async def list_groups(groups: GroupDep, limit: int = 200) -> list[Group]:
    return await groups.list(limit=limit)


@router.post("/groups", response_model=Group, status_code=201)
async def create_group(groups: GroupDep, body: CreateGroupRequest) -> Group:
    group = Group(
        group_id=uuid4().hex,
        name=body.name,
        member_ids=sorted({mask_user_id(e) for e in body.member_emails if e.strip()}),
        created_at=datetime.now(timezone.utc),
    )
    return await groups.record(group)


@router.patch("/groups/{group_id}", response_model=Group)
async def update_group(groups: GroupDep, group_id: str, body: UpdateGroupRequest) -> Group:
    group = await groups.get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    if body.name is not None:
        group.name = body.name
    add_ids = {mask_user_id(e) for e in body.add_member_emails if e.strip()}
    members = (set(group.member_ids) | add_ids) - set(body.remove_member_ids)
    group.member_ids = sorted(members)
    return await groups.update(group)


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(groups: GroupDep, group_id: str) -> None:
    await groups.delete(group_id)
