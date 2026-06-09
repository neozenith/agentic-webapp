"""InMemoryDatabaseManager — a real, dependency-free DatabaseManager for tests and
the GCP-free local loop. query() supports no SQL (raises) — portable code uses the
typed methods; only backend-specific code calls query()."""

from __future__ import annotations

from typing import Any

from .base import DatabaseManager, Row, Rows


class InMemoryDatabaseManager(DatabaseManager):
    def __init__(self) -> None:
        self._tables: dict[str, list[Row]] = {}

    async def insert(self, table: str, rows: Rows) -> None:
        self._tables.setdefault(table, []).extend(dict(r) for r in rows)

    async def get(self, table: str, *, key_field: str, key: str) -> Row | None:
        for row in self._tables.get(table, []):
            if str(row.get(key_field)) == key:
                return dict(row)
        return None

    async def list(self, table: str, *, limit: int = 100, order_by: str | None = None) -> Rows:
        rows = [dict(r) for r in self._tables.get(table, [])]
        if order_by:
            rows.sort(key=lambda r: r.get(order_by) or "", reverse=True)
        return rows[:limit]

    async def delete(self, table: str, *, key_field: str, key: str) -> None:
        rows = self._tables.get(table)
        if rows is not None:
            self._tables[table] = [r for r in rows if str(r.get(key_field)) != key]

    async def query(self, sql: str, *, params: dict[str, Any] | None = None) -> Rows:
        raise NotImplementedError("InMemoryDatabaseManager does not support raw SQL; use the typed methods.")
