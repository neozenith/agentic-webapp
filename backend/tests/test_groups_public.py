"""The read-only top-level group listing: GET /api/groups lets ANY authenticated user
discover groups (group_id + name) so they can share with one, without the admin gate on
/api/admin/groups. Membership is never exposed here. Real in-memory managers, no mocks."""

VERA = {"X-Goog-Authenticated-User-Email": "vera.viewer@example.com"}


def test_public_groups_lists_names_only_for_non_admins(admin_client, client):
    # admin creates a group with a member; client/admin_client share one group manager
    created = admin_client.post(
        "/api/admin/groups", json={"name": "Engineering", "member_emails": ["vera.viewer@example.com"]}
    )
    assert created.status_code == 201, created.text
    gid = created.json()["group_id"]

    # a non-admin (vera) is blocked from the admin route but can read the public listing
    assert client.get("/api/admin/groups", headers=VERA).status_code == 403
    resp = client.get("/api/groups", headers=VERA)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    by_id = {g["group_id"]: g for g in body}
    assert gid in by_id
    assert by_id[gid]["name"] == "Engineering"
    # only group_id + name — no membership leaked through the public route
    for g in body:
        assert set(g.keys()) == {"group_id", "name"}


def test_public_groups_empty_when_none_exist(client):
    assert client.get("/api/groups", headers=VERA).json() == []
