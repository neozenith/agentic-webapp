"""Analytics API tests — seed real extractions via AnalyticsManager (in-memory), inject
through dependency_overrides, hit the endpoints. No mocks."""

from datetime import datetime, timezone

from agentic_core.database import AnalyticsManager, InMemoryDatabaseManager
from agentic_core.models import ExtractionRecord

from agentic_webapp.api import deps


def _extraction(eid: str, doc_type: str, **fields: object) -> ExtractionRecord:
    return ExtractionRecord(
        extraction_id=eid,
        asset_id="a1",
        doc_type=doc_type,
        user_id="alice@example.com",
        session_id="s1",
        fields=fields,
        model_id="gemini-2.5-flash-lite",
        created_at=datetime.now(timezone.utc),
    )


def test_extractions_list_and_semantic_summary(client, run):
    manager = AnalyticsManager(InMemoryDatabaseManager())
    run(manager.record_extraction(_extraction("e1", "fuel_receipt", vendor="Shell", total="82.50")))
    run(manager.record_extraction(_extraction("e2", "fuel_receipt", vendor="BP", litres="45.2")))
    run(manager.record_extraction(_extraction("e3", "odometer", reading="123456")))
    client.app.dependency_overrides[deps.get_analytics_manager] = lambda: manager

    rows = client.get("/api/analytics/extractions")
    assert rows.status_code == 200
    assert {r["extraction_id"] for r in rows.json()} == {"e1", "e2", "e3"}

    summary = client.get("/api/analytics/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 3
    by_doc = {d["doc_type"]: d for d in body["by_doc_type"]}
    assert by_doc["fuel_receipt"]["count"] == 2
    # The semantic layer = the union of field keys discovered for the doc_type.
    assert set(by_doc["fuel_receipt"]["fields"]) == {"vendor", "total", "litres"}
    assert by_doc["odometer"]["fields"] == ["reading"]
