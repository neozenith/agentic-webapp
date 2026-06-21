"""Pure-builder tests for the observability module. Real dict fixtures, no BigQuery."""

from datetime import datetime, timedelta

from dbt_service.config import Settings
from dbt_service.observability import build_gantt, build_invocations

_T0 = datetime(2026, 6, 20, 10, 0, 0)


def _ts(seconds: float) -> datetime:
    return _T0 + timedelta(seconds=seconds)


def _run_result(
    invocation_id: str,
    thread_id: str,
    name: str,
    *,
    start: float | None,
    end: float,
    status: str = "success",
    execution_time: float = 1.0,
) -> dict[str, object]:
    return {
        "invocation_id": invocation_id,
        "thread_id": thread_id,
        "unique_id": f"model.p.{name}",
        "name": name,
        "resource_type": "model",
        "status": status,
        "execute_started_at": _ts(start) if start is not None else None,
        "execute_completed_at": _ts(end),
        "execution_time": execution_time,
        "created_at": _ts(start or 0),
    }


def test_build_invocations_aggregates() -> None:
    invocations = [
        {
            "invocation_id": "inv-1",
            "command": "build",
            "run_started_at": _ts(0),
            "run_completed_at": _ts(10),
            "target_name": "dev",
            "dbt_version": "1.11.11",
            "created_at": _ts(0),
        }
    ]
    run_results = [
        _run_result("inv-1", "Thread-1", "a", start=0, end=4, execution_time=4.0),
        _run_result("inv-1", "Thread-2", "b", start=2, end=10, execution_time=8.0),
    ]
    out = build_invocations(invocations, run_results)
    assert len(out) == 1
    row = out[0]
    assert row["invocation_id"] == "inv-1"
    assert row["n_nodes"] == 2
    assert row["wall_secs"] == 10.0  # max(end=10) - min(start=0)
    assert row["has_failures"] is False
    assert row["run_started_at"] == "2026-06-20T10:00:00"
    assert row["run_completed_at"] == "2026-06-20T10:00:10"


def test_build_invocations_null_run_times() -> None:
    invocations = [
        {
            "invocation_id": "inv-x",
            "command": "run",
            "run_started_at": None,
            "run_completed_at": None,
            "target_name": "prod",
            "dbt_version": "1.11.11",
            "created_at": _ts(0),
        }
    ]
    out = build_invocations(invocations, [])
    assert out[0]["run_started_at"] is None
    assert out[0]["n_nodes"] == 0
    assert out[0]["wall_secs"] == 0.0
    assert out[0]["has_failures"] is False


def test_build_invocations_detects_failures() -> None:
    invocations = [
        {
            "invocation_id": "inv-1",
            "command": "build",
            "run_started_at": _ts(0),
            "run_completed_at": _ts(3),
            "target_name": "dev",
            "dbt_version": "1.11.11",
            "created_at": _ts(0),
        }
    ]
    run_results = [
        _run_result("inv-1", "Thread-1", "ok", start=0, end=1, status="success"),
        _run_result("inv-1", "Thread-1", "bad", start=1, end=3, status="error"),
    ]
    assert build_invocations(invocations, run_results)[0]["has_failures"] is True

    run_results_fail = [_run_result("inv-1", "Thread-1", "bad", start=0, end=1, status="fail")]
    assert build_invocations(invocations, run_results_fail)[0]["has_failures"] is True


def test_build_invocations_filters_null_started() -> None:
    invocations = [
        {
            "invocation_id": "inv-1",
            "command": "build",
            "run_started_at": _ts(0),
            "run_completed_at": _ts(5),
            "target_name": "dev",
            "dbt_version": "1.11.11",
            "created_at": _ts(0),
        }
    ]
    run_results = [
        _run_result("inv-1", "Thread-1", "a", start=0, end=5),
        _run_result("inv-1", "Thread-2", "skipped", start=None, end=5, status="error"),
    ]
    out = build_invocations(invocations, run_results)
    # The NULL-started skipped node is dropped: it neither counts nor flags failure.
    assert out[0]["n_nodes"] == 1
    assert out[0]["has_failures"] is False


def test_build_invocations_sorted_recent_first() -> None:
    invocations = [
        {
            "invocation_id": "old",
            "command": "run",
            "run_started_at": _ts(0),
            "run_completed_at": _ts(1),
            "target_name": "dev",
            "dbt_version": "1.11.11",
            "created_at": _ts(0),
        },
        {
            "invocation_id": "new",
            "command": "run",
            "run_started_at": _ts(100),
            "run_completed_at": _ts(101),
            "target_name": "dev",
            "dbt_version": "1.11.11",
            "created_at": _ts(100),
        },
    ]
    out = build_invocations(invocations, [])
    assert [r["invocation_id"] for r in out] == ["new", "old"]


def test_build_gantt_offsets_and_thread_sort() -> None:
    run_results = [
        _run_result("inv-1", "Thread-10", "late", start=8, end=12, execution_time=4.0),
        _run_result("inv-1", "Thread-2", "early", start=3, end=7, execution_time=4.0),
        _run_result("inv-1", "Thread-1", "first", start=0, end=3, execution_time=3.0),
    ]
    gantt = build_gantt("inv-1", run_results)
    assert gantt["invocation_id"] == "inv-1"
    assert gantt["wall_secs"] == 12.0
    # Natural sort: Thread-2 before Thread-10.
    assert gantt["threads"] == ["Thread-1", "Thread-2", "Thread-10"]
    # Nodes ordered by start_offset, computed relative to the earliest start.
    nodes = gantt["nodes"]
    assert [n["start_offset_secs"] for n in nodes] == [0.0, 3.0, 8.0]
    assert [n["name"] for n in nodes] == ["first", "early", "late"]
    assert nodes[0]["duration_secs"] == 3.0
    assert nodes[0]["node_id"] == "model.p.first"


def test_build_gantt_filters_null_started() -> None:
    run_results = [
        _run_result("inv-1", "Thread-1", "ran", start=0, end=5),
        _run_result("inv-1", "Thread-2", "skipped", start=None, end=5),
    ]
    gantt = build_gantt("inv-1", run_results)
    assert len(gantt["nodes"]) == 1
    assert gantt["threads"] == ["Thread-1"]


def test_build_gantt_empty() -> None:
    gantt = build_gantt("inv-empty", [])
    assert gantt == {"invocation_id": "inv-empty", "wall_secs": 0.0, "threads": [], "nodes": []}


def test_settings_elementary_dataset_default() -> None:
    settings = Settings(bigquery_dataset="agentic_webapp")
    assert settings.elementary_dataset == "agentic_webapp_elementary"


def test_settings_elementary_dataset_explicit() -> None:
    settings = Settings(bigquery_dataset="agentic_webapp", elementary_dataset="custom_obs")
    assert settings.elementary_dataset == "custom_obs"
