"""record_usage against a REAL in-memory LlmUsageManager (no mocks). The ADK callback
objects are plain SimpleNamespace stubs — real objects carrying the attributes the
callback reads, not mock-framework objects."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from assistant import bookkeeping


def _ctx(app: str = "assistant", user: str = "u", sid: str = "s", inv: str = "inv-1") -> SimpleNamespace:
    session = SimpleNamespace(app_name=app, user_id=user, id=sid)
    return SimpleNamespace(_invocation_context=SimpleNamespace(session=session), invocation_id=inv)


def _resp(prompt: int = 10, output: int = 5, total: int = 15) -> SimpleNamespace:
    usage = SimpleNamespace(prompt_token_count=prompt, candidates_token_count=output, total_token_count=total)
    return SimpleNamespace(usage_metadata=usage)


def test_record_usage_writes_a_row():
    before = len(asyncio.run(bookkeeping._USAGE.list()))
    asyncio.run(bookkeeping.record_usage(_ctx(user="alice"), _resp(total=15)))
    rows = asyncio.run(bookkeeping._USAGE.list())
    assert len(rows) == before + 1
    latest = rows[0]  # list() orders by timestamp desc
    assert latest.total_tokens == 15
    assert latest.user_id == "alice"


def test_record_usage_skips_when_no_usage_metadata():
    before = len(asyncio.run(bookkeeping._USAGE.list()))
    assert asyncio.run(bookkeeping.record_usage(_ctx(), SimpleNamespace(usage_metadata=None))) is None
    assert len(asyncio.run(bookkeeping._USAGE.list())) == before


def test_record_usage_skips_zero_token_calls():
    before = len(asyncio.run(bookkeeping._USAGE.list()))
    asyncio.run(bookkeeping.record_usage(_ctx(), _resp(prompt=0, output=0, total=0)))
    assert len(asyncio.run(bookkeeping._USAGE.list())) == before
