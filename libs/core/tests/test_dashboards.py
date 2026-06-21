"""Contract tests for DashboardManager + the seeded fuel dashboards (in-memory, no mocks)."""

from datetime import datetime, timezone

from agentic_core.database import DashboardManager, fuel_dashboards

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_dashboard_crud_roundtrip(database, run):
    mgr = DashboardManager(database)
    [overview, tco] = fuel_dashboards(now=_NOW)
    run(mgr.create(overview))
    run(mgr.create(tco))

    got = run(mgr.get("fuel-overview"))
    assert got is not None
    assert got.name == "Fuel Cost Overview"
    assert got.semantic_model_id == "fuel_tracking"
    # charts (and their nested SemanticQuery) survive the JSON round-trip
    kpi = next(c for c in got.charts if c.chart_id == "kpi-total-spend")
    assert kpi.chart_type == "kpi"
    assert kpi.query.entity == "fuel_purchases"
    monthly = next(c for c in got.charts if c.chart_id == "monthly-spend")
    assert monthly.query.time_grain == "month"
    assert monthly.encoding == {"x": "purchased_at", "y": "total_cost"}

    ids = {d.dashboard_id for d in run(mgr.list())}
    assert ids == {"fuel-overview", "fuel-tco"}


def test_update_and_delete(database, run):
    mgr = DashboardManager(database)
    [overview, _] = fuel_dashboards(now=_NOW)
    run(mgr.create(overview))

    overview.description = "edited"
    run(mgr.update(overview))
    assert run(mgr.get("fuel-overview")).description == "edited"
    assert len(run(mgr.list())) == 1

    run(mgr.delete("fuel-overview"))
    assert run(mgr.get("fuel-overview")) is None


def test_get_missing_returns_none(database, run):
    assert run(DashboardManager(database).get("nope")) is None
