"""Dependency wiring: build the concrete managers from settings, once per process.

Selection is explicit and fails loud — choosing a GCP backend without its required
config raises at first use rather than silently degrading to in-memory. Tests swap
implementations via FastAPI's dependency_overrides (see tests/), so these are only
the production defaults.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from agentic_core.database import (
    AnalyticsManager,
    AssetMetadataManager,
    BigQueryDatabaseManager,
    DashboardManager,
    DatabaseManager,
    FirestoreDatabaseManager,
    FolderManager,
    GroupManager,
    InMemoryDatabaseManager,
    LlmUsageManager,
    SemanticManager,
)
from ..services import AssetService, DbtClient, FilesystemDbtClient, HttpDbtClient
from agentic_core.storage import GCSStorageManager, InMemoryStorageManager, StorageManager


@lru_cache
def get_storage() -> StorageManager:
    s = get_settings()
    if s.storage_backend == "gcs":
        if not s.assets_bucket:
            raise RuntimeError("STORAGE_BACKEND=gcs requires ASSETS_BUCKET to be set")
        return GCSStorageManager(  # pragma: no cover — real GCS client; covered by live deploy
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
        return BigQueryDatabaseManager(
            project=s.gcp_project, dataset=s.bigquery_dataset
        )  # pragma: no cover — real BQ client; covered by live deploy
    if s.database_backend == "firestore":
        if not (s.gcp_project and s.firestore_database):
            raise RuntimeError("DATABASE_BACKEND=firestore requires GCP_PROJECT and FIRESTORE_DATABASE")
        return FirestoreDatabaseManager(
            project=s.gcp_project, database=s.firestore_database
        )  # pragma: no cover — real Firestore client; covered by libs/core emulator tests + live deploy
    return InMemoryDatabaseManager()


@lru_cache
def get_asset_metadata_manager() -> AssetMetadataManager:
    return AssetMetadataManager(get_database(), table=get_settings().asset_metadata_table)


@lru_cache
def get_folder_manager() -> FolderManager:
    return FolderManager(get_database())


@lru_cache
def get_group_manager() -> GroupManager:
    return GroupManager(get_database())


@lru_cache
def get_llm_usage_manager() -> LlmUsageManager:
    return LlmUsageManager(get_database(), table=get_settings().llm_usage_table)


@lru_cache
def get_analytics_database() -> DatabaseManager:
    """The shared ANALYTICS warehouse handle — BigQuery when a project+dataset are configured,
    else ONE in-memory store. Distinct from get_database() (operational Firestore): analytics is
    its own backend axis. Returned as a singleton so the analytics, semantic, dashboard managers
    (and the local demo seed) all read/write the SAME tables — without this, each manager would
    build its own empty in-memory DB and a seeded fact table would be invisible to a query."""
    s = get_settings()
    if s.gcp_project and s.bigquery_dataset:
        return BigQueryDatabaseManager(  # pragma: no cover — real BQ client; covered by live deploy
            project=s.gcp_project, dataset=s.bigquery_dataset
        )
    return InMemoryDatabaseManager()


@lru_cache
def get_analytics_manager() -> AnalyticsManager:
    """The analytics warehouse (AnalyticsManager), over the shared analytics DB axis."""
    return AnalyticsManager(get_analytics_database())


@lru_cache
def get_semantic_manager() -> SemanticManager:
    """The semantic layer (logical data model) over the shared analytics DB axis."""
    return SemanticManager(get_analytics_database(), table=get_settings().semantic_models_table)


@lru_cache
def get_dashboard_manager() -> DashboardManager:
    """The dashboard specs (AnalyticsManager data→pixels) over the shared analytics DB axis."""
    return DashboardManager(get_analytics_database(), table=get_settings().dashboards_table)


@lru_cache
def get_dbt_client() -> DbtClient:
    """The dbt-core project window — the HTTP sidecar when DBT_BASE_URL is set (cloud/compose),
    else the on-disk filesystem client (local: lists models offline, runs dbt if the CLI exists)."""
    s = get_settings()
    if s.dbt_base_url:
        return HttpDbtClient(s.dbt_base_url)  # pragma: no cover — real sidecar; covered by live deploy
    return FilesystemDbtClient(s.dbt_project_dir, target=s.environment)


@lru_cache
def get_asset_service() -> AssetService:
    s = get_settings()
    return AssetService(
        get_storage(),
        get_asset_metadata_manager(),
        signed_url_ttl_seconds=s.signed_url_ttl_seconds,
    )
