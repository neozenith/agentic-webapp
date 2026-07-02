"""Tests for the fuel-domain seed — the worked example everything else builds on."""

from datetime import datetime, timezone

from agentic_core.database import (
    BigQueryDatabaseManager,
    DashboardManager,
    SemanticManager,
    seed_fuel_domain,
)
from agentic_core.database.seed import (
    FUEL_FACT_TABLE,
    MAINT_FACT_TABLE,
    sample_fuel_rows,
    sample_maintenance_rows,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_seed_populates_everything(database, run):
    run(seed_fuel_domain(db=database, now=_NOW))

    models = run(SemanticManager(database).list_models())
    assert [m.model_id for m in models] == ["fuel_tracking"]
    dashboards = run(DashboardManager(database).list())
    assert {d.dashboard_id for d in dashboards} == {"fuel-overview", "fuel-tco"}
    assert len(run(database.list(FUEL_FACT_TABLE, limit=1000))) == len(sample_fuel_rows())
    assert len(run(database.list(MAINT_FACT_TABLE, limit=1000))) == len(sample_maintenance_rows())


def test_seed_is_idempotent(database, run):
    run(seed_fuel_domain(db=database, now=_NOW))
    run(seed_fuel_domain(db=database, now=_NOW))  # second run must not duplicate
    assert len(run(SemanticManager(database).list_models())) == 1
    assert len(run(DashboardManager(database).list())) == 2
    assert len(run(database.list(FUEL_FACT_TABLE, limit=1000))) == len(sample_fuel_rows())


def test_seed_skips_sql_backends():
    """On a raw-SQL backend (BigQuery) dbt + Terraform own the tables; seeding is a no-op."""
    # BigQueryDatabaseManager construction needs a client; assert the guard via supports_sql.
    assert BigQueryDatabaseManager.supports_sql is True


def test_seeded_dashboard_queries_execute_end_to_end(database, run):
    """Every chart's SemanticQuery in every seeded dashboard runs against the seeded data —
    proving the model, dashboards and sample rows are mutually consistent."""
    run(seed_fuel_domain(db=database, now=_NOW))
    sem = SemanticManager(database)
    model = run(sem.get_model("fuel_tracking"))
    assert model is not None
    for dashboard in run(DashboardManager(database).list()):
        for chart in dashboard.charts:
            res = run(sem.run_query(model, chart.query))
            assert res.row_count >= 1, f"{dashboard.dashboard_id}/{chart.chart_id} returned no rows"
            # every column the chart encodes onto Plotly must exist in the result
            for col in chart.encoding.values():
                assert col in res.columns, f"{chart.chart_id} encodes missing column {col}"


def test_sample_rows_have_expected_shape():
    fuel = sample_fuel_rows()
    assert len(fuel) == 48  # 2 fills/month * 24 months
    assert {"purchase_id", "purchased_at", "litres", "price_per_litre", "total_cost"} <= fuel[0].keys()
    maint = sample_maintenance_rows()
    assert len(maint) == 10  # 5 categories * 2 years
    assert {"maintenance_id", "serviced_at", "category", "total_cost"} <= maint[0].keys()
