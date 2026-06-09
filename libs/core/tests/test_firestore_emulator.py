"""Contract tests for FirestoreDatabaseManager against the REAL Firestore emulator.

No mocks (per the project testing rules): we exercise the actual async Firestore
client. These run only when the emulator is reachable, which the suite signals via
FIRESTORE_EMULATOR_HOST. Start one with:

    gcloud emulators firestore start --host-port=localhost:8089
    FIRESTORE_EMULATOR_HOST=localhost:8089 uv run --directory libs/core pytest

The async Firestore client binds to the event loop of its first use, so each test
runs all its operations inside a single asyncio.run() (one loop). Each test uses a
unique collection so repeated runs against a persistent emulator stay isolated.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest

from agentic_core.database import AssetMetadataManager
from agentic_core.database.firestore import FirestoreDatabaseManager
from agentic_core.models import AssetMetadata

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Requires the Firestore emulator (set FIRESTORE_EMULATOR_HOST)",
)


def _db() -> FirestoreDatabaseManager:
    return FirestoreDatabaseManager(project="agentic-webapp-test", database="(default)")


def test_insert_get_list_delete():
    async def scenario():
        db = _db()
        table = f"t_{uuid.uuid4().hex}"
        await db.insert(table, [{"id": "1", "v": "a"}, {"id": "2", "v": "b"}])
        assert (await db.get(table, key_field="id", key="1"))["v"] == "a"
        assert await db.get(table, key_field="id", key="missing") is None
        assert len(await db.list(table)) == 2
        ordered = await db.list(table, order_by="id")  # exercises the order_by branch
        assert [r["id"] for r in ordered] == ["2", "1"]
        await db.delete(table, key_field="id", key="1")
        assert await db.get(table, key_field="id", key="1") is None

    asyncio.run(scenario())


def test_asset_metadata_roundtrip_preserves_tags():
    async def scenario():
        table = f"asset_metadata_{uuid.uuid4().hex}"
        mgr = AssetMetadataManager(_db(), table=table)
        now = datetime.now(timezone.utc)
        await mgr.record(
            AssetMetadata(
                asset_id="abc",
                storage_key="assets/abc.png",
                filename="abc.png",
                content_type="image/png",
                size_bytes=3,
                created_at=now,
                updated_at=now,
                tags={"kind": "test"},
            )
        )
        got = await mgr.get("abc")
        assert got is not None
        assert got.storage_key == "assets/abc.png"
        assert got.tags == {"kind": "test"}  # survived JSON (de)serialization round-trip

    asyncio.run(scenario())
