"""Dependency wiring: build the concrete managers from settings, once per process.

Selection is explicit and fails loud — choosing a GCP backend without its required
config raises at first use rather than silently degrading to in-memory. Tests swap
implementations via FastAPI's dependency_overrides (see tests/), so these are only
the production defaults.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from ..database import (
    AssetMetadataManager,
    BigQueryDatabaseManager,
    DatabaseManager,
    InMemoryDatabaseManager,
)
from ..services import AssetService
from ..storage import GCSStorageManager, InMemoryStorageManager, StorageManager


@lru_cache
def get_storage() -> StorageManager:
    s = get_settings()
    if s.storage_backend == "gcs":
        if not s.assets_bucket:
            raise RuntimeError("STORAGE_BACKEND=gcs requires ASSETS_BUCKET to be set")
        return GCSStorageManager(
            s.assets_bucket,
            signing_service_account=s.signing_service_account,
            temp_dir=s.temp_dir,
        )
    return InMemoryStorageManager(temp_dir=s.temp_dir)


@lru_cache
def get_database() -> DatabaseManager:
    s = get_settings()
    if s.database_backend == "bigquery":
        if not (s.gcp_project and s.bigquery_dataset):
            raise RuntimeError("DATABASE_BACKEND=bigquery requires GCP_PROJECT and BIGQUERY_DATASET")
        return BigQueryDatabaseManager(project=s.gcp_project, dataset=s.bigquery_dataset)
    return InMemoryDatabaseManager()


@lru_cache
def get_asset_metadata_manager() -> AssetMetadataManager:
    return AssetMetadataManager(get_database(), table=get_settings().asset_metadata_table)


@lru_cache
def get_asset_service() -> AssetService:
    s = get_settings()
    return AssetService(
        get_storage(),
        get_asset_metadata_manager(),
        signed_url_ttl_seconds=s.signed_url_ttl_seconds,
    )
