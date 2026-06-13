"""Tests for the session summariser — pure helpers + the bookkeeping recorder (real
in-memory LlmUsageManager, no mocks). The live Vertex call in summarize_session is
covered by the live deploy (pragma'd)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from assistant import bookkeeping, summarizer


def _event(author: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(author=author, content=SimpleNamespace(parts=[SimpleNamespace(text=text)]))


def test_should_title_requires_an_exchange_and_no_existing_title():
    user_only = [_event("user", "hello")]
    full = [_event("user", "hello"), _event("assistant", "hi there")]
    assert summarizer.should_title({}, full) is True
    assert summarizer.should_title({}, user_only) is False  # no reply yet
    assert summarizer.should_title({}, []) is False
    assert summarizer.should_title({"title": "Existing"}, full) is False  # already titled


def test_build_prompt_labels_roles_and_flattens_whitespace():
    events = [_event("user", "Read my\n\nfuel receipt"), _event("assistant", "Recorded $82.50")]
    prompt = summarizer.build_prompt(events)
    assert "User: Read my fuel receipt" in prompt
    assert "Assistant: Recorded $82.50" in prompt


def test_clean_title_strips_quotes_and_caps_words():
    assert summarizer.clean_title('"Fuel receipt analysis"') == "Fuel receipt analysis"
    assert summarizer.clean_title("one two three four five six seven eight") == "one two three four five six"
    assert summarizer.clean_title("  **Odometer reading**\nsecond line ") == "Odometer reading"
    assert summarizer.clean_title(None) == ""


def test_record_llm_call_itemises_an_auxiliary_call():
    before = len(asyncio.run(bookkeeping._USAGE.list()))
    asyncio.run(
        bookkeeping.record_llm_call(
            user_id="alice",
            session_id="s1",
            prompt_tokens=40,
            output_tokens=5,
            app_name="summarizer",
        )
    )
    rows = asyncio.run(bookkeeping._USAGE.list())
    assert len(rows) == before + 1
    latest = rows[0]
    assert latest.app_name == "summarizer"
    assert latest.session_id == "s1"
    assert latest.total_tokens == 45


def test_summarize_session_no_exchange_is_a_noop():
    # No events -> should_title False -> returns None without calling Vertex.
    ctx = SimpleNamespace(state={}, _invocation_context=SimpleNamespace(session=SimpleNamespace(events=[], id="s1")))
    assert asyncio.run(summarizer.summarize_session(ctx)) is None
    assert "title" not in ctx.state
