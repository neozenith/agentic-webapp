# `infra/` — Terraform (stacks + modules)

Terraform for the **agentic-webapp**, organised as **independently-deployed
stacks** (each with its own GCS state) composed from **reusable modules**. The
same `*.tf` in a stack plan/apply against any of three GCP projects
(`dbt-{dev,test,prod}-jaffleshop`) via **partial backend configuration**.

> **Layout lineage:** this is the stacks + modules layout from the sibling
> `dbt-gcp-jaffleshop` repo, re-used here for a different workload. The two
> repos share the same GCP projects but never collide — see
> [Coexistence with `dbt-gcp-jaffleshop`](#coexistence-with-dbt-gcp-jaffleshop).

## The model

1. **Bootstrap = bare minimum.** Per environment: reuse the existing GCS state
   bucket + a **new** `agentic-webapp-deployer` SA + a **new** OIDC provider in
   the existing WIF pool that this repo's CI impersonates. Run directly against
   GCP (`bootstrap/`), never through Terraform.
2. **A stack is one cohesive, independently-deployable definition.** `webapp` is
   *the IAP-protected Cloud Run service* — kept whole. Independence comes from
   adding **new** stacks, not from splitting an existing one.
3. **One workflow per stack** promotes it through dev → test → prod.
4. **Many stacks, one bucket per env, state namespaced by stack name** —
   `prefix = "terraform/state/<stack>"`, uniformly (no exceptions). This is also
   what keeps us from colliding with the dbt repo's state.
5. **Primitives become modules** once a second stack reuses them — extracted from
   real reuse, not anticipated.

## Layout

```
infra/
├── bootstrap/              one-time GCP + GitHub setup scripts (see bootstrap/README.md)
├── config.yml             per-env GCP settings consumed by the scaffolder
├── Makefile               STACK-aware wrapper around terraform + tooling (default STACK=webapp)
├── .tflint.hcl            tflint config (recursive across stacks + modules)
├── modules/               reusable building blocks (see modules/README.md)
│   └── <module>/
├── tfs/                    the `tfs` stack-lifecycle CLI (installable uv tool — see tfs/README.md)
│   └── src/tfs/           argparse app + commands/ + packaged scaffolding templates/
└── stacks/
    └── webapp/            the Cloud Run + IAP stack (scales to zero, single-user IAP)
        ├── backend.tf  provider.tf  main.tf  variables.tf  cloudrun.tf  iap.tf  outputs.tf
        ├── README.md
        └── backends/{dev,test,prod}.config
```

## Quickstart

```bash
make -C infra help                       # list every target
make -C infra plan-dev                   # plan STACK (default webapp) against dev
make -C infra apply-dev                  # apply
make -C infra STACK=webapp plan-prod
make -C infra ci                         # no-cloud gate: fmt-check + security + validate + gha-check
```

The `tfs` CLI is the streamlined path (it adds a `gcloud` project guardrail and
wires the terraform flags). Install it once as a uv tool and call it anywhere:

```bash
uv tool install 'tfs @ ./infra/tfs'      # from the repo root; then, anywhere in the repo:
tfs plan  webapp dev
tfs apply webapp dev
```

Or run it without installing (what the Makefile + CI do — no global state):

```bash
uv run --directory infra/tfs tfs plan  webapp dev
uv run --directory infra/tfs tfs apply webapp dev
```

## Coexistence with `dbt-gcp-jaffleshop`

This repo and `dbt-gcp-jaffleshop` deploy into the **same three GCP projects**.
Nothing collides because every shared surface is namespaced:

| Surface | dbt repo | this repo | Why no collision |
|---|---|---|---|
| tfstate bucket | `dbt-<env>-jaffleshop-tfstate` | `dbt-<env>-jaffleshop-agentic-webapp-tfstate` | **separate bucket** |
| state prefix | `terraform/state/dbt_platform` | `terraform/state/webapp` | distinct objects, distinct bucket |
| deployer SA | `terraform-deployer@…` | `agentic-webapp-deployer@…` | distinct SA, distinct IAM |
| WIF pool | `github-pool` | **same pool** | a pool hosts many providers (reused read-only) |
| OIDC provider | `github-provider` (repo: dbt) | `agentic-webapp-provider` (repo: this) | distinct provider, distinct repo claim |
| Artifact Registry | — | `agentic-webapp` repo | distinct name |
| runtime resources | BigQuery, dbt SAs | Cloud Run `agentic-webapp`, IAP | different services / names |

The only project-level resource this repo *shares* is the `github-pool` WIF pool
(reused read-only — a pool is just a container for providers). Everything else —
state bucket, deployer SA, OIDC provider, Artifact Registry, Cloud Run service —
is a brand-new, distinctly-named resource. The dbt platform is never touched.

## Adding a new stack

```bash
make -C infra create-stack NAME=monitoring
# or: tfs create monitoring   (or: uv run --directory infra/tfs tfs create monitoring)
```

This scaffolds `stacks/monitoring/` (backend/provider/main/variables `.tf`,
per-env `backends/*.config`, a `README.md`) **and** the matching CI caller
`.github/workflows/terraform-cicd-stack-monitoring.yml`. Then:

```bash
make -C infra gha-check                              # confirm stack ↔ workflow coverage
make -C infra STACK=monitoring validate-all          # init + validate every env
```

## State management

- **One tfstate bucket per project** — `dbt-<env>-jaffleshop-tfstate`. A
  misconfigured stack physically cannot touch another project's state.
- **One state object per stack**, isolated by GCS `prefix`:

  | Stack | `prefix` | Why |
  |---|---|---|
  | *every stack* | `terraform/state/<stack>` | Per-stack isolation so stacks never collide. |

  `tfs validate` enforces this uniform rule; `make ci` runs it.

## CI/CD

Each stack is driven by a thin **per-stack caller**
(`.github/workflows/terraform-cicd-stack-<stack>.yml`, generated by `tfs create`)
that forwards to the shared **reusable workflow**
`.github/workflows/terraform-cicd-per-stack.yml`. The reusable workflow owns the
routing and delegates every cloud-touching terraform call to the composite action
[`.github/actions/terraform`](../.github/actions/terraform/README.md) (WIF auth +
init + plan/apply). See each stack's README for its trigger → env table.

## Tooling

| Tool | Role | Make target | Install |
|---|---|---|---|
| `terraform fmt` | Canonical formatter | `make fmt` / `make fmt-check` | bundled with terraform |
| `terraform validate` | Static check per env (post-init) | `make validate-<env>` | bundled with terraform |
| [`tfs`](./tfs/README.md) | Stack lifecycle: create / validate / gha-check / tf passthrough | `make create-stack` / `validate-backends` / `gha-check` | `uv tool install 'tfs @ ./infra/tfs'` (or `uv run --directory infra/tfs tfs …`) |
| [`tflint`](https://github.com/terraform-linters/tflint) | Lint + Google ruleset (`.tflint.hcl`) | `make lint` | `brew install tflint` then `tflint --init` |
| [`terraform-docs`](https://terraform-docs.io/) | Inject Inputs/Outputs tables into stack/module READMEs | `make docs` | `brew install terraform-docs` |
| [`trivy config`](https://trivy.dev/) | IaC security scan | `make security` | `brew install trivy` |

## See also

- [`../SETUP.md`](../SETUP.md) — **from-scratch runbook** (recreate the whole project step by step).
- [`stacks/webapp/README.md`](./stacks/webapp/README.md) — the Cloud Run + IAP stack (start here).
- [`modules/README.md`](./modules/README.md) — when/how to extract a module.
- [`bootstrap/README.md`](./bootstrap/README.md) — one-time GCP + GitHub setup.
- [`AUTH.md`](./AUTH.md) — the authn/authz model (TF Deployer + IAP access).
