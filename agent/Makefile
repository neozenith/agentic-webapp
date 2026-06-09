# agent/Makefile — the ADK agent sidecar.
SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

IMAGE ?= agentic-webapp-agent:local
PORT  ?= 8081
REPO_ROOT := $(shell git rev-parse --show-toplevel)

.PHONY: help install dev test typecheck lint fix ci docker-build docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync deps
	uv sync

dev: ## Run adk web (debug UI at /dev-ui/, API at /run_sse etc.) on :$(PORT). Needs ADC for Vertex.
	uv run adk web --host 0.0.0.0 --port $(PORT) agents

test: ## Tests + coverage; boots a throwaway Firestore emulator for REAL coverage
	$(REPO_ROOT)/scripts/with-firestore-emulator.sh uv run pytest

typecheck: ## Strict type-check (mypy --strict via pyproject)
	uv run mypy agents

lint: ## Lint — any finding fails (warnings treated as errors)
	uvx ruff check . --line-length 120

fix: ## Auto-format + fix
	uvx ruff format . --line-length 120
	uvx ruff check . --line-length 120 --fix-only

ci: lint typecheck test ## Full QA gate (lint + strict types + tests >=90% coverage)

docker-build: ## Build the agent image (repo-root context)
	docker build -f Dockerfile -t $(IMAGE) ..

docker-run: ## Run the agent container on :$(PORT)
	docker run --rm -p $(PORT):8081 $(IMAGE)
