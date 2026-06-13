"""Asset ownership + sharing: a caller sees only assets they own or that are shared with
them; admins see all; only the owner/admin may share or delete. Identity via the IAP
header (test personas). Real in-memory AssetService (no mocks)."""

NINA = {"X-Goog-Authenticated-User-Email": "nina.analyst@example.com"}
VERA = {"X-Goog-Authenticated-User-Email": "vera.viewer@example.com"}
ADA = {"X-Goog-Authenticated-User-Email": "ada.admin@example.com"}


def _upload(client, headers) -> str:
    r = client.post("/api/assets", files={"file": ("n.txt", b"hi", "text/plain")}, headers=headers)
    assert r.status_code == 201
    return r.json()["asset_id"]


def _ids(client, headers) -> set[str]:
    return {a["asset_id"] for a in client.get("/api/assets", headers=headers).json()}


def test_owner_only_visibility_then_sharing(client):
    aid = _upload(client, NINA)
    # the uploaded asset is owned (pseudonymous owner_id recorded)
    assert client.get(f"/api/assets/{aid}", headers=NINA).json()["owner_id"]

    # owner sees it; a different user does NOT; admin does
    assert aid in _ids(client, NINA)
    assert aid not in _ids(client, VERA)
    assert aid in _ids(client, ADA)

    # an unauthorised viewer can't even fetch the bytes (404 — don't leak existence)
    assert client.get(f"/api/assets/{aid}/content", headers=VERA).status_code == 404
    assert client.get(f"/api/assets/{aid}/content", headers=NINA).status_code == 200

    # owner shares with vera -> she can now see and fetch it
    share = client.post(
        f"/api/assets/{aid}/share", json={"add_user_emails": ["vera.viewer@example.com"]}, headers=NINA
    )
    assert share.status_code == 200
    assert aid in _ids(client, VERA)
    assert client.get(f"/api/assets/{aid}/content", headers=VERA).status_code == 200


def test_only_owner_or_admin_may_share_or_delete(client):
    aid = _upload(client, NINA)
    # a non-owner, non-admin may not share or delete
    assert (
        client.post(f"/api/assets/{aid}/share", json={"add_user_emails": ["x@y.com"]}, headers=VERA).status_code == 403
    )
    assert client.delete(f"/api/assets/{aid}", headers=VERA).status_code == 403
    # admin may delete anyone's asset
    assert client.delete(f"/api/assets/{aid}", headers=ADA).status_code == 204
    assert aid not in _ids(client, NINA)


def test_agent_internal_viewer_header_scopes_visibility(client):
    """The agent (no IAP email) passes the chat user's id via X-Viewer-User-Id; it should
    see that user's assets but not another user's."""
    aid = _upload(client, NINA)
    owner_id = client.get(f"/api/assets/{aid}", headers=NINA).json()["owner_id"]
    as_owner = {"X-Viewer-User-Id": owner_id}
    as_other = {"X-Viewer-User-Id": "someone-else"}
    assert aid in _ids(client, as_owner)
    assert aid not in _ids(client, as_other)
