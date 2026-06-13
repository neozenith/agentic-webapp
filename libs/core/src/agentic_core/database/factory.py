"""build_database_from_env — the single env-driven DatabaseManager selector shared by
every analytics manager that runs outside the FastAPI backend (the agent's bookkeeping
and extraction tools, and future tools of that category). The backend itself selects via
its pydantic Settings (api/deps.py); this is the equivalent for the agent, kept in one
place so the 'which backend?' rule never drifts between tools.

Selection mirrors the backend's DATABASE_BACKEND switch, with presence-based fallback so
the agent stays usable with no extra config:
  - DATABASE_BACKEND=firestore (or unset + FIRESTORE_DATABASE present) -> Firestore
  - DATABASE_BACKEND=bigquery  (or unset + BIGQUERY_DATASET present)   -> BigQuery
  - otherwise                                                          -> in-memory (local/dev)
"""

from __future__ import annotations

import logging
import os

from .base import DatabaseManager
from .bigquery import BigQueryDatabaseManager
from .firestore import FirestoreDatabaseManager
from .memory import InMemoryDatabaseManager

log = logging.getLogger(__name__)


def build_database_from_env() -> DatabaseManager:
    """Construct the configured DatabaseManager from environment variables."""
    project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    backend = os.environ.get("DATABASE_BACKEND", "").lower()
    firestore_db = os.environ.get("FIRESTORE_DATABASE")
    dataset = os.environ.get("BIGQUERY_DATASET")

    want_firestore = backend == "firestore" or (not backend and firestore_db)
    want_bigquery = backend == "bigquery" or (not backend and dataset and not firestore_db)

    if want_firestore and project and firestore_db:  # pragma: no cover — real Firestore client; covered by live deploy
        log.info("database -> Firestore %s/%s", project, firestore_db)
        return FirestoreDatabaseManager(project=project, database=firestore_db)
    if want_bigquery and project and dataset:  # pragma: no cover — real BQ client; covered by live deploy
        log.info("database -> BigQuery %s.%s", project, dataset)
        return BigQueryDatabaseManager(project=project, dataset=dataset)
    log.warning("No durable DB configured (DATABASE_BACKEND/FIRESTORE_DATABASE/BIGQUERY_DATASET) — using in-memory")
    return InMemoryDatabaseManager()
