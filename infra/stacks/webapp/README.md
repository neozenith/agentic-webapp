# `webapp` stack

A **scale-to-zero Cloud Run service protected by Identity-Aware Proxy (IAP)**,
locked to a single Google identity (`joshpeak05@gmail.com` by default). Deploys
into the same `dbt-<env>-jaffleshop` projects as the dbt platform, with its own
GCS state object (`gs://dbt-<env>-jaffleshop-tfstate/terraform/state/webapp`).

## What this provisions

| Resource | Purpose |
|---|---|
| `google_project_service.run`/`.iap`/`.artifactregistry`/`.bigquery` | Enable required APIs (idempotent, additive) |
| `google_artifact_registry_repository.app` | Docker repo for the backend image |
| `google_service_account.runtime` | Least-privilege identity the container runs as |
| `google_cloud_run_v2_service.app` | The FastAPI service: `min=0` (scale to zero), env-wired to GCS+BigQuery |
| **`google_storage_bucket.assets`** | Dedicated bucket for asset blobs (images/PDFs/etc.) |
| **`google_bigquery_dataset.app` + `google_bigquery_table.asset_metadata`** | App dataset + the asset-metadata catalogue table |
| `google_storage_bucket_iam_member.runtime_object_admin` | Runtime SA can read/write asset blobs |
| `google_bigquery_dataset_iam_member.runtime_data_editor` + `google_project_iam_member.runtime_job_user` | Runtime SA can read/write rows + run queries |
| `google_service_account_iam_member.runtime_self_token_creator` | Runtime SA can sign V4 URLs via IAM (keyless on Cloud Run) |
| `google_project_service_identity.iap` + `*.iap_invoker` + `*.accessors` (IAP envs only) | IAP service agent + invoker + the human allow-list |
| `google_iap_settings.webapp` (IAP envs only) | Attaches the custom OAuth client (no-org requirement) |

## How the auth works (two hops)

```
You ──HTTPS──> IAP ──(as IAP service agent)──> Cloud Run container
       │              │
       │              └── needs roles/run.invoker         (iap_invoker)
       └── needs roles/iap.httpsResourceAccessor          (accessors)
```

Both grants are required. The end user is admitted by IAP (`httpsResourceAccessor`);
the request that reaches Cloud Run is made by the IAP service agent, which holds
`run.invoker`. The container itself runs as a third identity (the runtime SA).

## IAP policy (presence-based — see ADR-0002)

IAP turns on **automatically when a custom OAuth client is supplied**
(`var.iap_oauth_client_id` is non-empty). There is no per-environment flag to
maintain — supplying the client *is* the switch:

| Env | OAuth client secret? | IAP | Why |
|-----|----------------------|-----|-----|
| **dev** | none | ❌ off | Public, IAP-free fast-iteration space; no sensitive data (ADR-0003). |
| **test** | none (today) | ❌ off | Public for now — add a test OAuth client secret to flip it on, no code change. |
| **prod** | yes (GitHub secret) | ✅ on | IAP-gated; only `var.iap_members` may reach it. |

In CI the client id/secret come from the matching **GitHub Environment secrets**
(`IAP_OAUTH_CLIENT_ID` / `IAP_OAUTH_CLIENT_SECRET`); an environment with no such
secret runs public. When IAP is off, the service gets `allUsers` `roles/run.invoker`
so the `run.app` URL works in a browser; scale-to-zero is unchanged either way.

**Flip any environment to IAP** = add its OAuth client (below) + set the two secrets
on that GitHub Environment, then redeploy. No terraform edit.

**Override for a single apply:** `var.enable_iap` (default `null` = presence-based)
forces a value, e.g. `-var enable_iap=true`.

### ⚠️ No-org IAP prerequisites (per project, manual — two parts)

For any environment with IAP **on**, the apply succeeds but IAP returns
**HTTP 502** (`x-goog-iap-generated-response: true`) until **both** of these exist
in that project. Neither can be created via API/Terraform for a project with **no
GCP organization** (the `google_iap_brand`/OAuth-client-creation APIs are org-only;
the IAP OAuth Admin APIs were shut down March 2026), so both are one-time manual
Console steps **per project**:

**1. OAuth consent screen**
> Console (correct project) → **APIs & Services → OAuth consent screen** (a.k.a.
> *Google Auth Platform → Branding*) → User type **External** → app name + your
> email → Save. Leave it in **Testing**, add your address under **Test users**.

**2. Custom OAuth client** — IAP's *Google-managed* client only works inside an
org, so no-org projects must supply their own:
> Console → **APIs & Services → Credentials → Create credentials → OAuth client ID
> → Web application**. After creating it, add this **Authorized redirect URI**:
> `https://iap.googleapis.com/v1/oauth/clientIds/CLIENT_ID:handleRedirect`
> (substitute the new client ID). Copy the **client ID** and **client secret**.

Then hand the client id/secret to Terraform (it attaches them via
`google_iap_settings`). Put them in a **gitignored** `prod.tfvars` (auto-loaded by
`tfs apply webapp prod`):

```hcl
# infra/stacks/webapp/prod.tfvars   (DO NOT COMMIT — *.tfvars is gitignored)
iap_oauth_client_id     = "...apps.googleusercontent.com"
iap_oauth_client_secret = "GOCSPX-..."
```

```sh
tfs apply webapp prod      # picks up prod.tfvars, attaches the OAuth client to IAP
```

After this, an unauthenticated request returns **302 → accounts.google.com**
(sign-in) instead of 502.

## Quickstart

```sh
# One-time, per project (see ../../bootstrap/README.md):
#   ../../bootstrap/bootstrap_all.sh && ../../bootstrap/bootstrap_github.sh
#   + configure the OAuth consent screen (above)

tfs init  webapp dev
tfs plan  webapp dev
tfs apply webapp dev

tfs output webapp dev          # service_uri, runtime_service_account, ...
```

Or drive `terraform` directly from `infra/`:

```sh
terraform -chdir=stacks/webapp init  -backend-config=./backends/dev.config -reconfigure
terraform -chdir=stacks/webapp plan  -var environment=dev
terraform -chdir=stacks/webapp apply -var environment=dev
```

## Deploying the application image

The stack defaults `container_image` to Google's `hello` sample so it is
deployable immediately. Point it at a real image once you have one:

```sh
terraform -chdir=stacks/webapp apply -var environment=dev \
  -var container_image=australia-southeast1-docker.pkg.dev/dbt-dev-jaffleshop/<repo>/agentic-webapp:<tag>
```

In CI, the application's own build/deploy pipeline passes `-var container_image`.
(An Artifact Registry repository for the image is intentionally **not** part of
this stack yet — add it here, or extract a module, when the app's CD lands.)

## Inputs worth knowing

| Variable | Default | Notes |
|---|---|---|
| `enable_iap` | `null` | `null` = use per-env policy (dev/test off, prod on); set `true`/`false` to override one apply. |
| `iap_members` | `["user:joshpeak05@gmail.com"]` | Who may pass IAP. Add `group:`/`user:` entries to share. |
| `container_image` | Google `hello` sample | Overridden by app CD (e.g. `…/agentic-webapp:v2`). |
| `repository_id` | `agentic-webapp` | Artifact Registry repo for the image. |
| `max_instances` | `2` | Min is pinned to 0 (scale to zero). |
| `service_name` | `agentic-webapp` | Cloud Run service name. |
| `region` | `australia-southeast1` | Cloud Run location. |

> Health endpoint is **`/health`**, not `/healthz` — Google's frontend reserves
> `/healthz` on Cloud Run and 404s it before it reaches the container.

## CI/CD

Deployed by `.github/workflows/terraform-cicd-stack-webapp.yml`, a thin per-stack
caller that forwards to the reusable `.github/workflows/terraform-cicd-per-stack.yml`.

| Git event | Terraform action |
|-----------|------------------|
| 🏚️ Draft PR (this stack's paths) | `fmt` + `validate` + `plan` (dev/test/prod) |
| 🏡 Ready-for-review PR | the above, then `apply` → **dev** |
| 🚀 Push to `main` | `apply` → **test** |
| 🏷️ Push tag `v*` / `workflow_dispatch` | `apply` → **prod** |

prod is only ever reached by a release tag or manual dispatch — never a branch push.

## Reference

The block below is auto-generated by `make docs` (terraform-docs). Hand-edits
between the markers are overwritten — keep narrative above this section.

<!-- BEGIN_TF_DOCS -->
<!-- END_TF_DOCS -->
