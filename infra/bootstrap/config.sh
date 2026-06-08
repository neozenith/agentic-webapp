#!/usr/bin/env bash
# Shared configuration for the bootstrap scripts.
# Source this file from other scripts; do not execute it directly.

# GitHub repo allowed to impersonate the deployer service accounts via WIF.
# THIS repo — distinct from the dbt repo, so its OIDC provider trusts a different
# repository claim.
GITHUB_REPO="${GITHUB_REPO:-neozenith/agentic-webapp}"

# GCS location for the Terraform state buckets in every project.
TF_STATE_LOCATION="${TF_STATE_LOCATION:-australia-southeast1}"

# Project namespace. Everything this repo creates is prefixed/suffixed with this
# so it never collides with the dbt platform sharing the same GCP project. In
# particular the tfstate bucket is dbt-<env>-jaffleshop-<NAMESPACE>-tfstate, a
# DISTINCT bucket from the dbt repo's dbt-<env>-jaffleshop-tfstate.
NAMESPACE="${NAMESPACE:-agentic-webapp}"

# Resource naming conventions, applied identically per project.
#
# These names are deliberately DIFFERENT from the dbt repo's bootstrap so the two
# repos coexist in the same projects without collision:
#   - TF_SA_NAME       : a new deployer SA (dbt uses "terraform-deployer")
#   - WIF_POOL_ID      : REUSE the existing pool ("github-pool"); a pool hosts
#                        many providers, and bootstrap is idempotent (won't touch
#                        the dbt provider already in it)
#   - WIF_PROVIDER_ID  : a new provider scoped to THIS repo (dbt uses "github-provider")
TF_SA_NAME="${TF_SA_NAME:-agentic-webapp-deployer}"
WIF_POOL_ID="${WIF_POOL_ID:-github-pool}"
WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-agentic-webapp-provider}"

# Ordered list of <gcp-project-id>:<env-name> pairs to bootstrap.
# Order matters: dev first so failures surface in the cheapest project first.
PROJECT_PAIRS=(
  "dbt-dev-jaffleshop:dev"
  "dbt-test-jaffleshop:test"
  "dbt-prod-jaffleshop:prod"
)
