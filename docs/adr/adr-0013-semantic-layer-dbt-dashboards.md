# ADR-0013: Top-down data modelling — semantic layer, dbt sidecar, dashboards

**Status:** Accepted · implemented

## Context

The analytics axis (ADR: AnalyticsManager on its own BigQuery backend) gave us raw
extractions and a discovered-schema summary, but nothing turned a human's description of a
domain into queryable, charted insight. The scaffold's promise is that someone clones the
repo and *vibe-codes their way to their own domain model* — so the modelling flow has to be
**top-down** (describe the domain in business terms first) and the physical implementation
has to follow, not the other way round.

The worked example is one sentence: *"I track fuel receipts and odometer readings every
refuel, plus maintenance expenses; I want average yearly cost and a forecast."* That has to
decompose into: a logical data model, physical tables, a queryable layer for agents, and
dashboards — each a guard-railed seam someone can re-point at their own domain.

## Decision

Add three layers, each a manager composed over the existing `DatabaseManager` (the same
pattern as AnalyticsManager), all on the shared **analytics** backend axis (one BigQuery
dataset in cloud, one in-memory store locally — `deps.get_analytics_database()` is the single
shared handle so a seeded fact table is visible to every reader):

1. **SemanticManager** (`libs/core/.../database/semantic.py`) — the logical data model. A
   `SemanticModel` is entities → dimensions (ways to slice) + measures (things to count). A
   `SemanticQuery` is backend-agnostic and runs two ways from one definition: **SQL push-down**
   when the backend `supports_sql` (BigQuery), **in-process aggregation** otherwise (local /
   tests). Both return the identical result *and the compiled SQL* for transparency. This is a
   capability axis, never a fallback that drops requirements (escalators-not-stairs).

2. **dbt-core sidecar** (`dbt/`) — a real dbt project (staging → marts for the fuel domain)
   plus a thin FastAPI service wrapping the dbt CLI. The backend reaches it through a
   `DbtClient` interface: `HttpDbtClient` to the sidecar in cloud/compose, `FilesystemDbtClient`
   locally (lists models offline; runs dbt when the CLI is present). The dbt marts' output
   columns are the **contract** the SemanticModel's physical columns bind to.

3. **DashboardManager + figures** (`dashboards.py`, `figures.py`) — a `DashboardChart` binds a
   `SemanticQuery` (data) to a Plotly figure via an `encoding` map (the Data→Pixels JSON).
   `/api/dashboards/{id}/render` runs every chart's query and projects it to a figure; the web
   dashboard suite renders it with react-plotly, and the inline MCP-UI `dashboard` tool embeds
   the *same* figures in a sandboxed iframe (ADR-0012 pattern). One renderer, two surfaces.

All three are plain `/api/*` routes, so they **auto-project as MCP tools** (ADR-0011): the
"queryable semantic layer in MCP" is `semantic_query` for free, with the same RBAC as REST.
New RBAC areas `semantic`/`dbt` (analyst+admin authoring) and `dashboards` (read-broad).

The fuel-tracking domain ships as a deletable **seed** (`seed.py`): the SemanticModel, two
dashboards, and sample rows — the template a new user replaces with their own domain.

## Consequences

- **Tailoring is top-down and guard-railed.** See `.claude/rules/data_modelling.md`: describe
  entities/measures → write dbt marts with matching columns → curate dashboards. The seed is
  the worked reference; delete it and seed your own.
- **The dbt↔semantic contract is column names.** A mart rename must be matched in the
  SemanticModel `entity.table`/dimension/measure `column`s, or a query 400s. Tests assert the
  seeded dashboards' queries all resolve against the seeded columns — that catches drift.
- **dbt on Cloud Run is request-scaled.** The sidecar is fine for first-pass review (UI-triggered
  `dbt run` completes within the proxied request); a Cloud Run Job is the longer-term primitive
  for scheduled/batch builds. Noted in `cloudrun.tf`.
- **Local works with zero cloud.** In-memory analytics + the seed mean the semantic page,
  dashboards, and MCP tools all work offline; the dbt page lists models offline and reports the
  CLI honestly instead of pretending a run happened.
