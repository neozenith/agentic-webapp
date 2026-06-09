"""Round-trip tests for FirestoreSessionService against the REAL Firestore emulator.

No mocks (project rule): we drive the actual async Firestore client and ADK models.
Runs only when the emulator is reachable (FIRESTORE_EMULATOR_HOST). Start one with:

    gcloud emulators firestore start --host-port=localhost:8089
    FIRESTORE_EMULATOR_HOST=localhost:8089 uv run --directory agent pytest

The async Firestore client binds to the event loop of its first use, so each test
runs all its operations in a single asyncio.run(). The "cold-start" resume case uses
a second service instance created inside the same loop. Each test uses a unique user
id so reruns against a persistent emulator stay isolated.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.sessions.base_session_service import GetSessionConfig
from google.genai import types

from assistant.firestore_session import FirestoreSessionService

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Requires the Firestore emulator (set FIRESTORE_EMULATOR_HOST)",
)

_APP = "assistant"


def _svc() -> FirestoreSessionService:
    return FirestoreSessionService(project="agentic-webapp-test", database="(default)")


def _text_event(text: str) -> Event:
    return Event(author="user", content=types.Content(role="user", parts=[types.Part(text=text)]))


def test_create_mints_server_side_id_when_none_given():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        created = await _svc().create_session(app_name=_APP, user_id=user)
        assert created.id  # server minted it; client supplied nothing
        # A second instance (cold-start analogue) resolves the same session.
        resumed = await _svc().get_session(app_name=_APP, user_id=user, session_id=created.id)
        assert resumed is not None and resumed.id == created.id

    asyncio.run(scenario())


def test_append_event_persists_and_resume_rehydrates_transcript():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        service = _svc()
        session = await service.create_session(app_name=_APP, user_id=user)
        await service.append_event(session, _text_event("hello firestore"))
        # New instance => no in-memory state; events must come back from Firestore.
        resumed = await _svc().get_session(app_name=_APP, user_id=user, session_id=session.id)
        assert resumed is not None
        assert [e.content.parts[0].text for e in resumed.events] == ["hello firestore"]

    asyncio.run(scenario())


def test_delete_removes_session_and_events():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        service = _svc()
        session = await service.create_session(app_name=_APP, user_id=user)
        await service.append_event(session, _text_event("x"))
        await service.delete_session(app_name=_APP, user_id=user, session_id=session.id)
        assert await _svc().get_session(app_name=_APP, user_id=user, session_id=session.id) is None

    asyncio.run(scenario())


def test_list_sessions_returns_the_users_sessions():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        service = _svc()
        a = await service.create_session(app_name=_APP, user_id=user)
        b = await service.create_session(app_name=_APP, user_id=user)
        listed = await _svc().list_sessions(app_name=_APP, user_id=user)
        assert {a.id, b.id} <= {s.id for s in listed.sessions}

    asyncio.run(scenario())


def test_state_scopes_persist_and_temp_is_dropped():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        s = await _svc().create_session(
            app_name=_APP,
            user_id=user,
            state={"k": "v", "app:x": 1, "user:y": 2, "temp:z": 3},
        )
        got = await _svc().get_session(app_name=_APP, user_id=user, session_id=s.id)
        assert got is not None
        assert got.state["k"] == "v"  # session-scoped
        assert got.state["app:x"] == 1  # app-scoped, shared
        assert got.state["user:y"] == 2  # user-scoped, shared
        assert "temp:z" not in got.state  # temp never persisted

    asyncio.run(scenario())


def test_append_event_persists_state_delta_by_scope():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        service = _svc()
        session = await service.create_session(app_name=_APP, user_id=user)
        delta_event = Event(
            author="assistant",
            actions=EventActions(state_delta={"k": "v", "app:a": 1, "user:u": 2, "temp:t": 9}),
        )
        await service.append_event(session, delta_event)
        got = await _svc().get_session(app_name=_APP, user_id=user, session_id=session.id)
        assert got is not None
        assert got.state["k"] == "v" and got.state["app:a"] == 1 and got.state["user:u"] == 2
        assert "temp:t" not in got.state

    asyncio.run(scenario())


def test_partial_event_is_not_persisted():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        service = _svc()
        session = await service.create_session(app_name=_APP, user_id=user)
        partial = Event(
            author="assistant", partial=True, content=types.Content(role="model", parts=[types.Part(text="…")])
        )
        await service.append_event(session, partial)
        got = await _svc().get_session(app_name=_APP, user_id=user, session_id=session.id)
        assert got is not None
        assert got.events == []  # streaming-partial events are never stored

    asyncio.run(scenario())


def test_get_session_honours_num_recent_events():
    async def scenario():
        user = f"u_{uuid.uuid4().hex}"
        service = _svc()
        session = await service.create_session(app_name=_APP, user_id=user)
        for i in range(3):
            await service.append_event(session, _text_event(f"m{i}"))
        got = await _svc().get_session(
            app_name=_APP, user_id=user, session_id=session.id, config=GetSessionConfig(num_recent_events=1)
        )
        assert got is not None
        assert [e.content.parts[0].text for e in got.events] == ["m2"]

    asyncio.run(scenario())
