"""Admin usage API tests — seed real records via LlmUsageManager (in-memory),
inject through dependency_overrides, hit the endpoints. No mocks."""

from datetime import datetime, timezone

from agentic_core.database import InMemoryDatabaseManager, LlmUsageManager
from agentic_core.models import LlmUsageRecord

from agentic_webapp.api import deps


def _record(rid: str, user: str, tokens: int) -> LlmUsageRecord:
    return LlmUsageRecord(
        request_id=rid,
        app_name="assistant",
        user_id=user,
        session_id="s1",
        model_id="gemini-2.5-flash-lite",
        prompt_tokens=tokens,
        output_tokens=tokens // 2,
        total_tokens=tokens + tokens // 2,
        est_cost_usd=0.0001,
        timestamp=datetime.now(timezone.utc),
    )


def test_usage_summary_and_records(client, run):
    manager = LlmUsageManager(InMemoryDatabaseManager(), table="llm_usage")
    run(manager.record(_record("r1", "alice@example.com", 100)))
    run(manager.record(_record("r2", "bob@example.com", 200)))
    client.app.dependency_overrides[deps.get_llm_usage_manager] = lambda: manager

    summary = client.get("/api/admin/usage")
    assert summary.status_code == 200
    body = summary.json()
    assert body["totals"]["calls"] == 2
    assert body["by_model"]["gemini-2.5-flash-lite"]["calls"] == 2
    assert body["by_user"]["alice@example.com"]["total_tokens"] == 150

    records = client.get("/api/admin/usage/records?limit=10")
    assert records.status_code == 200
    assert {r["request_id"] for r in records.json()} == {"r1", "r2"}
