"""Pydantic response/request models — the HTTP contract the backend integrates against."""

from typing import Any

from pydantic import BaseModel, Field


class DbtModelInfo(BaseModel):
    """One dbt model, as surfaced to the webapp's dbt page."""

    name: str
    resource_type: str = "model"
    db_schema: str
    materialized: str
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    path: str


class DbtProjectInfo(BaseModel):
    """Project-level metadata plus the full model list."""

    name: str
    profile: str
    version: str
    target: str
    project_dir: str
    dbt_cli_available: bool
    model_count: int
    models: list[DbtModelInfo]


class DbtRunResult(BaseModel):
    """Outcome of a `dbt run|test|build|compile` invocation."""

    command: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    nodes: list[dict[str, Any]]
    elapsed_seconds: float


class RunRequest(BaseModel):
    """Body for the run/test/build/compile endpoints; `select` is a dbt node selector."""

    select: str | None = None


class HealthResponse(BaseModel):
    """Liveness probe payload."""

    status: str = "ok"


class ObservabilityInvocation(BaseModel):
    """One dbt invocation as surfaced by GET /observability/invocations."""

    invocation_id: str
    command: str
    run_started_at: str | None
    run_completed_at: str | None
    target_name: str
    dbt_version: str
    n_nodes: int
    wall_secs: float
    has_failures: bool


class GanttNode(BaseModel):
    """One node (model/test/...) on an invocation's gantt timeline."""

    thread_id: str
    node_id: str
    name: str
    resource_type: str
    status: str
    start_offset_secs: float
    duration_secs: float


class GanttResponse(BaseModel):
    """Per-invocation gantt: thread lanes plus offset-positioned nodes."""

    invocation_id: str
    wall_secs: float
    threads: list[str]
    nodes: list[GanttNode]
