# `libs/core` — agentic-core

Shared cloud primitives consumed by **both** `backend/` and `agent/`:

- **`agentic_core.storage`** — `StorageManager` ABC + `GCSStorageManager` / `InMemoryStorageManager`.
- **`agentic_core.database`** — `DatabaseManager` ABC + `BigQueryDatabaseManager` / `InMemoryDatabaseManager`, and `AssetMetadataManager`.
- **`agentic_core.models`** — shared pydantic models.

## Consumed via editable path dependency (no uv workspace)

Each service depends on this lib by relative path so it can build its **own** image
with its **own** lockfile — there is no shared root venv/lockfile to drag into every
Docker context. In `backend/pyproject.toml` (and `agent/`):

```toml
dependencies = ["agentic-core", ...]

[tool.uv.sources]
agentic-core = { path = "../libs/core", editable = true }
```

`uv sync` then installs `agentic-core` editable from `../libs/core`; edits here are
picked up live. In each service's Dockerfile, copy `libs/core` into the build
context alongside the service before `uv sync --frozen`.

> Why not a uv *workspace*? A workspace centralises one lockfile/venv across members —
> great when you build+deploy them together, awkward when each service is its own
> container image. Path deps keep the services independently buildable.

## Test

```bash
uv run --directory libs/core pytest -q
```
