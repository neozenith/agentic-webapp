"""build_figure — the Data→Pixels projection shared by the web dashboards and MCP-UI.

A DashboardChart pairs a SemanticQuery (data) with an `encoding` map and a `chart_type`.
This module turns a chart + its query result into a Plotly figure dict (``{data, layout}``)
— the literal JSON that maps result columns onto pixels. Both the ``/api/dashboards/{id}/render``
route (React renders it with react-plotly) and the inline MCP-UI dashboard tool (Plotly from a
CDN inside a sandboxed iframe) consume the identical figure, so the two surfaces never diverge.
"""

from __future__ import annotations

from typing import Any

from agentic_core.models import DashboardChart, SemanticQueryResult


def build_figure(chart: DashboardChart, result: SemanticQueryResult) -> dict[str, Any]:
    """A Plotly figure ({data, layout}) for `chart` over `result`. KPI charts carry an empty
    data list (the frontend renders the single `value` big); every other type emits one trace."""
    enc = chart.encoding
    rows = result.rows
    layout: dict[str, Any] = {"title": {"text": chart.title}, "margin": {"t": 40, "r": 16, "b": 40, "l": 56}}
    layout.update({k: v for k, v in chart.layout.items() if k != "unit"})

    if chart.chart_type == "kpi":
        return {"data": [], "layout": layout}

    x_key, y_key = enc.get("x"), enc.get("y")
    xs = [_cell(r, x_key) for r in rows] if x_key else []
    ys = [_cell(r, y_key) for r in rows] if y_key else []

    trace: dict[str, Any]
    if chart.chart_type == "pie":
        trace = {"type": "pie", "labels": xs, "values": ys}
    elif chart.chart_type == "line":
        trace = {"type": "scatter", "mode": "lines+markers", "x": xs, "y": ys}
    elif chart.chart_type == "area":
        trace = {"type": "scatter", "mode": "lines", "fill": "tozeroy", "x": xs, "y": ys}
    elif chart.chart_type == "scatter":
        trace = {"type": "scatter", "mode": "markers", "x": xs, "y": ys}
    elif chart.chart_type == "table":
        trace = {
            "type": "table",
            "header": {"values": result.columns},
            "cells": {"values": [[_cell(r, c) for r in rows] for c in result.columns]},
        }
    else:  # bar (default)
        trace = {"type": "bar", "x": xs, "y": ys}
    return {"data": [trace], "layout": layout}


def kpi_value(chart: DashboardChart, result: SemanticQueryResult) -> float | None:
    """The single number a KPI chart shows — its encoded `value` column from the first row."""
    if chart.chart_type != "kpi" or not result.rows:
        return None
    key = chart.encoding.get("value")
    if not key:
        return None
    raw = result.rows[0].get(key)
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _cell(row: dict[str, Any], key: str | None) -> Any:
    return row.get(key) if key else None
