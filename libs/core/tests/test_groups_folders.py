"""Contract tests for GroupManager + FolderManager (in-memory, real, no mocks)."""

from datetime import datetime, timezone

from agentic_core.database import FolderManager, GroupManager
from agentic_core.models import Folder, Group

NOW = datetime.now(timezone.utc)


def test_group_roundtrip_and_membership_lookup(database, run):
    mgr = GroupManager(database)
    run(mgr.record(Group(group_id="g1", name="Finance", member_ids=["u1", "u2"], created_at=NOW)))
    run(mgr.record(Group(group_id="g2", name="Ops", member_ids=["u2"], created_at=NOW)))

    one = run(mgr.get("g1"))
    assert one is not None and one.name == "Finance" and one.member_ids == ["u1", "u2"]
    assert run(mgr.group_ids_for_user("u2")) == {"g1", "g2"}
    assert run(mgr.group_ids_for_user("u1")) == {"g1"}
    assert run(mgr.group_ids_for_user("nobody")) == set()


def test_group_update_and_delete(database, run):
    mgr = GroupManager(database)
    run(mgr.record(Group(group_id="g1", name="Finance", member_ids=["u1"], created_at=NOW)))
    run(mgr.update(Group(group_id="g1", name="Finance Team", member_ids=["u1", "u3"], created_at=NOW)))
    got = run(mgr.get("g1"))
    assert got is not None and got.name == "Finance Team" and got.member_ids == ["u1", "u3"]
    run(mgr.delete("g1"))
    assert run(mgr.get("g1")) is None


def test_folder_roundtrip_with_sharing(database, run):
    mgr = FolderManager(database)
    run(
        mgr.record(
            Folder(
                folder_id="f1",
                name="Receipts",
                parent_id=None,
                owner_id="u1",
                shared_user_ids=["u2"],
                shared_group_ids=["g1"],
                created_at=NOW,
            )
        )
    )
    f = run(mgr.get("f1"))
    assert f is not None
    assert f.name == "Receipts" and f.owner_id == "u1"
    assert f.shared_user_ids == ["u2"] and f.shared_group_ids == ["g1"]
    assert {x.folder_id for x in run(mgr.list())} == {"f1"}
