# agentic-webapp CLI

A thin terminal client for the core API. It is **one interface among several** — the SPA, the
MCP server, and the agent all hit the same `/api/*` surface — and it is deliberately dumb about
authorization: it forwards a persona as the IAP identity header (`--as`) and lets the server's
one RBAC engine decide. That makes RBAC simulation a single flag.

## What it does NOT do

This is the negative space, and it is load-bearing:

| It does NOT… | Because… |
|--------------|----------|
| enforce any RBAC locally | the server is the single source of truth; the CLI only forwards identity (`--as`) |
| manage real auth tokens | identity is the simulated IAP header ([ADR-0004](../docs/adr/adr-0004-user-identity-and-simulation.md)); in prod IAP sets it |
| vendor the API's data models | the OpenAPI spec is the contract; the CLI reads server JSON and stays schema-light |
| cache anything | every command is a live call — what you see is the server's current state |

## Quickstart

You will want the backend running first (in-memory backends, identity simulation on):

```sh
make -C backend dev                 # API at http://localhost:8080, in another shell
```

Then drive it as a persona. `--as` picks who you are; `--json` swaps the table for raw JSON:

```sh
uv run --directory cli -m agentic_cli personas --as ada.admin@example.com
```

Output:

```
email                      name             roles
-------------------------  ---------------  --------
ada.admin@example.com      Ada — Admin      admin
nina.analyst@example.com   Nina — Analyst   analyst
otto.operator@example.com  Otto — Operator  operator
vera.viewer@example.com    Vera — Viewer    viewer

(4 rows)
```

RBAC simulation is the same persona, a different outcome — a viewer is refused server-side:

```sh
uv run --directory cli -m agentic_cli admin users --as vera.viewer@example.com
```

Output:

```
error: forbidden: 'admin' requires a role you don't have (HTTP 403)
```

That command exits `1`. Usage errors exit `2`; success exits `0`.

## Commands

`--base-url`, `--as EMAIL`, and `--json` are global and accepted in any position.

| Group | Commands | Notes |
|-------|----------|-------|
| (top) | `me`, `personas`, `directory` | who you are, who you can be, the id→name map |
| `assets` | `list`, `get`, `url`, `upload`, `move`, `share`, `combine`, `delete` | visibility-scoped; only owner/admin may move/share/delete |
| `folders` | `list`, `create`, `share`, `delete` | sharing cascades to contained assets |
| `groups` | `list` | public discovery (id + name only) |
| `admin` | `users`, `usage`, `usage-records`, `sessions`, `group-create`, `group-delete` | **admin role only — else 403** |
| `analytics` | `summary`, `extractions` | **analyst or admin only — else 403** |

Sharing takes emails for users and ids for groups, applied as deltas:

```sh
uv run --directory cli -m agentic_cli assets share <asset_id> \
  --add-user nina.analyst@example.com --add-group <group_id> --as ada.admin@example.com
```

## Quality

`make -C cli ci` runs lint + strict types + tests. The tests boot the **real** backend
in-process (via `agentic_webapp.testing.live_backend`) and drive the CLI over HTTP — no mocks,
so RBAC is exercised end to end. Coverage gate is 90%.

----

For the design rationale — why the API is the hub and every client a spoke — see
[ADR-0011](../docs/adr/adr-0011-core-api-mcp-and-cli.md).
