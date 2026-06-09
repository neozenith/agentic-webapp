"""Health + readiness. NB: use /health, not /healthz — Google's frontend reserves
/healthz on Cloud Run and 404s it before it reaches the container."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ...config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "environment": s.environment,
        "storage_backend": s.storage_backend,
        "database_backend": s.database_backend,
    }
