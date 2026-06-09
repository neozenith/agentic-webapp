"""Dependency-factory selection: real Settings from real env vars (no mocks), the
fail-loud branches for cloud backends, and the in-memory defaults. Cloud-client
construction lines are pragma'd (need real creds; covered by live deploy)."""

import pytest

from agentic_core.database import InMemoryDatabaseManager, LlmUsageManager
from agentic_core.storage import InMemoryStorageManager
from agentic_webapp.api import deps
from agentic_webapp.config import get_settings


def _clear() -> None:
    get_settings.cache_clear()
    deps.get_storage.cache_clear()
    deps.get_database.cache_clear()
    deps.get_asset_metadata_manager.cache_clear()
    deps.get_llm_usage_manager.cache_clear()
    deps.get_asset_service.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_caches():
    _clear()
    yield
    _clear()


def test_database_defaults_to_in_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    assert isinstance(deps.get_database(), InMemoryDatabaseManager)


def test_storage_defaults_to_in_memory(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    assert isinstance(deps.get_storage(), InMemoryStorageManager)


def test_database_firestore_requires_project_and_db(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "firestore")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("FIRESTORE_DATABASE", raising=False)
    with pytest.raises(RuntimeError, match="FIRESTORE_DATABASE"):
        deps.get_database()


def test_database_bigquery_requires_dataset(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "bigquery")
    monkeypatch.setenv("GCP_PROJECT", "proj")
    monkeypatch.delenv("BIGQUERY_DATASET", raising=False)
    with pytest.raises(RuntimeError, match="BIGQUERY_DATASET"):
        deps.get_database()


def test_storage_gcs_requires_bucket(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "gcs")
    monkeypatch.delenv("ASSETS_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="ASSETS_BUCKET"):
        deps.get_storage()


def test_domain_managers_compose_on_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    assert isinstance(deps.get_llm_usage_manager(), LlmUsageManager)
    assert deps.get_asset_metadata_manager() is not None
    assert deps.get_asset_service() is not None
