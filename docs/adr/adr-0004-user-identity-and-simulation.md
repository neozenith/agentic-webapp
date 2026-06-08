# ADR-0004: User identity from IAP; header simulation in non-prod

**Status:** Accepted · partially implemented

## Context

When IAP is on (prod), the proxy authenticates the user and forwards their verified
identity to Cloud Run in the `X-Goog-Authenticated-User-Email` header (format
`accounts.google.com:user@example.com`). IAP **strips any client-supplied copy** of
that header before forwarding, so behind IAP it cannot be spoofed.

We want to develop and test multi-user behaviour (e.g. per-user assets) without
standing up real IAP locally or in dev — i.e. **simulate different users**.

## Decision

- **The backend derives the current user from `X-Goog-Authenticated-User-Email`**
  (parsed in `main.py`), stripping the `accounts.google.com:` prefix. This is the one
  source of identity.
- **Simulation = send that header yourself in a non-IAP environment.** Because IAP
  overwrites/strips it in prod, a client-set header is honoured only where there is
  no IAP in front (local, dev, test) — which is exactly where simulation is wanted
  and is safe (those tiers hold no sensitive data, ADR-0003).
  ```bash
  curl -H 'X-Goog-Authenticated-User-Email: accounts.google.com:alice@example.com' \
       http://localhost:8080/
  ```
- A settings flag (`trust_forwarded_user`, default on for non-prod) may gate this so
  it can be turned off if a non-prod environment ever needs to.

## Consequences

- One identity mechanism across all environments; no separate "dev auth" code path.
- Simulating a user is a header, not a login — trivial in tests and local tooling.
- Safe by construction: the only place a client can set the identity is where IAP
  isn't enforcing, and those tiers are non-sensitive by policy.

## Lens

Reuse the production identity channel for simulation instead of inventing a parallel
dev-only auth path: trust the IAP header everywhere, and let the absence of IAP in
non-prod be what makes client-supplied identity (simulation) possible — same code,
no spoofing risk where it matters.
