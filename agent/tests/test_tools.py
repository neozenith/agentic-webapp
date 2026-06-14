"""Tests for the agent's local attachment logic — pure helpers, no mocks. ADK context
objects are plain SimpleNamespace stubs carrying the attributes the code reads (same approach
as test_bookkeeping). Asset listing + extraction recording are the kernel's MCP tools now, so
they're tested in the backend (tests/test_extractions.py), not here."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from assistant import attachments, tools
from assistant.assets_client import _viewer_headers, preview_url


def test_preview_url():
    assert preview_url("xyz") == "/api/assets/xyz/content"


def test_viewer_headers_only_when_identified():
    assert _viewer_headers("u1") == {"X-Viewer-User-Id": "u1"}
    assert _viewer_headers(None) == {}


def test_is_injectable():
    assert attachments.is_injectable("image/jpeg")
    assert attachments.is_injectable("application/pdf")
    assert not attachments.is_injectable("text/plain")
    assert not attachments.is_injectable(None)


def test_parse_referenced_ids_dedups_in_order():
    text = "Process [attached asset 0123abcd4567 — IMG_1.jpg] and [attached asset 89abcdef0123 — IMG_2.jpg] and again [attached asset 0123abcd4567 — IMG_1.jpg]"
    assert attachments.parse_referenced_ids(text) == ["0123abcd4567", "89abcdef0123"]
    assert attachments.parse_referenced_ids("") == []


def test_note_tool_attachment_resets_on_new_invocation():
    state: dict = {}
    # Turn 1 (invocation inv-1): attach two assets.
    attachments.note_tool_attachment(state, "inv-1", "a1")
    assert attachments.note_tool_attachment(state, "inv-1", "a2") == ["a1", "a2"]
    # Turn 2 (inv-2): the stale turn-1 ids are dropped — this is the bug fix.
    assert attachments.note_tool_attachment(state, "inv-2", "a9") == ["a9"]
    assert state[attachments.IDS_KEY] == ["a9"]


def test_ids_for_turn_unions_message_refs_and_same_invocation_tool_attachments():
    state = {attachments.INVOCATION_KEY: "inv-1", attachments.IDS_KEY: ["tool-asset"]}
    cb = SimpleNamespace(state=state, _invocation_context=SimpleNamespace(invocation_id="inv-1"))
    llm_request = SimpleNamespace(
        contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="see [attached asset deadbeef1234 — x.png]")])]
    )
    ids = attachments.ids_for_turn(cb, llm_request)
    assert ids == ["deadbeef1234", "tool-asset"]


def test_ids_for_turn_ignores_tool_attachments_from_a_previous_invocation():
    # state was set during inv-1, but we're now in inv-2 -> the old tool ids must not leak.
    state = {attachments.INVOCATION_KEY: "inv-1", attachments.IDS_KEY: ["stale"]}
    cb = SimpleNamespace(state=state, _invocation_context=SimpleNamespace(invocation_id="inv-2"))
    llm_request = SimpleNamespace(contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="hi")])])
    assert attachments.ids_for_turn(cb, llm_request) == []


def _tool_ctx(inv: str = "inv-1") -> SimpleNamespace:
    return SimpleNamespace(state={}, _invocation_context=SimpleNamespace(invocation_id=inv))


def test_attach_asset_records_and_returns_preview_url():
    ctx = _tool_ctx()
    out = asyncio.run(tools.attach_asset("a1", ctx))
    assert out["status"] == "attached"
    assert out["preview_url"] == "/api/assets/a1/content"
    assert ctx.state[attachments.IDS_KEY] == ["a1"]


def test_attach_asset_requires_an_id():
    out = asyncio.run(tools.attach_asset("", _tool_ctx()))
    assert out["status"] == "error"
