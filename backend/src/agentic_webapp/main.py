"""FastAPI application factory + entrypoint.

Run locally:  uv run uvicorn agentic_webapp.main:app --reload
In container:  uvicorn agentic_webapp.main:app --host 0.0.0.0 --port $PORT
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import admin, agent, assets, health
from .config import get_settings
from .logging_setup import configure_logging

IAP_USER_HEADER = "x-goog-authenticated-user-email"


def _iap_user(request: Request) -> str | None:
    """The caller's identity from IAP. In prod IAP sets (and sanitizes) the header;
    in non-prod a client may set it to simulate users when trust_forwarded_user is on
    (ADR-0004). Disable trust to ignore client-supplied identity."""
    if not get_settings().trust_forwarded_user:
        return None
    raw = request.headers.get(IAP_USER_HEADER)
    if not raw:
        return None
    return raw.split(":", 1)[-1]  # strip "accounts.google.com:" prefix


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    app.include_router(admin.router)
    # Scoped proxy to the agent sidecar (ADK run endpoints + /dev-ui), registered
    # before the SPA so those paths reach the agent, not the SPA fallback.
    app.include_router(agent.build_router())

    @app.get("/api/me")
    async def me(request: Request) -> dict:
        """Identity the SPA shows — from IAP in prod (ADR-0004), null when no IAP."""
        return {"user": _iap_user(request), "environment": settings.environment}

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings) -> None:  # noqa: ANN001
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
