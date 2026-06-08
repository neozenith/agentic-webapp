"""API tests through FastAPI's TestClient with in-memory backends injected via
dependency_overrides — real request/response cycle, no mocks."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "agentic-webapp" in r.text


def test_asset_lifecycle(client):
    r = client.post("/api/assets", files={"file": ("hi.txt", b"hello", "text/plain")})
    assert r.status_code == 201, r.text
    asset_id = r.json()["asset_id"]

    assert client.get(f"/api/assets/{asset_id}").status_code == 200
    assert any(a["asset_id"] == asset_id for a in client.get("/api/assets").json())

    url = client.get(f"/api/assets/{asset_id}/url").json()
    assert url["url"] and url["expires_in_seconds"] == 60

    content = client.get(f"/api/assets/{asset_id}/content")
    assert content.status_code == 200
    assert content.content == b"hello"

    assert client.delete(f"/api/assets/{asset_id}").status_code == 204
    assert client.get(f"/api/assets/{asset_id}").status_code == 404


def test_combine_downloads_to_temp_and_concatenates(client):
    a = client.post("/api/assets", files={"file": ("a.txt", b"AAA", "text/plain")}).json()["asset_id"]
    b = client.post("/api/assets", files={"file": ("b.txt", b"BBB", "text/plain")}).json()["asset_id"]

    r = client.post("/api/assets/combine", json={"asset_ids": [a, b], "filename": "c.bin"})
    assert r.status_code == 201, r.text
    combined_id = r.json()["asset_id"]
    assert r.json()["tags"]["combined_from"] == f"{a},{b}"

    assert client.get(f"/api/assets/{combined_id}/content").content == b"AAABBB"


def test_combine_requires_two_assets(client):
    assert client.post("/api/assets/combine", json={"asset_ids": ["only-one"]}).status_code == 400


def test_get_missing_asset_404(client):
    assert client.get("/api/assets/does-not-exist").status_code == 404
