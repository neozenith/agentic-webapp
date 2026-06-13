"""Request identity + RBAC enforcement.

`iap_email` reads the caller from the IAP header (ADR-0004; simulated in non-prod). The
`require_area` dependency 403s a request whose roles don't grant the area — the
server-side source of truth that backs the SPA's gating. Wired onto sensitive routers in
main.py (admin, analytics)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request

from .. import rbac
from ..config import get_settings
from ..identity import mask_user_id

IAP_USER_HEADER = "x-goog-authenticated-user-email"
# Internal-only: the agent sidecar (no IAP email) passes the chat user's pseudonymous id
# so asset visibility is scoped to that user. Same-pod localhost call; never an admin.
INTERNAL_VIEWER_HEADER = "x-viewer-user-id"


def iap_email(request: Request) -> str | None:
    """The caller's IAP email, or None. In prod IAP sets/sanitises the header; in non-prod
    a client may set it to simulate users when trust_forwarded_user is on (ADR-0004)."""
    if not get_settings().trust_forwarded_user:
        return None
    raw = request.headers.get(IAP_USER_HEADER)
    if not raw:
        return None
    return raw.split(":", 1)[-1]  # strip "accounts.google.com:" prefix


def current_roles(request: Request) -> list[str]:
    s = get_settings()
    return rbac.roles_for(iap_email(request), environment=s.environment, user_roles=s.rbac_user_roles)


def viewer(request: Request) -> tuple[str | None, bool]:
    """(viewer_user_id, is_admin) for asset visibility. From the IAP email (pseudonymised)
    in the normal path; from the trusted internal header for the agent's on-behalf calls
    (never admin); (None, False) when there's no identity."""
    email = iap_email(request)
    if email:
        return mask_user_id(email), "admin" in current_roles(request)
    return request.headers.get(INTERNAL_VIEWER_HEADER) or None, False


def require_area(area: str) -> Callable[[Request], Awaitable[None]]:
    """A dependency that allows the request only if the caller's roles grant `area`."""

    async def _enforce(request: Request) -> None:
        if area not in rbac.permissions_for(current_roles(request)):
            raise HTTPException(status_code=403, detail=f"forbidden: '{area}' requires a role you don't have")

    return _enforce
