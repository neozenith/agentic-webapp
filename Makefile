# Root Makefile — the single command-and-control surface (see the global working-dir
# rule). `make fix` / `make ci` fan out to every subproject's own fix/ci target.
SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Order: libs/core first (backend + agent depend on it), then the apps, then infra.
SUBPROJECTS := libs/core backend agent frontend infra

.PHONY: help install fix ci $(addprefix ci-,$(SUBPROJECTS)) $(addprefix fix-,$(SUBPROJECTS))

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_/-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install/sync deps in every subproject
	@for d in $(SUBPROJECTS); do echo ">>> install $$d"; $(MAKE) -C $$d install; done

fix: ## Auto-fix (format + lint) across every subproject
	@for d in $(SUBPROJECTS); do echo ">>> fix $$d"; $(MAKE) -C $$d fix; done

ci: ## Run the full QA gate (lint + strict types + tests >=90%) across every subproject
	@for d in $(SUBPROJECTS); do echo ">>> ci $$d"; $(MAKE) -C $$d ci; done

# Per-subproject escape hatches: `make ci-backend`, `make fix-frontend`, …
ci-%: ## Run ci for one subproject (e.g. make ci-backend)
	$(MAKE) -C $* ci

fix-%: ## Run fix for one subproject (e.g. make fix-frontend)
	$(MAKE) -C $* fix
