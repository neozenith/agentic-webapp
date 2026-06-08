"""FastAPI application factory + entrypoint.

Run locally:  uv run uvicorn agentic_webapp.main:app --reload
In container:  uvicorn agentic_webapp.main:app --host 0.0.0.0 --port $PORT
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from .api.routes import agent, assets, health
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
    app.include_router(health.router)
    app.include_router(assets.router)

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request) -> str:
        user = _iap_user(request) or "(local — no IAP in front)"
        return f"""<!doctype html><html><head><meta charset=utf-8>
<title>agentic-webapp</title>
<style>body{{font-family:system-ui,sans-serif;background:#0b1120;color:#e2e8f0;
display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:2.5rem 3rem;max-width:34rem}}
a{{color:#7dd3fc}} .k{{color:#94a3b8}} .v{{color:#5eead4}}</style></head>
<body><div class=card>
<h1>🛡️ agentic-webapp</h1>
<p>Async FastAPI backend — storage + database abstractions over GCS &amp; BigQuery.</p>
<p><span class=k>signed in as</span> <span class=v>{user}</span></p>
<p><span class=k>environment</span> <span class=v>{settings.environment}</span> ·
<span class=k>storage</span> <span class=v>{settings.storage_backend}</span> ·
<span class=k>database</span> <span class=v>{settings.database_backend}</span></p>
<p><a href="/docs">/docs</a> · <a href="/health">/health</a> · <a href="/api/assets">/api/assets</a></p>
</div></body></html>"""

    # Catch-all LAST: any path the backend doesn't own is proxied to the agent
    # sidecar (ADK debug UI /dev-ui/, /run_sse, /list-apps, /apps/...). Backend
    # routes above (/, /health, /api/assets, /docs) take precedence.
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def agent_proxy(full_path: str, request: Request) -> StreamingResponse:
        return await agent.proxy_to_agent(request, full_path)

    return app


app = create_app()
