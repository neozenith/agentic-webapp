"""FastAPI application factory + entrypoint.

Run locally:  uv run uvicorn agentic_webapp.main:app --reload
In container:  uvicorn agentic_webapp.main:app --host 0.0.0.0 --port $PORT
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import rbac
from .api.auth import iap_email, require_area
from .api.routes import admin, agent, analytics, assets, folders, health
from .config import Settings, get_settings
from .identity import mask_user_id
from .logging_setup import configure_logging

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="agentic-webapp",
        version="0.1.0",
        summary="Async FastAPI backend with pluggable storage + database abstractions.",
        lifespan=lifespan,
    )
    # Backend APIs.
    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(folders.router)
    # Sensitive areas are enforced server-side (defense-in-depth behind the SPA gating).
    app.include_router(admin.router, dependencies=[Depends(require_area("admin"))])
    app.include_router(analytics.router, dependencies=[Depends(require_area("analytics"))])
    # Scoped proxy to the agent sidecar (ADK run endpoints + /dev-ui), registered
    # before the SPA so those paths reach the agent, not the SPA fallback.
    app.include_router(agent.build_router())

    @app.get("/api/me")
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

    @app.get("/api/auth/personas")
    async def personas() -> list[dict[str, Any]]:
        """Switchable test identities (non-prod only) so RBAC mappings can be exercised."""
        return rbac.personas(settings.environment)

    @app.get("/api/directory")
    async def directory() -> dict[str, dict[str, str]]:
        """Pseudonymous-id -> {email, name} lookup so the SPA can render human names for the
        user_ids on shared assets/folders. Any signed-in user may read it."""
        return rbac.directory(user_roles=settings.rbac_user_roles)

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
