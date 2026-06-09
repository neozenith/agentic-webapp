# infra/Makefile — convenience wrapper around terraform + the stacks/modules tooling.
#
# Run from the infra/ directory, or `make -C infra <target>` from the repo root.
#
#   make help                       list every target
#   make bootstrap                  one-time GCP-side setup for all three projects
#   make create-stack NAME=foo      scaffold a new stacks/foo/ + its CI workflow
#   make plan-dev                   terraform plan for STACK against dbt-dev-jaffleshop
#   make apply-dev                  terraform apply for STACK against dbt-dev-jaffleshop
#   make ci                         local CI gate (fmt-check + security + validate + gha-check)
#
# Which stack a terraform target operates on is selected with STACK= (default
# webapp). Per-environment terraform targets are pattern rules — substitute
# dev/test/prod for <env> in init-<env>, plan-<env>, apply-<env>, validate-<env>:
#
#   make STACK=webapp     plan-prod
#   make STACK=monitoring apply-dev

SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Which stack the terraform targets act on. Override on the command line:
#   make STACK=<name> plan-dev
STACK ?= webapp
TF_DIR := stacks/$(STACK)

ENVS := dev test prod

# Platforms covered by each stack's .terraform.lock.hcl. Each entry adds one
# per-platform h1: install-hash so `terraform init` works on that OS/arch.
# - linux_amd64:  GitHub Actions ubuntu-latest runners.
# - darwin_arm64: Apple Silicon Macs (contributor laptops).
# - darwin_amd64: Intel Macs (legacy contributor laptops).
TF_LOCK_PLATFORMS := linux_amd64 darwin_arm64 darwin_amd64

.PHONY: help bootstrap bootstrap-github create-stack validate-backends gha-check diagram \
        fmt fmt-check fix lint docs security lock lock-check validate-all tfs-ci ci

# NOTE: deliberately NOT declaring init-/plan-/apply-/validate-<env> as .PHONY.
# GNU Make 3.81 (macOS default) has a bug where adding pattern-matched targets
# to .PHONY suppresses their pattern rules entirely ("Nothing to be done").
# These targets fire correctly without .PHONY because no real files of those
# names exist to be timestamp-compared.

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---- One-time bootstrap ----

bootstrap: ## Run GCP-side bootstrap for every project (idempotent)
	./bootstrap/bootstrap_all.sh

bootstrap-github: ## Create/refresh GitHub Environments + vars (run AFTER bootstrap)
	./bootstrap/bootstrap_github.sh

# ---- Stack lifecycle (the `tfs` CLI — infra/tfs/) ----
# Run via `uv run --directory tfs tfs <cmd>`: uv builds/uses the tfs project env
# (exposing the `tfs` console script) without needing a global install. Humans can
# also `uv tool install 'tfs @ ./infra/tfs'` and then call a bare `tfs` anywhere.

create-stack: ## Scaffold a new stack + its CI workflow:  make create-stack NAME=<stack>
	@test -n "$(NAME)" || { echo "ERROR: NAME=<stack> is required, e.g. make create-stack NAME=monitoring" >&2; exit 2; }
	uv run --directory tfs tfs create $(NAME)

validate-backends: ## Check every stacks/*/backends/*.config matches the state convention
	uv run --directory tfs tfs validate

gha-check: ## Verify every stack has a matching per-stack CI workflow (and vice versa)
	uv run --directory tfs tfs gha-check

diagram: ## Render an architecture diagram: make diagram STACK=webapp ENV=dev MODE=state|plan
	@test -n "$(ENV)" || { echo "ERROR: ENV=<dev|test|prod> is required" >&2; exit 2; }
	uv run --directory tfs tfs diagram $(STACK) $(ENV) --mode $(or $(MODE),state)

# ---- Per-environment terraform targets (operate on STACK) ----
# init-<env>, plan-<env>, apply-<env>, validate-<env>
# `-reconfigure` on init makes env-switching in the same checkout safe.
#
# init is inlined into plan/apply/validate via TF_INIT_CMD instead of being a
# pattern-rule prerequisite (`plan-%: init-%`), which trips the GNU Make 3.81
# (macOS) chained-pattern-rule bug. `brew install make` gives a modern gmake.

TF_INIT_CMD = terraform -chdir=$(TF_DIR) init -backend-config=./backends/$*.config -reconfigure

init-%: ## terraform init -reconfigure for STACK/<env>  (e.g. make init-dev)
	$(TF_INIT_CMD)

plan-%: ## terraform plan for STACK/<env>
	$(TF_INIT_CMD)
	terraform -chdir=$(TF_DIR) plan -input=false -var environment=$*

apply-%: ## terraform apply for STACK/<env> (-auto-approve)
	$(TF_INIT_CMD)
	terraform -chdir=$(TF_DIR) apply -input=false -auto-approve -var environment=$*

validate-%: ## terraform validate for STACK/<env>
	$(TF_INIT_CMD)
	terraform -chdir=$(TF_DIR) validate

validate-all: $(addprefix validate-,$(ENVS)) ## terraform validate STACK against every env's backend

# ---- Quality gates (recursive across all stacks + modules) ----

fmt: ## terraform fmt -recursive (writes changes)
	terraform fmt -recursive

fmt-check: ## terraform fmt -check -recursive (read-only, CI-safe)
	terraform fmt -check -recursive

fix: ## Auto-fix: terraform fmt + ruff format/fix on the tfs CLI
	terraform fmt -recursive
	uvx ruff format tfs
	uvx ruff check tfs --fix

lint: ## tflint (auto-inits plugins; idempotent)
	tflint --init
	tflint --recursive

tfs-ci: ## tfs Python gate: ruff (warnings=errors) + mypy --strict + pytest >=90% coverage
	uvx ruff check tfs --line-length 120
	uv run --directory tfs mypy src
	uv run --directory tfs pytest

docs: ## Regenerate the terraform-docs block in every stack/module README
	@for d in stacks/*/ modules/*/; do \
	  if compgen -G "$$d*.tf" >/dev/null; then \
	    echo "terraform-docs -> $${d}README.md"; \
	    terraform-docs markdown table --output-file README.md --output-mode inject "$$d"; \
	  fi; \
	done

security: ## Optional: trivy config scan for IaC misconfigurations (install: brew install trivy)
	trivy config .

lock: ## Regenerate STACK's .terraform.lock.hcl with checksums for every TF_LOCK_PLATFORMS
	terraform -chdir=$(TF_DIR) providers lock $(addprefix -platform=,$(TF_LOCK_PLATFORMS))

lock-check: ## Fail if STACK's .terraform.lock.hcl is stale (CI gate; mutates file on drift)
	@terraform -chdir=$(TF_DIR) providers lock $(addprefix -platform=,$(TF_LOCK_PLATFORMS)) >/dev/null
	@git diff --exit-code $(TF_DIR)/.terraform.lock.hcl >/dev/null || \
	  { echo >&2 "ERROR: $(TF_DIR)/.terraform.lock.hcl is stale. Run 'make STACK=$(STACK) lock' and commit."; exit 1; }

ci: fmt-check lint security validate-backends gha-check tfs-ci ## Full QA gate: tf fmt+lint+security + backend/workflow checks + tfs lint/types/tests. Run validate-<env> separately.
