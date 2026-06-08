# Setup runbook — agentic-webapp from scratch

End-to-end steps to recreate this project: a scale-to-zero Cloud Run web app that
runs locally, deploys to the shared `dbt-{dev,test,prod}-jaffleshop` GCP projects
**without colliding** with the dbt platform there, with a public dev/test space
and an IAP-gated prod (single-user).

It is written so you can follow it top-to-bottom on empty projects. Every value
that's a naming choice is called out so you can re-namespace for a different app.

## Table of contents

- [0. Mental model](#0-mental-model)
- [1. Prerequisites](#1-prerequisites)
- [2. Naming / namespacing (how collisions are avoided)](#2-naming--namespacing-how-collisions-are-avoided)
- [3. Run it locally first](#3-run-it-locally-first)
- [4. One-time GCP provisioning (per environment)](#4-one-time-gcp-provisioning-per-environment)
- [5. Deploy dev (public)](#5-deploy-dev-public)
- [6. Deploy prod (IAP, single user)](#6-deploy-prod-iap-single-user)
- [7. Verify](#7-verify)
- [8. Day-2 operations](#8-day-2-operations)
- [9. Gotchas we hit (read this)](#9-gotchas-we-hit-read-this)
- [10. Optional: CI/CD via GitHub Actions](#10-optional-cicd-via-github-actions)
- [11. Teardown](#11-teardown)

---

## 0. Mental model

- **`backend/`** — the async **FastAPI** service (runs locally and in the container).
  Built around two general, swappable abstractions: `StorageManager`
  (→`GCSStorageManager`) and `DatabaseManager` (→`BigQueryDatabaseManager`, used by
  `AssetMetadataManager`). Each has an in-memory twin for tests / GCP-free local dev.
- **`infra/`** — Terraform, organised as the `stacks + modules` layout driven by the
  `tfs` CLI. The product stack is `infra/stacks/webapp/` — it provisions Cloud Run,
  the assets **GCS bucket**, the **BigQuery dataset + table**, IAM, and (per env) IAP.
- **State + auth are namespaced per app**, so this project shares the GCP projects
  with `dbt-gcp-jaffleshop` but never touches its resources.
- **IAP policy is per environment, encoded in code** (`local.iap_default_by_env` in
  `infra/stacks/webapp/main.tf`): `dev=false`, `test=false`, `prod=true`.

## 1. Prerequisites

Tools (versions we used in parentheses):

| Tool | Used for | Notes |
|---|---|---|
| `gcloud` (565+) | GCP provisioning, Cloud Build | `gcloud auth login` **and** `gcloud auth application-default login` |
| `terraform` (1.14; min 1.10) | infra | |
| `uv` (0.11+) | runs the `tfs` CLI **and the FastAPI backend** | |
| `docker` (optional) | run the container locally | Cloud Build is used for the deploy image, so Docker isn't required to deploy |
| `gh` (optional) | only for the CI/CD path (section 10) | |

GCP assumptions:
- The three projects already exist **with billing enabled**:
  `dbt-{dev,test,prod}-jaffleshop`.
- You are `roles/owner` on them (we deployed directly with user ADC; the CI path in
  §10 uses a dedicated deployer SA instead).
- ⚠️ **These projects have no GCP organization.** That changes the IAP setup — see §6 and §9.

## 2. Naming / namespacing (how collisions are avoided)

Everything this project creates is namespaced `agentic-webapp` so it coexists with
the dbt platform in the same projects:

| Resource | This project | dbt platform | Collision? |
|---|---|---|---|
| tfstate bucket | `dbt-<env>-jaffleshop-agentic-webapp-tfstate` | `dbt-<env>-jaffleshop-tfstate` | separate bucket |
| state prefix | `terraform/state/webapp` | `terraform/state/dbt_platform` | distinct |
| Artifact Registry | `agentic-webapp` | — | distinct |
| Cloud Run service | `agentic-webapp` | — | distinct |
| runtime SA | `agentic-webapp-run@…` | — | distinct |
| deployer SA (CI) | `agentic-webapp-deployer@…` | `terraform-deployer@…` | distinct |
| OIDC provider (CI) | `agentic-webapp-provider` | `github-provider` | distinct (same `github-pool`, reused read-only) |

The bucket name + state prefix are configured in `infra/config.yml` and
`infra/stacks/webapp/backends/<env>.config`. To re-use this for a different app,
change the `agentic-webapp` namespace in those files (and `bootstrap/config.sh`).

## 3. Run it locally first

The backend defaults to the in-memory storage + database backends, so it runs with
zero cloud setup:

```bash
make -C backend install    # uv sync (first time)
make -C backend dev        # hot-reload at http://localhost:8080
make -C backend test       # real tests, no mocks
```

Open http://localhost:8080 (UI), `/docs` (OpenAPI), `/health`. Locally there's no
IAP, so the page shows "(local — no IAP in front)". Switch `STORAGE_BACKEND=gcs` /
`DATABASE_BACKEND=bigquery` in `backend/.env` to run against real GCP. This is the
inner-loop dev experience — no GCP needed by default.

## 4. One-time GCP provisioning (per environment)

Do this once per project you want to deploy to. Examples use **dev**
(`dbt-dev-jaffleshop`); repeat with `test` / `prod` project IDs as needed.

```bash
PROJECT=dbt-dev-jaffleshop
REGION=australia-southeast1
BUCKET=$PROJECT-agentic-webapp-tfstate

# 4a. Enable the APIs this stack needs (idempotent, additive — safe alongside dbt)
gcloud services enable \
  run.googleapis.com iap.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com iamcredentials.googleapis.com storage.googleapis.com \
  --project=$PROJECT

# 4b. Create THIS project's own namespaced tfstate bucket (UBL + PAP + versioned)
gcloud storage buckets create gs://$BUCKET --project=$PROJECT --location=$REGION \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://$BUCKET --project=$PROJECT --versioning
```

> The bucket name must be globally unique; `dbt-<env>-jaffleshop-agentic-webapp-tfstate`
> is distinct from the dbt repo's `dbt-<env>-jaffleshop-tfstate`, so they coexist.

## 5. Deploy dev (public)

Dev is intentionally IAP-free for fast iteration. The IAP policy in code already
sets `dev=false`, so no flags are needed for the auth side.

```bash
REGION=australia-southeast1
PROJECT=dbt-dev-jaffleshop
IMG=$REGION-docker.pkg.dev/$PROJECT/agentic-webapp/agentic-webapp

# 5a. Point Terraform at dev's backend
terraform -chdir=infra/stacks/webapp init -backend-config=./backends/dev.config -reconfigure

# 5b. Create the Artifact Registry repo first (so we can push to it).
#     -target is a deliberate bootstrap step to break the image<->service cycle.
terraform -chdir=infra/stacks/webapp apply -auto-approve -var environment=dev \
  -target=google_project_service.artifactregistry \
  -target=google_artifact_registry_repository.app

# 5c. Build + push the image (remote build — no local Docker needed)
gcloud builds submit backend/ --tag $IMG:v1 --project=$PROJECT

# 5d. Full apply with the real image (dev => public, scale-to-zero)
terraform -chdir=infra/stacks/webapp apply -auto-approve \
  -var environment=dev -var container_image=$IMG:v1
```

The `service_uri` output is your dev URL. It's public (`allUsers` invoker) so it
opens directly in a browser; it still scales to zero. The same apply also creates
the **assets GCS bucket**, the **BigQuery dataset + `asset_metadata` table**, and the
runtime SA's IAM (object admin, BQ data editor + job user, and token-creator-on-self
for signing) — and wires them into the service as env vars. No extra steps.

> Equivalent via the `tfs` CLI: `tfs init/apply webapp dev` (it adds a gcloud
> project guardrail and the backend/flag wiring). You still pass
> `-var container_image=…` for the build tag, e.g. by putting it in a
> (gitignored) `dev.tfvars` which `tfs` auto-loads.

## 6. Deploy prod (IAP, single user)

Prod's IAP policy is `true` in code, so the apply turns IAP on automatically. The
extra work is **all** because the projects have no GCP organization.

### 6a. Provision prod (same as §4 with the prod project)

```bash
PROJECT=dbt-prod-jaffleshop  REGION=australia-southeast1
BUCKET=$PROJECT-agentic-webapp-tfstate
gcloud services enable run.googleapis.com iap.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com \
  iamcredentials.googleapis.com storage.googleapis.com --project=$PROJECT
gcloud storage buckets create gs://$BUCKET --project=$PROJECT --location=$REGION \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://$BUCKET --project=$PROJECT --versioning
```

### 6b. AR repo + image (same pattern as §5b/§5c, prod project)

```bash
IMG=$REGION-docker.pkg.dev/$PROJECT/agentic-webapp/agentic-webapp
terraform -chdir=infra/stacks/webapp init -backend-config=./backends/prod.config -reconfigure
terraform -chdir=infra/stacks/webapp apply -auto-approve -var environment=prod \
  -target=google_project_service.artifactregistry \
  -target=google_artifact_registry_repository.app
gcloud builds submit backend/ --tag $IMG:v1 --project=$PROJECT
```

### 6c. IAP one-time manual setup (Console — required for no-org projects)

IAP's default OAuth client is Google-managed and **only works inside an org**, so
a no-org project needs its **own** consent screen *and* a **custom OAuth client**.
Neither can be created via API/CLI/Terraform here. In the **prod** project's Console:

1. **OAuth consent screen** — APIs & Services → OAuth consent screen (a.k.a. *Google
   Auth Platform → Branding*) → User type **External** → app name + your email →
   Save. Leave it **Testing**, add your Google account under **Test users**.
2. **Custom OAuth client** — APIs & Services → Credentials → **Create credentials →
   OAuth client ID → Web application**. Create it, then add this **Authorized
   redirect URI** (substitute the new client ID):
   ```
   https://iap.googleapis.com/v1/oauth/clientIds/CLIENT_ID:handleRedirect
   ```
   Copy the **client ID** and **client secret**. (Propagation of the redirect URI
   can take ~5 minutes.)

### 6d. Hand the client to Terraform and apply

Put the build image + OAuth client into a **gitignored** `prod.tfvars` (auto-loaded
by `tfs apply webapp prod`):

```hcl
# infra/stacks/webapp/prod.tfvars   — DO NOT COMMIT (*.tfvars is gitignored)
container_image         = "australia-southeast1-docker.pkg.dev/dbt-prod-jaffleshop/agentic-webapp/agentic-webapp:v1"
iap_oauth_client_id     = "....apps.googleusercontent.com"
iap_oauth_client_secret = "GOCSPX-..."
```

```bash
terraform -chdir=infra/stacks/webapp init -backend-config=./backends/prod.config -reconfigure
terraform -chdir=infra/stacks/webapp apply -auto-approve -var environment=prod -var-file=prod.tfvars
# or simply:  tfs apply webapp prod   (auto-loads prod.tfvars)
```

This creates the Cloud Run service with `iap_enabled = true`, grants the IAP
service agent `run.invoker`, grants you `roles/iap.httpsResourceAccessor`, and
attaches the custom OAuth client via `google_iap_settings`.

## 7. Verify

```bash
DEV=$(terraform -chdir=infra/stacks/webapp output -raw service_uri)   # after a dev apply

# dev: public -> 200 directly
curl -s -o /dev/null -w '%{http_code}\n' "$DEV/"

# prod: IAP -> 302 to accounts.google.com (NOT 502, NOT 200)
curl -s -o /dev/null -D - https://<prod-service_uri>/ | grep -iE '^HTTP/|^location:'
```

- **dev** should be `200` and serve the app.
- **prod** should be `302` with a `location:` to `accounts.google.com/o/oauth2/...`.
  Open it in a browser, sign in as the allowed user, and the page footer shows your
  email. A `502` means the OAuth client isn't attached yet (see §9); a
  `redirect_uri_mismatch` on the Google screen means the redirect URI in 6c-2 hasn't
  propagated/saved.

## 8. Day-2 operations

**Ship a new app version** (rebuild → push new tag → re-apply):
```bash
gcloud builds submit backend/ --tag $IMG:v2 --project=$PROJECT
# dev:
terraform -chdir=infra/stacks/webapp apply -auto-approve -var environment=dev -var container_image=$IMG:v2
# prod: bump container_image in prod.tfvars, then:  tfs apply webapp prod
```

**Rotate the IAP OAuth client secret** (zero downtime):
1. Console → Credentials → the OAuth client → **Add secret** (keeps old one valid).
2. Update `iap_oauth_client_secret` in `prod.tfvars` → `tfs apply webapp prod`.
3. Console → **delete the old secret**.

**Turn IAP on for test later**: set `test = true` in `local.iap_default_by_env`
(`infra/stacks/webapp/main.tf`), do the §6c consent-screen + OAuth-client steps in
the test project, add a `test.tfvars` with the client creds, then `tfs apply webapp test`.

**Force IAP on/off for one apply** (override the policy): `-var enable_iap=true|false`.

## 9. Gotchas we hit (read this)

| Symptom | Cause | Fix |
|---|---|---|
| `terraform validate`: *"iap_enabled is not expected"* | `iap_enabled` (GA) needs provider **≥ 7.21**; the dbt stack's `~> 6.0` is too old | webapp stack pins `~> 7.21` (independent lockfile) |
| Prod IAP returns **HTTP 502** `x-goog-iap-generated-response: true` | No usable OAuth client. IAP's managed client is **org-only**; no-org projects need a custom client | §6c + §6d (consent screen + custom client + `google_iap_settings`) |
| `gcloud iap oauth-brands` → *"Project must belong to an organization"* | Legacy IAP OAuth Admin API is org-only and was shut down (Mar 2026) | Don't use it; create the OAuth client in the Console (§6c) |
| `/healthz` returns a Google **404** but `/` works | Google's frontend reserves `/healthz` on Cloud Run — it never reaches the container | App's health route is **`/health`** |
| Cloud Run badge shows `local` in the cloud | `ENVIRONMENT` not set | stack injects `env { ENVIRONMENT = var.environment }` |
| `redirect_uri_mismatch` at Google sign-in | Authorized redirect URI not saved/propagated | re-check §6c-2; allow ~5 min |
| Secret would land in git | `prod.tfvars` holds it | `*.tfvars` is gitignored; verify with `git check-ignore infra/stacks/webapp/prod.tfvars` |

## 10. Optional: CI/CD via GitHub Actions

To deploy from PRs instead of a laptop, bootstrap a dedicated deployer identity per
project (idempotent; creates the namespaced SA + an OIDC provider in the existing
`github-pool`, scoped to this repo — never touching the dbt deployer):

```bash
./infra/bootstrap/bootstrap_all.sh        # SA + WIF provider + APIs + tfstate bucket, all 3 projects
./infra/bootstrap/bootstrap_github.sh     # GitHub Environments + WIF_PROVIDER/TF_SA vars (needs gh)
```

Then the per-stack workflow `.github/workflows/terraform-cicd-stack-webapp.yml`
(→ reusable `terraform-cicd-per-stack.yml` → composite `.github/actions/terraform`)
runs plan on PRs and applies dev→test→prod by trigger. See
[`infra/bootstrap/README.md`](infra/bootstrap/README.md) and
[`infra/AUTH.md`](infra/AUTH.md).

> CI applies don't have `prod.tfvars`. For IAP prod via CI, store the OAuth client
> id/secret as GitHub Environment secrets and pass them through as
> `TF_VAR_iap_oauth_client_id` / `TF_VAR_iap_oauth_client_secret`.

## 11. Teardown

```bash
# Per environment (destroys the Cloud Run service, IAP wiring, AR repo, runtime SA):
terraform -chdir=infra/stacks/webapp init -backend-config=./backends/<env>.config -reconfigure
terraform -chdir=infra/stacks/webapp destroy -var environment=<env> -var-file=<env>.tfvars   # prod
#                                              (dev: -var container_image=$IMG:<tag> instead of -var-file)

# Then, if you also want the state bucket gone (irreversible):
gcloud storage rm -r gs://dbt-<env>-jaffleshop-agentic-webapp-tfstate
```

Prod has `deletion_protection = true` on the Cloud Run service; flip it to false and
apply before destroy if needed. The OAuth consent screen + client are left in place
(harmless) — delete them in the Console if you want a truly clean project.
