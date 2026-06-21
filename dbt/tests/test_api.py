"""FastAPI route tests via TestClient.

GET routes hit the real project files; POST routes use a fake runner injected
through dependency_overrides (a real object, not a mock/patch) so we exercise
the handlers without a live BigQuery warehouse.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dbt_service.app import create_app, get_runner, get_settings
from dbt_service.config import Settings
from dbt_service.schemas import DbtRunResult

EXPECTED_MODELS = {
    "stg_fuel_receipts",
    "stg_maintenance",
    "fct_fuel_purchases",
    "fct_maintenance",
    "agg_vehicle_costs_yearly",
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
