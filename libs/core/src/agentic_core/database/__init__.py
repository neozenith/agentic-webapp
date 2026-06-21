"""Tabular-database abstraction, its implementations, and domain managers built on
top of it."""

from .analytics import AnalyticsManager
from .asset_metadata import AssetMetadataManager
from .base import DatabaseManager
from .bigquery import BigQueryDatabaseManager
from .dashboards import DashboardManager, DashboardNotFoundError
from .factory import build_analytics_database_from_env, build_database_from_env
from .firestore import FirestoreDatabaseManager
from .folder import FolderManager
from .group import GroupManager
from .llm_usage import LlmUsageManager
from .memory import InMemoryDatabaseManager
from .seed import (
    FUEL_MODEL_ID,
    fuel_dashboards,
    fuel_semantic_model,
    seed_fuel_domain,
)
from .seed_consulting import (
    CONSULTING_MODEL_ID,
    consulting_dashboards,
    consulting_semantic_model,
    seed_consulting_domain,
)
from .semantic import SemanticManager, SemanticModelNotFoundError, SemanticQueryError

__all__ = [
    "DatabaseManager",
    "BigQueryDatabaseManager",
    "FirestoreDatabaseManager",
    "InMemoryDatabaseManager",
    "AssetMetadataManager",
    "FolderManager",
    "GroupManager",
    "LlmUsageManager",
    "AnalyticsManager",
    "SemanticManager",
    "SemanticModelNotFoundError",
    "SemanticQueryError",
    "DashboardManager",
    "DashboardNotFoundError",
    "FUEL_MODEL_ID",
    "fuel_semantic_model",
    "fuel_dashboards",
    "seed_fuel_domain",
    "CONSULTING_MODEL_ID",
    "consulting_semantic_model",
    "consulting_dashboards",
    "seed_consulting_domain",
    "build_database_from_env",
    "build_analytics_database_from_env",
]
