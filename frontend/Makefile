# frontend/Makefile — Vite + React SPA (served in prod by the FastAPI backend).
SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help install dev dev-frontend-only build preview fix lint typecheck test ci

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install deps
	bun install

dev: ## Full stack via concurrently — agent :8081 + backend :8080 + Vite :5173 (Ctrl-C stops all)
	bun run dev

dev-frontend-only: ## Vite only (proxies /api + agent paths to a backend already on :8080)
	bun run dev:frontend-only

build: ## Type-check + production build to dist/
	bun run build

preview: ## Preview the production build
	bun run preview

fix: ## Auto-format + fix lint/imports (biome --write)
	bun run fix

lint: ## Lint with biome (warnings treated as errors)
	bun run lint

typecheck: ## Strict type-check (tsc --noEmit)
	bun run typecheck

test: ## Vitest run with coverage (>=90%)
	bun run test

ci: lint typecheck test ## Full QA gate (lint + strict types + tests >=90% coverage)
