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


def test_usage_summary_and_records(admin_client, run):
    manager = LlmUsageManager(InMemoryDatabaseManager(), table="llm_usage")
    run(manager.record(_record("r1", "alice@example.com", 100)))
    run(manager.record(_record("r2", "bob@example.com", 200)))
    admin_client.app.dependency_overrides[deps.get_llm_usage_manager] = lambda: manager

    summary = admin_client.get("/api/admin/usage")
    assert summary.status_code == 200
    body = summary.json()
    assert body["totals"]["calls"] == 2
    assert body["by_model"]["gemini-2.5-flash-lite"]["calls"] == 2
    assert body["by_user"]["alice@example.com"]["total_tokens"] == 150

    records = admin_client.get("/api/admin/usage/records?limit=10")
    assert records.status_code == 200
    assert {r["request_id"] for r in records.json()} == {"r1", "r2"}


def _record_in(rid: str, user: str, session: str, tokens: int) -> LlmUsageRecord:
    return _record(rid, user, tokens).model_copy(update={"session_id": session})


def test_users_rollup_and_user_sessions_drilldown(admin_client, run):
    manager = LlmUsageManager(InMemoryDatabaseManager(), table="llm_usage")
    # alice: two sessions; bob: one.
    run(manager.record(_record_in("r1", "alice@example.com", "s1", 100)))
    run(manager.record(_record_in("r2", "alice@example.com", "s1", 100)))
    run(manager.record(_record_in("r3", "alice@example.com", "s2", 100)))
    run(manager.record(_record_in("r4", "bob@example.com", "s9", 100)))
    admin_client.app.dependency_overrides[deps.get_llm_usage_manager] = lambda: manager

    users = admin_client.get("/api/admin/users")
    assert users.status_code == 200
    by_user = {u["user_id"]: u for u in users.json()}
    assert by_user["alice@example.com"]["sessions"] == 2
    assert by_user["alice@example.com"]["calls"] == 3
    assert by_user["bob@example.com"]["sessions"] == 1

    sessions = admin_client.get("/api/admin/users/alice@example.com/sessions")
    assert sessions.status_code == 200
    by_session = {s["session_id"]: s for s in sessions.json()}
    assert set(by_session) == {"s1", "s2"}
    assert by_session["s1"]["calls"] == 2
    assert "s9" not in by_session  # bob's session must not leak into alice's drilldown
