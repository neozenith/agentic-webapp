"""Asset endpoints — upload/list/get/signed-url/content/move/share/delete/combine. Thin:
coordination lives in AssetService; RBAC visibility lives in `agentic_core.access`. A caller
sees only assets they own, that are shared with them (directly or via a group), or that live
in a folder they can see (admins see all). Only the owner/admin may move, share, or delete.
Identity comes from `auth.viewer` (IAP email, or the agent's internal header)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from agentic_core.access import accessible_folder_ids, asset_visible
from agentic_core.database import FolderManager, GroupManager
from agentic_core.models import AssetMetadata, SignedUrlResponse
from ...identity import mask_user_id
from ...services import AssetService
from ..access import viewer_ctx
from ..auth import viewer
from ..deps import get_asset_service, get_folder_manager, get_group_manager

router = APIRouter(prefix="/api/assets", tags=["assets"])

ServiceDep = Annotated[AssetService, Depends(get_asset_service)]
FolderDep = Annotated[FolderManager, Depends(get_folder_manager)]
GroupDep = Annotated[GroupManager, Depends(get_group_manager)]


class CombineRequest(BaseModel):
    asset_ids: list[str]
    filename: str = "combined.bin"
    content_type: str = "application/octet-stream"


class ShareRequest(BaseModel):
    # Emails to grant access to (pseudonymised to user_ids server-side) + group ids; and
    # the principal ids to revoke. All optional — only the supplied deltas are applied.
    add_user_emails: list[str] = []
    remove_user_ids: list[str] = []
    add_group_ids: list[str] = []
    remove_group_ids: list[str] = []


class MoveRequest(BaseModel):
    folder_id: str | None = None


def _owner_or_admin(meta: AssetMetadata, viewer_id: str | None, *, is_admin: bool) -> bool:
    """Owner, admin, or an unowned (legacy/public) asset — who may move/share/delete it."""
    return is_admin or meta.owner_id is None or meta.owner_id == viewer_id


async def _require_visible(
    service: AssetService, folders: FolderManager, groups: GroupManager, request: Request, asset_id: str
) -> AssetMetadata:
    """Fetch an asset, 404ing if it doesn't exist OR the caller may not see it (don't leak
    existence to unauthorised callers)."""
    meta = await service.get(asset_id)
    viewer_id, is_admin, group_ids = await viewer_ctx(request, groups)
    accessible = accessible_folder_ids(
        await folders.list(), viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids
    )
    if meta is None or not asset_visible(
        meta, viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids, accessible_folders=accessible
    ):
        raise HTTPException(status_code=404, detail="asset not found")
    return meta


@router.post("", response_model=AssetMetadata, status_code=201)
async def upload_asset(
    service: ServiceDep,
    request: Request,
    file: Annotated[UploadFile, File(description="The asset to store")],
    folder_id: Annotated[str | None, Form()] = None,
) -> AssetMetadata:
    data = await file.read()
    owner_id, _ = viewer(request)
    return await service.upload(
        data=data,
        filename=file.filename,
        content_type=file.content_type,
        owner_id=owner_id,
        folder_id=folder_id,
    )


@router.get("", response_model=list[AssetMetadata])
async def list_assets(
    service: ServiceDep, folders: FolderDep, groups: GroupDep, request: Request, limit: int = 100
) -> list[AssetMetadata]:
    viewer_id, is_admin, group_ids = await viewer_ctx(request, groups)
    accessible = accessible_folder_ids(
        await folders.list(), viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids
    )
    return [
        m
        for m in await service.list(limit=limit)
        if asset_visible(
            m, viewer_id=viewer_id, is_admin=is_admin, viewer_group_ids=group_ids, accessible_folders=accessible
        )
    ]


@router.get("/{asset_id}", response_model=AssetMetadata)
async def get_asset(
    service: ServiceDep, folders: FolderDep, groups: GroupDep, request: Request, asset_id: str
) -> AssetMetadata:
    return await _require_visible(service, folders, groups, request, asset_id)


@router.get("/{asset_id}/url", response_model=SignedUrlResponse)
async def get_asset_url(
    service: ServiceDep, folders: FolderDep, groups: GroupDep, request: Request, asset_id: str
) -> SignedUrlResponse:
    await _require_visible(service, folders, groups, request, asset_id)
    url = await service.signed_url(asset_id)
    if url is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return SignedUrlResponse(asset_id=asset_id, url=url, expires_in_seconds=service.signed_url_ttl_seconds)


@router.get("/{asset_id}/content")
async def get_asset_content(
    service: ServiceDep, folders: FolderDep, groups: GroupDep, request: Request, asset_id: str
) -> Response:
    await _require_visible(service, folders, groups, request, asset_id)
    result = await service.content(asset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="asset not found")
    data, content_type = result
    return Response(content=data, media_type=content_type or "application/octet-stream")


# Key-based content proxy — the URL the in-memory StorageManager hands out as its
# "signed URL". `key:path` lets the storage key contain slashes (assets/<id>.png).
@router.get("/content/{key:path}")
async def get_content_by_key(service: ServiceDep, key: str) -> Response:
    try:
        data = await service.content_by_key(key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="object not found") from exc
    return Response(content=data, media_type="application/octet-stream")


@router.post("/{asset_id}/move", response_model=AssetMetadata)
async def move_asset(service: ServiceDep, request: Request, asset_id: str, body: MoveRequest) -> AssetMetadata:
    meta = await service.get(asset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="asset not found")
    viewer_id, is_admin = viewer(request)
    if not _owner_or_admin(meta, viewer_id, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="only the owner or an admin may move this asset")
    moved = await service.move(asset_id, body.folder_id)
    assert moved is not None  # existence checked above
    return moved


@router.post("/{asset_id}/share", response_model=AssetMetadata)
async def share_asset(service: ServiceDep, request: Request, asset_id: str, body: ShareRequest) -> AssetMetadata:
    meta = await service.get(asset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="asset not found")
    viewer_id, is_admin = viewer(request)
    if not _owner_or_admin(meta, viewer_id, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="only the owner or an admin may share this asset")
    add_user_ids = [mask_user_id(e) for e in body.add_user_emails if e.strip()]
    return await service.set_share(
        meta,
        add_user_ids=add_user_ids,
        add_group_ids=body.add_group_ids,
        remove_user_ids=body.remove_user_ids,
        remove_group_ids=body.remove_group_ids,
    )


@router.post("/combine", response_model=AssetMetadata, status_code=201)
async def combine_assets(service: ServiceDep, body: CombineRequest) -> AssetMetadata:
    if len(body.asset_ids) < 2:
        raise HTTPException(status_code=400, detail="combine needs at least two asset_ids")
    try:
        return await service.combine(
            body.asset_ids,
            filename=body.filename,
            content_type=body.content_type,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"asset not found: {exc}") from exc


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(service: ServiceDep, request: Request, asset_id: str) -> Response:
    meta = await service.get(asset_id)
    if meta is not None:
        viewer_id, is_admin = viewer(request)
        if not _owner_or_admin(meta, viewer_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail="only the owner or an admin may delete this asset")
        await service.delete(asset_id)
    return Response(status_code=204)
