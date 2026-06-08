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

COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev
COPY agent/agents ./agents

# Sidecar listens on a fixed internal port (the backend proxies to it). Cloud Run's
# $PORT belongs to the ingress (backend) container, so this is hard-coded.
EXPOSE 8081
CMD [".venv/bin/adk", "web", "--host", "0.0.0.0", "--port", "8081", "agents"]
