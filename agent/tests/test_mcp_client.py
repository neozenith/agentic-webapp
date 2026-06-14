"""The MCP test-agent wires the core API's MCP with the right URL + persona identity header.
Construction-only (no LLM, no live server) so it runs in CI for $0; the actual LLM-driven run
is exercised manually via `python -m harness.mcp_agent`. Real objects, no mocks."""

from __future__ import annotations

from google.adk.tools.mcp_tool import McpToolset

from harness.mcp_agent import IAP_USER_HEADER, build_agent, mcp_connection

ADMIN = "ada.admin@example.com"


def test_connection_carries_persona_identity_header() -> None:
    conn = mcp_connection("http://localhost:8080", ADMIN)
    assert conn.url == "http://localhost:8080/mcp/"
    assert conn.headers[IAP_USER_HEADER] == ADMIN


def test_anonymous_connection_has_no_identity_header() -> None:
    conn = mcp_connection("http://localhost:8080/", None)  # trailing slash normalised
    assert conn.url == "http://localhost:8080/mcp/"
    assert IAP_USER_HEADER not in (conn.headers or {})


def test_agent_tools_are_only_the_mcp_toolset() -> None:
    agent = build_agent("http://localhost:8080", ADMIN, model="gemini-2.5-flash-lite")
    assert agent.name == "mcp_tester"
    assert len(agent.tools) == 1
    assert isinstance(agent.tools[0], McpToolset)
