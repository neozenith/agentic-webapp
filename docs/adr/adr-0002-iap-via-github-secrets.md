# ADR-0002: IAP via custom OAuth client from GitHub secrets (presence-based)

**Status:** Accepted · implemented

## Context

Access control to the deployed service is Identity-Aware Proxy (IAP) on Cloud Run.
Two constraints shaped how it's configured:

1. **No GCP organization.** These projects belong to a personal Google account.
   IAP's default *Google-managed* OAuth client only works for users inside an org,
   so a no-org project must supply its **own custom OAuth client** (client id +
   secret) or IAP returns `HTTP 502 "Empty OAuth client ID/secret"`. The OAuth
   client can only be created in the Console (no API for no-org projects).
2. We initially kept the client id/secret in a gitignored `prod.tfvars`. That file
   is invisible to CI and is one more secret-bearing artifact to maintain locally.

## Decision

- **The custom OAuth client id/secret are supplied as per-environment GitHub
  Environment secrets** (`IAP_OAUTH_CLIENT_ID` / `IAP_OAUTH_CLIENT_SECRET`), passed
  to Terraform as `TF_VAR_iap_oauth_client_id` / `_secret`. `prod.tfvars` is no
  longer the source of truth for CI (it remains usable for local manual applies).
- **IAP enablement is presence-based:** `local.iap_enabled = var.enable_iap != null
  ? var.enable_iap : (var.iap_oauth_client_id != "")`. A non-empty client id ⇒ IAP
  on; empty ⇒ public. There is no per-environment policy map — supplying the client
  *is* the switch. `var.enable_iap` remains an explicit override.
- The OAuth **consent screen** + **client** creation stay a one-time manual Console
  step per project (unavoidable for no-org); everything after is automated.
- Secret **rotation** is owned by the human in GitHub Secrets (add new secret on the
  OAuth client → update the GitHub secret → redeploy → delete the old).

## Consequences

- Flipping any environment to IAP = add its OAuth client + set the two secrets on
  that GitHub Environment, then redeploy. **No code change.** (test is wired this way
  and is currently public simply because its secrets are unset.)
- Secrets live in GitHub's encrypted environment store, scoped per environment, not
  in a local file — easier to rotate and audit.
- The terraform `google_iap_settings` resource is created only when the client id is
  present, so a public environment shows no IAP resources at all.

## Lens

Make the *presence of a credential* the feature switch where it's safe to — it
removes a parallel "is it enabled?" flag that can drift out of sync with "is it
configured?". For no-org GCP + IAP, always supply a custom OAuth client; never rely
on the Google-managed one.
