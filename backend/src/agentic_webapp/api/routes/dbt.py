"""dbt API — manage the dbt-core project/sidecar from the webapp.

Thin proxy over the injected DbtClient (HTTP sidecar in cloud, filesystem locally). Lists the
project's models and runs dbt commands (run/test/build/compile). Area-gated (``dbt``) in
main.py; like every /api/* route it also auto-projects as MCP tools.
"""

from __future__ import annotations

from typing import Annotated, Any

from agentic_core.models import DbtGantt, DbtInvocation, DbtModelInfo, DbtRunResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...services import DbtClient
from ..deps import get_dbt_client

router = APIRouter(prefix="/api/dbt", tags=["dbt"])

DbtDep = Annotated[DbtClient, Depends(get_dbt_client)]


class DbtRunRequest(BaseModel):
    """Optional dbt node selector, e.g. "staging" or "fct_fuel_purchases+"."""

    select: str | None = None


@router.get("/project")
async def project(client: DbtDep) -> dict[str, Any]:
    """Project metadata + its models (name, profile, target, dbt_cli_available, models[])."""
    return await client.project()


@router.get("/models", response_model=list[DbtModelInfo])
async def models(client: DbtDep) -> list[DbtModelInfo]:
    """The models/seeds/sources discovered in the dbt project."""
    return await client.list_models()


@router.post("/run", response_model=DbtRunResult)
async def run(body: DbtRunRequest, client: DbtDep) -> DbtRunResult:
    """`dbt run` — materialise the models into the warehouse."""
    return await client.run(select=body.select)


@router.post("/test", response_model=DbtRunResult)
async def test(body: DbtRunRequest, client: DbtDep) -> DbtRunResult:
    """`dbt test` — run the project's data tests."""
    return await client.test(select=body.select)


@router.post("/build", response_model=DbtRunResult)
async def build(body: DbtRunRequest, client: DbtDep) -> DbtRunResult:
    """`dbt build` — run + test in dependency order."""
    return await client.build(select=body.select)


@router.post("/compile", response_model=DbtRunResult)
async def compile_project(body: DbtRunRequest, client: DbtDep) -> DbtRunResult:
    """`dbt compile` — compile SQL without touching the warehouse."""
    return await client.compile(select=body.select)


@router.get("/observability/invocations", response_model=list[DbtInvocation])
async def invocations(client: DbtDep, days: int = 30) -> list[DbtInvocation]:
    """Recent dbt runs from Elementary metadata — the observability overview (one point/run)."""
    return await client.invocations(days=days)


@router.get("/observability/invocations/{invocation_id}", response_model=DbtGantt)
async def gantt(invocation_id: str, client: DbtDep) -> DbtGantt:
    """One run's per-node execution timeline (Elementary `dbt_run_results`) for the gantt."""
    return await client.gantt(invocation_id)
