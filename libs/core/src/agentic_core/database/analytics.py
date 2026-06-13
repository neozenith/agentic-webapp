"""AnalyticsManager — the agentic-webapp analytics / data-modelling space.

This is a SEPARATE concern from the operational stores: sessions (SessionsManager) and
asset metadata (AssetMetadataManager) live in **Firestore**, whereas analytics data lives
in **BigQuery** in the cloud (and an in-memory DatabaseManager locally). Keeping analytics
on its own backend axis lets it grow into an extensible data-modelling + semantic layer
(explored on the Analytics page, dashboards layered on top) without entangling the
low-latency operational path.

The first analytics record type is the extraction (structured data an agent tool pulled
from an asset, e.g. a fuel receipt). New analytics record types are added here as more
methods over the same backend-agnostic DatabaseManager.
"""

from __future__ import annotations

import json

from ..models import ExtractionRecord
from .base import DatabaseManager, Row


class AnalyticsManager:
    def __init__(self, db: DatabaseManager, *, extractions_table: str = "extractions") -> None:
        self._db = db
        self._extractions = extractions_table

    # --- extractions (the first analytics record type) ---------------------------------

    async def record_extraction(self, extraction: ExtractionRecord) -> ExtractionRecord:
        """Insert one extraction record."""
        await self._db.insert(self._extractions, [self._extraction_to_row(extraction)])
        return extraction

    async def get_extraction(self, extraction_id: str) -> ExtractionRecord | None:
        row = await self._db.get(self._extractions, key_field="extraction_id", key=extraction_id)
        return self._extraction_from_row(row) if row else None

    async def list_extractions(self, *, limit: int = 200) -> list[ExtractionRecord]:
        rows = await self._db.list(self._extractions, limit=limit, order_by="created_at")
        return [self._extraction_from_row(r) for r in rows]

    async def delete_extraction(self, extraction_id: str) -> None:
        await self._db.delete(self._extractions, key_field="extraction_id", key=extraction_id)

    @staticmethod
    def _extraction_to_row(e: ExtractionRecord) -> Row:
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
    def _extraction_from_row(row: Row) -> ExtractionRecord:
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
