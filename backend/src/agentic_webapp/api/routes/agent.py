"""Reverse-proxy the ADK agent sidecar for a SCOPED set of paths (the agent's run
endpoints + debug UI). Scoped, not catch-all, so the React SPA owns everything else.

In cloud the agent listens on localhost only (single ingress); the backend forwards
these paths to it, streaming responses so SSE passes through. The IAP user header
flows through for the agent's bookkeeping.
"""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from ...config import get_settings

_HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade"}
# The agent sidecar is reachable ONLY through this same-process proxy on localhost,
# so the backend — not the agent — is the trust boundary. The browser's Origin/Referer
# point at the public site, which ADK's CSRF/origin guard rejects ("Forbidden: origin
# not allowed"). Drop them so the localhost hop is treated as same-origin.
_DROP = _HOP | {"origin", "referer"}

# ADK paths owned by the agent. Everything else is the SPA / backend API.
_FIXED = ["/run", "/run_sse", "/list-apps", "/dev-ui"]
_WILD = ["/apps/{path:path}", "/dev-ui/{path:path}", "/debug/{path:path}", "/builder/{path:path}"]
_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]


async def _aclose(response: httpx.Response, client: httpx.AsyncClient) -> None:
    await response.aclose()
    await client.aclose()


def forward_headers(incoming: dict[str, str]) -> dict[str, str]:
    """Headers to forward to the localhost sidecar: drop hop-by-hop headers plus the
    browser Origin/Referer (which ADK's origin guard would reject — see _DROP)."""
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP}


async def proxy_to_agent(request: Request, path: str) -> StreamingResponse:
    target = f"{get_settings().agent_base_url}/{path}"
    client = httpx.AsyncClient(timeout=None)
    headers = forward_headers(dict(request.headers))
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


def build_router() -> APIRouter:
    router = APIRouter(tags=["agent"])

    async def fixed(request: Request) -> StreamingResponse:
        return await proxy_to_agent(request, request.url.path.lstrip("/"))

    async def wild(request: Request, path: str) -> StreamingResponse:  # noqa: ARG001 — path satisfies the route
        return await proxy_to_agent(request, request.url.path.lstrip("/"))

    # A reverse-proxy passthrough, not documented API operations: keep it out of the OpenAPI
    # schema (one handler bound to many paths would otherwise emit duplicate operation ids,
    # and it must never surface as an MCP tool).
    for p in _FIXED:
        router.add_api_route(p, fixed, methods=_METHODS, include_in_schema=False)
    for p in _WILD:
        router.add_api_route(p, wild, methods=_METHODS, include_in_schema=False)
    return router
