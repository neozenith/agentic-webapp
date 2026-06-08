"""Contract tests for DatabaseManager + AssetMetadataManager, against the in-memory
implementation."""

from datetime import datetime, timezone

from agentic_core.database import AssetMetadataManager
from agentic_core.models import AssetMetadata


def test_insert_get_list_delete(database, run):
    run(database.insert("t", [{"id": "1", "v": "a"}, {"id": "2", "v": "b"}]))
    assert run(database.get("t", key_field="id", key="1"))["v"] == "a"
    assert run(database.get("t", key_field="id", key="missing")) is None
    assert len(run(database.list("t"))) == 2
    run(database.delete("t", key_field="id", key="1"))
    assert run(database.get("t", key_field="id", key="1")) is None


def _meta(asset_id: str) -> AssetMetadata:
    now = datetime.now(timezone.utc)
    return AssetMetadata(
        asset_id=asset_id,
        storage_key=f"assets/{asset_id}.png",
        filename=f"{asset_id}.png",
        content_type="image/png",
        size_bytes=3,
        created_at=now,
        updated_at=now,
        tags={"kind": "test"},
    )


def test_asset_metadata_roundtrip_preserves_tags(database, run):
    mgr = AssetMetadataManager(database, table="asset_metadata")
    run(mgr.record(_meta("abc")))
    got = run(mgr.get("abc"))
    assert got is not None
    assert got.storage_key == "assets/abc.png"
    assert got.tags == {"kind": "test"}  # survived JSON (de)serialization


def test_asset_metadata_list_and_delete(database, run):
    mgr = AssetMetadataManager(database, table="asset_metadata")
    run(mgr.record(_meta("a")))
    run(mgr.record(_meta("b")))
    assert {m.asset_id for m in run(mgr.list())} == {"a", "b"}
    run(mgr.delete("a"))
    assert run(mgr.get("a")) is None
