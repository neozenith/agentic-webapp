"""Folder create/list/share + the cascade: a file in a shared folder becomes visible to the
sharee. Plus asset move. Real in-memory managers (no mocks), identity via the IAP header."""

NINA = {"X-Goog-Authenticated-User-Email": "nina.analyst@example.com"}
VERA = {"X-Goog-Authenticated-User-Email": "vera.viewer@example.com"}
ADA = {"X-Goog-Authenticated-User-Email": "ada.admin@example.com"}


def _upload(client, headers, *, folder_id=None) -> str:
    data = {"folder_id": folder_id} if folder_id is not None else None
    r = client.post("/api/assets", files={"file": ("n.txt", b"hi", "text/plain")}, data=data, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def _asset_ids(client, headers) -> set[str]:
    return {a["asset_id"] for a in client.get("/api/assets", headers=headers).json()}


def _folder_ids(client, headers) -> set[str]:
    return {f["folder_id"] for f in client.get("/api/folders", headers=headers).json()}


def test_folder_create_list_and_owner_scoping(client):
    r = client.post("/api/folders", json={"name": "Reports"}, headers=NINA)
    assert r.status_code == 201, r.text
    fid = r.json()["folder_id"]
    assert r.json()["owner_id"]
    # owner sees it; another user does not; admin sees all
    assert fid in _folder_ids(client, NINA)
    assert fid not in _folder_ids(client, VERA)
    assert fid in _folder_ids(client, ADA)


def test_file_in_shared_folder_cascades_to_sharee(client):
    fid = client.post("/api/folders", json={"name": "Shared"}, headers=NINA).json()["folder_id"]
    aid = _upload(client, NINA, folder_id=fid)

    # vera can't see the file or the folder yet
    assert aid not in _asset_ids(client, VERA)
    assert fid not in _folder_ids(client, VERA)
    assert client.get(f"/api/assets/{aid}/content", headers=VERA).status_code == 404

    # nina shares the folder with vera -> the folder AND the contained file become visible
    share = client.post(
        f"/api/folders/{fid}/share", json={"add_user_emails": ["vera.viewer@example.com"]}, headers=NINA
    )
    assert share.status_code == 200
    assert fid in _folder_ids(client, VERA)
    assert aid in _asset_ids(client, VERA)
    assert client.get(f"/api/assets/{aid}/content", headers=VERA).status_code == 200


def test_only_owner_or_admin_may_share_or_delete_folder(client):
    fid = client.post("/api/folders", json={"name": "Locked"}, headers=NINA).json()["folder_id"]
    assert client.post(f"/api/folders/{fid}/share", json={"add_user_emails": ["x@y.com"]}, headers=VERA).status_code == 403
    assert client.delete(f"/api/folders/{fid}", headers=VERA).status_code == 403
    # admin may delete anyone's folder
    assert client.delete(f"/api/folders/{fid}", headers=ADA).status_code == 204
    assert fid not in _folder_ids(client, NINA)


def test_asset_move(client):
    fid = client.post("/api/folders", json={"name": "Dest"}, headers=NINA).json()["folder_id"]
    aid = _upload(client, NINA)
    assert client.get(f"/api/assets/{aid}", headers=NINA).json()["folder_id"] is None

    moved = client.post(f"/api/assets/{aid}/move", json={"folder_id": fid}, headers=NINA)
    assert moved.status_code == 200
    assert moved.json()["folder_id"] == fid

    # a non-owner may not move; a missing asset is 404
    assert client.post(f"/api/assets/{aid}/move", json={"folder_id": None}, headers=VERA).status_code == 403
    assert client.post("/api/assets/nope/move", json={"folder_id": None}, headers=NINA).status_code == 404
