"""LlmUsageManager — the bookkeeping inventory of LLM calls, built on a
DatabaseManager (composition, like AssetMetadataManager). The agent writes records
via its ADK callback; the backend admin panel reads them. Backend-agnostic: BigQuery
in cloud, in-memory in tests."""

from __future__ import annotations

from ..models import LlmUsageRecord
from .base import DatabaseManager, Row


class LlmUsageManager:
    def __init__(self, db: DatabaseManager, *, table: str = "llm_usage") -> None:
        self._db = db
        self._table = table

    async def record(self, usage: LlmUsageRecord) -> LlmUsageRecord:
        await self._db.insert(self._table, [self._to_row(usage)])
        return usage

    async def list(self, *, limit: int = 200) -> list[LlmUsageRecord]:
        rows = await self._db.list(self._table, limit=limit, order_by="timestamp")
        return [self._from_row(r) for r in rows]

    @staticmethod
    def _to_row(u: LlmUsageRecord) -> Row:
        return {
            "request_id": u.request_id,
            "app_name": u.app_name,
            "user_id": u.user_id,
            "session_id": u.session_id,
            "model_id": u.model_id,
            "prompt_tokens": u.prompt_tokens,
            "output_tokens": u.output_tokens,
            "total_tokens": u.total_tokens,
            "est_cost_usd": u.est_cost_usd,
            "timestamp": u.timestamp.isoformat(),
        }

    @staticmethod
    def _from_row(row: Row) -> LlmUsageRecord:
        return LlmUsageRecord(
            request_id=row["request_id"],
            app_name=row["app_name"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            model_id=row["model_id"],
            prompt_tokens=row.get("prompt_tokens") or 0,
            output_tokens=row.get("output_tokens") or 0,
            total_tokens=row.get("total_tokens") or 0,
            est_cost_usd=row.get("est_cost_usd") or 0.0,
            timestamp=row["timestamp"],  # pydantic coerces str|datetime
        )
