"""Contract tests for SemanticManager — CRUD + the portable query engine (in-memory,
no mocks). The BigQuery push-down path is exercised only by the live deploy."""

from datetime import datetime, timezone

import pytest

from agentic_core.database import (
    InMemoryDatabaseManager,
    SemanticManager,
    SemanticQueryError,
    fuel_semantic_model,
)
from agentic_core.database.seed import FUEL_FACT_TABLE, sample_fuel_rows, sample_maintenance_rows
from agentic_core.models import SemanticFilter, SemanticQuery

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def seeded(database, run):
    """In-memory db with the fuel model + sample facts; returns (manager, model)."""
    mgr = SemanticManager(database)
    model = fuel_semantic_model(now=_NOW)
    run(mgr.create_model(model))
    run(database.insert(FUEL_FACT_TABLE, sample_fuel_rows()))
    run(database.insert("fct_maintenance", sample_maintenance_rows()))
    return mgr, model


# --- CRUD --------------------------------------------------------------------------------


def test_model_crud_roundtrip(database, run):
    mgr = SemanticManager(database)
    model = fuel_semantic_model(now=_NOW)
    run(mgr.create_model(model))

    got = run(mgr.get_model(model.model_id))
    assert got is not None
    assert got.name == "Fuel & Vehicle Costs"
    assert {e.name for e in got.entities} == {"fuel_purchases", "maintenance"}
    # dimensions/measures survive the JSON round-trip
    fuel = next(e for e in got.entities if e.name == "fuel_purchases")
    assert fuel.time_dimension == "purchased_at"
    assert any(m.agg == "avg" for m in fuel.measures)

    assert [m.model_id for m in run(mgr.list_models())] == [model.model_id]


def test_update_and_delete(database, run):
    mgr = SemanticManager(database)
    model = fuel_semantic_model(now=_NOW)
    run(mgr.create_model(model))

    model.description = "edited"
    run(mgr.update_model(model))
    assert run(mgr.get_model(model.model_id)).description == "edited"
    assert len(run(mgr.list_models())) == 1  # update is replace, not append

    run(mgr.delete_model(model.model_id))
    assert run(mgr.get_model(model.model_id)) is None


# --- query engine ------------------------------------------------------------------------


def test_group_by_dimension_sum(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases",
                                                 measures=["total_cost"], dimensions=["station"])))
    assert res.columns == ["station", "total_cost"]
    assert res.row_count == 4  # four stations
    stations = {r["station"] for r in res.rows}
    assert stations == {"Shell", "BP", "Caltex", "7-Eleven"}
    # default order is the first measure, descending
    costs = [r["total_cost"] for r in res.rows]
    assert costs == sorted(costs, reverse=True)


def test_time_grain_year_matches_manual_sum(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=["total_cost"],
                                                 time_grain="year", order_by="purchased_at",
                                                 descending=False)))
    assert [r["purchased_at"] for r in res.rows] == ["2024-01-01", "2025-01-01"]
    rows = sample_fuel_rows()
    expect_2024 = round(sum(r["total_cost"] for r in rows if r["purchased_at"].startswith("2024")), 6)
    got_2024 = next(r["total_cost"] for r in res.rows if r["purchased_at"] == "2024-01-01")
    assert got_2024 == pytest.approx(expect_2024, rel=1e-6)


def test_time_grain_month_buckets(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=["fill_count"],
                                                 time_grain="month")))
    assert res.row_count == 24  # 24 months across two years
    # two fills per month in the sample data
    assert all(r["fill_count"] == 2 for r in res.rows)


@pytest.mark.parametrize(
    "measure,agg_check",
    [
        ("litres", lambda rows: round(sum(r["litres"] for r in rows), 6)),
        ("fill_count", lambda rows: len(rows)),
    ],
)
def test_measures_no_group(seeded, run, measure, agg_check):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=[measure])))
    assert res.row_count == 1
    assert res.rows[0][measure] == pytest.approx(agg_check(sample_fuel_rows()), rel=1e-6)


def test_avg_min_max_distinct(seeded, run):
    mgr, model = seeded
    # add explicit min/max/distinct measures via a query against existing avg measure + raw
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases",
                                                 measures=["avg_price_per_litre"])))
    rows = sample_fuel_rows()
    expect = round(sum(r["price_per_litre"] for r in rows) / len(rows), 6)
    assert res.rows[0]["avg_price_per_litre"] == pytest.approx(expect, rel=1e-6)


def test_filter_equals_and_in(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"],
        filters=[SemanticFilter(field="station", op="=", value="Shell")])))
    shell = sum(1 for r in sample_fuel_rows() if r["station"] == "Shell")
    assert res.rows[0]["fill_count"] == shell

    res_in = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"], dimensions=["station"],
        filters=[SemanticFilter(field="station", op="in", value=["Shell", "BP"])])))
    assert {r["station"] for r in res_in.rows} == {"Shell", "BP"}


def test_filter_numeric_comparison(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"],
        filters=[SemanticFilter(field="litres", op=">", value=40.0)])))
    expect = sum(1 for r in sample_fuel_rows() if r["litres"] > 40.0)
    assert res.rows[0]["fill_count"] == expect


def test_limit_applies(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=["total_cost"],
                                                 dimensions=["station"], limit=2)))
    assert res.row_count == 2


def test_compiled_sql_is_present_and_shaped(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=["total_cost"],
                                                 dimensions=["station"], time_grain="month")))
    sql = res.sql
    assert "SELECT" in sql and "GROUP BY" in sql
    assert "DATE_TRUNC(CAST(`purchased_at` AS DATE), MONTH)" in sql
    assert "SUM(`total_cost`)" in sql
    assert "fct_fuel_purchases" in sql


def test_compile_sql_escapes_string_filter(seeded):
    mgr, model = seeded
    sql = mgr.compile_sql(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"],
        filters=[SemanticFilter(field="station", op="=", value="O'Brien")]))
    assert "O\\'Brien" in sql  # single quote escaped


# --- errors ------------------------------------------------------------------------------


def test_unknown_entity_raises(seeded, run):
    mgr, model = seeded
    with pytest.raises(SemanticQueryError, match="unknown entity"):
        run(mgr.run_query(model, SemanticQuery(entity="nope", measures=["total_cost"])))


def test_unknown_dimension_and_measure_raise(seeded, run):
    mgr, model = seeded
    with pytest.raises(SemanticQueryError, match="unknown dimension"):
        run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", dimensions=["nope"])))
    with pytest.raises(SemanticQueryError, match="unknown measure"):
        run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=["nope"])))


def test_empty_query_raises(seeded, run):
    mgr, model = seeded
    with pytest.raises(SemanticQueryError, match="at least one"):
        run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases")))


def test_time_grain_without_time_dimension_raises(database, run):
    from agentic_core.models import SemanticEntity, SemanticMeasure, SemanticModel

    model = SemanticModel(
        model_id="m", name="m",
        entities=[SemanticEntity(name="e", table="t",
                                 measures=[SemanticMeasure(name="c", column="*", agg="count")])],
        created_at=_NOW, updated_at=_NOW,
    )
    mgr = SemanticManager(database)
    run(database.insert("t", [{"x": 1}]))
    with pytest.raises(SemanticQueryError, match="no time_dimension"):
        run(mgr.run_query(model, SemanticQuery(entity="e", measures=["c"], time_grain="month")))


def test_supports_sql_flag_default_false():
    assert InMemoryDatabaseManager().supports_sql is False
    assert InMemoryDatabaseManager().qualified_table("t") == "t"


def test_all_aggregations(database, run):
    """min/max/count_distinct/avg/sum over a hand-built entity, plus their SQL fragments."""
    from agentic_core.models import SemanticEntity, SemanticMeasure, SemanticModel

    measures = [
        SemanticMeasure(name="total", column="v", agg="sum"),
        SemanticMeasure(name="mean", column="v", agg="avg"),
        SemanticMeasure(name="lo", column="v", agg="min"),
        SemanticMeasure(name="hi", column="v", agg="max"),
        SemanticMeasure(name="kinds", column="k", agg="count_distinct"),
        SemanticMeasure(name="rows", column="*", agg="count"),
    ]
    model = SemanticModel(model_id="m", name="m",
                          entities=[SemanticEntity(name="e", table="t", measures=measures)],
                          created_at=_NOW, updated_at=_NOW)
    mgr = SemanticManager(database)
    run(database.insert("t", [{"v": 10, "k": "a"}, {"v": 20, "k": "a"}, {"v": 30, "k": "b"}]))
    res = run(mgr.run_query(model, SemanticQuery(
        entity="e", measures=["total", "mean", "lo", "hi", "kinds", "rows"])))
    row = res.rows[0]
    assert row == {"total": 60, "mean": 20, "lo": 10.0, "hi": 30.0, "kinds": 2, "rows": 3}

    sql = mgr.compile_sql(model, SemanticQuery(entity="e", measures=["lo", "hi", "kinds", "rows"]))
    assert "MIN(`v`)" in sql and "MAX(`v`)" in sql
    assert "COUNT(DISTINCT `k`)" in sql and "COUNT(*)" in sql


@pytest.mark.parametrize("grain,expected_first", [
    ("day", "2024-01-05"),
    ("week", "2024-01-01"),  # Monday of the week containing 2024-01-05 (a Friday)
    ("quarter", "2024-01-01"),
])
def test_time_grain_buckets_all(seeded, run, grain, expected_first):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(entity="fuel_purchases", measures=["fill_count"],
                                                 time_grain=grain, order_by="purchased_at",
                                                 descending=False)))
    assert res.rows[0]["purchased_at"] == expected_first


def test_filter_like_and_not_equal(seeded, run):
    mgr, model = seeded
    res_like = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"], dimensions=["station"],
        filters=[SemanticFilter(field="station", op="like", value="%7-%")])))
    assert {r["station"] for r in res_like.rows} == {"7-Eleven"}

    res_ne = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"], dimensions=["station"],
        filters=[SemanticFilter(field="station", op="!=", value="Shell")])))
    assert "Shell" not in {r["station"] for r in res_ne.rows}


def test_filter_string_comparison_non_numeric(seeded, run):
    mgr, model = seeded
    # fuel_type values are non-numeric strings -> the ">" falls back to string comparison
    res = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["fill_count"], dimensions=["fuel_type"],
        filters=[SemanticFilter(field="fuel_type", op=">", value="d")])))
    # only "diesel" and "premium_95"/"unleaded_91" > "d": diesel < d? 'd'=='d', 'di' > 'd'
    assert all(r["fuel_type"] > "d" for r in res.rows)


def test_order_by_dimension_ascending(seeded, run):
    mgr, model = seeded
    res = run(mgr.run_query(model, SemanticQuery(
        entity="fuel_purchases", measures=["total_cost"], dimensions=["station"],
        order_by="station", descending=False)))
    stations = [r["station"] for r in res.rows]
    assert stations == sorted(stations)


def test_sort_handles_none_values(database, run):
    from agentic_core.models import SemanticDimension, SemanticEntity, SemanticMeasure, SemanticModel

    model = SemanticModel(model_id="m", name="m", entities=[SemanticEntity(
        name="e", table="t",
        dimensions=[SemanticDimension(name="g", column="g")],
        measures=[SemanticMeasure(name="c", column="*", agg="count")],
    )], created_at=_NOW, updated_at=_NOW)
    mgr = SemanticManager(database)
    run(database.insert("t", [{"g": "x"}, {"g": None}, {"g": "y"}]))
    res = run(mgr.run_query(model, SemanticQuery(entity="e", measures=["c"], dimensions=["g"],
                                                 order_by="g", descending=False)))
    assert res.row_count == 3  # the None group sorts without error
