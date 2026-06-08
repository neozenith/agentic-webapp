"""Fixtures for the core contract tests — real in-memory implementations, no mocks."""

import asyncio

import pytest

from agentic_core.database import InMemoryDatabaseManager
from agentic_core.storage import InMemoryStorageManager


@pytest.fixture
def run():
    return lambda coro: asyncio.run(coro)


@pytest.fixture
def storage(tmp_path):
    return InMemoryStorageManager(temp_dir=tmp_path)


@pytest.fixture
def database():
    return InMemoryDatabaseManager()
