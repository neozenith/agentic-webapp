"""Tests for the Consulting Engagement worked domain — model, dashboards, sample marts, and
that every seeded dashboard query resolves against the seeded columns (the dbt↔semantic
contract net). In-memory, no mocks."""

from datetime import datetime, timezone

from agentic_core.database import (
    CONSULTING_MODEL_ID,
    DashboardManager,
    SemanticManager,
    seed_consulting_domain,
)
from agentic_core.database.seed_consulting import (
    ENGAGEMENTS_TABLE,
    FINANCIALS_TABLE,
    TIME_ENTRIES_TABLE,
    sample_engagement_rows,
    sample_financial_rows,
    sample_time_entry_rows,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_seed_populates_model_dashboards_and_facts(database, run):
    run(seed_consulting_domain(db=database, now=_NOW))
    sem = SemanticManager(database)
    model = run(sem.get_model(CONSULTING_MODEL_ID))
    assert model is not None
    assert {e.name for e in model.entities} == {
        "engagements", "time_entries", "financials", "deliverables", "invoices"
    }
    dash_ids = {d.dashboard_id for d in run(DashboardManager(database).list())}
    assert {"consulting-exec", "consulting-delivery"} <= dash_ids
    assert len(run(database.list(ENGAGEMENTS_TABLE, limit=100))) == len(sample_engagement_rows())
    assert len(run(database.list(TIME_ENTRIES_TABLE, limit=1000))) == len(sample_time_entry_rows())


def test_seed_is_idempotent(database, run):
    run(seed_consulting_domain(db=database, now=_NOW))
    run(seed_consulting_domain(db=database, now=_NOW))
    assert len(run(SemanticManager(database).list_models())) == 1
    assert len(run(DashboardManager(database).list())) == 2
    assert len(run(database.list(FINANCIALS_TABLE, limit=1000))) == len(sample_financial_rows())


def test_every_consulting_dashboard_query_resolves(database, run):
    run(seed_consulting_domain(db=database, now=_NOW))
    sem = SemanticManager(database)
    model = run(sem.get_model(CONSULTING_MODEL_ID))
    for dashboard in run(DashboardManager(database).list()):
        for chart in dashboard.charts:
            res = run(sem.run_query(model, chart.query))
            assert res.row_count >= 1, f"{dashboard.dashboard_id}/{chart.chart_id} empty"
            for col in chart.encoding.values():
                assert col in res.columns, f"{chart.chart_id} encodes missing column {col}"


def test_known_kpis(database, run):
    """The exec KPIs match the deterministic sample data (a regression anchor)."""
    run(seed_consulting_domain(db=database, now=_NOW))
    sem = SemanticManager(database)
    model = run(sem.get_model(CONSULTING_MODEL_ID))
    from agentic_core.models import SemanticQuery

    tcv = run(sem.run_query(model, SemanticQuery(entity="engagements", measures=["contract_value"])))
    assert tcv.rows[0]["contract_value"] == sum(r["contract_value"] for r in sample_engagement_rows())
    # revenue is sliceable by client and bucketable by month
    by_client = run(sem.run_query(model, SemanticQuery(
        entity="financials", measures=["revenue"], dimensions=["client"])))
    assert by_client.row_count >= 1
    monthly = run(sem.run_query(model, SemanticQuery(
        entity="financials", measures=["revenue"], time_grain="month")))
    assert monthly.row_count == 12  # 12 months of financials
