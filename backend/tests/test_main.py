"""App factory: the SPA mount vs. status-page fallback, lifespan, and /api/me shape.
Uses a real TestClient against a real (in-memory) app — no mocks. The TestClient
context manager triggers the lifespan handler."""

from fastapi.testclient import TestClient

from agentic_webapp import config
from agentic_webapp.main import create_app


def _app(monkeypatch, frontend_dist) -> TestClient:
    monkeypatch.setenv("FRONTEND_DIST", str(frontend_dist))
    config.get_settings.cache_clear()
    return TestClient(create_app())


def test_status_page_when_spa_not_built(tmp_path, monkeypatch):
    with _app(monkeypatch, tmp_path / "absent") as c:  # triggers lifespan
        r = c.get("/")
        assert r.status_code == 200
        assert "agentic-webapp" in r.text


def test_spa_served_when_built(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>SPA</title>", encoding="utf-8")
    with _app(monkeypatch, dist) as c:
        r = c.get("/chat/some-session-id")  # client-side route -> index fallback
        assert r.status_code == 200
        assert "SPA" in r.text


def test_api_me_returns_identity_shape(tmp_path, monkeypatch):
    with _app(monkeypatch, tmp_path / "absent") as c:
        body = c.get("/api/me").json()
        assert set(body) >= {"email", "user_id", "environment"}
        assert body["email"] is None  # no IAP header supplied
        assert body["user_id"] is None


def test_api_me_masks_user_from_iap_header(tmp_path, monkeypatch):
    with _app(monkeypatch, tmp_path / "absent") as c:
        body = c.get("/api/me", headers={"x-goog-authenticated-user-email": "accounts.google.com:a@b.com"}).json()
        assert body["email"] == "a@b.com"
        assert body["user_id"] and body["user_id"] != "a@b.com"  # pseudonymous
