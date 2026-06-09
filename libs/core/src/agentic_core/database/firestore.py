"""FirestoreDatabaseManager — Firestore implementation of DatabaseManager.

Logical table names map to Firestore collections; each row becomes one document with
a Firestore-minted id (the domain managers own the logical key field, so inserts
append rather than upsert — matching BigQueryDatabaseManager's streaming semantics).
Reads resolve the logical key via an equality query. query() raises (Firestore has no
SQL); portable code uses the typed methods. The async client is used so calls don't
block the event loop the ADK/FastAPI servers run on.

Every query here is either a single-field equality (get/delete) or a single-field
order_by (list) — both are auto-indexed, so no composite indexes are required.
"""

from __future__ import annotations

from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .base import DatabaseManager, Row


class FirestoreDatabaseManager(DatabaseManager):
    def __init__(
        self,
        *,
        project: str,
        database: str = "(default)",
        client: firestore.AsyncClient | None = None,
    ) -> None:
        self._project = project
        self._database = database
        self._client = client or firestore.AsyncClient(project=project, database=database)

    async def insert(self, table: str, rows: list[Row]) -> None:
        col = self._client.collection(table)
        for row in rows:
            await col.add(dict(row))

    async def get(self, table: str, *, key_field: str, key: str) -> Row | None:
        query = self._client.collection(table).where(filter=FieldFilter(key_field, "==", key)).limit(1)
        async for doc in query.stream():
            return doc.to_dict()
        return None

    async def list(self, table: str, *, limit: int = 100, order_by: str | None = None) -> list[Row]:
        query: Any = self._client.collection(table)
        if order_by:
            query = query.order_by(order_by, direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        return [doc.to_dict() async for doc in query.stream()]

    async def delete(self, table: str, *, key_field: str, key: str) -> None:
        query = self._client.collection(table).where(filter=FieldFilter(key_field, "==", key))
        async for doc in query.stream():
            await doc.reference.delete()

    async def query(self, sql: str, *, params: dict[str, Any] | None = None) -> list[Row]:
        raise NotImplementedError("FirestoreDatabaseManager does not support raw SQL; use the typed methods.")
