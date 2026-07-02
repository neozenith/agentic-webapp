"""dbt route tests — the FilesystemDbtClient parses a REAL on-disk dbt project (written into
tmp_path), proxied through the /api/dbt routes. No mocks; no live BigQuery or dbt run needed."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_webapp.api import deps
from agentic_webapp.main import create_app
from agentic_webapp.services import FilesystemDbtClient
from fastapi.testclient import TestClient

ADMIN = "ada.admin@example.com"
VIEWER = "vera.viewer@example.com"


@pytest.fixture
def dbt_project(tmp_path: Path) -> Path:
    proj = tmp_path / "dbt"
    (proj / "models" / "staging").mkdir(parents=True)
    (proj / "models" / "marts").mkdir(parents=True)
    (proj / "dbt_project.yml").write_text(
        "name: 'demo_dbt'\nprofile: 'demo_dbt'\nversion: '1.2.0'\n", encoding="utf-8"
    )
    (proj / "models" / "staging" / "stg_fuel.sql").write_text(
        "select * from {{ source('raw', 'extractions') }} where doc_type = 'fuel_receipt'", encoding="utf-8"
    )
    (proj / "models" / "marts" / "fct_fuel.sql").write_text(
        "{{ config(materialized='table') }}\nselect * from {{ ref('stg_fuel') }}", encoding="utf-8"
    )
    return proj


@pytest.fixture
def app(dbt_project: Path):
    app = create_app()
    app.dependency_overrides[deps.get_dbt_client] = lambda: FilesystemDbtClient(dbt_project, target="dev")
    return app


@pytest.fixture
def admin(app) -> TestClient:
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": ADMIN})
    return c


def test_project_metadata(admin: TestClient) -> None:
    p = admin.get("/api/dbt/project").json()
    assert p["name"] == "demo_dbt"
    assert p["version"] == "1.2.0"
    assert p["target"] == "dev"
    assert p["model_count"] == 2
    assert isinstance(p["dbt_cli_available"], bool)


def test_models_are_parsed_with_layers_and_deps(admin: TestClient) -> None:
    models = {m["name"]: m for m in admin.get("/api/dbt/models").json()}
    assert set(models) == {"stg_fuel", "fct_fuel"}
    # marts → table, staging → view (dbt defaults, inferred from the layer)
    assert models["fct_fuel"]["materialized"] == "table"
    assert models["stg_fuel"]["materialized"] == "view"
    assert models["fct_fuel"]["db_schema"] == "marts"
    assert models["stg_fuel"]["db_schema"] == "staging"
    # ref()/source() become depends_on edges
    assert models["fct_fuel"]["depends_on"] == ["stg_fuel"]
    assert models["stg_fuel"]["depends_on"] == ["raw.extractions"]


def test_run_returns_a_result_even_without_the_cli(admin: TestClient) -> None:
    r = admin.post("/api/dbt/run", json={"select": "fct_fuel"}).json()
    assert r["command"] == "run"
    assert isinstance(r["success"], bool)  # honest result; CLI may be absent in CI (rc 127)
    assert "return_code" in r and "stdout" in r and "stderr" in r


def test_viewer_is_forbidden(app) -> None:
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": VIEWER})
    assert c.get("/api/dbt/models").status_code == 403


def test_observability_empty_without_elementary(admin: TestClient) -> None:
    """The FilesystemDbtClient has no Elementary metadata — honest empty, not an error."""
    invs = admin.get("/api/dbt/observability/invocations")
    assert invs.status_code == 200
    assert invs.json() == []
    gantt = admin.get("/api/dbt/observability/invocations/anything").json()
    assert gantt["invocation_id"] == "anything"
    assert gantt["nodes"] == [] and gantt["threads"] == []


def test_observability_forbidden_for_viewer(app) -> None:
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": VIEWER})
    assert c.get("/api/dbt/observability/invocations").status_code == 403
