"""ExtractionManager — the inventory of structured extractions pulled from assets by
agent tools, built on a DatabaseManager (composition, like LlmUsageManager and
AssetMetadataManager). This is the first manager of the 'extract from a document' tool
category: the common envelope lives in ExtractionRecord, and the variable per-doc-type
payload rides in `fields` (serialised to a single fields_json column), so growing the
next extraction tool needs no new table or schema. Backend-agnostic: BigQuery in cloud,
Firestore in the deployed envs, in-memory in tests."""

from __future__ import annotations

import json

from ..models import ExtractionRecord
from .base import DatabaseManager, Row


class ExtractionManager:
    def __init__(self, db: DatabaseManager, *, table: str = "extractions") -> None:
        self._db = db
        self._table = table

    async def record(self, extraction: ExtractionRecord) -> ExtractionRecord:
        """Insert one extraction record."""
        await self._db.insert(self._table, [self._to_row(extraction)])
        return extraction

    async def get(self, extraction_id: str) -> ExtractionRecord | None:
        row = await self._db.get(self._table, key_field="extraction_id", key=extraction_id)
        return self._from_row(row) if row else None

    async def list(self, *, limit: int = 200) -> list[ExtractionRecord]:
        rows = await self._db.list(self._table, limit=limit, order_by="created_at")
        return [self._from_row(r) for r in rows]

    async def delete(self, extraction_id: str) -> None:
        await self._db.delete(self._table, key_field="extraction_id", key=extraction_id)

    @staticmethod
    def _to_row(e: ExtractionRecord) -> Row:
        return {
            "extraction_id": e.extraction_id,
            "asset_id": e.asset_id,
            "doc_type": e.doc_type,
            "user_id": e.user_id,
            "session_id": e.session_id,
            "fields_json": json.dumps(e.fields or {}),
            "model_id": e.model_id,
            "created_at": e.created_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: Row) -> ExtractionRecord:
        raw_fields = row.get("fields_json")
        fields = json.loads(raw_fields) if raw_fields else {}
        return ExtractionRecord(
            extraction_id=row["extraction_id"],
            asset_id=row["asset_id"],
            doc_type=row["doc_type"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            fields=fields,
            model_id=row.get("model_id"),
            created_at=row["created_at"],  # pydantic coerces str|datetime
        )
