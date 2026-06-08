# Authentication & Authorization

How identities are established and what they may touch in the **agentic-webapp**
infra. Two distinct principals, both authenticating with **zero long-lived
keyfiles**:

- **TF Deployer** — the `agentic-webapp-deployer` SA that *provisions* the
  `webapp` stack. Reached only via GitHub OIDC → Workload Identity Federation.
- **IAP Human** — the Google identities in `var.iap_members` that *use* the
  deployed Cloud Run service through Identity-Aware Proxy.

These map to the two halves of the system: the deployer builds the service; IAP
governs who may then reach it.

---

## Lens 1 — TF Deployer (provisioning)

A GitHub-signed OIDC JWT is exchanged at this repo's WIF provider (gated on
`attribute.repository == neozenith/agentic-webapp`), yielding a federated token
that impersonates `agentic-webapp-deployer`, which runs `plan`/`apply`.

```mermaid
flowchart LR
    gha["GitHub Actions<br/>terraform-cicd-stack-webapp.yml"]:::ingress
    oidc["GitHub OIDC<br/>JWT"]:::ingress
    wif["WIF provider<br/>agentic-webapp-provider<br/>(in github-pool)"]:::compute
    tfsa["agentic-webapp-deployer SA<br/>vars.TF_SA"]:::compute
    proj[("dbt-env-jaffleshop")]:::data
    res["provisions<br/>Cloud Run + IAP IAM,<br/>runtime SA, API enables"]:::data

    gha --> oidc
    oidc --> wif
    wif -->|"impersonate (repo claim must match)"| tfsa
    tfsa --> proj
    tfsa --> res

    classDef ingress  fill:#1e40af,stroke:#93c5fd,color:#fff,stroke-width:2px
    classDef compute  fill:#5b21b6,stroke:#c4b5fd,color:#fff,stroke-width:2px
    classDef data     fill:#115e59,stroke:#5eead4,color:#fff,stroke-width:2px
```

The dual WIF gate (OIDC provider's repo condition **and** the SA's `principalSet`
binding) is what isolates this repo from the dbt repo even though they share the
project and the `github-pool`. See [`bootstrap/README.md`](./bootstrap/README.md).

---

## Lens 2 — IAP Human (using the service)

Every request to the Cloud Run `run.app` URL is intercepted by IAP. Access is a
two-hop chain — the user is admitted by IAP, then IAP (as its service agent)
invokes Cloud Run.

```mermaid
flowchart LR
    user["You<br/>joshpeak05@gmail.com<br/>(var.iap_members)"]:::ingress
    iap["Identity-Aware Proxy"]:::compute
    agent["IAP service agent<br/>service-NUM@gcp-sa-iap"]:::compute
    run["Cloud Run<br/>agentic-webapp (min=0)"]:::data
    app["Container<br/>(runs as runtime SA)"]:::data

    user -->|"roles/iap.httpsResourceAccessor"| iap
    iap -->|"as agent"| agent
    agent -->|"roles/run.invoker"| run
    run --> app

    classDef ingress  fill:#1e40af,stroke:#93c5fd,color:#fff,stroke-width:2px
    classDef compute  fill:#5b21b6,stroke:#c4b5fd,color:#fff,stroke-width:2px
    classDef data     fill:#115e59,stroke:#5eead4,color:#fff,stroke-width:2px
```

*Three identities, one request:* the **human** (admitted by IAP), the **IAP
service agent** (invokes Cloud Run), and the **runtime SA** (what the container
executes as). Removing a user from `var.iap_members` revokes their access at the
outer hop without touching the service.

---

## Why no keyfiles anywhere

| Path | GitHub-side gate | GCP-side gate |
|------|------------------|---------------|
| TF Deployer | `terraform-cicd-stack-webapp.yml` env + `id-token: write` | WIF `attribute.repository == neozenith/agentic-webapp` + `agentic-webapp-deployer` `workloadIdentityUser` binding |
| IAP Human | — (Google sign-in at the IAP consent screen) | `roles/iap.httpsResourceAccessor` on the IAP resource, for `var.iap_members` only |

Both halves fail **closed**: a workflow from any other repo can't impersonate the
deployer (repo claim mismatch), and any Google account not in `iap_members` is
rejected by IAP before a single request reaches the container.
