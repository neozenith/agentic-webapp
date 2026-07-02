"""Elementary-backed observability for dbt runs.

Two layers:

* PURE builders (`build_invocations`, `build_gantt`) that turn already-fetched
  Elementary rows into the exact HTTP payload shapes. These are unit-tested with
  real dict fixtures, no live BigQuery.
* A thin `ObservabilityService` that queries the Elementary tables in BigQuery
  and feeds the rows to the builders. The query path is `# pragma: no cover`
  (it needs a live warehouse); a missing Elementary table on a fresh project is
  caught and surfaced as an honest empty result, not a crash.
"""

import re
from datetime import datetime
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from .config import Settings

Row = dict[str, Any]

# Columns the builders read; the SQL selects exactly these.
_INVOCATIONS_SQL = """
SELECT invocation_id, command, run_started_at, run_completed_at,
       target_name, dbt_version, created_at
FROM `{project}.{dataset}.dbt_invocations`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
ORDER BY created_at DESC
"""

_RUN_RESULTS_RECENT_SQL = """
SELECT invocation_id, thread_id, unique_id, name, resource_type, status,
       execute_started_at, execute_completed_at, execution_time, created_at
FROM `{project}.{dataset}.dbt_run_results`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
"""

_RUN_RESULTS_BY_INVOCATION_SQL = """
SELECT invocation_id, thread_id, unique_id, name, resource_type, status,
       execute_started_at, execute_completed_at, execution_time, created_at
FROM `{project}.{dataset}.dbt_run_results`
WHERE invocation_id = @invocation_id
"""


def _to_iso(value: Any) -> str | None:
    """Render a timestamp as ISO-8601, or None. Accepts datetime or string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _to_dt(value: Any) -> datetime | None:
    """Coerce a BigQuery timestamp (datetime or ISO string) to datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _natural_key(text: str) -> list[Any]:
    """Sort key that orders e.g. 'Thread-2' before 'Thread-10'."""
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", text)]


def _has_failure(status: Any) -> bool:
    """True when a dbt status string indicates an error or failure."""
    s = str(status or "").lower()
    return "error" in s or "fail" in s


def _started_rows(rows: list[Row]) -> list[Row]:
    """Drop rows with a NULL execute_started_at (incomplete / skipped nodes)."""
    return [r for r in rows if r.get("execute_started_at") is not None]


def _wall_secs(rows: list[Row]) -> float:
    """Wall-clock span of an invocation: max(completed) - min(started), in seconds."""
    starts = [_to_dt(r.get("execute_started_at")) for r in rows]
    completed = [_to_dt(r.get("execute_completed_at")) for r in rows]
    valid_starts = [s for s in starts if s is not None]
    valid_completed = [c for c in completed if c is not None]
    if not valid_starts or not valid_completed:
        return 0.0
    return (max(valid_completed) - min(valid_starts)).total_seconds()


def build_invocations(invocation_rows: list[Row], run_result_rows: list[Row]) -> list[Row]:
    """Aggregate invocation + run-result rows into the /observability/invocations payload."""
    results_by_invocation: dict[str, list[Row]] = {}
    for row in _started_rows(run_result_rows):
        results_by_invocation.setdefault(str(row.get("invocation_id")), []).append(row)

    out: list[Row] = []
    for inv in invocation_rows:
        invocation_id = str(inv.get("invocation_id"))
        node_rows = results_by_invocation.get(invocation_id, [])
        out.append(
            {
                "invocation_id": invocation_id,
                "command": inv.get("command") or "",
                "run_started_at": _to_iso(inv.get("run_started_at")),
                "run_completed_at": _to_iso(inv.get("run_completed_at")),
                "target_name": inv.get("target_name") or "",
                "dbt_version": inv.get("dbt_version") or "",
                "n_nodes": len(node_rows),
                "wall_secs": _wall_secs(node_rows),
                "has_failures": any(_has_failure(r.get("status")) for r in node_rows),
            }
        )
    out.sort(key=lambda item: item["run_started_at"] or "", reverse=True)
    return out


def build_gantt(invocation_id: str, run_result_rows: list[Row]) -> Row:
    """Build the per-invocation gantt payload (threads + offset-positioned nodes)."""
    rows = _started_rows(run_result_rows)
    starts = [_to_dt(r.get("execute_started_at")) for r in rows]
    valid_starts = [s for s in starts if s is not None]
    base = min(valid_starts) if valid_starts else None

    nodes: list[Row] = []
    for row in rows:
        started = _to_dt(row.get("execute_started_at"))
        offset = (started - base).total_seconds() if (started is not None and base is not None) else 0.0
        nodes.append(
            {
                "thread_id": row.get("thread_id") or "",
                "node_id": row.get("unique_id") or "",
                "name": row.get("name") or "",
                "resource_type": row.get("resource_type") or "",
                "status": row.get("status") or "",
                "start_offset_secs": offset,
                "duration_secs": float(row.get("execution_time") or 0.0),
            }
        )
    nodes.sort(key=lambda node: node["start_offset_secs"])
    threads = sorted({str(r.get("thread_id") or "") for r in rows}, key=_natural_key)
    return {
        "invocation_id": invocation_id,
        "wall_secs": _wall_secs(rows),
        "threads": threads,
        "nodes": nodes,
    }


def _empty_gantt(invocation_id: str) -> Row:
    """The honest-empty gantt payload for a fresh project (no Elementary table yet)."""
    return {"invocation_id": invocation_id, "wall_secs": 0.0, "threads": [], "nodes": []}


class ObservabilityService:
    """Queries the Elementary tables in BigQuery and builds the observability payloads."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self) -> bigquery.Client:  # pragma: no cover
        return bigquery.Client(project=self.settings.gcp_project or None)

    def invocations(self, days: int) -> list[Row]:  # pragma: no cover
        project = self.settings.gcp_project
        dataset = self.settings.elementary_dataset
        client = self._client()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)]
        )
        try:
            invocation_rows = [
                dict(r)
                for r in client.query(
                    _INVOCATIONS_SQL.format(project=project, dataset=dataset), job_config=job_config
                ).result()
            ]
            run_result_rows = [
                dict(r)
                for r in client.query(
                    _RUN_RESULTS_RECENT_SQL.format(project=project, dataset=dataset), job_config=job_config
                ).result()
            ]
        except NotFound:
            return []
        return build_invocations(invocation_rows, run_result_rows)

    def gantt(self, invocation_id: str) -> Row:  # pragma: no cover
        project = self.settings.gcp_project
        dataset = self.settings.elementary_dataset
        client = self._client()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("invocation_id", "STRING", invocation_id)]
        )
        try:
            run_result_rows = [
                dict(r)
                for r in client.query(
                    _RUN_RESULTS_BY_INVOCATION_SQL.format(project=project, dataset=dataset),
                    job_config=job_config,
                ).result()
            ]
        except NotFound:
            return _empty_gantt(invocation_id)
        return build_gantt(invocation_id, run_result_rows)
