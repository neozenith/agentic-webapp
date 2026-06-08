"""Transparent reverse-proxy to the ADK agent sidecar.

In cloud the agent listens on localhost only (single Cloud Run ingress), so the
backend forwards any path it doesn't own to the sidecar — including the ADK debug
UI (/dev-ui/...) and run endpoints (/run_sse, /list-apps, /apps/...). This makes the
agent reachable through the one public URL, and both containers scale to zero
together. Responses stream so SSE passes through live; the IAP user header flows
through for the agent's bookkeeping (PR3).

Registered as a catch-all in main.create_app() AFTER the backend's own routes, so
those take precedence.
"""

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from ...config import get_settings

_HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade"}


async def _aclose(response: httpx.Response, client: httpx.AsyncClient) -> None:
    await response.aclose()
    await client.aclose()


async def proxy_to_agent(request: Request, path: str) -> StreamingResponse:
    target = f"{get_settings().agent_base_url}/{path}"
    client = httpx.AsyncClient(timeout=None)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP}
    upstream = client.build_request(
        request.method,
        target,
        params=request.query_params,
        headers=headers,
        content=await request.body(),
    )
    response = await client.send(upstream, stream=True)
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers={k: v for k, v in response.headers.items() if k.lower() not in _HOP},
        background=BackgroundTask(_aclose, response, client),
    )
