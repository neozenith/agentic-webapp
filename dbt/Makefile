# dbt/Makefile — the dbt-core BigQuery project + its FastAPI sidecar.
# Run from dbt/, or `make -C dbt <target>` from the repo root.

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

IMAGE ?= agentic-webapp-dbt:local
PORT  ?= 8082

.PHONY: help install dev start test typecheck lint fix ci docker-build docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync the venv from uv.lock
	uv sync

dev: ## Run the sidecar locally with hot reload at http://localhost:$(PORT)
	uv run uvicorn dbt_service.app:app --reload --host 0.0.0.0 --port $(PORT)

start: ## Run the sidecar without reload (production entrypoint)
	uv run uvicorn dbt_service.app:app --host 0.0.0.0 --port $(PORT)

test: ## Run the test suite (real impls, no mocks; no live BigQuery)
	uv run pytest -q

typecheck: ## Strict type-check (mypy --strict via pyproject)
	uv run mypy src

lint: ## Lint — any finding fails (warnings treated as errors)
	uvx ruff check . --line-length 120

fix: ## Auto-format + fix
	uvx ruff format . --line-length 120
	uvx ruff check . --line-length 120 --fix-only

ci: lint typecheck test ## Full QA gate (lint + strict types + tests >=90% coverage)

docker-build: ## Build the container image (repo-root context, mirrors backend)
	docker build -f Dockerfile -t $(IMAGE) ..

docker-run: ## Run the sidecar container locally at http://localhost:$(PORT)
	docker run --rm -p $(PORT):8082 -e PORT=8082 $(IMAGE)
