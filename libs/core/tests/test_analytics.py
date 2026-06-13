"""Contract tests for AnalyticsManager + the env factories (in-memory, real, no mocks)."""

from datetime import datetime, timezone

from agentic_core.database import (
    AnalyticsManager,
    InMemoryDatabaseManager,
    build_analytics_database_from_env,
    build_database_from_env,
)
from agentic_core.models import ExtractionRecord

_BACKEND_VARS = ("DATABASE_BACKEND", "FIRESTORE_DATABASE", "BIGQUERY_DATASET", "GCP_PROJECT", "GOOGLE_CLOUD_PROJECT")


def _record(eid: str, **fields: object) -> ExtractionRecord:
    return ExtractionRecord(
        extraction_id=eid,
        asset_id="a1",
        doc_type="fuel_receipt",
        user_id="alice@example.com",
        session_id="s1",
        fields=fields or {"vendor": "Shell", "total": "82.50", "currency": "AUD"},
        model_id="gemini-2.5-flash-lite",
        created_at=datetime.now(timezone.utc),
    )


def test_extraction_record_get_list_roundtrip(database, run):
    mgr = AnalyticsManager(database)
    run(mgr.record_extraction(_record("e1")))
    run(mgr.record_extraction(_record("e2", vendor="BP", litres="45.2")))

    rows = run(mgr.list_extractions())
    assert {r.extraction_id for r in rows} == {"e1", "e2"}

    one = run(mgr.get_extraction("e1"))
    assert one is not None
    assert one.doc_type == "fuel_receipt"
    # The free-form payload survives the JSON round-trip through the row layer.
    assert one.fields["vendor"] == "Shell"
    assert one.fields["currency"] == "AUD"


def test_get_missing_returns_none(database, run):
    assert run(AnalyticsManager(database).get_extraction("nope")) is None


def test_delete_removes_the_record(database, run):
    mgr = AnalyticsManager(database)
    run(mgr.record_extraction(_record("e9")))
    run(mgr.delete_extraction("e9"))
    assert run(mgr.get_extraction("e9")) is None


def test_operational_factory_defaults_to_in_memory(monkeypatch):
    for var in _BACKEND_VARS:
        monkeypatch.delenv(var, raising=False)
    assert isinstance(build_database_from_env(), InMemoryDatabaseManager)


def test_analytics_factory_defaults_to_in_memory(monkeypatch):
    # Analytics never falls back to Firestore; with no BIGQUERY_DATASET it's in-memory.
    for var in _BACKEND_VARS:
        monkeypatch.delenv(var, raising=False)
    assert isinstance(build_analytics_database_from_env(), InMemoryDatabaseManager)


def test_analytics_factory_in_memory_without_dataset_even_with_project(monkeypatch):
    for var in _BACKEND_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GCP_PROJECT", "proj")  # project set, but no dataset -> still in-memory
    assert isinstance(build_analytics_database_from_env(), InMemoryDatabaseManager)
