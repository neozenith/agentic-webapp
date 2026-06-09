"""ADK after_model_callback that itemises every LLM call into the bookkeeping table
(token counts + estimated cost, per user + session + model + timestamp) via the
shared agentic-core LlmUsageManager.

Backend selection mirrors the backend's DATABASE_BACKEND switch: Firestore (default in
the deployed envs) or BigQuery when configured, otherwise in-memory (local/dev — not
durable). When DATABASE_BACKEND is unset, fall back to presence-based detection so the
agent stays usable without extra config.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agentic_core.database import (
    BigQueryDatabaseManager,
    FirestoreDatabaseManager,
    InMemoryDatabaseManager,
    LlmUsageManager,
)
from agentic_core.models import LlmUsageRecord
from agentic_core.pricing import estimate_cost_usd

log = logging.getLogger(__name__)

_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")


def _build_usage_manager() -> LlmUsageManager:
    project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    table = os.environ.get("LLM_USAGE_TABLE", "llm_usage")
    backend = os.environ.get("DATABASE_BACKEND", "").lower()
    firestore_db = os.environ.get("FIRESTORE_DATABASE")
    dataset = os.environ.get("BIGQUERY_DATASET")

    want_firestore = backend == "firestore" or (not backend and firestore_db)
    want_bigquery = backend == "bigquery" or (not backend and dataset and not firestore_db)

    if want_firestore and project and firestore_db:  # pragma: no cover — real Firestore client; covered by live deploy
        log.info("LLM usage -> Firestore %s/%s table=%s", project, firestore_db, table)
        return LlmUsageManager(FirestoreDatabaseManager(project=project, database=firestore_db), table=table)
    if want_bigquery and project and dataset:  # pragma: no cover — real BQ client; covered by live deploy
        log.info("LLM usage -> BigQuery %s.%s.%s", project, dataset, table)
        return LlmUsageManager(BigQueryDatabaseManager(project=project, dataset=dataset), table=table)
    log.warning(
        "No durable DB configured (DATABASE_BACKEND/FIRESTORE_DATABASE/BIGQUERY_DATASET) — LLM usage in-memory only"
    )
    return LlmUsageManager(InMemoryDatabaseManager(), table=table)


_USAGE = _build_usage_manager()


async def record_usage(callback_context: Any, llm_response: Any) -> None:  # ADK callback signature (untyped)
    """Record one model call's token usage + estimated cost. Returns None so ADK
    keeps the original response. Never raises — bookkeeping must not break a reply."""
    usage = getattr(llm_response, "usage_metadata", None)
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    output = getattr(usage, "candidates_token_count", 0) or 0
    total = getattr(usage, "total_token_count", 0) or (prompt + output)
    if total <= 0:
        return None

    ictx = getattr(callback_context, "_invocation_context", None)
    session = getattr(ictx, "session", None)
    invocation_id = getattr(callback_context, "invocation_id", "") or "unknown"
    record = LlmUsageRecord(
        # Unique per model call (a turn can make several), for a fully itemised inventory.
        request_id=f"{invocation_id}:{uuid4().hex[:8]}",
        app_name=getattr(session, "app_name", None) or "assistant",
        user_id=getattr(session, "user_id", None) or "anonymous",
        session_id=getattr(session, "id", None) or "unknown",
        model_id=_MODEL,
        prompt_tokens=prompt,
        output_tokens=output,
        total_tokens=total,
        est_cost_usd=estimate_cost_usd(_MODEL, prompt, output),
        timestamp=datetime.now(timezone.utc),
    )
    try:
        await _USAGE.record(record)
        log.info(
            "usage: user=%s session=%s tokens=%d cost=$%.6f",
            record.user_id,
            record.session_id,
            total,
            record.est_cost_usd,
        )
    except Exception:  # noqa: BLE001 — auxiliary write; resilience over failing the reply  # pragma: no cover — defensive catch-all
        log.exception("failed to record LLM usage")
    return None
