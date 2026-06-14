# agentic-webapp CLI

A thin local CLI for driving the core API — one **interface** to the same backend the SPA,
the MCP server, and the agent all use. It enforces nothing itself: it forwards a chosen
persona as the IAP identity header (`--as`), and the server's RBAC decides the outcome. That
makes RBAC simulation a one-flag affair.

## Run

Start the backend (`make -C backend dev`, in-memory backends, identity simulation on), then:

```bash
uv run --directory cli -m agentic_cli me --as ada.admin@example.com
uv run --directory cli -m agentic_cli assets list --as otto.operator@example.com
uv run --directory cli -m agentic_cli admin users --as vera.viewer@example.com   # → 403, exit 1
```

`--as <email>` picks the persona (`ada.admin`, `nina.analyst`, `otto.operator`,
`vera.viewer` — see `agentic_cli personas`). `--base-url` points at another environment;
`--json` emits raw JSON instead of a table.

## Commands

| Group | Commands |
|-------|----------|
| (top) | `me`, `personas`, `directory` |
| `assets` | `list`, `get`, `url`, `upload`, `move`, `share`, `combine`, `delete` |
| `folders` | `list`, `create`, `share`, `delete` |
| `groups` | `list` (public discovery) |
| `admin` | `users`, `usage`, `usage-records`, `sessions`, `group-create`, `group-delete` (admin role) |
| `analytics` | `summary`, `extractions` (analyst/admin) |

`admin` and `analytics` are RBAC-gated server-side: the same command yields data for an
admin/analyst and a `403` (exit 1) for a viewer. `assets`/`folders` are visibility-scoped —
a persona sees only what it owns or has been shared.

## Quality

`make -C cli ci` (lint + strict types + tests). Tests boot the real backend in-process and
drive the CLI over HTTP — no mocks.
