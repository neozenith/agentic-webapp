"""Folder endpoints — create/list/share/delete real named folders for the Asset Manager.
Any signed-in user may create + list (scoped to what they can see); only the owner/admin
may share or delete. Folders nest via parent_id and cascade their sharing to contained
assets and sub-folders (see agentic_core.access). Identity comes from `auth.viewer`."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agentic_core.access import accessible_folder_ids, folder_visible
from agentic_core.database import FolderManager, GroupManager
from agentic_core.models import Folder
from ...identity import mask_user_id
from ..access import viewer_ctx
from ..auth import viewer
from ..deps import get_folder_manager, get_group_manager

router = APIRouter(prefix="/api/folders", tags=["folders"])

FolderDep = Annotated[FolderManager, Depends(get_folder_manager)]
GroupDep = Annotated[GroupManager, Depends(get_group_manager)]


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: str | None = None


class ShareRequest(BaseModel):
    add_user_emails: list[str] = []
    remove_user_ids: list[str] = []
    add_group_ids: list[str] = []
    remove_group_ids: list[str] = []


def _owner_or_admin(folder: Folder, viewer_id: str | None, *, is_admin: bool) -> bool:
    return is_admin or folder.owner_id is None or folder.owner_id == viewer_id


@router.post("", response_model=Folder, status_code=201)
async def create_folder(folders: FolderDep, request: Request, body: CreateFolderRequest) -> Folder:
    owner_id, _ = viewer(request)
    folder = Folder(
        folder_id=uuid4().hex,
        name=body.name,
        parent_id=body.parent_id,
        owner_id=owner_id,
        created_at=datetime.now(timezone.utc),
    )
    return await folders.record(folder)


@router.get("", response_model=list[Folder])
async def list_folders(folders: FolderDep, groups: GroupDep, request: Request) -> list[Folder]:
    viewer_id, is_admin, group_ids = await viewer_ctx(request, groups)
    all_folders = await folders.list()
    accessible = accessible_folder_ids(
        all_folders, viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids
    )
    return [
        f
        for f in all_folders
        if folder_visible(
            f, viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids, accessible_folders=accessible
        )
    ]


@router.post("/{folder_id}/share", response_model=Folder)
async def share_folder(folders: FolderDep, request: Request, folder_id: str, body: ShareRequest) -> Folder:
    folder = await folders.get(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    viewer_id, is_admin = viewer(request)
    if not _owner_or_admin(folder, viewer_id, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="only the owner or an admin may share this folder")
    add_user_ids = {mask_user_id(e) for e in body.add_user_emails if e.strip()}
    users = (set(folder.shared_user_ids) | add_user_ids) - set(body.remove_user_ids)
    groups_set = (set(folder.shared_group_ids) | set(body.add_group_ids)) - set(body.remove_group_ids)
    folder.shared_user_ids = sorted(users)
    folder.shared_group_ids = sorted(groups_set)
    return await folders.update(folder)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(folders: FolderDep, request: Request, folder_id: str) -> None:
    folder = await folders.get(folder_id)
    if folder is not None:
        viewer_id, is_admin = viewer(request)
        if not _owner_or_admin(folder, viewer_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail="only the owner or an admin may delete this folder")
        await folders.delete(folder_id)
