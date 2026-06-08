"""Shared fixtures. Everything uses REAL in-memory implementations — no mocks
(project rule). `run` drives the async managers from sync tests without an extra
async-test plugin."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from agentic_webapp.api import deps
from agentic_core.database import AssetMetadataManager, InMemoryDatabaseManager
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
def client(asset_service):
    app = create_app()
    app.dependency_overrides[deps.get_asset_service] = lambda: asset_service
    return TestClient(app)
