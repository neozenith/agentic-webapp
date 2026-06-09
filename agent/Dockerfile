# ADK agent sidecar container. Built from the REPO ROOT context (consistent with
# backend, and ready for PR3 when it adds the shared lib for bookkeeping):
#   docker build -f agent/Dockerfile -t agentic-webapp-agent:local .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    GOOGLE_GENAI_USE_VERTEXAI=True

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Shared lib at ../libs/core (matches the editable path dep), then deps, then code.
COPY libs/core /libs/core
COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev
COPY agent/agents ./agents

# Sidecar listens on a fixed internal port (the backend proxies to it). Cloud Run's
# $PORT belongs to the ingress (backend) container, so this is hard-coded.
EXPOSE 8081
# --allow_origins '*': the sidecar sits behind the backend proxy (which already
# strips the browser Origin), so ADK's own origin guard is redundant here; widening
# it also lets the direct dev UI on :8081 be opened for debugging.
#
# Session persistence is opt-in via SESSION_SERVICE_URI (e.g. firestore://). When set,
# agents/services.py maps the firestore:// scheme to the durable FirestoreSessionService
# (DB id from FIRESTORE_DATABASE); when unset, ADK uses its in-memory session service.
# Shell form + exec so env expands AND adk stays PID 1 (receives SIGTERM on Cloud Run).
CMD exec .venv/bin/adk web --host 0.0.0.0 --port 8081 --allow_origins '*' \
    ${SESSION_SERVICE_URI:+--session_service_uri $SESSION_SERVICE_URI} agents
