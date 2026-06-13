"""Thin async client the agent tools use to reach the backend's asset API.

The agent has NO direct GCS access by design: the backend's AssetService (GCS blobs +
metadata catalogue) is the single source of truth for assets (see
docs/adr/adr-0006-assets-single-source-of-truth.md). So the agent reads assets over HTTP
from the backend, never from a parallel store. BACKEND_BASE_URL points at the backend:
http://localhost:8080 locally and on Cloud Run (shared localhost), http://backend:8080
under docker compose.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# Default works for `make dev` (concurrently) and the single Cloud Run service, where the
# backend shares localhost with the agent. docker-compose overrides it to the service name.
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8080")

_TIMEOUT = httpx.Timeout(15.0)


def preview_url(asset_id: str) -> str:
    """Same-origin URL the SPA can render as an <img> (the backend proxies GCS bytes)."""
    return f"/api/assets/{asset_id}/content"


def _summarise(asset: dict[str, Any]) -> dict[str, Any]:
    """Compact a backend AssetMetadata dict down to what the model needs to choose one."""
    asset_id = asset.get("asset_id")
    return {
        "asset_id": asset_id,
        "filename": asset.get("filename"),
        "content_type": asset.get("content_type"),
        "size_bytes": asset.get("size_bytes"),
        "created_at": asset.get("created_at"),
        # A servable link the agent can hand back to render a preview in chat.
        "preview_url": preview_url(asset_id) if asset_id else None,
    }


async def list_assets(*, limit: int = 50) -> list[dict[str, Any]]:
    """Return a compact catalogue of stored assets (most-recent first per the backend)."""
    async with httpx.AsyncClient(base_url=BACKEND_BASE_URL, timeout=_TIMEOUT) as client:  # pragma: no cover — live HTTP
        resp = await client.get("/api/assets", params={"limit": limit})
        resp.raise_for_status()
        return [_summarise(a) for a in resp.json()]


async def fetch_content(asset_id: str) -> tuple[bytes, str]:
    """Return (bytes, content_type) for an asset, proxied through the backend from GCS."""
    async with httpx.AsyncClient(base_url=BACKEND_BASE_URL, timeout=_TIMEOUT) as client:  # pragma: no cover — live HTTP
        resp = await client.get(f"/api/assets/{asset_id}/content")
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip()
        return resp.content, content_type


async def get_metadata(asset_id: str) -> dict[str, Any] | None:
    """Return the asset's metadata dict, or None if it doesn't exist."""
    async with httpx.AsyncClient(base_url=BACKEND_BASE_URL, timeout=_TIMEOUT) as client:  # pragma: no cover — live HTTP
        resp = await client.get(f"/api/assets/{asset_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _summarise(resp.json())
