"""DashboardManager — the AnalyticsManager's insight→pixels store.

A dashboard is a curated page of charts; each chart binds a SemanticQuery (data) to a
Plotly figure template (pixels). This manager only persists the *specs* — rendering and
query execution happen at read time (web dashboard suite, MCP-UI inline) by running each
chart's SemanticQuery through the SemanticManager and projecting the result onto Plotly
via the chart's `encoding`. Storage mirrors the other managers: one row per dashboard, the
charts serialised to a `charts_json` column.
"""

from __future__ import annotations

import json

from ..models import DashboardChart, DashboardSpec
from .base import DatabaseManager, Row


class DashboardNotFoundError(KeyError):
    """Raised when a dashboard id does not exist."""


class DashboardManager:
    def __init__(self, db: DatabaseManager, *, table: str = "dashboards") -> None:
        self._db = db
        self._table = table

    async def create(self, dashboard: DashboardSpec) -> DashboardSpec:
        await self._db.insert(self._table, [self._to_row(dashboard)])
        return dashboard

    async def get(self, dashboard_id: str) -> DashboardSpec | None:
        row = await self._db.get(self._table, key_field="dashboard_id", key=dashboard_id)
        return self._from_row(row) if row else None

    async def list(self, *, limit: int = 100) -> list[DashboardSpec]:
        rows = await self._db.list(self._table, limit=limit, order_by="updated_at")
        return [self._from_row(r) for r in rows]

    async def update(self, dashboard: DashboardSpec) -> DashboardSpec:
        await self._db.delete(self._table, key_field="dashboard_id", key=dashboard.dashboard_id)
        await self._db.insert(self._table, [self._to_row(dashboard)])
        return dashboard

    async def delete(self, dashboard_id: str) -> None:
        await self._db.delete(self._table, key_field="dashboard_id", key=dashboard_id)

    @staticmethod
    def _to_row(d: DashboardSpec) -> Row:
        return {
            "dashboard_id": d.dashboard_id,
            "name": d.name,
            "description": d.description,
            "semantic_model_id": d.semantic_model_id,
            "charts_json": json.dumps([c.model_dump() for c in d.charts]),
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: Row) -> DashboardSpec:
        raw = row.get("charts_json")
        charts = [DashboardChart.model_validate(c) for c in (json.loads(raw) if raw else [])]
        return DashboardSpec(
            dashboard_id=row["dashboard_id"],
            name=row["name"],
            description=row.get("description") or "",
            semantic_model_id=row.get("semantic_model_id"),
            charts=charts,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
