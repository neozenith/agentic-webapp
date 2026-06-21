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
