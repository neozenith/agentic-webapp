# ADR-0003: Environment data-sensitivity tiers

**Status:** Accepted · implemented

## Context

The three environments share the same GCP projects as the dbt platform and serve
different purposes. They need different access postures, and the team must be able to
iterate fast without authentication friction while still protecting real data.

## Decision

Each environment has an explicit data-sensitivity tier that determines its access
posture:

| Env | Access | Sensitive data | Purpose |
|-----|--------|----------------|---------|
| **dev** | public (no IAP) | **not allowed** | Fast iteration; mirrors the local loop. Treated as throwaway. |
| **test** | public today; IAP-capable | avoid | Integration/QA. Flips to IAP by adding its OAuth client secret (ADR-0002) when needed. |
| **prod** | IAP, single user (`iap_members`) | yes | Real data; only authorized identities. |

- **dev is deliberately IAP-free and must hold no sensitive data.** This is a
  standing constraint, not a temporary state — code and tests must not seed dev with
  anything confidential.
- IAP on/off is presence-based (ADR-0002), so the tier is realized by which
  environments carry an OAuth client secret.

## Consequences

- Developers get a frictionless public dev URL and local loop without auth plumbing.
- The blast radius of dev being public is bounded by the "no sensitive data" rule.
- Promotion dev → test → prod increases protection; data sensitivity must never move
  the other way (no copying prod data into dev/test).

## Lens

Tie the access posture of an environment to an explicit data-sensitivity tier, and
keep the lowest tier (dev) both frictionless **and** empty of sensitive data — the
friction you remove is only safe because there's nothing there to protect.
