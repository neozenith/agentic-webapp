"""Tests for the agent tools — real in-memory ExtractionManager + pure helpers, no mocks.
The ADK context objects are plain SimpleNamespace stubs carrying the attributes the tools
read (the same approach as test_bookkeeping)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from assistant import tools
from assistant.assets_client import _summarise


def test_summarise_picks_the_catalogue_fields():
    full = {
        "asset_id": "a1",
        "storage_key": "assets/a1.png",
        "filename": "receipt.png",
        "content_type": "image/png",
        "size_bytes": 2048,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:00Z",
        "tags": {},
    }
    assert _summarise(full) == {
        "asset_id": "a1",
        "filename": "receipt.png",
        "content_type": "image/png",
        "size_bytes": 2048,
        "created_at": "2026-06-10T00:00:00Z",
    }


def test_is_injectable():
    assert tools._is_injectable("image/jpeg")
    assert tools._is_injectable("image/png; charset=binary")
    assert tools._is_injectable("application/pdf")
    assert tools._is_injectable("audio/mpeg")
    assert not tools._is_injectable("text/plain")
    assert not tools._is_injectable("application/json")
    assert not tools._is_injectable(None)


def test_add_attached_dedups():
    state: dict = {}
    assert tools._add_attached(state, "a1") == ["a1"]
    assert tools._add_attached(state, "a2") == ["a1", "a2"]
    # idempotent — re-attaching the same id doesn't duplicate it
    assert tools._add_attached(state, "a1") == ["a1", "a2"]
    assert state[tools._ATTACHED_KEY] == ["a1", "a2"]


def test_attach_asset_run_async_records_id_in_state():
    tool = tools.AttachAssetTool()
    ctx = SimpleNamespace(state={})
    out = asyncio.run(tool.run_async(args={"asset_id": "a1"}, tool_context=ctx))
    assert out["status"] == "attached"
    assert out["asset_id"] == "a1"
    assert ctx.state[tools._ATTACHED_KEY] == ["a1"]


def test_attach_asset_requires_an_id():
    tool = tools.AttachAssetTool()
    ctx = SimpleNamespace(state={})
    out = asyncio.run(tool.run_async(args={}, tool_context=ctx))
    assert out["status"] == "error"


def test_attach_asset_declaration_has_required_asset_id():
    decl = tools.AttachAssetTool()._get_declaration()
    assert decl.name == "attach_asset"
    assert "asset_id" in decl.parameters.properties
    assert decl.parameters.required == ["asset_id"]


def test_parse_fields_handles_object_scalar_and_garbage():
    assert tools._parse_fields('{"vendor":"Shell","total":"82.50"}') == {"vendor": "Shell", "total": "82.50"}
    assert tools._parse_fields("") == {}
    assert tools._parse_fields("[1,2]") == {"value": [1, 2]}  # non-object JSON -> wrapped
    assert tools._parse_fields("not json") == {"raw": "not json"}


def _ctx(user: str = "alice", sid: str = "s1") -> SimpleNamespace:
    session = SimpleNamespace(app_name="assistant", user_id=user, id=sid)
    return SimpleNamespace(_invocation_context=SimpleNamespace(session=session))


def test_record_extraction_writes_a_row():
    before = len(asyncio.run(tools._EXTRACTIONS.list()))
    out = asyncio.run(
        tools.record_extraction(
            asset_id="a1",
            doc_type="fuel_receipt",
            fields_json='{"vendor":"Shell","total":"82.50","currency":"AUD"}',
            tool_context=_ctx(user="alice"),
        )
    )
    assert out["status"] == "recorded"
    assert out["doc_type"] == "fuel_receipt"
    rows = asyncio.run(tools._EXTRACTIONS.list())
    assert len(rows) == before + 1
    latest = rows[0]  # list() orders by created_at desc
    assert latest.user_id == "alice"
    assert latest.asset_id == "a1"
    assert latest.fields["vendor"] == "Shell"
