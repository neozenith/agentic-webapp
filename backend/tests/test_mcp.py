"""The MCP interface enforces the SAME RBAC as the core API.

The MCP server is mounted in the app and calls /api/* over loopback HTTP, forwarding the
caller's identity header per request. These tests drive it exactly as a real MCP client
(claude -p / codex / the ADK harness) would: a live server + a fastmcp `Client` over
streamable-HTTP carrying a persona's `X-Goog-Authenticated-User-Email`. Real in-memory
backends, no mocks (project rule) — so RBAC-over-MCP is proven against the real engine.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ADMIN = "ada.admin@example.com"
ANALYST = "nina.analyst@example.com"
VIEWER = "vera.viewer@example.com"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def mcp_url() -> Iterator[str]:
    """A real backend on an ephemeral port with the MCP mounted, identity-simulation on, and
    the loopback base-url pinned to the same port. Module-scoped: boot once, probe many times."""
    from agentic_webapp.config import get_settings
    from agentic_webapp.main import create_app

    port = _free_port()
    keys = ("ENVIRONMENT", "TRUST_FORWARDED_USER", "SELF_BASE_URL", "PORT")
    prev = {k: os.environ.get(k) for k in keys}
    os.environ.update(
        ENVIRONMENT="dev",
        TRUST_FORWARDED_USER="true",
        SELF_BASE_URL=f"http://127.0.0.1:{port}",
        PORT=str(port),
    )
    get_settings.cache_clear()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:  # pragma: no cover — tight startup spin
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}/mcp/"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def _client(url: str, email: str | None) -> Client:
    headers = {"X-Goog-Authenticated-User-Email": email} if email else {}
    return Client(StreamableHttpTransport(url, headers=headers))


def _list_tools(url: str, email: str | None) -> list[str]:
    async def _run() -> list[str]:
        async with _client(url, email) as client:
            return sorted(tool.name for tool in await client.list_tools())

    return asyncio.run(_run())


def _call(url: str, email: str | None, tool: str, args: dict[str, Any]) -> Any:
    """Call a tool, returning its parsed data; raises (ToolError) if the API 403s the persona."""

    async def _run() -> Any:
        async with _client(url, email) as client:
            result = await client.call_tool(tool, args)
            data = getattr(result, "data", None)
            if data is not None:
                return data
            return json.loads(result.content[0].text)  # pragma: no cover — fallback path

    return asyncio.run(_run())


def test_mcp_exposes_only_core_api_tools(mcp_url: str) -> None:
    tools = _list_tools(mcp_url, ADMIN)
    # The whole /api/* surface is present as predictably-named tools…
    assert {"assets_list", "assets_share", "folders_list", "admin_users", "analytics_summary", "identity_me"} <= set(
        tools
    )
    # …binary byte-stream endpoints are NOT tools, and neither are SPA/agent-proxy paths.
    assert not any("content" in name for name in tools)
    assert all(not name.startswith(("agent_", "spa", "health")) for name in tools)


def test_admin_tool_allowed_for_admin_denied_for_viewer(mcp_url: str) -> None:
    assert isinstance(_call(mcp_url, ADMIN, "admin_users", {}), list)  # admin may list users
    with pytest.raises(Exception, match="403"):
        _call(mcp_url, VIEWER, "admin_users", {})


def test_analytics_tool_denied_for_viewer_allowed_for_analyst(mcp_url: str) -> None:
    assert _call(mcp_url, ANALYST, "analytics_summary", {}) is not None
    with pytest.raises(Exception, match="403"):
        _call(mcp_url, VIEWER, "analytics_summary", {})


def test_identity_forwarded_per_persona(mcp_url: str) -> None:
    # identity_me round-trips the forwarded header through to the RBAC engine.
    assert _call(mcp_url, ANALYST, "identity_me", {})["roles"] == ["analyst"]
    assert _call(mcp_url, ADMIN, "identity_me", {})["roles"] == ["admin"]


def test_anonymous_mcp_call_is_denied_admin(mcp_url: str) -> None:
    # No identity header at all → no roles → admin area locked (same as the API with no IAP email).
    assert _call(mcp_url, None, "identity_me", {})["roles"] == []
    with pytest.raises(Exception, match="403"):
        _call(mcp_url, None, "admin_users", {})
