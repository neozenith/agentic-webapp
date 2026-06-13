"""Contract tests for ExtractionManager + build_database_from_env (in-memory, real,
no mocks)."""

from datetime import datetime, timezone

from agentic_core.database import ExtractionManager, InMemoryDatabaseManager, build_database_from_env
from agentic_core.models import ExtractionRecord


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


def test_record_get_list_roundtrip(database, run):
    mgr = ExtractionManager(database, table="extractions")
    run(mgr.record(_record("e1")))
    run(mgr.record(_record("e2", vendor="BP", litres="45.2")))

    rows = run(mgr.list())
    assert {r.extraction_id for r in rows} == {"e1", "e2"}

    one = run(mgr.get("e1"))
    assert one is not None
    assert one.doc_type == "fuel_receipt"
    # The free-form payload survives the JSON round-trip through the row layer.
    assert one.fields["vendor"] == "Shell"
    assert one.fields["currency"] == "AUD"


def test_get_missing_returns_none(database, run):
    mgr = ExtractionManager(database, table="extractions")
    assert run(mgr.get("nope")) is None


def test_delete_removes_the_record(database, run):
    mgr = ExtractionManager(database, table="extractions")
    run(mgr.record(_record("e9")))
    run(mgr.delete("e9"))
    assert run(mgr.get("e9")) is None


def test_build_database_from_env_defaults_to_in_memory(monkeypatch):
    # No backend env vars set -> the safe local default, never a real cloud client.
    for var in ("DATABASE_BACKEND", "FIRESTORE_DATABASE", "BIGQUERY_DATASET", "GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"):
        monkeypatch.delenv(var, raising=False)
    assert isinstance(build_database_from_env(), InMemoryDatabaseManager)
