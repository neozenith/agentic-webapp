# cli/Makefile — the agentic-webapp local API CLI.
# Run from cli/, or `make -C cli <target>` from the repo root.

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help install run test typecheck lint fix ci

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync the venv from uv.lock
	uv sync

run: ## Run the CLI (pass args after --, e.g. `make run -- assets list --as ada.admin@example.com`)
	uv run -m agentic_cli $(filter-out $@,$(MAKECMDGOALS))

test: ## Run the test suite (drives the real backend in-process; no mocks)
	uv run pytest -q

typecheck: ## Strict type-check (mypy --strict)
	uv run mypy src

lint: ## Lint — any finding fails
	uvx ruff check . --line-length 120

fix: ## Auto-format + fix
	uvx ruff format . --line-length 120
	uvx ruff check . --line-length 120 --fix-only

ci: lint typecheck test ## Full QA gate (lint + strict types + tests >=90% coverage)
