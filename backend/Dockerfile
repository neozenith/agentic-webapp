# Cloud Run container for the FastAPI backend, which also serves the built React SPA.
# Build from the REPO ROOT context (libs/core + frontend + backend all in scope):
#   docker build -f backend/Dockerfile -t agentic-webapp-backend:local .

# --- Stage 1: build the React SPA with bun ---
FROM oven/bun:1.3-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run build   # -> /fe/dist

# --- Stage 2: the Python backend ---
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Shared lib at ../libs/core (matches the editable path dep), then deps, then code.
COPY libs/core /libs/core
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev

# The built SPA — served by FastAPI from settings.frontend_dist (= ./frontend_dist).
COPY --from=frontend /fe/dist ./frontend_dist

EXPOSE 8080
CMD ["sh", "-c", ".venv/bin/uvicorn agentic_webapp.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
