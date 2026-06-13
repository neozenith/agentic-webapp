"""RBAC visibility rules (pure functions, no I/O)."""

from datetime import datetime, timezone

from agentic_core.access import accessible_folder_ids, asset_visible, folder_visible
from agentic_core.models import AssetMetadata, Folder

NOW = datetime.now(timezone.utc)


def _asset(aid: str, **over: object) -> AssetMetadata:
    return AssetMetadata(asset_id=aid, storage_key=f"assets/{aid}", created_at=NOW, updated_at=NOW, **over)


def _folder(fid: str, **over: object) -> Folder:
    return Folder(folder_id=fid, name=fid, created_at=NOW, **over)


def test_asset_principal_matches():
    owned = _asset("a", owner_id="u1")
    assert asset_visible(owned, viewer_id="u1", is_admin=False, viewer_group_ids=set(), accessible_folders=set())
    assert not asset_visible(owned, viewer_id="u2", is_admin=False, viewer_group_ids=set(), accessible_folders=set())
    # shared with a user
    shared_u = _asset("b", owner_id="u1", shared_user_ids=["u2"])
    assert asset_visible(shared_u, viewer_id="u2", is_admin=False, viewer_group_ids=set(), accessible_folders=set())
    # shared with a group the viewer belongs to
    shared_g = _asset("c", owner_id="u1", shared_group_ids=["g1"])
    assert asset_visible(shared_g, viewer_id="u2", is_admin=False, viewer_group_ids={"g1"}, accessible_folders=set())
    assert not asset_visible(shared_g, viewer_id="u2", is_admin=False, viewer_group_ids={"g9"}, accessible_folders=set())


def test_admin_and_unowned_are_visible():
    owned = _asset("a", owner_id="u1")
    assert asset_visible(owned, viewer_id="zzz", is_admin=True, viewer_group_ids=set(), accessible_folders=set())
    legacy = _asset("b", owner_id=None)
    assert asset_visible(legacy, viewer_id=None, is_admin=False, viewer_group_ids=set(), accessible_folders=set())


def test_folder_share_cascades_to_files_and_subfolders():
    # parent shared with u2 (directly); child folder inherits; a file in the child inherits.
    parent = _folder("p", owner_id="u1", shared_user_ids=["u2"])
    child = _folder("c", owner_id="u1", parent_id="p")
    other = _folder("o", owner_id="u1")  # unrelated, not shared
    acc = accessible_folder_ids([parent, child, other], viewer_id="u2", is_admin=False, viewer_group_ids=set())
    assert acc == {"p", "c"}  # parent + descendant, not the unrelated folder

    file_in_child = _asset("f", owner_id="u1", folder_id="c")
    assert asset_visible(file_in_child, viewer_id="u2", is_admin=False, viewer_group_ids=set(), accessible_folders=acc)
    file_in_other = _asset("g", owner_id="u1", folder_id="o")
    assert not asset_visible(file_in_other, viewer_id="u2", is_admin=False, viewer_group_ids=set(), accessible_folders=acc)
    assert folder_visible(child, viewer_id="u2", is_admin=False, viewer_group_ids=set(), accessible_folders=acc)


def test_admin_sees_all_folders():
    folders = [_folder("p", owner_id="u1"), _folder("c", owner_id="u1", parent_id="p")]
    assert accessible_folder_ids(folders, viewer_id="x", is_admin=True, viewer_group_ids=set()) == {"p", "c"}
