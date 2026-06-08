# frontend/Makefile — Vite + React SPA (served in prod by the FastAPI backend).
SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help install dev build preview

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install deps
	bun install

dev: ## Vite dev server (proxies /api + agent paths to backend on :8080)
	bun run dev

build: ## Type-check + production build to dist/
	bun run build

preview: ## Preview the production build
	bun run preview
