"""RBAC: role/permission resolution + server-side enforcement. Real app + TestClient,
identity via the IAP header (no mocks)."""

from agentic_webapp import rbac

ADMIN = {"X-Goog-Authenticated-User-Email": "ada.admin@example.com"}
VIEWER = {"X-Goog-Authenticated-User-Email": "vera.viewer@example.com"}


def test_roles_for_personas_config_and_default():
    # non-prod test persona
    assert rbac.roles_for("nina.analyst@example.com", environment="dev") == ["analyst"]
    # explicit mapping (prod/config) wins, even in prod
    assert rbac.roles_for("boss@corp.com", environment="prod", user_roles={"boss@corp.com": ["admin"]}) == ["admin"]
    # signed-in but unmapped -> default role
    assert rbac.roles_for("stranger@corp.com", environment="prod") == [rbac.DEFAULT_ROLE]
    # personas don't apply in prod
    assert rbac.roles_for("nina.analyst@example.com", environment="prod") == [rbac.DEFAULT_ROLE]
    # no identity -> no roles
    assert rbac.roles_for(None, environment="dev") == []


def test_permissions_union_and_admin_superset():
    assert "admin" in rbac.permissions_for(["admin"])
    assert "admin" not in rbac.permissions_for(["analyst"])
    assert set(rbac.permissions_for(["admin"])) == set(rbac.AREAS)
    assert rbac.permissions_for([]) == []


def test_personas_hidden_in_prod():
    assert rbac.personas("dev")  # non-empty
    assert rbac.personas("prod") == []


def test_me_returns_roles_and_permissions(client):
    me = client.get("/api/me", headers=ADMIN)
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "ada.admin@example.com"
    assert body["roles"] == ["admin"]
    assert "admin" in body["permissions"]


def test_personas_endpoint_lists_test_users(client):
    resp = client.get("/api/auth/personas")
    assert resp.status_code == 200
    emails = {p["email"] for p in resp.json()}
    assert "ada.admin@example.com" in emails


def test_admin_area_enforced_server_side(client):
    # No identity -> 403 (locked); admin persona -> allowed; viewer -> 403.
    assert client.get("/api/admin/usage").status_code == 403
    assert client.get("/api/admin/usage", headers=ADMIN).status_code == 200
    assert client.get("/api/admin/usage", headers=VIEWER).status_code == 403


def test_analytics_area_enforced_for_viewer(client):
    assert client.get("/api/analytics/summary", headers=ADMIN).status_code == 200
    assert client.get("/api/analytics/summary", headers=VIEWER).status_code == 403
