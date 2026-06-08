"""Contract tests for pricing + LlmUsageManager (in-memory, real, no mocks)."""

from datetime import datetime, timezone

from agentic_core.database import LlmUsageManager
from agentic_core.models import LlmUsageRecord
from agentic_core.pricing import estimate_cost_usd


def test_estimate_cost_flash_lite():
    # 1M in + 1M out at $0.10 / $0.40 = $0.50
    assert estimate_cost_usd("gemini-2.5-flash-lite", 1_000_000, 1_000_000) == 0.50


def test_estimate_cost_unknown_model_falls_back_nonzero():
    assert estimate_cost_usd("some-future-model", 1_000_000, 0) == 0.10


def _record(rid: str) -> LlmUsageRecord:
    return LlmUsageRecord(
        request_id=rid,
        app_name="assistant",
        user_id="alice@example.com",
        session_id="s1",
        model_id="gemini-2.5-flash-lite",
        prompt_tokens=120,
        output_tokens=30,
        total_tokens=150,
        est_cost_usd=estimate_cost_usd("gemini-2.5-flash-lite", 120, 30),
        timestamp=datetime.now(timezone.utc),
    )


def test_record_and_list_roundtrip(database, run):
    mgr = LlmUsageManager(database, table="llm_usage")
    run(mgr.record(_record("r1")))
    run(mgr.record(_record("r2")))
    rows = run(mgr.list())
    assert {r.request_id for r in rows} == {"r1", "r2"}
    assert rows[0].user_id == "alice@example.com"
    assert rows[0].total_tokens == 150
    assert rows[0].est_cost_usd > 0
