# backend/Makefile — the agentic-webapp FastAPI service.
# Run from backend/, or `make -C backend <target>` from the repo root.

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

IMAGE ?= agentic-webapp-backend:local
PORT  ?= 8080

.PHONY: help install dev start test typecheck lint fix docker-build docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync the venv from uv.lock
	uv sync

dev: ## Run locally with hot reload at http://localhost:$(PORT)  (in-memory backends)
	uv run uvicorn agentic_webapp.main:app --reload --host 0.0.0.0 --port $(PORT)

GCP_ENV ?= dev
dev-cloud: ## Run locally AGAINST cloud services (GCS+BigQuery in the dev project; uses your ADC). See ADR-0005.
	STORAGE_BACKEND=gcs DATABASE_BACKEND=bigquery \
	GCP_PROJECT=dbt-$(GCP_ENV)-jaffleshop \
	ASSETS_BUCKET=dbt-$(GCP_ENV)-jaffleshop-agentic-webapp-assets \
	BIGQUERY_DATASET=agentic_webapp \
	ENVIRONMENT=$(GCP_ENV) \
	uv run uvicorn agentic_webapp.main:app --reload --host 0.0.0.0 --port $(PORT)

start: ## Run locally without reload (production entrypoint)
	uv run uvicorn agentic_webapp.main:app --host 0.0.0.0 --port $(PORT)

test: ## Run the test suite (real impls, no mocks)
	uv run pytest -q

typecheck: ## Type-check with mypy
	uvx mypy src

lint: ## Lint with ruff
	uvx ruff check . --line-length 120

fix: ## Auto-format + fix
	uvx ruff format . --line-length 120
	uvx ruff check . --line-length 120 --fix-only

docker-build: ## Build the container image
	docker build -t $(IMAGE) .

docker-run: ## Run the container locally at http://localhost:$(PORT)
	docker run --rm -p $(PORT):8080 -e PORT=8080 $(IMAGE)
