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

IAP_USER_HEADER = "x-goog-authenticated-user-email"


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


def require_area(area: str) -> Callable[[Request], Awaitable[None]]:
    """A dependency that allows the request only if the caller's roles grant `area`."""

    async def _enforce(request: Request) -> None:
        if area not in rbac.permissions_for(current_roles(request)):
            raise HTTPException(status_code=403, detail=f"forbidden: '{area}' requires a role you don't have")

    return _enforce
