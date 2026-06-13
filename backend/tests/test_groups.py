"""Group CRUD (admin-only) + group-based asset sharing: a member of a group an asset is
shared with inherits access. Real in-memory managers, identity via the IAP header."""

NINA = {"X-Goog-Authenticated-User-Email": "nina.analyst@example.com"}
VERA = {"X-Goog-Authenticated-User-Email": "vera.viewer@example.com"}
OTTO = {"X-Goog-Authenticated-User-Email": "otto.operator@example.com"}


def _upload(client, headers) -> str:
    r = client.post("/api/assets", files={"file": ("n.txt", b"hi", "text/plain")}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def _asset_ids(client, headers) -> set[str]:
    return {a["asset_id"] for a in client.get("/api/assets", headers=headers).json()}


def test_group_crud_admin_only(admin_client, client):
    # a non-admin can't reach the admin group routes
    assert client.get("/api/admin/groups", headers=VERA).status_code == 403

    created = admin_client.post(
        "/api/admin/groups", json={"name": "Team A", "member_emails": ["vera.viewer@example.com"]}
    )
    assert created.status_code == 201, created.text
    gid = created.json()["group_id"]
    assert len(created.json()["member_ids"]) == 1

    listed = admin_client.get("/api/admin/groups")
    assert gid in {g["group_id"] for g in listed.json()}

    # patch: rename + add a member
    patched = admin_client.patch(
        f"/api/admin/groups/{gid}", json={"name": "Team B", "add_member_emails": ["otto.operator@example.com"]}
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Team B"
    assert len(patched.json()["member_ids"]) == 2

    assert admin_client.delete(f"/api/admin/groups/{gid}").status_code == 204
    assert gid not in {g["group_id"] for g in admin_client.get("/api/admin/groups").json()}


def test_group_shared_asset_visible_to_members_only(admin_client):
    gid = admin_client.post(
        "/api/admin/groups", json={"name": "Sharers", "member_emails": ["vera.viewer@example.com"]}
    ).json()["group_id"]

    aid = _upload(admin_client, NINA)
    share = admin_client.post(f"/api/assets/{aid}/share", json={"add_group_ids": [gid]}, headers=NINA)
    assert share.status_code == 200
    assert gid in share.json()["shared_group_ids"]

    # vera (a member) sees it; otto (not a member) does not
    assert aid in _asset_ids(admin_client, VERA)
    assert aid not in _asset_ids(admin_client, OTTO)
