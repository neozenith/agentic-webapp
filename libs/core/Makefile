# libs/core/Makefile — shared cloud primitives (agentic-core).
# Run from libs/core/, or `make -C libs/core <target>` from the repo root.
SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help

REPO_ROOT := $(shell git rev-parse --show-toplevel)
PKG       := src

.PHONY: help install fix lint typecheck test ci

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Sync the venv from uv.lock
	uv sync

fix: ## Auto-format + fix lint/imports
	uvx ruff format .
	uvx ruff check . --fix

lint: ## Lint — any finding fails (warnings treated as errors)
	uvx ruff check .

typecheck: ## Strict type-check (mypy --strict via pyproject)
	uv run mypy $(PKG)

test: ## Tests + coverage; boots a throwaway Firestore emulator for REAL coverage
	$(REPO_ROOT)/scripts/with-firestore-emulator.sh uv run pytest

ci: lint typecheck test ## Full QA gate (lint + strict types + tests >=90% coverage)
