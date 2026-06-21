# Cloud Run container for the dbt sidecar (FastAPI wrapping the dbt CLI).
# Built from the REPO ROOT context, consistent with backend/agent:
#   docker build -f dbt/Dockerfile -t agentic-webapp-dbt:local .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DBT_PROJECT_DIR=/app \
    DBT_TARGET=prod \
    # dbt subprocesses resolve the CLI by bare name; put the venv on PATH. HOME must be
    # writable so dbt can create ~/.dbt (it does this even with --profiles-dir set).
    HOME=/app \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Deps + the sidecar package first (better layer caching), then the dbt project.
COPY dbt/pyproject.toml dbt/uv.lock ./
COPY dbt/src ./src
RUN uv sync --frozen --no-dev

# The dbt project itself lives at /app (DBT_PROJECT_DIR): dbt_project.yml +
# profiles.yml + models. The sidecar passes --project-dir/--profiles-dir /app.
COPY dbt/dbt_project.yml dbt/profiles.yml dbt/packages.yml dbt/package-lock.yml ./
COPY dbt/macros ./macros
COPY dbt/models ./models

# Vendor the dbt packages (Elementary + its deps) into the image's dbt_packages
# at build time, so the runtime has no network dependency on dbt hub. Uses the
# committed package-lock.yml for reproducibility. dbt deps needs no warehouse.
RUN dbt deps

EXPOSE 8082
CMD ["sh", "-c", ".venv/bin/uvicorn dbt_service.app:app --host 0.0.0.0 --port ${PORT:-8082}"]
