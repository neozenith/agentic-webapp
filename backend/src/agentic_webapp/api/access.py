"""Route-level RBAC context helper.

Resolves the (viewer_id, is_admin, group_ids) triple the `agentic_core.access` helpers
need. Group membership is loaded here (the one I/O the pure access rules can't do) so the
routes can stay thin and just call `accessible_folder_ids` / `asset_visible` / `folder_visible`.
"""

from __future__ import annotations

from fastapi import Request

from agentic_core.database import GroupManager
from .auth import viewer


async def viewer_ctx(request: Request, groups: GroupManager) -> tuple[str | None, bool, set[str]]:
    """(viewer_id, is_admin, group_ids) for the caller. group_ids is empty for an
    unidentified caller."""
    viewer_id, is_admin = viewer(request)
    group_ids = await groups.group_ids_for_user(viewer_id) if viewer_id else set()
    return viewer_id, is_admin, group_ids
