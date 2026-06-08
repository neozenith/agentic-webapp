# `infra/bootstrap/`

One-time scripts that prepare each GCP project so **this repo's** Terraform can
manage a Cloud Run + IAP webapp from GitHub Actions — coexisting with the dbt
platform already in those projects. Every script is idempotent — re-running is
safe.

## Quickstart

```bash
# 1. Bootstrap GCP (all three projects)
./infra/bootstrap/bootstrap_all.sh

# 2. Bootstrap GitHub Environments + variables
./infra/bootstrap/bootstrap_github.sh
```

Or step-by-step in GCP:

```bash
./infra/bootstrap/bootstrap_project.sh dbt-dev-jaffleshop  dev
./infra/bootstrap/bootstrap_project.sh dbt-test-jaffleshop test
./infra/bootstrap/bootstrap_project.sh dbt-prod-jaffleshop prod
```

Each GCP invocation prints the two values to copy into the matching **GitHub
Environment** (Settings → Environments → `dev`/`test`/`prod`):

```
WIF_PROVIDER  = projects/<number>/locations/global/workloadIdentityPools/github-pool/providers/agentic-webapp-provider
TF_SA         = agentic-webapp-deployer@dbt-<env>-jaffleshop.iam.gserviceaccount.com
```

`bootstrap_github.sh` writes both vars for all three environments via the GitHub
API; the manual UI route is the fallback.

## What this creates vs. reuses

These projects are **shared** with the `dbt-gcp-jaffleshop` repo. To avoid
collision, this bootstrap only adds repo-specific, distinctly-named resources and
reuses the rest:

| # | Resource | Action | Collision avoidance |
|---|---|---|---|
| 1 | APIs (`run`, `iap`, + base set) | enable | enabling is idempotent / additive |
| 2 | `*-tfstate` bucket | **reuse** | our state uses a distinct GCS prefix (`terraform/state/webapp`) |
| 3 | `agentic-webapp-deployer` SA | **create** | distinct name (dbt uses `terraform-deployer`) |
| 4 | `github-pool` WIF pool | **reuse** | a pool hosts many providers |
| 5 | `agentic-webapp-provider` OIDC provider | **create** | distinct name + scoped to `neozenith/agentic-webapp` |
| 6 | `workloadIdentityUser` binding | **create** | binds THIS repo's principalSet to THIS SA |

## Prerequisites

1. The three GCP projects already exist with billing enabled (owned by the dbt
   bootstrap): `dbt-{dev,test,prod}-jaffleshop`.
2. The caller is authenticated to gcloud with rights to enable services, create
   service accounts, grant `roles/owner`, and create WIF providers on each project.
3. `gh` CLI installed + authenticated with repo-admin on `${GITHUB_REPO}` (needed
   by `bootstrap_github.sh`).

The scripts deliberately **do not** authenticate — they assume the caller already
has credentials.

## IAP one-time manual step (no-org projects)

These projects belong to a Gmail account with **no GCP organization**. IAP's
OAuth consent screen for *external* user type cannot be created via Terraform
(`google_iap_brand` only supports org-internal brands). Before the first apply of
the `webapp` stack, configure the consent screen once in the Console:

> APIs & Services → OAuth consent screen → User type **External** → fill app name
> + support email → Save. (No need to add scopes or publish for IAP to work with
> your own Google account as a test user / owner.)

This is a genuine manual prerequisite, not an optional step — see
[`../stacks/webapp/README.md`](../stacks/webapp/README.md).

## Scripts

| Script | Purpose |
|---|---|
| `config.sh` | Shared constants (repo name, region, SA/provider names, project list). Sourced by the others. |
| `bootstrap_project.sh` | Sets up steps 1–7 for **one** project. Usage: `bootstrap_project.sh <project-id> <env-name>`. |
| `bootstrap_all.sh` | Runs `bootstrap_project.sh` for every entry in `PROJECT_PAIRS` (dev → test → prod). |
| `bootstrap_github.sh` | Creates the GitHub Environments and writes `WIF_PROVIDER` + `TF_SA`. Run **after** `bootstrap_all.sh`. |

## Overriding defaults

The scripts honour environment variables so one-off overrides don't require
editing `config.sh`:

```bash
GITHUB_REPO=neozenith/some-fork ./infra/bootstrap/bootstrap_all.sh
TF_STATE_LOCATION=us-central1   ./infra/bootstrap/bootstrap_project.sh dbt-dev-jaffleshop dev
```
