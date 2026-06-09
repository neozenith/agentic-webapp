"""ADK service-registry wiring: the firestore:// factory builds a real
FirestoreSessionService and fails loud without a project. Construction is safe under
the emulator (anonymous creds, no connection until first use)."""

from __future__ import annotations

import os

import pytest

import services
from assistant.firestore_session import FirestoreSessionService

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Requires the Firestore emulator (client construction needs anonymous creds)",
)


def test_factory_builds_firestore_session_service(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj")
    monkeypatch.setenv("FIRESTORE_DATABASE", "(default)")
    svc = services._firestore_session_factory("firestore://")
    assert isinstance(svc, FirestoreSessionService)


def test_factory_reads_database_from_uri_host(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj")
    monkeypatch.delenv("FIRESTORE_DATABASE", raising=False)
    svc = services._firestore_session_factory("firestore://my-db")
    assert isinstance(svc, FirestoreSessionService)


def test_factory_requires_a_project(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="GCP_PROJECT"):
        services._firestore_session_factory("firestore://")
