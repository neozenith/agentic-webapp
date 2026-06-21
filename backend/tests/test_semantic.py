"""Semantic-layer route tests — CRUD + query + RBAC, over a seeded in-memory analytics store.
Real implementations, no mocks (project rule)."""

from __future__ import annotations

import asyncio

import pytest
from agentic_core.database import DashboardManager, InMemoryDatabaseManager, SemanticManager, seed_fuel_domain
from agentic_webapp.api import deps
from agentic_webapp.main import create_app
from fastapi.testclient import TestClient

ADMIN = "ada.admin@example.com"
ANALYST = "nina.analyst@example.com"
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


def test_list_and_get_models(admin: TestClient) -> None:
    models = admin.get("/api/semantic/models").json()
    assert [m["model_id"] for m in models] == ["fuel_tracking"]
    one = admin.get("/api/semantic/models/fuel_tracking")
    assert one.status_code == 200
    assert {e["name"] for e in one.json()["entities"]} == {"fuel_purchases", "maintenance"}
    assert admin.get("/api/semantic/models/nope").status_code == 404


def test_create_update_delete_model(admin: TestClient) -> None:
    body = {"name": "Sales", "description": "demo", "entities": []}
    created = admin.post("/api/semantic/models", json=body)
    assert created.status_code == 201
    mid = created.json()["model_id"]
    assert mid and mid != "fuel_tracking"  # server-minted id

    upd = admin.put(f"/api/semantic/models/{mid}", json={**body, "description": "edited"})
    assert upd.status_code == 200
    assert upd.json()["description"] == "edited"
    assert admin.put("/api/semantic/models/nope", json=body).status_code == 404

    assert admin.delete(f"/api/semantic/models/{mid}").status_code == 204
    assert admin.get(f"/api/semantic/models/{mid}").status_code == 404


def test_query_returns_rows_and_sql(admin: TestClient) -> None:
    q = {
        "model_id": "fuel_tracking",
        "query": {"entity": "fuel_purchases", "measures": ["total_cost"], "dimensions": ["station"]},
    }
    res = admin.post("/api/semantic/query", json=q)
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["station", "total_cost"]
    assert body["row_count"] == 4
    assert "SUM(`total_cost`)" in body["sql"]


def test_query_unknown_model_404_and_bad_query_400(admin: TestClient) -> None:
    assert admin.post("/api/semantic/query", json={"model_id": "nope", "query": {"entity": "x"}}).status_code == 404
    bad = admin.post(
        "/api/semantic/query",
        json={"model_id": "fuel_tracking", "query": {"entity": "nope", "measures": ["total_cost"]}},
    )
    assert bad.status_code == 400
    assert "unknown entity" in bad.json()["detail"]


@pytest.mark.parametrize("persona", [ANALYST])
def test_analyst_may_use_semantic(app, persona: str) -> None:
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": persona})
    assert c.get("/api/semantic/models").status_code == 200


def test_viewer_is_forbidden(app) -> None:
    c = TestClient(app)
    c.headers.update({"X-Goog-Authenticated-User-Email": VIEWER})
    assert c.get("/api/semantic/models").status_code == 403
