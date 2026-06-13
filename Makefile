# Root Makefile — the single command-and-control surface (see the global working-dir
# rule). `make fix` / `make ci` fan out to every subproject's own fix/ci target.
SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Order: libs/core first (backend + agent depend on it), then the apps, then infra.
SUBPROJECTS := libs/core backend agent frontend infra

.PHONY: help install dev dev-docker clean-ports fix ci $(addprefix ci-,$(SUBPROJECTS)) $(addprefix fix-,$(SUBPROJECTS))

# Local dev ports — agent sidecar, FastAPI backend, Vite SPA.
DEV_PORTS := 8081 8080 5173

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_/-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install/sync deps in every subproject
	@for d in $(SUBPROJECTS); do echo ">>> install $$d"; $(MAKE) -C $$d install; done

dev: ## Run the whole webapp locally: agent :8081 + backend :8080 + Vite :5173 (concurrently; Ctrl-C stops all)
	@scripts/dev-preflight.sh
	@echo ">>> starting agent + backend + frontend — open http://localhost:5173"
	bun run --cwd frontend dev

dev-docker: ## Run the cloud-integrated stack via docker compose (agent + backend at :8080). Needs ADC.
	@echo ">>> docker compose up --build  (SPA served by backend at http://localhost:8080)"
	@echo ">>> for hot-reload frontend dev, run 'make -C frontend dev-frontend-only' alongside this"
	docker compose up --build

clean-ports: ## Kill any stray processes holding the local dev ports (8081 agent, 8080 backend, 5173 frontend)
	@for p in $(DEV_PORTS); do \
	  pid=$$(lsof -ti:$$p 2>/dev/null || true); \
	  if [ -n "$$pid" ]; then kill -9 $$pid && echo "💣 killed PID $$pid on port $$p"; else echo "✅ port $$p free"; fi; \
	done

fix: ## Auto-fix (format + lint) across every subproject
	@for d in $(SUBPROJECTS); do echo ">>> fix $$d"; $(MAKE) -C $$d fix; done

ci: ## Run the full QA gate (lint + strict types + tests >=90%) across every subproject
	@for d in $(SUBPROJECTS); do echo ">>> ci $$d"; $(MAKE) -C $$d ci; done

# Per-subproject escape hatches: `make ci-backend`, `make fix-frontend`, …
ci-%: ## Run ci for one subproject (e.g. make ci-backend)
	$(MAKE) -C $* ci

fix-%: ## Run fix for one subproject (e.g. make fix-frontend)
	$(MAKE) -C $* fix
