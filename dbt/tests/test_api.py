"""FastAPI route tests via TestClient.

GET routes hit the real project files; POST routes use a fake runner injected
through dependency_overrides (a real object, not a mock/patch) so we exercise
the handlers without a live BigQuery warehouse.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dbt_service.app import create_app, get_observability, get_runner, get_settings
from dbt_service.config import Settings
from dbt_service.observability import build_gantt, build_invocations
from dbt_service.schemas import DbtRunResult

EXPECTED_MODELS = {
    "stg_fuel_receipts",
    "stg_maintenance",
    "fct_fuel_purchases",
    "fct_maintenance",
    "agg_vehicle_costs_yearly",
    "stg_consulting__engagements",
    "stg_consulting__time_entries",
    "stg_consulting__financials",
    "stg_consulting__deliverables",
    "stg_consulting__invoices",
    "dim_engagements",
    "fct_time_entries",
    "fct_engagement_financials",
    "fct_deliverables",
    "fct_invoices",
}


class FakeRunner:
    """Stand-in DbtRunner whose `run` returns a canned result (no subprocess)."""

    def run(self, command: str, select: str | None = None) -> DbtRunResult:
        return DbtRunResult(
            command=command,
            success=True,
            return_code=0,
            stdout=f"ran {command} select={select}",
            stderr="",
            nodes=[{"name": "fct_fuel_purchases", "status": "success", "execution_time": 0.5, "message": None}],
            elapsed_seconds=0.5,
        )


@pytest.fixture
def client(project_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(dbt_project_dir=project_dir, dbt_target="test")
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_project(client: TestClient) -> None:
    resp = client.get("/project")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "agentic_webapp_dbt"
    assert body["profile"] == "agentic_webapp_dbt"
    assert body["version"] == "1.0.0"
    assert body["target"] == "test"
    assert body["model_count"] == len(EXPECTED_MODELS)
    assert isinstance(body["dbt_cli_available"], bool)
    assert {m["name"] for m in body["models"]} == EXPECTED_MODELS
    one = next(m for m in body["models"] if m["name"] == "fct_fuel_purchases")
    assert one["db_schema"] == "agentic_webapp"
    assert one["materialized"] == "table"
    assert one["depends_on"] == ["stg_fuel_receipts"]


def test_models(client: TestClient) -> None:
    resp = client.get("/models")
    assert resp.status_code == 200
    body = resp.json()
    assert {m["name"] for m in body} == EXPECTED_MODELS
    for model in body:
        assert set(model) == {
            "name",
            "resource_type",
            "db_schema",
            "materialized",
            "description",
            "depends_on",
            "tags",
            "path",
        }


@pytest.mark.parametrize("command", ["run", "test", "build", "compile"])
def test_command_endpoints(client: TestClient, command: str) -> None:
    client.app.dependency_overrides[get_runner] = FakeRunner
    resp = client.post(f"/{command}", json={"select": "fct_fuel_purchases"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["command"] == command
    assert body["success"] is True
    assert body["return_code"] == 0
    assert "fct_fuel_purchases" in body["stdout"]
    assert body["nodes"][0]["name"] == "fct_fuel_purchases"
    assert body["elapsed_seconds"] == 0.5


def test_command_endpoint_null_select(client: TestClient) -> None:
    client.app.dependency_overrides[get_runner] = FakeRunner
    resp = client.post("/run", json={})
    assert resp.status_code == 200
    assert resp.json()["command"] == "run"


# --- Observability routes -------------------------------------------------
# Real fixture rows (datetimes as the BigQuery client returns them) fed to the
# real pure builders through an injected fake service — no live BigQuery.

_T0 = datetime(2026, 6, 20, 10, 0, 0)


def _ts(seconds: float) -> datetime:
    return _T0 + timedelta(seconds=seconds)


INVOCATION_ROWS = [
    {
        "invocation_id": "inv-1",
        "command": "build",
        "run_started_at": _ts(0),
        "run_completed_at": _ts(12),
        "target_name": "dev",
        "dbt_version": "1.11.11",
        "created_at": _ts(0),
    }
]

RUN_RESULT_ROWS = [
    {
        "invocation_id": "inv-1",
        "thread_id": "Thread-1",
        "unique_id": "model.p.a",
        "name": "a",
        "resource_type": "model",
        "status": "success",
        "execute_started_at": _ts(0),
        "execute_completed_at": _ts(5),
        "execution_time": 5.0,
        "created_at": _ts(0),
    },
    {
        "invocation_id": "inv-1",
        "thread_id": "Thread-2",
        "unique_id": "model.p.b",
        "name": "b",
        "resource_type": "model",
        "status": "error",
        "execute_started_at": _ts(5),
        "execute_completed_at": _ts(12),
        "execution_time": 7.0,
        "created_at": _ts(5),
    },
]


class FakeObservability:
    """Stand-in ObservabilityService driving the REAL pure builders off fixtures."""

    def invocations(self, days: int) -> list[dict[str, object]]:
        return build_invocations(INVOCATION_ROWS, RUN_RESULT_ROWS)

    def gantt(self, invocation_id: str) -> dict[str, object]:
        return build_gantt(invocation_id, RUN_RESULT_ROWS)


def test_observability_invocations(client: TestClient) -> None:
    client.app.dependency_overrides[get_observability] = FakeObservability
    resp = client.get("/observability/invocations", params={"days": 30})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    row = body[0]
    assert row["invocation_id"] == "inv-1"
    assert row["command"] == "build"
    assert row["target_name"] == "dev"
    assert row["n_nodes"] == 2
    assert row["wall_secs"] == 12.0
    assert row["has_failures"] is True
    assert row["run_started_at"] == "2026-06-20T10:00:00"


def test_observability_gantt(client: TestClient) -> None:
    client.app.dependency_overrides[get_observability] = FakeObservability
    resp = client.get("/observability/invocations/inv-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["invocation_id"] == "inv-1"
    assert body["wall_secs"] == 12.0
    assert body["threads"] == ["Thread-1", "Thread-2"]
    assert [n["start_offset_secs"] for n in body["nodes"]] == [0.0, 5.0]
    assert {n["node_id"] for n in body["nodes"]} == {"model.p.a", "model.p.b"}
