# e2e/Makefile — Playwright evidence suite for the deployed app.
# Run from the repo root, e.g.  make -C e2e test
SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Default target env is Test (no IAP). Override: make -C e2e test BASE_URL=https://...
BASE_URL ?= https://agentic-webapp-qfe3o66q6q-ts.a.run.app

.PHONY: help install test report

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install deps + the chromium browser
	bun install
	bun run install-browser

test: ## Run the suite against BASE_URL (default: Test); writes screenshots + HTML report
	BASE_URL=$(BASE_URL) bun run test

report: ## Open the last HTML report
	bun run report
