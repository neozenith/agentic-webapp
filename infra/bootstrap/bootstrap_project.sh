#!/usr/bin/env bash
# Bootstrap one GCP project so this repo's Terraform (driven from GitHub Actions)
# can manage a Cloud Run + IAP webapp in it — ALONGSIDE the existing dbt platform,
# never colliding with it.
#
# Idempotent: re-running is safe. Every gcloud call either checks existence first
# or uses an "add"/"update" command that converges to the desired state.
#
# Creates / ensures in the target project:
#   1. Required Google APIs enabled (incl. run + iap for this workload)
#   2. GCS bucket "<project>-tfstate" (REUSED if it already exists; UBL, PAP, versioned)
#   3. Service account "agentic-webapp-deployer" with roles/owner on the project
#   4. Workload Identity Pool "github-pool" (REUSED — created by whichever repo runs first)
#   5. OIDC provider "agentic-webapp-provider" restricted to ${GITHUB_REPO}
#   6. IAM binding allowing principals from that repo to impersonate the SA

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./config.sh
source "${SCRIPT_DIR}/config.sh"

PROJECT_ID="${1:-}"
ENV_NAME="${2:-}"

if [[ -z "${PROJECT_ID}" || -z "${ENV_NAME}" ]]; then
  echo "Usage: $0 <project-id> <env-name>" >&2
  echo "Example: $0 dbt-dev-jaffleshop dev" >&2
  exit 2
fi

# This repo's OWN tfstate bucket — namespaced, distinct from the dbt repo's
# ${PROJECT_ID}-tfstate. Nothing this script touches collides with the dbt platform.
TF_STATE_BUCKET="${PROJECT_ID}-${NAMESPACE}-tfstate"
TF_SA_EMAIL="${TF_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

log() { printf '\n==> %s\n' "$*"; }
sub() { printf '    - %s\n' "$*"; }

log "Bootstrapping ${PROJECT_ID} (env=${ENV_NAME})"
sub "github repo  : ${GITHUB_REPO}"
sub "state bucket : gs://${TF_STATE_BUCKET} (${TF_STATE_LOCATION})"
sub "deployer SA  : ${TF_SA_EMAIL}"
sub "wif provider : ${WIF_PROVIDER_ID} (in pool ${WIF_POOL_ID})"

# 0. Precheck: billing must be linked, otherwise bucket creation (step 2)
#    fails partway through with a confusing HTTPError 403 from GCS.
log "Checking project billing"
billing_status="$(gcloud billing projects describe "${PROJECT_ID}" \
  --format='value(billingEnabled)' 2>/dev/null || true)"
if [[ "${billing_status}" != "True" && "${billing_status}" != "true" ]]; then
  cat >&2 <<EOF

ERROR: project '${PROJECT_ID}' has no active billing account (or you lack access).

This repo expects the three dbt-*-jaffleshop projects to already exist with
billing enabled (they are created/owned by the dbt-gcp-jaffleshop bootstrap).
Triage:

  gcloud billing projects describe ${PROJECT_ID}
  gcloud billing accounts list
  gcloud billing projects link ${PROJECT_ID} --billing-account=ACCOUNT_ID

Then re-run (idempotent):  ${0##*/} ${PROJECT_ID} ${ENV_NAME}

EOF
  exit 1
fi
sub "billing enabled"

# 1. Enable required APIs --------------------------------------------------
# Base set mirrors the dbt bootstrap (re-enabling is a no-op); run + iap are the
# additions this Cloud Run + IAP workload needs.
log "Enabling APIs"
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  storage.googleapis.com \
  serviceusage.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  iap.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="${PROJECT_ID}"

# 2. GCS bucket for Terraform state ---------------------------------------
# Shared with the dbt repo (one tfstate bucket per project); our stack lives
# under a distinct GCS prefix, so reusing the bucket cannot collide.
log "GCS tfstate bucket"
if gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" \
    --project="${PROJECT_ID}" --format=none >/dev/null 2>&1; then
  sub "bucket exists (reusing)"
else
  gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
    --project="${PROJECT_ID}" \
    --location="${TF_STATE_LOCATION}" \
    --uniform-bucket-level-access \
    --public-access-prevention
  sub "bucket created"
fi
gcloud storage buckets update "gs://${TF_STATE_BUCKET}" \
  --project="${PROJECT_ID}" --versioning >/dev/null
sub "versioning enabled"

# 3. Terraform deployer service account ------------------------------------
log "Service account"
if gcloud iam service-accounts describe "${TF_SA_EMAIL}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
  sub "service account exists"
else
  gcloud iam service-accounts create "${TF_SA_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="Agentic Webapp Deployer (${ENV_NAME})" \
    --description="GitHub Actions (${GITHUB_REPO}) impersonates this SA to apply the webapp stack in ${PROJECT_ID}"
  sub "service account created"
fi

# 4. Grant roles/owner on the project --------------------------------------
# Broad, like the dbt deployer: a deployer that provisions IAP IAM + service
# identities needs wide rights. Narrow later once the resource set is stable.
# Blast radius is still bounded by the dual WIF gate (repo claim + SA binding).
log "Granting roles/owner to deployer SA"
# SA creation is eventually consistent: a freshly-created SA can be invisible to
# the IAM policy API for a few seconds, so the grant may 400 with "does not
# exist". Retry briefly before giving up.
binding_ok=""
for attempt in 1 2 3 4 5 6; do
  if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${TF_SA_EMAIL}" \
      --role="roles/owner" \
      --condition=None \
      --quiet >/dev/null 2>&1; then
    binding_ok="yes"
    break
  fi
  sub "deployer SA not yet visible to IAM, retrying (${attempt})…"
  sleep 5
done
[ -n "${binding_ok}" ] || { echo "ERROR: failed to grant roles/owner to ${TF_SA_EMAIL}" >&2; exit 1; }
sub "binding ensured"

# 5. Workload Identity Pool ------------------------------------------------
# Reuse the existing github-pool. If the dbt bootstrap already created it, the
# describe short-circuits; if THIS repo runs first, we create it.
log "Workload Identity Pool"
if gcloud iam workload-identity-pools describe "${WIF_POOL_ID}" \
    --project="${PROJECT_ID}" --location=global >/dev/null 2>&1; then
  sub "pool exists (reusing)"
else
  gcloud iam workload-identity-pools create "${WIF_POOL_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --display-name="GitHub Actions"
  sub "pool created"
fi

# 6. GitHub OIDC provider on the pool --------------------------------------
# A NEW provider (distinct ID) restricted to THIS repo. Does not touch the dbt
# repo's provider in the same pool. Mapping + condition are converged on every run.
log "OIDC provider"
WIF_ATTR_MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref,attribute.ref_type=assertion.ref_type,attribute.event_name=assertion.event_name"
WIF_ATTR_CONDITION="assertion.repository == '${GITHUB_REPO}'"
if gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_ID}" \
    --project="${PROJECT_ID}" --location=global \
    --workload-identity-pool="${WIF_POOL_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "${WIF_PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --workload-identity-pool="${WIF_POOL_ID}" \
    --attribute-mapping="${WIF_ATTR_MAPPING}" \
    --attribute-condition="${WIF_ATTR_CONDITION}" >/dev/null
  sub "provider converged (mapping + condition updated)"
else
  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --workload-identity-pool="${WIF_POOL_ID}" \
    --display-name="GitHub OIDC (agentic-webapp)" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="${WIF_ATTR_MAPPING}" \
    --attribute-condition="${WIF_ATTR_CONDITION}"
  sub "provider created (restricted to repo ${GITHUB_REPO})"
fi

# 7. Allow the repo's workflows to impersonate the SA ----------------------
log "Workload Identity binding"
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
WIF_PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_ID}/attribute.repository/${GITHUB_REPO}"

gcloud iam service-accounts add-iam-policy-binding "${TF_SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="${WIF_PRINCIPAL}" \
  --quiet >/dev/null
sub "workloadIdentityUser binding ensured for ${GITHUB_REPO}"

# 8. Print the values to wire into GitHub Environments ---------------------
WIF_PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_ID}/providers/${WIF_PROVIDER_ID}"

cat <<EOF

==> ${ENV_NAME} (${PROJECT_ID}) bootstrap complete.

Configure GitHub Environment "${ENV_NAME}" with these two variables (the rest
are derived in Terraform / infra/stacks/webapp/backends/${ENV_NAME}.config):

  WIF_PROVIDER  = ${WIF_PROVIDER_RESOURCE}
  TF_SA         = ${TF_SA_EMAIL}

For reference / debugging:
  project_id   = ${PROJECT_ID}      (from local.project_id in infra/stacks/webapp/main.tf)
  state bucket = ${TF_STATE_BUCKET} (from infra/stacks/webapp/backends/${ENV_NAME}.config)

EOF
