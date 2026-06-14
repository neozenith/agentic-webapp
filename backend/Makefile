# backend/Makefile — the agentic-webapp FastAPI service.
# Run from backend/, or `make -C backend <target>` from the repo root.

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

IMAGE ?= agentic-webapp-backend:local
PORT  ?= 8080

.PHONY: help install dev dev-cloud start openapi test typecheck lint fix ci docker-build docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync the venv from uv.lock
	uv sync

dev: ## Run locally with hot reload at http://localhost:$(PORT)  (in-memory backends)
	uv run uvicorn agentic_webapp.main:app --reload --host 0.0.0.0 --port $(PORT)

GCP_ENV ?= dev
dev-cloud: ## Run locally AGAINST cloud services (GCS+Firestore in the dev project; uses your ADC). See ADR-0005.
	STORAGE_BACKEND=gcs DATABASE_BACKEND=firestore \
	GCP_PROJECT=dbt-$(GCP_ENV)-jaffleshop \
	ASSETS_BUCKET=dbt-$(GCP_ENV)-jaffleshop-agentic-webapp-assets \
	FIRESTORE_DATABASE=agentic-webapp \
	ENVIRONMENT=$(GCP_ENV) \
	uv run uvicorn agentic_webapp.main:app --reload --host 0.0.0.0 --port $(PORT)

start: ## Run locally without reload (production entrypoint)
	uv run uvicorn agentic_webapp.main:app --host 0.0.0.0 --port $(PORT)

openapi: ## Dump the OpenAPI spec to openapi.json (the contract CLIs/clients integrate against)
	uv run python -c "import json; from agentic_webapp.main import create_app; print(json.dumps(create_app().openapi(), indent=2))" > openapi.json
	@echo ">>> wrote backend/openapi.json"

test: ## Run the test suite (real impls, no mocks)
	uv run pytest -q

typecheck: ## Strict type-check (mypy --strict via pyproject; runs in the venv so deps resolve)
	uv run mypy src

lint: ## Lint — any finding fails (warnings treated as errors)
	uvx ruff check . --line-length 120

fix: ## Auto-format + fix
	uvx ruff format . --line-length 120
	uvx ruff check . --line-length 120 --fix-only

ci: lint typecheck test ## Full QA gate (lint + strict types + tests >=90% coverage)

docker-build: ## Build the container image (repo-root context so libs/core is included)
	docker build -f Dockerfile -t $(IMAGE) ..

docker-run: ## Run the container locally at http://localhost:$(PORT)
	docker run --rm -p $(PORT):8080 -e PORT=8080 $(IMAGE)
