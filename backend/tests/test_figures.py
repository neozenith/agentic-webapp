"""Unit tests for the Data→Pixels projection (figures.build_figure) and the inline-dashboard
HTML renderer (mcp_ui.render_dashboard_ui). Pure functions, no I/O, no mocks."""

from __future__ import annotations

import pytest
from agentic_webapp.figures import build_figure, kpi_value
from agentic_webapp.mcp_ui import dashboard_summary, render_dashboard_ui
from agentic_core.models import DashboardChart, SemanticQuery, SemanticQueryResult

_RESULT = SemanticQueryResult(
    columns=["month", "total"],
    rows=[{"month": "2024-01-01", "total": 100.0}, {"month": "2024-02-01", "total": 150.0}],
    sql="SELECT ...",
    row_count=2,
)


def _chart(chart_type: str, encoding: dict[str, str]) -> DashboardChart:
    return DashboardChart(
        chart_id="c", title="T", chart_type=chart_type,  # type: ignore[arg-type]
        query=SemanticQuery(entity="e"), encoding=encoding,
    )


@pytest.mark.parametrize(
    "chart_type,expected_trace_type",
    [("bar", "bar"), ("line", "scatter"), ("area", "scatter"), ("scatter", "scatter"), ("pie", "pie")],
)
def test_build_figure_trace_types(chart_type: str, expected_trace_type: str) -> None:
    fig = build_figure(_chart(chart_type, {"x": "month", "y": "total"}), _RESULT)
    assert fig["data"][0]["type"] == expected_trace_type
    assert fig["layout"]["title"]["text"] == "T"


def test_build_figure_pie_uses_labels_values() -> None:
    fig = build_figure(_chart("pie", {"x": "month", "y": "total"}), _RESULT)
    assert fig["data"][0]["labels"] == ["2024-01-01", "2024-02-01"]
    assert fig["data"][0]["values"] == [100.0, 150.0]


def test_build_figure_table_lays_out_columns() -> None:
    fig = build_figure(_chart("table", {}), _RESULT)
    trace = fig["data"][0]
    assert trace["type"] == "table"
    assert trace["header"]["values"] == ["month", "total"]
    assert trace["cells"]["values"] == [["2024-01-01", "2024-02-01"], [100.0, 150.0]]


def test_build_figure_kpi_has_no_trace() -> None:
    fig = build_figure(_chart("kpi", {"value": "total"}), _RESULT)
    assert fig["data"] == []


def test_kpi_value_reads_first_row_and_handles_bad_input() -> None:
    assert kpi_value(_chart("kpi", {"value": "total"}), _RESULT) == 100.0
    assert kpi_value(_chart("bar", {"x": "month"}), _RESULT) is None  # not a kpi
    assert kpi_value(_chart("kpi", {}), _RESULT) is None  # no value encoding
    text = SemanticQueryResult(columns=["v"], rows=[{"v": "abc"}], row_count=1)
    assert kpi_value(_chart("kpi", {"value": "v"}), text) is None  # non-numeric
    empty = SemanticQueryResult(columns=["v"], rows=[], row_count=0)
    assert kpi_value(_chart("kpi", {"value": "v"}), empty) is None  # no rows


def test_render_dashboard_ui_embeds_plotly_kpi_and_errors() -> None:
    render = {
        "dashboard_id": "d1",
        "name": "My Dash",
        "description": "desc",
        "charts": [
            {"chart_id": "k", "title": "Total", "chart_type": "kpi", "value": 3802.04, "figure": {"data": []},
             "error": None},
            {"chart_id": "l", "title": "Trend", "chart_type": "line", "value": None,
             "figure": {"data": [{"type": "scatter", "x": [1], "y": [2]}], "layout": {}}, "error": None},
            {"chart_id": "e", "title": "Broken", "chart_type": "bar", "value": None,
             "figure": {"data": []}, "error": "boom"},
        ],
    }
    resource = render_dashboard_ui(render)
    html = resource.resource.text  # type: ignore[union-attr]
    assert "ui://dashboard/d1" in str(resource.resource.uri)  # type: ignore[union-attr]
    assert "3,802.04" in html  # KPI formatted
    assert "Plotly.newPlot" in html  # line chart embedded
    assert "cdn.plot.ly" in html
    assert "boom" in html  # error chart surfaced, not dropped


def test_dashboard_summary_counts_charts_and_kpis() -> None:
    render = {"name": "D", "charts": [{"chart_type": "kpi"}, {"chart_type": "bar"}]}
    summary = dashboard_summary(render)
    assert "2 chart(s)" in summary
    assert "1 KPI(s)" in summary
