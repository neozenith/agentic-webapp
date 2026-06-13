"""Turn-scoped image attachment for the agent.

Bug context (session 16d0bb43…): the previous attach_asset tool stashed asset_ids in
session state and re-injected ALL of them on every model call. So a receipt attached in
turn 1 stayed injected in turn 2, crowding out a new odometer photo — the model "couldn't
see" the new image. Phone filenames also collide (two different IMG_1282.jpeg), so the
model can't disambiguate by name.

Fix: inject only the assets relevant to the CURRENT turn (invocation), and do it via a
before_model_callback so it doesn't depend on the model deciding to call a tool. The set of
assets for a turn is the union of:
  - asset_ids referenced in the latest user message (`[attached asset <id> — <name>]`), and
  - asset_ids the model explicitly attached via the attach_asset tool *this* invocation.
Bytes are re-fetched from the backend (GCS) each turn and never persisted locally (ADR-0006).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from google.genai import types

from . import assets_client

log = logging.getLogger(__name__)

# State keys: the asset_ids attached via the tool, scoped to the invocation that set them.
INVOCATION_KEY = "_attach_invocation_id"
IDS_KEY = "_attached_asset_ids"

# Matches the reference the chat composer appends, e.g. "[attached asset 3f9a… — IMG_1.jpg]".
_REF_RE = re.compile(r"\[attached asset\s+([0-9a-fA-F]{8,})")

# MIME types Gemini accepts inline (image/audio/video + pdf).
_INJECTABLE = ("image/", "audio/", "video/")


def _invocation_id(ctx: Any) -> str:
    ictx = getattr(ctx, "_invocation_context", None)
    return getattr(ictx, "invocation_id", "") or getattr(ctx, "invocation_id", "") or ""


def is_injectable(mime: str | None) -> bool:
    m = (mime or "").split(";", 1)[0].strip().lower()
    return m.startswith(_INJECTABLE) or m == "application/pdf"


def parse_referenced_ids(text: str) -> list[str]:
    """Asset ids referenced in a message, in order, de-duplicated."""
    seen: dict[str, None] = {}
    for match in _REF_RE.findall(text or ""):
        seen.setdefault(match, None)
    return list(seen)


def note_tool_attachment(state: Any, invocation_id: str, asset_id: str) -> list[str]:
    """Record an attach_asset tool call, scoped to the current invocation. Starting a new
    invocation resets the list so stale attachments from prior turns are dropped."""
    ids: list[str] = list(state.get(IDS_KEY, [])) if state.get(INVOCATION_KEY) == invocation_id else []
    if asset_id not in ids:
        ids.append(asset_id)
    state[INVOCATION_KEY] = invocation_id
    state[IDS_KEY] = ids
    return ids


def _latest_user_text(llm_request: Any) -> str:
    """Concatenated text of the most recent user message in the request."""
    contents = getattr(llm_request, "contents", None) or []
    for content in reversed(contents):
        if getattr(content, "role", None) == "user":
            return " ".join(p.text for p in (content.parts or []) if getattr(p, "text", None))
    return ""


def ids_for_turn(callback_context: Any, llm_request: Any) -> list[str]:
    """Union of assets referenced in the latest user message and those attached via the
    tool during the current invocation — the assets to show the model THIS turn."""
    ids = parse_referenced_ids(_latest_user_text(llm_request))
    state = getattr(callback_context, "state", {})
    if state.get(INVOCATION_KEY) == _invocation_id(callback_context):
        for asset_id in state.get(IDS_KEY, []):
            if asset_id not in ids:
                ids.append(asset_id)
    return ids


async def attach_referenced_assets(callback_context: Any, llm_request: Any) -> None:
    """before_model_callback: inject the current turn's assets inline. Returns None so the
    model still runs. Never raises — a missing asset must not break the reply."""
    ids = ids_for_turn(callback_context, llm_request)
    for asset_id in ids:  # pragma: no cover — live HTTP + injection; covered by e2e
        try:
            data, mime = await assets_client.fetch_content(asset_id)
        except Exception:  # noqa: BLE001
            log.warning("attach: could not fetch %s", asset_id)
            continue
        if not is_injectable(mime):
            continue
        llm_request.contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"Image for asset {asset_id}:"),
                    types.Part.from_bytes(data=data, mime_type=mime),
                ],
            )
        )
    return None
