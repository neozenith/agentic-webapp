"""Recording an extraction is gated by ASSET VISIBILITY — you may record against an asset
you can see, not one you can't. Real app + TestClient, identity via the IAP header, no mocks."""

from fastapi.testclient import TestClient

OWNER = {"X-Goog-Authenticated-User-Email": "otto.operator@example.com"}
OTHER = {"X-Goog-Authenticated-User-Email": "vera.viewer@example.com"}


def _upload(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/api/assets", files={"file": ("receipt.png", b"bytes", "image/png")}, headers=headers)
    assert resp.status_code == 201
    return str(resp.json()["asset_id"])


def test_record_extraction_for_a_visible_asset(client: TestClient) -> None:
    asset_id = _upload(client, OWNER)
    resp = client.post(
        "/api/extractions",
        json={"asset_id": asset_id, "doc_type": "fuel_receipt", "fields": {"total": "82.50"}, "model_id": "gemini"},
        headers=OWNER,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["asset_id"] == asset_id
    assert body["doc_type"] == "fuel_receipt"
    assert body["fields"] == {"total": "82.50"}
    assert body["model_id"] == "gemini"
    assert body["user_id"]  # server-authoritative pseudonymous id, not client-supplied


def test_record_denied_for_an_invisible_asset(client: TestClient) -> None:
    asset_id = _upload(client, OWNER)  # owned by Otto, not shared with Vera
    resp = client.post("/api/extractions", json={"asset_id": asset_id, "doc_type": "x"}, headers=OTHER)
    assert resp.status_code == 404  # don't leak existence to someone who can't see it


def test_record_unknown_asset_is_404(client: TestClient) -> None:
    resp = client.post("/api/extractions", json={"asset_id": "does-not-exist", "doc_type": "x"}, headers=OWNER)
    assert resp.status_code == 404
