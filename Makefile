# Root Makefile — the single command-and-control surface (see the global working-dir
# rule). `make fix` / `make ci` fan out to every subproject's own fix/ci target.
SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Order: libs/core first (backend + agent depend on it), then the apps, the CLI, then infra.
SUBPROJECTS := libs/core backend agent cli frontend infra

.PHONY: help install dev dev-docker clean-ports fix ci openapi mcp-cli mcp-agent mcp-claude mcp-codex $(addprefix ci-,$(SUBPROJECTS)) $(addprefix fix-,$(SUBPROJECTS))

# Local dev ports — agent sidecar, FastAPI backend, Vite SPA.
DEV_PORTS := 8081 8080 5173

# --- Local MCP testing harness (manual; run `make -C backend dev` in another shell first) ---
# Pick a persona by alias (ada/nina/otto/vera) or pass a full email: `make mcp-cli PERSONA=vera`.
PERSONA       ?= ada
EMAIL_ada     := ada.admin@example.com
EMAIL_nina    := nina.analyst@example.com
EMAIL_otto    := otto.operator@example.com
EMAIL_vera    := vera.viewer@example.com
PERSONA_EMAIL := $(or $(EMAIL_$(PERSONA)),$(PERSONA))
MCP_PROMPT    ?= List your MCP tools, call identity_me for my roles, then try admin_users. Be terse.
GCP_PROJECT   ?= dbt-dev-jaffleshop
GCP_REGION    ?= australia-southeast1

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

openapi: ## Dump the backend OpenAPI spec (the contract CLIs/clients integrate against)
	$(MAKE) -C backend openapi

mcp-cli: ## Drive the core API via the local CLI as PERSONA (e.g. make mcp-cli PERSONA=vera)
	uv run --directory cli -m agentic_cli me --as $(PERSONA_EMAIL)
	@echo ">>> admin users as $(PERSONA_EMAIL) (RBAC 403s a non-admin — that's the point):"
	-uv run --directory cli -m agentic_cli admin users --as $(PERSONA_EMAIL)

mcp-agent: ## Drive the MCP via the ADK test agent as PERSONA (needs Vertex/ADC)
	GOOGLE_GENAI_USE_VERTEXAI=True GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) GOOGLE_CLOUD_LOCATION=$(GCP_REGION) \
	  uv run --directory agent python -m harness.mcp_agent --as $(PERSONA_EMAIL) "$(MCP_PROMPT)"

mcp-claude: ## Print the `claude -p` MCP command as PERSONA (add RUN=1 to execute it)
	uv run scripts/mcp_harness.py claude --as $(PERSONA_EMAIL) --prompt "$(MCP_PROMPT)" $(if $(RUN),--run,)

mcp-codex: ## Print the `codex exec` MCP command as PERSONA (add RUN=1 to execute it)
	uv run scripts/mcp_harness.py codex --as $(PERSONA_EMAIL) --prompt "$(MCP_PROMPT)" $(if $(RUN),--run,)
