"""Shared fixtures. Everything uses REAL in-memory implementations — no mocks
(project rule). `run` drives the async managers from sync tests without an extra
async-test plugin."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from agentic_webapp.api import deps
from agentic_core.database import AssetMetadataManager, FolderManager, GroupManager, InMemoryDatabaseManager
from agentic_webapp.main import create_app
from agentic_webapp.services import AssetService
from agentic_core.storage import InMemoryStorageManager


@pytest.fixture
def run():
    """Run a coroutine to completion (real event loop, real code)."""
    return lambda coro: asyncio.run(coro)


@pytest.fixture
def storage(tmp_path):
    return InMemoryStorageManager(temp_dir=tmp_path)


@pytest.fixture
def database():
    return InMemoryDatabaseManager()


@pytest.fixture
def asset_service(storage, database):
    metadata = AssetMetadataManager(database, table="asset_metadata")
    return AssetService(storage, metadata, signed_url_ttl_seconds=60)


@pytest.fixture
def folder_manager(database):
    return FolderManager(database)


@pytest.fixture
def group_manager(database):
    return GroupManager(database)


@pytest.fixture
def client(asset_service, folder_manager, group_manager):
    """A TestClient whose asset, folder, and group managers all share one in-memory
    operational store (the `database` fixture), so cross-resource visibility (a file in a
    shared folder, a group-shared asset) resolves against real, consistent data."""
    app = create_app()
    app.dependency_overrides[deps.get_asset_service] = lambda: asset_service
    app.dependency_overrides[deps.get_folder_manager] = lambda: folder_manager
    app.dependency_overrides[deps.get_group_manager] = lambda: group_manager
    return TestClient(app)


@pytest.fixture
def admin_client(client):
    """A client carrying the admin test persona, so RBAC-gated areas (admin/analytics)
    are reachable. Identity is the IAP header (ADR-0004), simulated here in tests."""
    client.headers.update({"X-Goog-Authenticated-User-Email": "ada.admin@example.com"})
    return client
