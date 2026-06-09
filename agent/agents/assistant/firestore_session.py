"""FirestoreSessionService — a durable ADK BaseSessionService backed by Firestore.

ADK's Python distribution ships only in-memory, SQL (DatabaseSessionService) and
Vertex session services; there is no native Firestore one. This implements the
BaseSessionService contract over the Firestore async client so conversations survive
Cloud Run cold starts and can be resumed by id.

It mirrors InMemorySessionService's semantics exactly, including ADK's four state
scopes (keyed by prefix): `app:` and `user:` state is shared across sessions and is
stored in its own collections; `temp:` state is never persisted; everything else is
session-scoped and lives on the session document.

Firestore layout (in a named database):
  adk_sessions/{app|user|session}            -> {app_name, user_id, id, state, last_update_time}
  adk_sessions/{...}/events/{event_id}        -> event.model_dump(json), ordered by timestamp
  adk_app_state/{app_name}                     -> shared app-scoped state
  adk_user_state/{app|user}                    -> shared user-scoped state

The server is authoritative for session ids: create_session mints a uuid4 when the
caller supplies none (never trust a client-provided id elsewhere).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from google.adk.errors.already_exists_error import AlreadyExistsError
from google.adk.events.event import Event
from google.adk.sessions.base_session_service import (
    BaseSessionService,
    GetSessionConfig,
    ListSessionsResponse,
)
from google.adk.sessions.session import Session
from google.adk.sessions.state import State
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

_SESSIONS = "adk_sessions"
_APP_STATE = "adk_app_state"
_USER_STATE = "adk_user_state"
_EVENTS = "events"


def _split_state(state: dict[str, Any] | None) -> tuple[dict, dict, dict]:
    """Split a flat state dict into (app, user, session) scopes by prefix. temp: keys
    are dropped (never persisted); session scope keeps unprefixed keys verbatim."""
    app: dict[str, Any] = {}
    user: dict[str, Any] = {}
    session: dict[str, Any] = {}
    for key, value in (state or {}).items():
        if key.startswith(State.APP_PREFIX):
            app[key[len(State.APP_PREFIX) :]] = value
        elif key.startswith(State.USER_PREFIX):
            user[key[len(State.USER_PREFIX) :]] = value
        elif key.startswith(State.TEMP_PREFIX):
            continue
        else:
            session[key] = value
    return app, user, session


class FirestoreSessionService(BaseSessionService):
    def __init__(
        self,
        *,
        project: str,
        database: str = "(default)",
        client: firestore.AsyncClient | None = None,
    ) -> None:
        self._client = client or firestore.AsyncClient(project=project, database=database)

    # --- document references -------------------------------------------------
    def _session_doc(self, app_name: str, user_id: str, session_id: str):
        return self._client.collection(_SESSIONS).document(f"{app_name}|{user_id}|{session_id}")

    def _app_doc(self, app_name: str):
        return self._client.collection(_APP_STATE).document(app_name)

    def _user_doc(self, app_name: str, user_id: str):
        return self._client.collection(_USER_STATE).document(f"{app_name}|{user_id}")

    async def _merge_scoped_state(self, session: Session) -> None:
        """Overlay shared app:/user: state onto a session's state (read path)."""
        app_snap = await self._app_doc(session.app_name).get()
        if app_snap.exists:
            for key, value in (app_snap.to_dict() or {}).items():
                session.state[State.APP_PREFIX + key] = value
        user_snap = await self._user_doc(session.app_name, session.user_id).get()
        if user_snap.exists:
            for key, value in (user_snap.to_dict() or {}).items():
                session.state[State.USER_PREFIX + key] = value

    # --- BaseSessionService --------------------------------------------------
    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        if session_id and session_id.strip():
            session_id = session_id.strip()
            if (await self._session_doc(app_name, user_id, session_id).get()).exists:
                raise AlreadyExistsError(f"Session with id {session_id} already exists.")
        else:
            session_id = str(uuid.uuid4())  # server mints the id

        app_delta, user_delta, session_state = _split_state(state)
        if app_delta:
            await self._app_doc(app_name).set(app_delta, merge=True)
        if user_delta:
            await self._user_doc(app_name, user_id).set(user_delta, merge=True)

        now = time.time()
        await self._session_doc(app_name, user_id, session_id).set(
            {
                "app_name": app_name,
                "user_id": user_id,
                "id": session_id,
                "state": session_state,
                "last_update_time": now,
            }
        )
        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=dict(session_state),
            last_update_time=now,
        )
        await self._merge_scoped_state(session)
        return session

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        ref = self._session_doc(app_name, user_id, session_id)
        snap = await ref.get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}

        query = ref.collection(_EVENTS).order_by("timestamp")
        events = [Event.model_validate(doc.to_dict()) async for doc in query.stream()]
        events = _apply_event_config(events, config)

        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=dict(data.get("state") or {}),
            events=events,
            last_update_time=data.get("last_update_time") or 0.0,
        )
        await self._merge_scoped_state(session)
        return session

    async def list_sessions(self, *, app_name: str, user_id: Optional[str] = None) -> ListSessionsResponse:
        query: Any = self._client.collection(_SESSIONS).where(filter=FieldFilter("app_name", "==", app_name))
        if user_id is not None:
            query = query.where(filter=FieldFilter("user_id", "==", user_id))
        sessions = []
        async for doc in query.stream():
            data = doc.to_dict() or {}
            # Per the contract, listed sessions carry no events/state — metadata only.
            sessions.append(
                Session(
                    app_name=app_name,
                    user_id=data.get("user_id", user_id or ""),
                    id=data["id"],
                    last_update_time=data.get("last_update_time") or 0.0,
                )
            )
        return ListSessionsResponse(sessions=sessions)

    async def delete_session(self, *, app_name: str, user_id: str, session_id: str) -> None:
        ref = self._session_doc(app_name, user_id, session_id)
        async for doc in ref.collection(_EVENTS).stream():
            await doc.reference.delete()
        await ref.delete()

    async def append_event(self, session: Session, event: Event) -> Event:
        # Base updates the in-memory session (state + events) and trims temp deltas;
        # it returns early for partial (streaming) events, which we must not persist.
        event = await super().append_event(session=session, event=event)
        if event.partial:
            return event

        session.last_update_time = event.timestamp
        ref = self._session_doc(session.app_name, session.user_id, session.id)
        await ref.collection(_EVENTS).document(event.id).set(event.model_dump(mode="json", exclude_none=True))

        session_delta: dict[str, Any] = {}
        if event.actions and event.actions.state_delta:
            app_delta, user_delta, session_delta = _split_state(event.actions.state_delta)
            if app_delta:
                await self._app_doc(session.app_name).set(app_delta, merge=True)
            if user_delta:
                await self._user_doc(session.app_name, session.user_id).set(user_delta, merge=True)

        update: dict[str, Any] = {"last_update_time": event.timestamp}
        if session_delta:
            update["state"] = session_delta  # deep-merged into the existing state map
        await ref.set(update, merge=True)
        return event


def _apply_event_config(events: list[Event], config: Optional[GetSessionConfig]) -> list[Event]:
    """Mirror InMemorySessionService's config filtering: most-recent-N, then a
    contiguous tail with timestamp >= after_timestamp."""
    if not config:
        return events
    if config.num_recent_events is not None:
        events = [] if config.num_recent_events == 0 else events[-config.num_recent_events :]
    if config.after_timestamp:
        i = len(events) - 1
        while i >= 0 and events[i].timestamp >= config.after_timestamp:
            i -= 1
        events = events[i + 1 :]
    return events
