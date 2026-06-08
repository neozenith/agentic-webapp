# `infra/modules/`

Reusable Terraform building blocks, called from one or more `stacks/<stack>/`.

A directory only earns module status once a pattern is consumed by **≥2 callers**
(or is complex enough that isolating + testing it independently pays for itself).
Until then, keep resources inline in the stack.

## Layout

Each module is standalone and self-describing:

```
modules/<module_name>/
├── main.tf        # the resources
├── variables.tf   # typed inputs
├── outputs.tf     # values callers consume
├── versions.tf    # required_providers / required_version
└── README.md      # purpose + a terraform-docs Inputs/Outputs block
```

## Levels of abstraction

A useful mental model (borrowed from CDK's construct levels) for deciding *what*
belongs in a module:

- **L1 — primitives.** A single provider resource (`google_cloud_run_v2_service`).
  Rarely worth a module on its own.
- **L2 — curated resources.** One logical thing with sane, opinionated defaults
  baked in (a Cloud Run service with scale-to-zero + IAP wired in). This is the
  sweet spot for most modules here — and a likely first extraction if a second
  stack needs an IAP-protected service.
- **L3 — patterns.** A composition of L2 modules that captures a whole
  architectural shape. Reach for these only once the same composition appears twice.

## Conventions

- Modules are **monorepo-local** — referenced by relative path
  (`source = "../../modules/<name>"`), never a remote registry.
- Modules never configure a `provider` or `backend` — those belong to the calling
  stack. A module declares only `required_providers` in `versions.tf`.
- `make docs` runs `terraform-docs` into each module's README between its
  `<!-- BEGIN_TF_DOCS -->` / `<!-- END_TF_DOCS -->` markers.
