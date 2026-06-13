"""Background session titling.

An extra LLM call — NOT the agent's tool-calling loop — that summarises a session into a
short, human-friendly title to accompany the session_id. It runs as an after_agent_callback
(once, when the session has no title yet), writes the title into the session state (which the
FirestoreSessionService persists and the SPA reads), and itemises its own token/cost against
the session via bookkeeping.record_llm_call (so the auxiliary call is still tracked).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from google import genai
from google.genai import types

from . import bookkeeping

log = logging.getLogger(__name__)

_MODEL = os.environ.get("SUMMARY_MODEL", os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite"))
_TITLE_KEY = "title"
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:  # pragma: no cover — real Vertex client; covered by live deploy
        _client = genai.Client()  # Vertex via GOOGLE_GENAI_USE_VERTEXAI + project/location env
    return _client


def _message_texts(events: list[Any]) -> list[tuple[str, str]]:
    """(author, text) for each non-empty event, oldest first."""
    out: list[tuple[str, str]] = []
    for event in events or []:
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) or []
        text = " ".join(p.text for p in parts if getattr(p, "text", None)).strip()
        if text:
            out.append((getattr(event, "author", "") or "model", text))
    return out


def should_title(state: dict[str, Any], events: list[Any]) -> bool:
    """Title a session once it has a real exchange and doesn't already have a title."""
    if state.get(_TITLE_KEY):
        return False
    msgs = _message_texts(events)
    has_user = any(a == "user" for a, _ in msgs)
    has_reply = any(a != "user" for a, _ in msgs)
    return has_user and has_reply


def build_prompt(events: list[Any], *, max_chars: int = 4000) -> str:
    """A compact transcript for the title prompt (strips embedded asset references)."""
    lines: list[str] = []
    for author, text in _message_texts(events):
        clean = " ".join(text.replace("\n", " ").split())
        lines.append(f"{'User' if author == 'user' else 'Assistant'}: {clean}")
    transcript = "\n".join(lines)
    return transcript[:max_chars]


def clean_title(raw: str | None, *, max_words: int = 6, max_chars: int = 60) -> str:
    """Normalise the model output into a short title (first line, no quotes/markdown)."""
    text = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
    text = text.strip().strip("\"'`*#").strip()
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])
    return text[:max_chars].strip()


async def summarize_session(callback_context: Any) -> None:
    """after_agent_callback: set a one-time session title. Returns None (keeps the reply).
    Never raises — titling must not break a response."""
    ictx = getattr(callback_context, "_invocation_context", None)
    session = getattr(ictx, "session", None)
    events = getattr(session, "events", None) or []
    state = callback_context.state
    if not should_title(state, events):
        return None
    try:  # pragma: no cover — live Vertex call + persistence; covered by live deploy
        resp = _get_client().models.generate_content(
            model=_MODEL,
            contents=build_prompt(events),
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You name chat sessions. Reply with ONLY a concise title of at most 6 words "
                    "that captures the topic. No quotes, no punctuation at the ends."
                ),
                max_output_tokens=20,
                temperature=0.2,
            ),
        )
        title = clean_title(getattr(resp, "text", None))
        if not title:
            return None
        state[_TITLE_KEY] = title
        usage = getattr(resp, "usage_metadata", None)
        await bookkeeping.record_llm_call(
            user_id=getattr(session, "user_id", None) or "anonymous",
            session_id=getattr(session, "id", None) or "unknown",
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            app_name="summarizer",
            model_id=_MODEL,
        )
        log.info("titled session %s: %r", getattr(session, "id", "?"), title)
    except Exception:  # noqa: BLE001
        log.exception("session titling failed")
    return None
