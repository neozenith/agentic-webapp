"""Pure RBAC visibility resolution for assets + folders.

Kept dependency-free (no DB, no I/O) so the rules are unit-testable. The service layer
loads the data (the viewer's group memberships, the folder set) and calls these.

Rules:
  - A principal match = the viewer owns it, is in shared_user_ids, or belongs to a group
    in shared_group_ids.
  - A folder is visible if: admin, unowned (legacy), a direct principal match, OR an
    ancestor folder is visible (sharing cascades down the folder tree).
  - An asset is visible if: admin, unowned, a direct principal match, OR its folder is
    visible (files inherit their folder's access).
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import AssetMetadata, Folder


def _principal_match(item: AssetMetadata | Folder, *, viewer_id: str | None, viewer_group_ids: set[str]) -> bool:
    if item.owner_id is None:  # legacy/unowned -> public
        return True
    if viewer_id is None:
        return False
    if item.owner_id == viewer_id or viewer_id in item.shared_user_ids:
        return True
    return bool(set(item.shared_group_ids) & viewer_group_ids)


def accessible_folder_ids(
    folders: Iterable[Folder],
    *,
    viewer_id: str | None,
    is_admin: bool,
    viewer_group_ids: set[str],
) -> set[str]:
    """The folder_ids the viewer can see — direct matches plus all descendants of those
    (sharing a folder grants its whole subtree)."""
    folder_list = list(folders)
    if is_admin:
        return {f.folder_id for f in folder_list}
    accessible = {
        f.folder_id for f in folder_list if _principal_match(f, viewer_id=viewer_id, viewer_group_ids=viewer_group_ids)
    }
    # Propagate down the tree: a folder is accessible if its parent is.
    changed = True
    while changed:
        changed = False
        for f in folder_list:
            if f.folder_id not in accessible and f.parent_id in accessible:
                accessible.add(f.folder_id)
                changed = True
    return accessible


def asset_visible(
    asset: AssetMetadata,
    *,
    viewer_id: str | None,
    is_admin: bool,
    viewer_group_ids: set[str],
    accessible_folders: set[str],
) -> bool:
    if is_admin:
        return True
    if _principal_match(asset, viewer_id=viewer_id, viewer_group_ids=viewer_group_ids):
        return True
    return asset.folder_id is not None and asset.folder_id in accessible_folders


def folder_visible(
    folder: Folder,
    *,
    viewer_id: str | None,
    is_admin: bool,
    viewer_group_ids: set[str],
    accessible_folders: set[str],
) -> bool:
    return is_admin or folder.folder_id in accessible_folders or _principal_match(
        folder, viewer_id=viewer_id, viewer_group_ids=viewer_group_ids
    )
