# `tfs` — Terraform stack lifecycle CLI

The stack lifecycle tool for `infra/` (the stacks + modules layout, GCS backend).
An installable, multi-module CLI so it can be run as a bare `tfs` from anywhere.

## Install (use anywhere)

```bash
uv tool install 'tfs @ ./infra/tfs'      # from the repo root
# then, from anywhere inside the repo:
tfs validate
tfs plan webapp dev
```

To pick up source changes after editing the tool: `uv tool install --reinstall 'tfs @ ./infra/tfs'`.

## Run without installing (dev / CI)

```bash
uv run --directory infra/tfs tfs validate          # uses this project's env
uv run --frozen --directory infra/tfs tfs gha-check # CI: lockfile-pinned
```

`--directory infra/tfs` sets the working dir inside the package; `tfs` then walks
**up** to find the infra root (`config.yml` + `stacks/`), so discovery still lands
on `infra/`.

## Commands

| Command | What it does |
|---|---|
| `tfs validate` | Check every `stacks/*/backends/*.config` matches the state convention |
| `tfs create <stack>` | Scaffold `stacks/<stack>/` + its per-stack GHA workflow |
| `tfs gha-check` | Verify each stack has a matching CI workflow (and vice versa) |
| `tfs diagram <stack> [env]` | Render a cloud architecture diagram from terraform, using vendored draw.io stencils (GCP/AWS/Azure/Kubernetes; ~180 resource types in `diagrams/registry.py`). Emits a **draw.io-compatible SVG** (editable in draw.io) **and a PNG**. `--mode state` (live infra, default) or `--mode plan` (delta, coloured by action); `--iam edges\|nodes`; `--out-dir`. PNG needs cairo (`brew install cairo` / `apt-get install libcairo2`). Output → `infra/diagrams/`. `--readme` embeds the prod-state SVG (no cairo) into `stacks/<stack>/README.md`; add `--check` to fail on a stale committed diagram. |
| `tfs diagram-comment <stack> <env> --png-artifact-id ID --svg-artifact-id ID` | CI only: post/update the sticky PR comment linking the uploaded PNG + SVG artifacts (reads `GH_TOKEN`/PR context from the environment; no terraform/cloud access). |
| `tfs init <stack> <env>` | `terraform init -reconfigure` |
| `tfs plan <stack> <env>` | `terraform plan` |
| `tfs apply <stack> <env>` | `terraform apply -auto-approve` |
| `tfs output <stack> <env>` | `terraform output -json` |
| `tfs import <stack> <env> <addr> <id>` | `terraform import` |
| `tfs force-unlock <stack> <env> <lock_id>` | release a stuck state lock |

Global flags (accepted before or after the subcommand): `--debug` (verbose
logging), `--infra-root <path>` (override discovery; also via `TFS_INFRA_ROOT`).

## How paths are resolved

Two roots are discovered **independently** — the tool never assumes `infra/` and
`.github/` are siblings:

- **infra root** — walk up from cwd for a dir with `config.yml` + `stacks/`
  (override: `--infra-root` / `TFS_INFRA_ROOT`). All stack/module paths hang off this.
- **repo root** — `git rev-parse --show-toplevel`; `.github/workflows/` lives here.

## Project layouts (single- vs multi-project)

`config.yml` declares a **required** `layout:` key that tells `tfs` how your GCP
projects and tfstate are partitioned. It drives the project `check_project` guards
and the state bucket. The **state prefix is the same in both layouts** —
`terraform/state/<env>/<stack>` — so the two collapse to one convention and only the
project/bucket resolution differs:

| `layout:` | GCP project | tfstate bucket | GCS prefix (canonical) | `environments:` shape |
|---|---|---|---|---|
| `multi-project` (this repo) | one **per env** | one **per env** | `terraform/state/<env>/<stack>` | map `{env: {project_id, state_bucket}}` |
| `single-project` | one **shared** | one **shared** | `terraform/state/<env>/<stack>` | list `[dev, test, prod]` + top-level `project_id`/`state_bucket` |

`tfs create` scaffolds new stacks with the env-baked prefix in both layouts. `tfs
validate` checks each `backends/*.config` against it — with one deliberate tolerance:
under **multi-project** it also accepts the legacy env-less prefix
`terraform/state/<stack>` (a safe manual override, since each env already has its own
bucket — this is what this repo's deployed `webapp` stack uses). Under
**single-project** the env-less form is rejected: all envs share one bucket, so an
env-less prefix would collide dev/test/prod state. A config whose shape doesn't match
its declared `layout:` fails loudly (no silent mode inference).

```yaml
# multi-project (this repo)
layout: multi-project
environments:
  dev:  { project_id: dbt-dev-jaffleshop,  state_bucket: ...-dev-...-tfstate }
  ...

# single-project
layout: single-project
project_id: my-project
state_bucket: my-project-tfstate
environments: [dev, test, prod]
```

## Layout

```
infra/tfs/
├── pyproject.toml          # name = "tfs", [project.scripts] tfs = "tfs.app:main"
└── src/tfs/
    ├── app.py              # build_parser() + main() — argparse wiring only
    ├── roots.py            # find_infra_root() / find_repo_root()
    ├── config.py           # layout_of, project_for/bucket_for, expected_prefix, list_stacks
    ├── backends.py         # backend *.config parsing + discovery
    ├── gcp.py              # check_project gcloud guardrail
    ├── errors.py           # typed exceptions
    ├── logging_setup.py    # --debug logging
    ├── commands/           # one handler module per command group
    │   ├── validate.py  create.py  gha.py  terraform.py
    └── templates/          # PACKAGE DATA stamped by `tfs create`
        ├── *.tf  README.md.j2
        ├── backends/base.config.j2
        └── workflows/terraform-cicd-stack-STACKNAME.yml.j2  → .github/workflows/
```

## Tests

```bash
uv run --directory infra/tfs pytest
```
