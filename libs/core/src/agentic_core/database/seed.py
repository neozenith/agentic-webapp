"""Seed the fuel-receipt domain — the worked example that ships with the scaffold.

This is the concrete instance of the top-down modelling flow: a plain-English domain
("I track fuel receipts and odometer readings every refuel, plus maintenance expenses;
I want average yearly cost and a forecast") turned into a SemanticModel, two curated
DashboardSpecs, and deterministic sample rows in the warehouse tables that dbt would
otherwise materialise. Anyone cloning the repo deletes this and seeds their own domain —
it is a template, not a fixture the code depends on.

The physical tables seeded here (``fct_fuel_purchases``, ``fct_maintenance``) mirror the
dbt marts in ``dbt/models/marts``; locally they are populated in-memory so the dashboards,
the semantic query layer, and the MCP tests all work with zero cloud config.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import (
    DashboardChart,
    DashboardSpec,
    SemanticDimension,
    SemanticEntity,
    SemanticMeasure,
    SemanticModel,
    SemanticQuery,
)
from .base import DatabaseManager
from .dashboards import DashboardManager
from .semantic import SemanticManager

FUEL_MODEL_ID = "fuel_tracking"
FUEL_FACT_TABLE = "fct_fuel_purchases"
MAINT_FACT_TABLE = "fct_maintenance"

_STATIONS = ["Shell", "BP", "Caltex", "7-Eleven"]
_FUEL_TYPES = ["unleaded_91", "premium_95", "diesel"]
_MAINT = [
    ("service", "MyMechanic", 320.0),
    ("tyres", "TyrePlus", 880.0),
    ("brakes", "MyMechanic", 540.0),
    ("registration", "Gov", 865.0),
    ("battery", "AutoParts", 210.0),
]


def fuel_semantic_model(*, now: datetime | None = None) -> SemanticModel:
    """The logical data model for the fuel-tracking domain: two entities (a refuel event
    and a maintenance event), each with its dimensions (ways to slice) and measures
    (things to count)."""
    now = now or datetime.now(timezone.utc)
    fuel = SemanticEntity(
        name="fuel_purchases",
        description="One refuel event: how much fuel, what it cost, and the odometer reading.",
        table=FUEL_FACT_TABLE,
        primary_key="purchase_id",
        time_dimension="purchased_at",
        dimensions=[
            SemanticDimension(name="purchased_at", column="purchased_at", dtype="time",
                              description="When the car was refuelled."),
            SemanticDimension(name="vehicle", column="vehicle", description="The vehicle refuelled."),
            SemanticDimension(name="station", column="station", description="The fuel station / brand."),
            SemanticDimension(name="fuel_type", column="fuel_type", description="Grade of fuel purchased."),
        ],
        measures=[
            SemanticMeasure(name="total_cost", column="total_cost", agg="sum", unit="$0,0.00",
                            description="Total spent on fuel."),
            SemanticMeasure(name="litres", column="litres", agg="sum", unit="0,0.0",
                            description="Litres of fuel purchased."),
            SemanticMeasure(name="avg_price_per_litre", column="price_per_litre", agg="avg", unit="$0.000",
                            description="Average pump price per litre."),
            SemanticMeasure(name="distance_km", column="distance_km", agg="sum", unit="0,0",
                            description="Kilometres driven since the previous fill."),
            SemanticMeasure(name="fill_count", column="*", agg="count",
                            description="Number of refuel events."),
        ],
    )
    maint = SemanticEntity(
        name="maintenance",
        description="One maintenance / running-cost event for the vehicle.",
        table=MAINT_FACT_TABLE,
        primary_key="maintenance_id",
        time_dimension="serviced_at",
        dimensions=[
            SemanticDimension(name="serviced_at", column="serviced_at", dtype="time",
                              description="When the work was done."),
            SemanticDimension(name="vehicle", column="vehicle", description="The vehicle serviced."),
            SemanticDimension(name="category", column="category", description="Type of maintenance."),
            SemanticDimension(name="vendor", column="vendor", description="Who did the work."),
        ],
        measures=[
            SemanticMeasure(name="total_cost", column="total_cost", agg="sum", unit="$0,0.00",
                            description="Total maintenance spend."),
            SemanticMeasure(name="event_count", column="*", agg="count",
                            description="Number of maintenance events."),
        ],
    )
    return SemanticModel(
        model_id=FUEL_MODEL_ID,
        name="Fuel & Vehicle Costs",
        description=(
            "Track fuel receipts and odometer readings at every refuel, plus maintenance "
            "expenses, to monitor average yearly running cost and forecast what is coming."
        ),
        entities=[fuel, maint],
        created_at=now,
        updated_at=now,
    )


def fuel_dashboards(*, now: datetime | None = None) -> list[DashboardSpec]:
    """Two curated dashboards over the fuel model — the AnalyticsManager 'data→pixels'
    artifacts the dashboard suite renders and the agent shows inline."""
    now = now or datetime.now(timezone.utc)
    overview = DashboardSpec(
        dashboard_id="fuel-overview",
        name="Fuel Cost Overview",
        description="Spend, volume and pump price for fuel over time.",
        semantic_model_id=FUEL_MODEL_ID,
        charts=[
            DashboardChart(
                chart_id="kpi-total-spend", title="Total fuel spend", chart_type="kpi",
                query=SemanticQuery(entity="fuel_purchases", measures=["total_cost"]),
                encoding={"value": "total_cost"}, layout={"unit": "$0,0.00"},
            ),
            DashboardChart(
                chart_id="monthly-spend", title="Monthly fuel spend", chart_type="line",
                query=SemanticQuery(entity="fuel_purchases", measures=["total_cost"],
                                    time_grain="month", order_by="purchased_at", descending=False),
                encoding={"x": "purchased_at", "y": "total_cost"},
                layout={"yaxis": {"title": "Spend ($)"}, "xaxis": {"title": "Month"}},
            ),
            DashboardChart(
                chart_id="spend-by-station", title="Spend by station", chart_type="bar",
                query=SemanticQuery(entity="fuel_purchases", measures=["total_cost"],
                                    dimensions=["station"]),
                encoding={"x": "station", "y": "total_cost"},
                layout={"yaxis": {"title": "Spend ($)"}},
            ),
            DashboardChart(
                chart_id="avg-price-trend", title="Average pump price per litre", chart_type="line",
                query=SemanticQuery(entity="fuel_purchases", measures=["avg_price_per_litre"],
                                    time_grain="month", order_by="purchased_at", descending=False),
                encoding={"x": "purchased_at", "y": "avg_price_per_litre"},
                layout={"yaxis": {"title": "$/litre"}},
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    tco = DashboardSpec(
        dashboard_id="fuel-tco",
        name="Total Cost of Ownership",
        description="Yearly fuel and maintenance costs — the average-per-year picture.",
        semantic_model_id=FUEL_MODEL_ID,
        charts=[
            DashboardChart(
                chart_id="yearly-fuel", title="Fuel cost per year", chart_type="bar",
                query=SemanticQuery(entity="fuel_purchases", measures=["total_cost"],
                                    time_grain="year", order_by="purchased_at", descending=False),
                encoding={"x": "purchased_at", "y": "total_cost"},
                layout={"yaxis": {"title": "Fuel ($)"}},
            ),
            DashboardChart(
                chart_id="yearly-maint", title="Maintenance cost per year", chart_type="bar",
                query=SemanticQuery(entity="maintenance", measures=["total_cost"],
                                    time_grain="year", order_by="serviced_at", descending=False),
                encoding={"x": "serviced_at", "y": "total_cost"},
                layout={"yaxis": {"title": "Maintenance ($)"}},
            ),
            DashboardChart(
                chart_id="maint-by-category", title="Maintenance by category", chart_type="bar",
                query=SemanticQuery(entity="maintenance", measures=["total_cost"],
                                    dimensions=["category"]),
                encoding={"x": "category", "y": "total_cost"},
                layout={"yaxis": {"title": "Spend ($)"}},
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    return [overview, tco]


def sample_fuel_rows() -> list[dict[str, Any]]:
    """Deterministic fuel facts: ~2 fills/month across 2024-2025, one vehicle. Mirrors the
    columns of the dbt mart ``fct_fuel_purchases``."""
    rows: list[dict[str, Any]] = []
    odometer = 42_000
    n = 0
    for year in (2024, 2025):
        for month in range(1, 13):
            for half in (5, 20):
                n += 1
                litres = 38.0 + (n % 7) * 1.5
                # Pump price drifts up over time with small monthly wobble.
                price = 1.72 + (year - 2024) * 0.18 + month * 0.006 + (half == 20) * 0.02
                distance = 480 + (n % 5) * 40
                odometer += distance
                rows.append({
                    "purchase_id": f"fp_{year}{month:02d}{half:02d}",
                    "purchased_at": f"{year}-{month:02d}-{half:02d}",
                    "vehicle": "Mazda CX-5",
                    "station": _STATIONS[n % len(_STATIONS)],
                    "fuel_type": _FUEL_TYPES[n % len(_FUEL_TYPES)],
                    "litres": round(litres, 2),
                    "price_per_litre": round(price, 3),
                    "total_cost": round(litres * price, 2),
                    "odometer_km": odometer,
                    "distance_km": distance,
                })
    return rows


def sample_maintenance_rows() -> list[dict[str, Any]]:
    """Deterministic maintenance facts across 2024-2025. Mirrors dbt mart ``fct_maintenance``."""
    rows: list[dict[str, Any]] = []
    n = 0
    for year in (2024, 2025):
        for i, (category, vendor, base) in enumerate(_MAINT):
            n += 1
            month = (i * 2 + 2) % 12 + 1
            rows.append({
                "maintenance_id": f"mx_{year}_{category}",
                "serviced_at": f"{year}-{month:02d}-15",
                "vehicle": "Mazda CX-5",
                "category": category,
                "vendor": vendor,
                "total_cost": round(base + (year - 2024) * 35 + n * 5, 2),
            })
    return rows


async def seed_fuel_domain(
    *,
    db: DatabaseManager,
    semantic_table: str = "semantic_models",
    dashboard_table: str = "dashboards",
    now: datetime | None = None,
) -> None:
    """Idempotently seed the fuel model, dashboards, and sample warehouse rows into `db`.

    Used by the local/dev bootstrap and the test fixtures. Only writes a record type if it
    is currently empty, so re-running on a populated store is a no-op. Skips the raw-SQL
    backends (BigQuery) — there the dbt sidecar and Terraform own the physical tables."""
    if db.supports_sql:  # pragma: no cover — cloud tables owned by dbt/Terraform
        return
    now = now or datetime.now(timezone.utc)

    existing_models = await db.list(semantic_table, limit=1)
    if not existing_models:
        await db.insert(semantic_table, [_model_row(fuel_semantic_model(now=now))])

    existing_dash = await db.list(dashboard_table, limit=1)
    if not existing_dash:
        await db.insert(dashboard_table, [_dashboard_row(d) for d in fuel_dashboards(now=now)])

    if not await db.list(FUEL_FACT_TABLE, limit=1):
        await db.insert(FUEL_FACT_TABLE, sample_fuel_rows())
    if not await db.list(MAINT_FACT_TABLE, limit=1):
        await db.insert(MAINT_FACT_TABLE, sample_maintenance_rows())


def _model_row(model: SemanticModel) -> dict[str, Any]:
    return SemanticManager._to_row(model)


def _dashboard_row(dashboard: DashboardSpec) -> dict[str, Any]:
    return DashboardManager._to_row(dashboard)
