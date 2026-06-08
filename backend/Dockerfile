# Cloud Run container for the FastAPI backend.
#
# IMPORTANT: build from the REPO ROOT as context (not backend/), because the
# editable path dep `agentic-core` lives at ../libs/core and Docker COPY can't
# reach outside the build context. CI uses backend/cloudbuild.yaml; locally:
#   docker build -f backend/Dockerfile -t agentic-webapp-backend:local .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# The shared lib must sit at ../libs/core relative to the project so the path dep
# (../libs/core) resolves: project=/app → ../libs/core=/libs/core.
COPY libs/core /libs/core

# Install deps first (cached layer), then the app source.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD ["sh", "-c", ".venv/bin/uvicorn agentic_webapp.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
