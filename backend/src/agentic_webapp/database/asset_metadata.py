"""AssetMetadataManager — the first domain manager built on a DatabaseManager.

It is composition, not inheritance: it holds *a* DatabaseManager and a table name,
and translates between the generic Row dicts the database speaks and the typed
AssetMetadata model the rest of the app speaks. Point it at any DatabaseManager
(BigQuery in prod, in-memory in tests) without changing a line of domain logic.
"""

from __future__ import annotations

import json

from ..models import AssetMetadata
from .base import DatabaseManager, Row


class AssetMetadataManager:
    def __init__(self, db: DatabaseManager, *, table: str = "asset_metadata") -> None:
        self._db = db
        self._table = table

    async def record(self, meta: AssetMetadata) -> AssetMetadata:
        await self._db.insert(self._table, [self._to_row(meta)])
        return meta

    async def get(self, asset_id: str) -> AssetMetadata | None:
        row = await self._db.get(self._table, key_field="asset_id", key=asset_id)
        return self._from_row(row) if row else None

    async def list(self, *, limit: int = 100) -> list[AssetMetadata]:
        rows = await self._db.list(self._table, limit=limit, order_by="created_at")
        return [self._from_row(r) for r in rows]

    async def delete(self, asset_id: str) -> None:
        await self._db.delete(self._table, key_field="asset_id", key=asset_id)

    # --- Row <-> model mapping (the table schema lives here) ---

    @staticmethod
    def _to_row(meta: AssetMetadata) -> Row:
        return {
            "asset_id": meta.asset_id,
            "storage_key": meta.storage_key,
            "filename": meta.filename,
            "content_type": meta.content_type,
            "size_bytes": meta.size_bytes,
            "created_at": meta.created_at.isoformat(),
            "updated_at": meta.updated_at.isoformat(),
            # Nested tags are flattened to a JSON string so the table schema stays
            # simple and portable across backends.
            "metadata_json": json.dumps(meta.tags or {}),
        }

    @staticmethod
    def _from_row(row: Row) -> AssetMetadata:
        raw_tags = row.get("metadata_json")
        tags = json.loads(raw_tags) if isinstance(raw_tags, str) and raw_tags else (raw_tags or {})
        return AssetMetadata(
            asset_id=row["asset_id"],
            storage_key=row["storage_key"],
            filename=row.get("filename"),
            content_type=row.get("content_type"),
            size_bytes=row.get("size_bytes"),
            created_at=row["created_at"],  # pydantic coerces str|datetime
            updated_at=row["updated_at"],
            tags=tags,
        )
