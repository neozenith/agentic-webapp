# agent/Makefile — the ADK agent sidecar.
SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

IMAGE ?= agentic-webapp-agent:local
PORT  ?= 8081

.PHONY: help install dev test lint fix docker-build docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync deps
	uv sync

dev: ## Run adk web (debug UI at /dev-ui/, API at /run_sse etc.) on :$(PORT). Needs ADC for Vertex.
	uv run adk web --host 0.0.0.0 --port $(PORT) agents

test: ## Run the test suite (real impls, no mocks; Firestore tests need FIRESTORE_EMULATOR_HOST)
	uv run pytest -q

lint: ## Lint with ruff
	uvx ruff check . --line-length 120

fix: ## Auto-format + fix
	uvx ruff format . --line-length 120
	uvx ruff check . --line-length 120 --fix-only

docker-build: ## Build the agent image (repo-root context)
	docker build -f Dockerfile -t $(IMAGE) ..

docker-run: ## Run the agent container on :$(PORT)
	docker run --rm -p $(PORT):8081 $(IMAGE)
