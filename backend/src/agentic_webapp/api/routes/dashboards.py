"""Dashboards API — the AnalyticsManager's curated data→pixels artifacts.

CRUD of DashboardSpecs plus the key read: ``/render`` runs every chart's SemanticQuery
through the SemanticManager and projects each result onto a Plotly figure (see figures.py).
That single payload is what the web dashboard suite renders and what the inline MCP-UI
dashboard tool embeds — both bound to the logical data model, never to hand-written SQL.
Area-gated (``dashboards``) in main.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from agentic_core.database import DashboardManager, SemanticManager, SemanticQueryError
from agentic_core.models import DashboardChart, DashboardSpec, SemanticQueryResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...figures import build_figure, kpi_value
from ..deps import get_dashboard_manager, get_semantic_manager

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])

DashboardDep = Annotated[DashboardManager, Depends(get_dashboard_manager)]
SemanticDep = Annotated[SemanticManager, Depends(get_semantic_manager)]


class DashboardUpsert(BaseModel):
    name: str
    description: str = ""
    semantic_model_id: str | None = None
    charts: list[DashboardChart] = Field(default_factory=list)


class ChartRender(BaseModel):
    """One rendered chart: the Plotly figure + (for KPIs) the single value + the raw result."""

    chart_id: str
    title: str
    chart_type: str
    figure: dict[str, Any]
    value: float | None = None
    result: SemanticQueryResult
    error: str | None = None


class DashboardRender(BaseModel):
    """A dashboard with every chart resolved to pixels — the dashboard transform the UI loads."""

    dashboard_id: str
    name: str
    description: str
    semantic_model_id: str | None
    charts: list[ChartRender]


@router.get("", response_model=list[DashboardSpec])
async def list_dashboards(manager: DashboardDep) -> list[DashboardSpec]:
    return await manager.list()


@router.get("/{dashboard_id}", response_model=DashboardSpec)
async def get_dashboard(dashboard_id: str, manager: DashboardDep) -> DashboardSpec:
    spec = await manager.get(dashboard_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    return spec


@router.post("", response_model=DashboardSpec, status_code=201)
async def create_dashboard(body: DashboardUpsert, manager: DashboardDep) -> DashboardSpec:
    now = datetime.now(timezone.utc)
    spec = DashboardSpec(
        dashboard_id=uuid4().hex, name=body.name, description=body.description,
        semantic_model_id=body.semantic_model_id, charts=body.charts, created_at=now, updated_at=now,
    )
    return await manager.create(spec)


@router.put("/{dashboard_id}", response_model=DashboardSpec)
async def update_dashboard(dashboard_id: str, body: DashboardUpsert, manager: DashboardDep) -> DashboardSpec:
    existing = await manager.get(dashboard_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    spec = DashboardSpec(
        dashboard_id=dashboard_id, name=body.name, description=body.description,
        semantic_model_id=body.semantic_model_id, charts=body.charts,
        created_at=existing.created_at, updated_at=datetime.now(timezone.utc),
    )
    return await manager.update(spec)


@router.delete("/{dashboard_id}", status_code=204)
async def delete_dashboard(dashboard_id: str, manager: DashboardDep) -> None:
    await manager.delete(dashboard_id)


@router.get("/{dashboard_id}/render", response_model=DashboardRender)
async def render_dashboard(dashboard_id: str, dashboards: DashboardDep, semantic: SemanticDep) -> DashboardRender:
    """Run every chart's query and project it to a Plotly figure. A chart whose query fails
    (e.g. its model was deleted) renders with an `error` instead of taking the page down."""
    spec = await dashboards.get(dashboard_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    model = await semantic.get_model(spec.semantic_model_id) if spec.semantic_model_id else None

    rendered: list[ChartRender] = []
    for chart in spec.charts:
        if model is None:
            rendered.append(ChartRender(
                chart_id=chart.chart_id, title=chart.title, chart_type=chart.chart_type,
                figure={"data": [], "layout": {}}, result=SemanticQueryResult(columns=[]),
                error="dashboard has no semantic model",
            ))
            continue
        try:
            result = await semantic.run_query(model, chart.query)
            rendered.append(ChartRender(
                chart_id=chart.chart_id, title=chart.title, chart_type=chart.chart_type,
                figure=build_figure(chart, result), value=kpi_value(chart, result), result=result,
            ))
        except SemanticQueryError as exc:
            rendered.append(ChartRender(
                chart_id=chart.chart_id, title=chart.title, chart_type=chart.chart_type,
                figure={"data": [], "layout": {}}, result=SemanticQueryResult(columns=[]), error=str(exc),
            ))
    return DashboardRender(
        dashboard_id=spec.dashboard_id, name=spec.name, description=spec.description,
        semantic_model_id=spec.semantic_model_id, charts=rendered,
    )
