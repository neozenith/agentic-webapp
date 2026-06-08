# Cloud Run container for the FastAPI backend. uv handles deps + the editable install.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# uv binary from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install deps first (cached layer), then the app.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8080
# Cloud Run injects PORT (default 8080). uvicorn binds 0.0.0.0.
CMD ["sh", "-c", ".venv/bin/uvicorn agentic_webapp.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
