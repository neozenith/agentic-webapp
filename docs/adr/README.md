# Architecture Decision Records

Short, durable records of the decisions that shape this project. Each ADR captures
the **context** (the forcing problem), the **decision**, its **consequences**, and a
**Lens** — a forward-looking rule to apply to the next related decision.

This project is intended as the **base for many future projects**, so the ADRs lean
toward general, reusable principles over one-off specifics.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](adr-0001-stateless-cloud-native-state.md) | Stateless servers; state in cloud-native primitives | Accepted · implemented |
| [0002](adr-0002-iap-via-github-secrets.md) | IAP via custom OAuth client from GitHub secrets (presence-based) | Accepted · implemented |
| [0003](adr-0003-environment-data-sensitivity-tiers.md) | Environment data-sensitivity tiers | Accepted · implemented |
| [0004](adr-0004-user-identity-and-simulation.md) | User identity from IAP; header simulation in non-prod | Accepted · partially implemented |
| [0005](adr-0005-local-dev-against-cloud-services.md) | Local development against cloud services | Accepted · partially implemented |

## Format

```
# ADR-NNNN: Title
Status · Context · Decision · Consequences · Lens
```
