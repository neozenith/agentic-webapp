"""BigQueryDatabaseManager — BigQuery implementation of DatabaseManager.

The SDK is synchronous; calls are offloaded with asyncio.to_thread. Logical table
names are resolved to fully-qualified `project.dataset.table` ids. Inserts use the
streaming API (insert_rows_json); reads use query jobs with named parameters.

Note: streaming-inserted rows are not immediately readable (BigQuery streaming
buffer), so a read straight after an insert may not see it. That's acceptable for a
metadata catalogue; tests run against InMemoryDatabaseManager for deterministic
behaviour.
"""

from __future__ import annotations

import asyncio
from typing import Any

from google.cloud import bigquery

from .base import DatabaseManager, Row, Rows


class BigQueryDatabaseManager(
    DatabaseManager
):  # pragma: no cover — real BigQuery SDK; un-mockable per no-mock rule (covered by live deploy)
    supports_sql = True

    def __init__(
        self,
        *,
        project: str,
        dataset: str,
        client: bigquery.Client | None = None,
    ) -> None:
        self._project = project
        self._dataset = dataset
        self._client = client or bigquery.Client(project=project)

    def _table_id(self, table: str) -> str:
        return f"{self._project}.{self._dataset}.{table}"

    def qualified_table(self, table: str) -> str:
        return f"`{self._table_id(table)}`"

    async def insert(self, table: str, rows: Rows) -> None:
        def _insert() -> None:
            errors = self._client.insert_rows_json(self._table_id(table), rows)
            if errors:
                raise RuntimeError(f"BigQuery insert into {table} failed: {errors}")

        await asyncio.to_thread(_insert)

    async def get(self, table: str, *, key_field: str, key: str) -> Row | None:
        sql = f"SELECT * FROM `{self._table_id(table)}` WHERE `{key_field}` = @key LIMIT 1"
        rows = await self.query(sql, params={"key": key})
        return rows[0] if rows else None

    async def list(self, table: str, *, limit: int = 100, order_by: str | None = None) -> Rows:
        order = f"ORDER BY `{order_by}` DESC" if order_by else ""
        sql = f"SELECT * FROM `{self._table_id(table)}` {order} LIMIT @limit"
        return await self.query(sql, params={"limit": limit})

    async def delete(self, table: str, *, key_field: str, key: str) -> None:
        sql = f"DELETE FROM `{self._table_id(table)}` WHERE `{key_field}` = @key"
        await self.query(sql, params={"key": key})

    async def query(self, sql: str, *, params: dict[str, Any] | None = None) -> Rows:
        def _query() -> Rows:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[_to_query_param(name, value) for name, value in (params or {}).items()]
            )
            job = self._client.query(sql, job_config=job_config)
            return [dict(row.items()) for row in job.result()]

        return await asyncio.to_thread(_query)


def _to_query_param(name: str, value: Any) -> bigquery.ScalarQueryParameter:  # pragma: no cover
    """Map a Python value to a typed BigQuery scalar parameter."""
    if isinstance(value, bool):
        type_ = "BOOL"
    elif isinstance(value, int):
        type_ = "INT64"
    elif isinstance(value, float):
        type_ = "FLOAT64"
    else:
        type_ = "STRING"
        value = str(value)
    return bigquery.ScalarQueryParameter(name, type_, value)
