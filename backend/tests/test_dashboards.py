"""Dashboard route tests — CRUD + the /render data→pixels transform + RBAC. Real in-memory
analytics store seeded with the fuel demo; no mocks."""

from __future__ import annotations

import asyncio

import pytest
from agentic_core.database import DashboardManager, InMemoryDatabaseManager, SemanticManager, seed_fuel_domain
from agentic_webapp.api import deps
from agentic_webapp.main import create_app
from fastapi.testclient import TestClient

ADMIN = "ada.admin@example.com"
VIEWER = "vera.viewer@example.com"


@pytest.fixture
def analytics_db() -> InMemoryDatabaseManager:
    db = InMemoryDatabaseManager()
    asyncio.run(seed_fuel_domain(db=db))
    return db


@pytest.fixture
def app(analytics_db: InMemoryDatabaseManager):
    app = create_app()
    app.dependency_overrides[deps.get_semantic_manager] = lambda: SemanticManager(analytics_db)
    app.dependency_overrides[deps.get_dashboard_manager] = lambda: DashboardManager(analytics_db)
    return app


@pytest.fixture
def admin(app) -> TestClient:
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": ADMIN})
    return c


def test_list_and_get(admin: TestClient) -> None:
    ids = {d["dashboard_id"] for d in admin.get("/api/dashboards").json()}
    assert ids == {"fuel-overview", "fuel-tco"}
    assert admin.get("/api/dashboards/fuel-overview").status_code == 200
    assert admin.get("/api/dashboards/nope").status_code == 404


def test_create_update_delete(admin: TestClient) -> None:
    body = {"name": "Custom", "description": "d", "semantic_model_id": "fuel_tracking", "charts": []}
    created = admin.post("/api/dashboards", json=body)
    assert created.status_code == 201
    did = created.json()["dashboard_id"]
    assert admin.put(f"/api/dashboards/{did}", json={**body, "name": "Renamed"}).json()["name"] == "Renamed"
    assert admin.put("/api/dashboards/nope", json=body).status_code == 404
    assert admin.delete(f"/api/dashboards/{did}").status_code == 204


def test_render_builds_plotly_figures_and_kpi(admin: TestClient) -> None:
    render = admin.get("/api/dashboards/fuel-overview/render").json()
    charts = {c["chart_id"]: c for c in render["charts"]}
    # KPI carries a numeric value and no trace
    kpi = charts["kpi-total-spend"]
    assert kpi["chart_type"] == "kpi"
    assert kpi["value"] == pytest.approx(3802.04, rel=1e-3)
    assert kpi["figure"]["data"] == []
    # a line chart carries one Plotly trace bound to the encoded columns
    monthly = charts["monthly-spend"]
    assert monthly["figure"]["data"][0]["type"] == "scatter"
    assert len(monthly["figure"]["data"][0]["x"]) == 24  # 24 months
    assert monthly["error"] is None


def test_render_missing_dashboard_404(admin: TestClient) -> None:
    assert admin.get("/api/dashboards/nope/render").status_code == 404


def test_render_timespine_grain_override(admin: TestClient) -> None:
    """grain re-buckets time-series charts; the monthly line becomes quarterly (4 buckets/yr)."""
    render = admin.get("/api/dashboards/fuel-overview/render", params={"grain": "quarter"}).json()
    monthly = next(c for c in render["charts"] if c["chart_id"] == "monthly-spend")
    assert len(monthly["figure"]["data"][0]["x"]) == 8  # 2 years × 4 quarters


def test_render_timespine_date_range_clamps_kpi(admin: TestClient) -> None:
    """start/end filter every time-aware chart — the total-spend KPI drops to the 2025 slice."""
    full = admin.get("/api/dashboards/fuel-overview/render").json()
    full_kpi = next(c for c in full["charts"] if c["chart_id"] == "kpi-total-spend")["value"]
    clamped = admin.get(
        "/api/dashboards/fuel-overview/render", params={"start": "2025-01-01", "end": "2025-12-31"}
    ).json()
    kpi = next(c for c in clamped["charts"] if c["chart_id"] == "kpi-total-spend")["value"]
    assert 0 < kpi < full_kpi  # a strict subset of the full spend


def test_render_rejects_bad_grain(admin: TestClient) -> None:
    assert admin.get("/api/dashboards/fuel-overview/render", params={"grain": "fortnight"}).status_code == 400


def test_dashboards_readable_by_viewer(app) -> None:
    """dashboards is a read-broad area (viewer + operator), unlike semantic/dbt."""
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": VIEWER})
    assert c.get("/api/dashboards").status_code == 200
