"""The agent's business logic IS the kernel's MCP: per-request identity forwarding (the chat
user's pseudonymous id → the internal viewer header) and a least-privilege tool filter.
Construction-only (no live MCP, no LLM), deterministic, no mocks."""

from __future__ import annotations

from types import SimpleNamespace

from assistant import mcp
from google.adk.tools.mcp_tool import McpToolset


def test_identity_headers_forward_the_session_user() -> None:
    headers = mcp.identity_headers(SimpleNamespace(user_id="user-123"))  # type: ignore[arg-type]
    assert headers == {"X-Viewer-User-Id": "user-123"}


def test_identity_headers_empty_when_anonymous() -> None:
    assert mcp.identity_headers(SimpleNamespace(user_id=None)) == {}  # type: ignore[arg-type]


def test_toolset_is_filtered_to_kernel_chat_tools() -> None:
    assert isinstance(mcp.build_mcp_toolset(), McpToolset)
    assert mcp._TOOL_FILTER == ["assets_list", "assets_get", "extractions_record", "browse"]
    assert mcp.MCP_URL.endswith("/mcp/")


def test_agent_composes_mcp_plus_local_directive_plus_web() -> None:
    from assistant.agent import root_agent

    type_names = [type(t).__name__ for t in root_agent.tools]
    assert "McpToolset" in type_names  # business logic via the kernel
    assert len(root_agent.tools) == 3  # mcp + attach_asset + web
    # the bespoke data tools were removed (now MCP tools on the kernel)
    names = [getattr(t, "__name__", getattr(t, "name", "")) for t in root_agent.tools]
    assert "list_assets" not in names
    assert "record_extraction" not in names
