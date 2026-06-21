"""Shared pydantic models — the data contracts crossing the abstraction boundaries
and the API surface."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StoredAsset(BaseModel):
    """A reference to an object in blob storage (the StorageManager's currency)."""

    key: str
    size: int | None = None
    content_type: str | None = None
    updated: datetime | None = None


class Shareable(BaseModel):
    """Mixin of RBAC sharing fields used by both assets and folders. `owner_id` is the
    pseudonymous uploader (None = legacy/unowned, visible to all); `shared_user_ids` and
    `shared_group_ids` are the principals granted access. Admins see everything."""

    owner_id: str | None = None
    shared_user_ids: list[str] = Field(default_factory=list)
    shared_group_ids: list[str] = Field(default_factory=list)


class AssetMetadata(Shareable):
    """A catalogued asset: its storage location plus descriptive metadata. The first domain
    record managed via the DatabaseManager (AssetMetadataManager)."""

    asset_id: str
    storage_key: str
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime
    # The folder the asset lives in (None = root). Files inherit their folder's sharing.
    folder_id: str | None = None
    # Arbitrary, app-defined key/values. Kept generic on purpose.
    tags: dict[str, str] = Field(default_factory=dict)


class Folder(Shareable):
    """A real (named) folder in the Asset Manager. Folders nest via parent_id and carry
    their own sharing; contained assets (and sub-folders) inherit folder access."""

    folder_id: str
    name: str
    parent_id: str | None = None
    created_at: datetime


class Group(BaseModel):
    """A custom group of users (admin-managed). Assets/folders can be shared with a group;
    a member then inherits that access. member_ids are pseudonymous user_ids."""

    group_id: str
    name: str
    member_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class SignedUrlResponse(BaseModel):
    """A time-limited URL the frontend can use to fetch an asset directly."""

    asset_id: str
    url: str
    expires_in_seconds: int


class LlmUsageRecord(BaseModel):
    """One itemised LLM call for the bookkeeping inventory: who, when, which model,
    how many tokens, and the estimated cost. Written by the agent's ADK callback,
    read by the backend admin panel."""

    request_id: str
    app_name: str
    user_id: str
    session_id: str
    model_id: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    est_cost_usd: float = 0.0
    timestamp: datetime


class ExtractionRecord(BaseModel):
    """One structured-data extraction pulled from an asset by an agent tool — the
    common envelope for the 'extract from a document' tool category. `doc_type` plus
    the free-form `fields` payload is the extensible seam: a new extraction type (fuel
    receipt, invoice, business card, …) is a new `doc_type` + `fields` shape, never a
    schema change. Persisted via ExtractionManager to the same DatabaseManager backend
    as the rest of the analytics tables (in-memory locally, Firestore/BigQuery in cloud)."""

    extraction_id: str
    asset_id: str
    doc_type: str
    user_id: str
    session_id: str
    # The type-specific extracted key/values; serialised to fields_json at the row layer.
    fields: dict[str, Any] = Field(default_factory=dict)
    model_id: str | None = None
    created_at: datetime


# ============================================================================
# Semantic layer — the top-down logical data model over the warehouse.
#
# The SemanticManager is the bridge between a human-described "Domain Model" and the
# physical tables that dbt materialises in BigQuery. You describe the domain ONCE, in
# business terms (entities, the things you measure, the ways you slice them); dbt makes
# the physical models real; agents and dashboards query the *semantic* layer, never raw
# SQL. This is the data→insight contract; the AnalyticsManager owns the insight→pixels
# contract (DashboardSpec below).
# ============================================================================

AggFn = Literal["sum", "avg", "count", "count_distinct", "min", "max"]
DimType = Literal["categorical", "time", "numeric", "boolean"]
TimeGrain = Literal["day", "week", "month", "quarter", "year"]
FilterOp = Literal["=", "!=", ">", ">=", "<", "<=", "in", "like"]


class SemanticDimension(BaseModel):
    """A way to slice an entity — a groupable attribute. `column` is the physical column
    in the entity's table; `dtype` marks time dimensions (which support a grain)."""

    name: str
    column: str
    dtype: DimType = "categorical"
    description: str = ""


class SemanticMeasure(BaseModel):
    """A thing you measure — a quantitative aggregation over a column. The atom of every
    metric. `column` is the physical column to aggregate ("*" for a row count)."""

    name: str
    column: str = "*"
    agg: AggFn = "sum"
    description: str = ""
    # Optional display hint for the UI/dashboards (e.g. "$0,0.00", "0.0%"). Advisory only.
    unit: str = ""


class SemanticEntity(BaseModel):
    """A logical table in the domain model — one business concept (a fuel purchase, a
    maintenance event). Maps to exactly one physical table / dbt model (`table`) and
    exposes the dimensions + measures the query layer is allowed to combine."""

    name: str
    description: str = ""
    table: str
    primary_key: str | None = None
    # Name (not column) of the dimension used as the default time axis, if any.
    time_dimension: str | None = None
    dimensions: list[SemanticDimension] = Field(default_factory=list)
    measures: list[SemanticMeasure] = Field(default_factory=list)


class SemanticModel(BaseModel):
    """The top-down logical data model for one domain: a named set of entities with their
    dimensions and measures. Authored in the SemanticManager page, implemented physically
    by the dbt sidecar, queried by agents over MCP and by the dashboard suite."""

    model_id: str
    name: str
    description: str = ""
    entities: list[SemanticEntity] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SemanticFilter(BaseModel):
    """A predicate on a dimension/column. `value` is a scalar (or list, for `in`)."""

    field: str
    op: FilterOp = "="
    value: Any = None


class SemanticQuery(BaseModel):
    """A backend-agnostic analytical question against one entity: which measures to
    aggregate, grouped by which dimensions, optionally filtered and time-grained. The
    SemanticManager compiles this to BigQuery SQL (transparency / dbt parity) AND executes
    it portably (in-memory aggregation locally, SQL push-down on BigQuery)."""

    entity: str
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[SemanticFilter] = Field(default_factory=list)
    time_grain: TimeGrain | None = None
    order_by: str | None = None
    descending: bool = True
    limit: int = 1000


class SemanticQueryResult(BaseModel):
    """The answer to a SemanticQuery: column-ordered tabular rows plus the compiled SQL so
    a human (or agent) can see exactly what was run."""

    columns: list[str]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    sql: str = ""
    row_count: int = 0


# ============================================================================
# dbt sidecar — typed views of the dbt-core project the sidecar manages.
# These are response shapes the backend proxies from the dbt sidecar service; the dbt
# project itself is the source of truth (see dbt/ at the repo root).
# ============================================================================


class DbtModelInfo(BaseModel):
    """One node in the dbt project (a model/seed/source/test), distilled from `dbt ls`
    + the manifest so the webapp can render the project without parsing dbt internals."""

    name: str
    resource_type: str = "model"
    db_schema: str = ""
    materialized: str = ""
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    path: str = ""


class DbtRunResult(BaseModel):
    """The outcome of a dbt command (run/test/build/compile). `nodes` are per-model results
    parsed from dbt's run_results.json; stdout/stderr are kept for the UI log panel."""

    command: str
    success: bool
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    elapsed_seconds: float = 0.0


# ============================================================================
# Dashboards — the AnalyticsManager's insight→pixels contract.
# A chart binds a SemanticQuery (data) to a Plotly figure template (pixels); `encoding`
# is the JSON that maps result columns onto Plotly trace fields. Rendered in the web
# dashboard suite AND inline in agent chat via MCP-UI.
# ============================================================================

ChartType = Literal["bar", "line", "area", "scatter", "pie", "table", "kpi"]


class DashboardChart(BaseModel):
    """One chart: a semantic query whose result columns are projected onto a Plotly figure.
    `encoding` is the Data→Pixels map (e.g. {"x":"month","y":"total_cost"}); `layout`
    holds Plotly layout overrides (titles, axis formats)."""

    chart_id: str
    title: str
    description: str = ""
    chart_type: ChartType = "bar"
    query: SemanticQuery
    encoding: dict[str, str] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)


class DashboardSpec(BaseModel):
    """A page of charts curated by the AnalyticsManager — the tangible 'dashboard transform'
    the frontend loads and the MCP renders inline. Each chart binds to a SemanticQuery, so
    a dashboard is always backed by the logical data model, never hand-written SQL."""

    dashboard_id: str
    name: str
    description: str = ""
    semantic_model_id: str | None = None
    charts: list[DashboardChart] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
