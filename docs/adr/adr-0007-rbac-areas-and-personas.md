# ADR-0007: RBAC — role-gated areas, with test personas in non-prod

**Status:** Accepted

## Context

The webapp needs to lock areas (Admin, Analytics, …) to authorised users. Identity already
comes from the IAP email header (ADR-0004), simulated in non-prod. We need a mapping from
identity → roles → permissible areas, real IAP users in prod and switchable test personas in
dev/test to exercise the mappings.

## Decision

- **Areas** are the gateable SPA surfaces (`home, chat, sessions, assets, analytics, admin`).
  **Roles** grant sets of areas (`rbac.ROLE_PERMISSIONS`). A user has roles.
- **Identity → roles** (`rbac.roles_for`): an explicit mapping wins (prod real users, via
  `Settings.rbac_user_roles` / `RBAC_USER_ROLES` env); else, in non-prod, the test
  **PERSONAS** (email → roles); else `DEFAULT_ROLE` for any other signed-in user; `[]` for none.
- **Test personas** (`rbac.PERSONAS`, non-prod only) are exposed at `GET /api/auth/personas`;
  the SPA's header offers a switcher that sets the persona as the IAP header on every call
  (`apiFetch`), re-resolving roles — the same code path as a real IAP user.
- `/api/me` returns `roles` + `permissions`; the SPA gates nav (Sidebar) and pages
  (`RequireArea`) on them.
- **Server-side enforcement is the source of truth**: sensitive routers (admin, analytics)
  carry a `require_area(...)` dependency that 403s unauthorised callers. SPA gating is UX —
  a tampered client still can't reach a gated API.

## Consequences

- Prod RBAC is config: set `RBAC_USER_ROLES` to map real IAP emails to roles.
- Dev/test get a one-click persona switcher to see areas lock/unlock; default persona has
  the `admin` role so the app is usable out of the box.
- New gated areas: add the area to `AREAS`/`ROLE_PERMISSIONS`, wrap the route in
  `RequireArea`, and add `require_area` to its router.

## Lens

Gate on the server first, mirror it in the UI second — UI gating is convenience, never the
control. Identity is one channel (the IAP header); a "test persona" must be the *same* path a
real user takes, not a parallel dev-only auth, so what you test is what ships.
