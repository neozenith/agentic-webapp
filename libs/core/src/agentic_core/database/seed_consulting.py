"""Seed a second worked domain — Consulting Engagement Management — so the scaffold ships
with two contrasting examples (a personal-finance one in seed.py, a B2B portfolio one here).

Domain (distilled from a delivery-portfolio handoff spec): engagements for clients, staffed by
consultants across service lines, tracked by time entries, financial actuals, deliverables and
invoices. The star schema is dim_engagements + four fact tables; the KPIs are revenue, margin,
utilisation-by-hours, delivery health (RAG) and invoicing. Same shape as the fuel seed: a
SemanticModel, two dashboards, and deterministic sample marts that mirror the dbt models.

Like the fuel seed this is a TEMPLATE — delete it and model your own domain. It is generic on
purpose (no real client/person names).
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

CONSULTING_MODEL_ID = "consulting_engagements"
ENGAGEMENTS_TABLE = "dim_engagements"
TIME_ENTRIES_TABLE = "fct_time_entries"
FINANCIALS_TABLE = "fct_engagement_financials"
DELIVERABLES_TABLE = "fct_deliverables"
INVOICES_TABLE = "fct_invoices"

_CONSULTANTS = ["A. Okafor", "B. Nguyen", "C. Rossi", "D. Haddad", "E. Larsson", "F. Tanaka"]
_ROLES = ["Engagement Lead", "Tech Lead", "Engineer", "Designer", "Analyst"]
_RAG = ["green", "amber", "red"]
_DELIVERABLE_STATUS = ["not_started", "in_progress", "at_risk", "completed"]
_INVOICE_STATUS = ["draft", "sent", "paid", "overdue"]

# Five engagements: (id, name, client, service_line, lead, phase, status, rag, contract_value)
_ENGAGEMENTS = [
    ("eng_nw_core", "Core Banking Uplift", "Northwind Bank", "Scale", "A. Okafor", "build", "active", "amber", 2_400_000),
    ("eng_he_grid", "Grid Analytics Platform", "Helios Energy", "Enable", "B. Nguyen", "run", "active", "green", 1_650_000),
    ("eng_mh_triage", "Clinical Triage AI", "Meridian Health", "Align", "C. Rossi", "discovery", "active", "red", 980_000),
    ("eng_cd_portal", "Citizen Portal Rebuild", "Civic Digital", "Scale", "D. Haddad", "build", "active", "green", 1_320_000),
    ("eng_nw_sec", "Zero-Trust Rollout", "Northwind Bank", "Secure", "E. Larsson", "mobilise", "setup", "amber", 760_000),
]


def consulting_semantic_model(*, now: datetime | None = None) -> SemanticModel:
    """The logical model: one engagement dimension + four fact entities."""
    now = now or datetime.now(timezone.utc)
    engagements = SemanticEntity(
        name="engagements", description="A client engagement — the portfolio spine.",
        table=ENGAGEMENTS_TABLE, primary_key="engagement_id", time_dimension="start_date",
        dimensions=[
            SemanticDimension(name="start_date", column="start_date", dtype="time", description="Engagement start."),
            SemanticDimension(name="client", column="client", description="The client organisation."),
            SemanticDimension(name="service_line", column="service_line", description="Delivery pillar."),
            SemanticDimension(name="lead_consultant", column="lead_consultant", description="Engagement lead."),
            SemanticDimension(name="phase", column="phase", description="mobilise → discovery → build → run."),
            SemanticDimension(name="status", column="status", description="setup / active."),
            SemanticDimension(name="rag_overall", column="rag_overall", description="Overall health RAG."),
        ],
        measures=[
            SemanticMeasure(name="contract_value", column="contract_value", agg="sum", unit="$0,0",
                            description="Total contract value (TCV)."),
            SemanticMeasure(name="revenue_to_date", column="revenue_to_date", agg="sum", unit="$0,0"),
            SemanticMeasure(name="avg_margin_pct", column="margin_pct", agg="avg", unit="0.0%"),
            SemanticMeasure(name="engagement_count", column="*", agg="count"),
        ],
    )
    time_entries = SemanticEntity(
        name="time_entries", description="One consultant's logged time on an engagement, per day.",
        table=TIME_ENTRIES_TABLE, primary_key="time_entry_id", time_dimension="entry_date",
        dimensions=[
            SemanticDimension(name="entry_date", column="entry_date", dtype="time"),
            SemanticDimension(name="consultant", column="consultant"),
            SemanticDimension(name="engagement", column="engagement"),
            SemanticDimension(name="role", column="role"),
            SemanticDimension(name="billable", column="billable", dtype="boolean"),
        ],
        measures=[
            SemanticMeasure(name="hours", column="hours", agg="sum", unit="0,0.0"),
            SemanticMeasure(name="cost", column="cost", agg="sum", unit="$0,0"),
            SemanticMeasure(name="entry_count", column="*", agg="count"),
        ],
    )
    financials = SemanticEntity(
        name="financials", description="Monthly financial actuals per engagement.",
        table=FINANCIALS_TABLE, primary_key="financial_id", time_dimension="period",
        dimensions=[
            SemanticDimension(name="period", column="period", dtype="time"),
            SemanticDimension(name="engagement", column="engagement"),
            SemanticDimension(name="client", column="client"),
        ],
        measures=[
            SemanticMeasure(name="revenue", column="revenue", agg="sum", unit="$0,0"),
            SemanticMeasure(name="cost", column="cost", agg="sum", unit="$0,0"),
            SemanticMeasure(name="margin", column="margin", agg="sum", unit="$0,0"),
        ],
    )
    deliverables = SemanticEntity(
        name="deliverables", description="Engagement deliverables and their delivery health.",
        table=DELIVERABLES_TABLE, primary_key="deliverable_id", time_dimension="due_date",
        dimensions=[
            SemanticDimension(name="due_date", column="due_date", dtype="time"),
            SemanticDimension(name="engagement", column="engagement"),
            SemanticDimension(name="status", column="status"),
            SemanticDimension(name="rag", column="rag"),
        ],
        measures=[
            SemanticMeasure(name="avg_progress", column="progress", agg="avg", unit="0%"),
            SemanticMeasure(name="deliverable_count", column="*", agg="count"),
        ],
    )
    invoices = SemanticEntity(
        name="invoices", description="Invoices raised against engagements.",
        table=INVOICES_TABLE, primary_key="invoice_id", time_dimension="issued_at",
        dimensions=[
            SemanticDimension(name="issued_at", column="issued_at", dtype="time"),
            SemanticDimension(name="engagement", column="engagement"),
            SemanticDimension(name="client", column="client"),
            SemanticDimension(name="status", column="status"),
        ],
        measures=[
            SemanticMeasure(name="amount", column="amount", agg="sum", unit="$0,0"),
            SemanticMeasure(name="invoice_count", column="*", agg="count"),
        ],
    )
    return SemanticModel(
        model_id=CONSULTING_MODEL_ID, name="Consulting Engagements",
        description=(
            "Portfolio of client engagements: revenue, margin, utilisation (logged hours), "
            "delivery health (RAG) and invoicing, sliced by client, service line and consultant."
        ),
        entities=[engagements, time_entries, financials, deliverables, invoices],
        created_at=now, updated_at=now,
    )


def consulting_dashboards(*, now: datetime | None = None) -> list[DashboardSpec]:
    now = now or datetime.now(timezone.utc)
    exec_portfolio = DashboardSpec(
        dashboard_id="consulting-exec", name="Executive Portfolio",
        description="Portfolio financials, margin and revenue across all engagements.",
        semantic_model_id=CONSULTING_MODEL_ID,
        charts=[
            DashboardChart(chart_id="kpi-tcv", title="Total contract value", chart_type="kpi",
                           query=SemanticQuery(entity="engagements", measures=["contract_value"]),
                           encoding={"value": "contract_value"}, layout={"unit": "$0,0"}),
            DashboardChart(chart_id="kpi-rev", title="Revenue to date", chart_type="kpi",
                           query=SemanticQuery(entity="engagements", measures=["revenue_to_date"]),
                           encoding={"value": "revenue_to_date"}, layout={"unit": "$0,0"}),
            DashboardChart(chart_id="rev-by-client", title="Revenue by client", chart_type="bar",
                           query=SemanticQuery(entity="financials", measures=["revenue"], dimensions=["client"]),
                           encoding={"x": "client", "y": "revenue"}),
            DashboardChart(chart_id="monthly-rev", title="Monthly revenue", chart_type="line",
                           query=SemanticQuery(entity="financials", measures=["revenue"], time_grain="month",
                                               order_by="period", descending=False),
                           encoding={"x": "period", "y": "revenue"}),
            DashboardChart(chart_id="hours-by-line", title="Logged hours by role", chart_type="bar",
                           query=SemanticQuery(entity="time_entries", measures=["hours"], dimensions=["role"]),
                           encoding={"x": "role", "y": "hours"}),
        ],
        created_at=now, updated_at=now,
    )
    delivery = DashboardSpec(
        dashboard_id="consulting-delivery", name="Engagement Delivery",
        description="Delivery health, utilisation and invoicing for active engagements.",
        semantic_model_id=CONSULTING_MODEL_ID,
        charts=[
            DashboardChart(chart_id="deliv-by-status", title="Deliverables by status", chart_type="bar",
                           query=SemanticQuery(entity="deliverables", measures=["deliverable_count"],
                                               dimensions=["status"]),
                           encoding={"x": "status", "y": "deliverable_count"}),
            DashboardChart(chart_id="monthly-hours", title="Monthly logged hours", chart_type="line",
                           query=SemanticQuery(entity="time_entries", measures=["hours"], time_grain="month",
                                               order_by="entry_date", descending=False),
                           encoding={"x": "entry_date", "y": "hours"}),
            DashboardChart(chart_id="hours-by-consultant", title="Hours by consultant", chart_type="bar",
                           query=SemanticQuery(entity="time_entries", measures=["hours"], dimensions=["consultant"]),
                           encoding={"x": "consultant", "y": "hours"}),
            DashboardChart(chart_id="invoice-by-status", title="Invoiced amount by status", chart_type="bar",
                           query=SemanticQuery(entity="invoices", measures=["amount"], dimensions=["status"]),
                           encoding={"x": "status", "y": "amount"}),
        ],
        created_at=now, updated_at=now,
    )
    return [exec_portfolio, delivery]


def sample_engagement_rows() -> list[dict[str, Any]]:
    rows = []
    for i, (eid, name, client, line, lead, phase, status, rag, tcv) in enumerate(_ENGAGEMENTS):
        rev = round(tcv * (0.35 + 0.1 * (i % 4)), 0)
        rows.append({
            "engagement_id": eid, "name": name, "client": client, "service_line": line,
            "lead_consultant": lead, "phase": phase, "status": status, "rag_overall": rag,
            "start_date": f"2025-0{(i % 6) + 1}-01", "end_date": "2026-06-30",
            "contract_value": tcv, "revenue_to_date": rev,
            "margin_pct": round(0.18 + 0.03 * (i % 4), 3),
        })
    return rows


def sample_time_entry_rows() -> list[dict[str, Any]]:
    rows, n = [], 0
    for month in range(1, 13):
        for i, (eid, *_rest) in enumerate(_ENGAGEMENTS):
            for c in range(3):  # 3 consultants logging per engagement per month
                n += 1
                consultant = _CONSULTANTS[(i + c) % len(_CONSULTANTS)]
                role = _ROLES[(i + c) % len(_ROLES)]
                hours = 80 + (n % 5) * 12
                billable = (n % 5) != 0
                rate = 180 + (n % 4) * 40
                rows.append({
                    "time_entry_id": f"te_{month:02d}_{eid}_{c}",
                    "entry_date": f"2025-{month:02d}-15", "consultant": consultant,
                    "engagement": eid, "role": role, "hours": hours, "billable": billable,
                    "cost": round(hours * rate * (0.55 if billable else 1.0), 0),
                })
    return rows


def sample_financial_rows() -> list[dict[str, Any]]:
    rows = []
    for month in range(1, 13):
        for i, (eid, _n, client, *_rest) in enumerate(_ENGAGEMENTS):
            revenue = round(120_000 + (i * 30_000) + (month * 4_000), 0)
            cost = round(revenue * (0.78 + 0.02 * (i % 3)), 0)
            rows.append({
                "financial_id": f"fin_{month:02d}_{eid}", "period": f"2025-{month:02d}-01",
                "engagement": eid, "client": client, "revenue": revenue, "cost": cost,
                "margin": round(revenue - cost, 0),
            })
    return rows


def sample_deliverable_rows() -> list[dict[str, Any]]:
    rows = []
    for i, (eid, *_rest) in enumerate(_ENGAGEMENTS):
        for d in range(4):
            n = i * 4 + d
            rows.append({
                "deliverable_id": f"del_{eid}_{d}", "engagement": eid,
                "name": f"D{d + 1}", "status": _DELIVERABLE_STATUS[n % len(_DELIVERABLE_STATUS)],
                "rag": _RAG[n % len(_RAG)], "due_date": f"2025-{((n % 12) + 1):02d}-20",
                "progress": (n * 17) % 101,
            })
    return rows


def sample_invoice_rows() -> list[dict[str, Any]]:
    rows = []
    for month in range(1, 13):
        for i, (eid, _n, client, *_rest) in enumerate(_ENGAGEMENTS):
            if (month + i) % 2:  # not every engagement invoices every month
                continue
            n = month + i
            rows.append({
                "invoice_id": f"inv_{month:02d}_{eid}", "engagement": eid, "client": client,
                "issued_at": f"2025-{month:02d}-28", "due_date": f"2025-{month:02d}-28",
                "amount": round(90_000 + (i * 25_000) + (month * 2_000), 0),
                "status": _INVOICE_STATUS[n % len(_INVOICE_STATUS)],
            })
    return rows


async def seed_consulting_domain(
    *,
    db: DatabaseManager,
    semantic_table: str = "semantic_models",
    dashboard_table: str = "dashboards",
    now: datetime | None = None,
) -> None:
    """Idempotently seed the consulting model, dashboards and sample marts into `db`.
    No-op on a SQL backend (BigQuery) — dbt + Terraform own the cloud tables there."""
    if db.supports_sql:  # pragma: no cover — cloud tables owned by dbt/Terraform
        return
    now = now or datetime.now(timezone.utc)
    if not any(m["model_id"] == CONSULTING_MODEL_ID for m in await db.list(semantic_table, limit=50)):
        await db.insert(semantic_table, [SemanticManager._to_row(consulting_semantic_model(now=now))])
    existing = {d["dashboard_id"] for d in await db.list(dashboard_table, limit=50)}
    new_dash = [d for d in consulting_dashboards(now=now) if d.dashboard_id not in existing]
    if new_dash:
        await db.insert(dashboard_table, [DashboardManager._to_row(d) for d in new_dash])
    for table, rows in (
        (ENGAGEMENTS_TABLE, sample_engagement_rows()),
        (TIME_ENTRIES_TABLE, sample_time_entry_rows()),
        (FINANCIALS_TABLE, sample_financial_rows()),
        (DELIVERABLES_TABLE, sample_deliverable_rows()),
        (INVOICES_TABLE, sample_invoice_rows()),
    ):
        if not await db.list(table, limit=1):
            await db.insert(table, rows)
