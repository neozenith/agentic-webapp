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
| [0006](adr-0006-assets-single-source-of-truth.md) | Assets have a single source of truth (no ADK artifact store) | Accepted · implemented |
| [0007](adr-0007-rbac-areas-and-personas.md) | RBAC: role-gated areas + non-prod test personas | Accepted · implemented |
| [0008](adr-0008-folders-groups-unified-sharing.md) | Folders, groups, unified file/folder sharing | Accepted · implemented |
| [0009](adr-0009-theming-and-live-brandpacks.md) | Dark/light theming + live brandpack design tokens | Accepted · implemented |
| [0010](adr-0010-agent-web-search-grounding.md) | Agent web-search grounding via an AgentTool sub-agent | Accepted · implemented |
| [0011](adr-0011-core-api-mcp-and-cli.md) | Core API is the hub; MCP, CLI, and agent are interfaces to it | Accepted · implemented |

## Format

```
# ADR-NNNN: Title
Status · Context · Decision · Consequences · Lens
```
