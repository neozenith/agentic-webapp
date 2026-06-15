"""FastAPI application factory + entrypoint.

Run locally:  uv run uvicorn agentic_webapp.main:app --reload
In container:  uvicorn agentic_webapp.main:app --host 0.0.0.0 --port $PORT
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from agentic_core.database import GroupManager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.utils import generate_unique_id as _default_unique_id

from . import rbac
from .api.auth import iap_email, require_area
from .api.deps import get_group_manager
from .api.routes import admin, agent, analytics, assets, extractions, folders, health, ui
from .config import Settings, get_settings
from .identity import mask_user_id
from .logging_setup import configure_logging
from .mcp_server import build_mcp


def _operation_id(route: APIRoute) -> str:
    """Stable, predictable operation ids for the /api/* surface (e.g. `assets_list`,
    `assets_share`, `admin_users`) so MCP tool names and generated clients are clean. The
    tag supplies the noun, so a redundant tag/singular token is stripped from the handler
    name. Non-API routes (agent proxy, health, SPA) keep FastAPI's collision-safe default —
    the proxy reuses one handler across many paths, which would otherwise collide."""
    if not route.path_format.startswith("/api/"):
        return _default_unique_id(route)
    tag = str(route.tags[0]) if route.tags else "api"
    singular = tag[:-1] if tag.endswith("s") else tag
    parts = [p for p in route.name.split("_") if p not in {tag, singular}]
    return f"{tag}_{'_'.join(parts)}" if parts else tag


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    # FastMCP's streamable-HTTP transport only starts inside its own app's lifespan; nest it
    # here (the MCP app is built in create_app and stashed on app.state, so it exists by now).
    mcp_app = getattr(app.state, "mcp_app", None)
    if mcp_app is None:
        yield
    else:
        async with mcp_app.lifespan(app):
            yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="agentic-webapp",
        version="0.1.0",
        summary="Async FastAPI backend with pluggable storage + database abstractions.",
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
        servers=[{"url": "/", "description": settings.environment}],
    )
    # Backend APIs.
    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(folders.router)
    # Extraction WRITE — visibility-gated (not area-gated): the agent records on a user's
    # behalf for any asset that user can see. Read stays admin/analytics-gated (analytics.router).
    app.include_router(extractions.router)
    # Sensitive areas are enforced server-side (defense-in-depth behind the SPA gating).
    app.include_router(admin.router, dependencies=[Depends(require_area("admin"))])
    app.include_router(analytics.router, dependencies=[Depends(require_area("analytics"))])
    # Scoped proxy to the agent sidecar (ADK run endpoints + /dev-ui), registered
    # before the SPA so those paths reach the agent, not the SPA fallback.
    app.include_router(agent.build_router())
    # Web-only MCP-UI drill-in proxy (/ui/browse). Not in OpenAPI, not an MCP tool — it
    # reuses the same render_browse as the MCP `browse` tool (ADR-0012).
    app.include_router(ui.router)

    @app.get("/api/me", tags=["identity"])
    async def me(request: Request) -> dict[str, Any]:
        """Identity the SPA shows — from IAP in prod (ADR-0004), null when no IAP.

        `user_id` is the pseudonymous, server-authoritative id the SPA uses for session
        ownership and bookkeeping; the raw email is never used as a key downstream."""
        email = iap_email(request)
        roles = rbac.roles_for(email, environment=settings.environment, user_roles=settings.rbac_user_roles)
        return {
            "email": email,
            "user_id": mask_user_id(email) if email else None,
            "environment": settings.environment,
            "roles": roles,
            "permissions": rbac.permissions_for(roles),
        }

    @app.get("/api/auth/personas", tags=["identity"])
    async def personas() -> list[dict[str, Any]]:
        """Switchable test identities (non-prod only) so RBAC mappings can be exercised."""
        return rbac.personas(settings.environment)

    @app.get("/api/directory", tags=["identity"])
    async def directory() -> dict[str, dict[str, str]]:
        """Pseudonymous-id -> {email, name} lookup so the SPA can render human names for the
        user_ids on shared assets/folders. Any signed-in user may read it."""
        return rbac.directory(user_roles=settings.rbac_user_roles)

    @app.get("/api/groups", tags=["identity"])
    async def groups(manager: Annotated[GroupManager, Depends(get_group_manager)]) -> list[dict[str, str]]:
        """Read-only group listing (group_id + name, NO membership) so any signed-in user can
        discover groups to share with. Membership and CRUD stay admin-only (/api/admin/groups)."""
        return [{"group_id": g.group_id, "name": g.name} for g in await manager.list()]

    # Expose the assembled /api/* surface as MCP tools (another interface to the core API).
    # Mounted BEFORE the SPA so /mcp/* isn't swallowed by the client-routing fallback; its
    # lifespan is nested in `lifespan` via app.state (see above).
    base_url = settings.self_base_url or f"http://127.0.0.1:{settings.port}"
    app.state.mcp_app = build_mcp(app, base_url=base_url).http_app(path="/")
    app.mount("/mcp", app.state.mcp_app)

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built React SPA (static assets + client-side-routing fallback) when
    present; otherwise a minimal status page. Registered last so API + agent routes win."""
    dist = settings.frontend_dist
    index = dist / "index.html"

    if not index.exists():

        @app.get("/", response_class=HTMLResponse)
        async def status_page() -> str:
            return (
                "<!doctype html><meta charset=utf-8><title>agentic-webapp</title>"
                "<body style='font-family:system-ui;background:#0b1120;color:#e2e8f0'>"
                f"<h1>agentic-webapp ({settings.environment})</h1>"
                "<p>SPA not built. API at <a style=color:#7dd3fc href=/docs>/docs</a>.</p>"
            )

        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", response_class=FileResponse)
    async def spa(full_path: str) -> FileResponse:  # noqa: ARG001 — SPA client-side routing
        return FileResponse(index)


app = create_app()
