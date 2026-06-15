"""The hand-authored MCP-UI `browse` tool + `/ui/browse` proxy (ADR-0012).

Same harness as test_mcp.py: a live backend + a fastmcp `Client` over streamable-HTTP
carrying a persona's `X-Goog-Authenticated-User-Email`. Real in-memory backends, no mocks.
These assert the UI render contract, that browse contents are RBAC-scoped by the forwarded
identity, and that the web proxy reuses the same renderer without leaking a tool or an API op.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

from datetime import datetime, timezone

import httpx
import pytest
from agentic_core.models import AssetMetadata, Folder
from agentic_webapp.mcp_ui import _human_size, _icon, browse_summary, render_browse
from agentic_webapp.testing import live_backend
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ADMIN = "ada.admin@example.com"
VIEWER = "vera.viewer@example.com"
HEADER = "X-Goog-Authenticated-User-Email"


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with live_backend() as url:
        yield url


def _client(base: str, email: str | None) -> Client:
    headers = {HEADER: email} if email else {}
    return Client(StreamableHttpTransport(f"{base}/mcp/", headers=headers))


def _call_blocks(base: str, email: str | None, tool: str, args: dict[str, Any]) -> list[Any]:
    async def _run() -> list[Any]:
        async with _client(base, email) as client:
            result = await client.call_tool(tool, args)
            return list(result.content)

    return asyncio.run(_run())


def _ui_text(blocks: list[Any]) -> str:
    """The HTML of the first embedded ui:// resource among a tool result's blocks."""
    for b in blocks:
        res = getattr(b, "resource", None)
        if res is not None and str(getattr(res, "uri", "")).startswith("ui://"):
            assert res.mimeType.startswith("text/html")
            return str(res.text)
    raise AssertionError(f"no ui:// resource in blocks: {blocks!r}")


def _make_folder(base: str, email: str, name: str) -> None:
    async def _run() -> None:
        async with _client(base, email) as client:
            await client.call_tool("folders_create", {"name": name})

    asyncio.run(_run())


def test_browse_is_listed_and_returns_a_ui_resource(base_url: str) -> None:
    async def _tools() -> list[str]:
        async with _client(base_url, ADMIN) as client:
            return [t.name for t in await client.list_tools()]

    assert "browse" in asyncio.run(_tools())
    blocks = _call_blocks(base_url, ADMIN, "browse", {})
    assert "Folders" in _ui_text(blocks)
    # A short text summary rides alongside the resource for the model.
    assert any(getattr(b, "text", None) for b in blocks if getattr(b, "type", None) == "text")


def test_browse_contents_are_rbac_scoped_by_identity(base_url: str) -> None:
    # Two personas each create a private folder; the viewer's browse must show only theirs.
    _make_folder(base_url, ADMIN, "ada-private-folder")
    _make_folder(base_url, VIEWER, "vera-private-folder")
    viewer_html = _ui_text(_call_blocks(base_url, VIEWER, "browse", {}))
    assert "vera-private-folder" in viewer_html
    assert "ada-private-folder" not in viewer_html  # identity forwarding scoped the fetch


def test_ui_browse_proxy_renders_same_resource(base_url: str) -> None:
    # The web host's drill-in proxy returns the embedded ui:// resource block.
    resp = httpx.get(f"{base_url}/ui/browse", headers={HEADER: VIEWER})
    resp.raise_for_status()
    block = resp.json()
    assert block["type"] == "resource"
    assert block["resource"]["uri"].startswith("ui://")
    assert "vera-private-folder" in block["resource"]["text"]  # same renderer, same RBAC


def test_ui_proxy_is_not_an_api_op_nor_a_tool(base_url: str) -> None:
    # /ui/* is a web-only seam: out of OpenAPI and never an MCP tool (guards ADR-0011/0012).
    spec = httpx.get(f"{base_url}/openapi.json").json()
    assert not any(p.startswith("/ui") for p in spec["paths"])

    async def _tools() -> list[str]:
        async with _client(base_url, ADMIN) as client:
            return [t.name for t in await client.list_tools()]

    tools = asyncio.run(_tools())
    assert not any("ui" == t or t.startswith("ui_") for t in tools)


# --- Pure renderer unit tests (no backend; exercise the drill-in filtering logic) ---

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _folder(fid: str, name: str, parent: str | None = None) -> Folder:
    return Folder(folder_id=fid, name=name, parent_id=parent, created_at=_T)


def _asset(aid: str, name: str, folder: str | None = None, ct: str = "image/png") -> AssetMetadata:
    return AssetMetadata(
        asset_id=aid, storage_key=f"k/{aid}", filename=name, content_type=ct,
        size_bytes=2048, created_at=_T, updated_at=_T, folder_id=folder,
    )


@pytest.mark.parametrize(
    "ct,icon", [("image/png", "🖼"), ("application/pdf", "📄"), ("text/plain", "📝"), ("application/zip", "📎"), (None, "📎")]
)
def test_icon_by_content_type(ct: str | None, icon: str) -> None:
    assert _icon(ct) == icon


@pytest.mark.parametrize("n,out", [(None, ""), (0, ""), (512, "512 B"), (2048, "2.0 KB"), (5 * 1024 * 1024, "5.0 MB")])
def test_human_size(n: int | None, out: str) -> None:
    assert _human_size(n) == out


def test_render_filters_to_current_folder_and_builds_breadcrumb() -> None:
    folders = [_folder("a", "Receipts"), _folder("b", "2026", parent="a"), _folder("c", "Invoices")]
    assets = [_asset("x", "lunch.png", folder="a"), _asset("y", "march.pdf", folder=None, ct="application/pdf")]

    root_html = render_browse(folders, assets, folder_id=None).resource.text
    assert "Receipts" in root_html and "Invoices" in root_html  # top-level folders
    assert "2026" not in root_html  # nested folder not shown at root
    assert "march.pdf" in root_html and "lunch.png" not in root_html  # only root-level assets

    inner = render_browse(folders, assets, folder_id="a").resource.text
    assert "2026" in inner and "lunch.png" in inner  # contents of Receipts
    assert "Home" in inner and "Receipts" in inner  # breadcrumb: Home / Receipts


def test_browse_summary_counts() -> None:
    folders = [_folder("a", "Receipts"), _folder("b", "2026", parent="a")]
    assets = [_asset("x", "lunch.png", folder="a")]
    assert browse_summary(folders, assets, None) == "Browsing root: 1 subfolder(s), 0 asset(s)."
    assert browse_summary(folders, assets, "a") == "Browsing “Receipts”: 1 subfolder(s), 1 asset(s)."
