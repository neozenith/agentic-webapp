"""The semantic layer is queryable over MCP — the "any agent can answer questions over the
data model" deliverable. Drives the real mounted MCP exactly as an MCP client (claude -p /
codex / the ADK agent) would: a live server + a fastmcp Client carrying a persona header.
RBAC is the same engine as REST, so a viewer is 403'd over MCP too. No mocks, no LLM."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from agentic_webapp.testing import live_backend
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ADMIN = "ada.admin@example.com"
ANALYST = "nina.analyst@example.com"
VIEWER = "vera.viewer@example.com"

_YEARLY = {
    "model_id": "fuel_tracking",
    "query": {
        "entity": "fuel_purchases",
        "measures": ["total_cost"],
        "time_grain": "year",
        "order_by": "purchased_at",
        "descending": False,
    },
}


@pytest.fixture(scope="module")
def mcp_url() -> Iterator[str]:
    """MCP endpoint of a real backend (lifespan seeds the fuel demo). Boot once per module."""
    with live_backend() as base_url:
        yield f"{base_url}/mcp/"


def _client(url: str, email: str | None) -> Client:
    headers = {"X-Goog-Authenticated-User-Email": email} if email else {}
    return Client(StreamableHttpTransport(url, headers=headers))


def _list_tools(url: str, email: str | None) -> list[str]:
    async def _run() -> list[str]:
        async with _client(url, email) as client:
            return sorted(t.name for t in await client.list_tools())

    return asyncio.run(_run())


def _call(url: str, email: str | None, tool: str, args: dict[str, Any]) -> Any:
    async def _run() -> Any:
        async with _client(url, email) as client:
            result = await client.call_tool(tool, args)
            return getattr(result, "data", None)

    return asyncio.run(_run())


def _call_raw_text(url: str, email: str | None, tool: str, args: dict[str, Any]) -> str:
    """Concatenated text of every content block — UI tools return text + a ui:// resource."""

    async def _run() -> str:
        async with _client(url, email) as client:
            result = await client.call_tool(tool, args)
            return " ".join(getattr(b, "text", "") or str(b) for b in result.content)

    return asyncio.run(_run())


def test_semantic_and_dashboard_tools_are_exposed(mcp_url: str) -> None:
    tools = _list_tools(mcp_url, ADMIN)
    for expected in ("semantic_query", "semantic_list_models", "dashboards_list", "dashboard"):
        assert expected in tools


def test_agent_queries_the_semantic_layer_via_mcp(mcp_url: str) -> None:
    data = _call(mcp_url, ANALYST, "semantic_query", _YEARLY)
    rows = data["rows"] if isinstance(data, dict) else data.rows
    years = [r["purchased_at"] for r in rows]
    assert years == ["2024-01-01", "2025-01-01"]
    # the compiled SQL is returned for transparency
    sql = data["sql"] if isinstance(data, dict) else data.sql
    assert "DATE_TRUNC" in sql


def test_semantic_query_forbidden_for_viewer_over_mcp(mcp_url: str) -> None:
    with pytest.raises(Exception, match="403"):
        _call(mcp_url, VIEWER, "semantic_query", _YEARLY)


def test_dashboard_tool_returns_inline_ui(mcp_url: str) -> None:
    text = _call_raw_text(mcp_url, ADMIN, "dashboard", {"dashboard_id": "fuel-overview"})
    assert "Rendered dashboard" in text
    assert "ui://dashboard/fuel-overview" in text
