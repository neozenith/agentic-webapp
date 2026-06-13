"""Role-based access control: who can reach which areas of the webapp.

Model:
  - AREAS are the gateable surfaces of the SPA (they match the routes/nav items).
  - ROLE_PERMISSIONS maps a role to the set of areas it may access.
  - A user (IAP email) has roles. In **prod** the mapping is real, supplied via
    Settings.rbac_user_roles (config/env). In **dev/test** a set of test PERSONAS provide
    identities you switch between (via the IAP-email header, ADR-0004) to exercise the
    mappings. A signed-in but unmapped user falls back to DEFAULT_ROLE.

The backend enforces this on sensitive routes (admin/analytics) AND returns the resolved
roles+permissions from /api/me so the SPA can gate nav + pages. Server-side enforcement is
the source of truth; the SPA gating is UX.
"""

from __future__ import annotations

from typing import Any

# Gateable areas — keep in sync with the SPA routes/nav.
AREAS: tuple[str, ...] = ("home", "chat", "sessions", "assets", "analytics", "admin")

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": set(AREAS),  # everything, incl. the Admin panel
    "analyst": {"home", "chat", "sessions", "assets", "analytics"},
    "operator": {"home", "chat", "sessions", "assets"},
    "viewer": {"home", "chat", "sessions"},
}

# Role given to a signed-in user with no explicit mapping.
DEFAULT_ROLE = "viewer"

# Test identities for dev/test. Admin first so the SPA's default persona is fully enabled;
# switch to a lower role to watch areas lock. (Never used in prod.)
PERSONAS: list[dict[str, Any]] = [
    {"email": "ada.admin@example.com", "name": "Ada — Admin", "roles": ["admin"]},
    {"email": "nina.analyst@example.com", "name": "Nina — Analyst", "roles": ["analyst"]},
    {"email": "otto.operator@example.com", "name": "Otto — Operator", "roles": ["operator"]},
    {"email": "vera.viewer@example.com", "name": "Vera — Viewer", "roles": ["viewer"]},
]
_PERSONA_ROLES: dict[str, list[str]] = {p["email"]: p["roles"] for p in PERSONAS}


def roles_for(email: str | None, *, environment: str, user_roles: dict[str, list[str]] | None = None) -> list[str]:
    """Resolve a user's roles. Explicit mapping (prod/config) wins; then non-prod test
    personas; then DEFAULT_ROLE for any other signed-in user; [] for no identity."""
    if not email:
        return []
    key = email.strip().lower()
    if user_roles and key in user_roles:
        return list(user_roles[key])
    if environment != "prod" and key in _PERSONA_ROLES:
        return list(_PERSONA_ROLES[key])
    return [DEFAULT_ROLE]


def permissions_for(roles: list[str]) -> list[str]:
    """The union of areas granted by the given roles, sorted."""
    perms: set[str] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, set())
    return sorted(perms)


def personas(environment: str) -> list[dict[str, Any]]:
    """Test personas to expose to the SPA — only in non-prod."""
    return [] if environment == "prod" else PERSONAS
