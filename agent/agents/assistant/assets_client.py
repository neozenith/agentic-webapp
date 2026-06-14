"""Backend access for the agent's multimodal image injection.

Asset LISTING + extraction recording are MCP tools now (mcp.py / ADR-0011). What remains here
is the one thing the MCP bridge can't carry — fetching an asset's raw bytes so the model can SEE
it (attachments.py). The agent has NO direct GCS access by design: the backend's AssetService is
the single source of truth (ADR-0006), so bytes are fetched over HTTP from the backend's
RBAC-checked content endpoint. BACKEND_BASE_URL points at the backend: http://localhost:8080
locally and on Cloud Run (shared localhost), http://backend:8080 under docker compose — and it
also seeds the agent's MCP URL (mcp.py).
"""

from __future__ import annotations

import os

import httpx

# Default works for `make dev` (concurrently) and the single Cloud Run service, where the
# backend shares localhost with the agent. docker-compose overrides it to the service name.
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8080")

_TIMEOUT = httpx.Timeout(15.0)

# Internal header: tells the backend which user the agent is acting for, so asset
# visibility (ownership/sharing) is scoped to that user (see api/auth.py).
_VIEWER_HEADER = "X-Viewer-User-Id"


def _viewer_headers(viewer_id: str | None) -> dict[str, str]:
    return {_VIEWER_HEADER: viewer_id} if viewer_id else {}


def preview_url(asset_id: str) -> str:
    """Same-origin URL the SPA can render as an <img> (the backend proxies GCS bytes)."""
    return f"/api/assets/{asset_id}/content"


async def fetch_content(asset_id: str, *, viewer_id: str | None = None) -> tuple[bytes, str]:
    """Return (bytes, content_type) for an asset, proxied through the backend from GCS."""
    async with httpx.AsyncClient(base_url=BACKEND_BASE_URL, timeout=_TIMEOUT) as client:  # pragma: no cover — live HTTP
        resp = await client.get(f"/api/assets/{asset_id}/content", headers=_viewer_headers(viewer_id))
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip()
        return resp.content, content_type
