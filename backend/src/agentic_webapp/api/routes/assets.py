"""Asset endpoints — upload/list/get/signed-url/content/combine/share/delete. Thin:
coordination lives in AssetService. Access is RBAC-scoped by owner: a caller sees only
assets they own or that are shared with them (admins see all); the owner/admin may share
or delete. Identity comes from `auth.viewer` (IAP email, or the agent's internal header)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from agentic_core.models import AssetMetadata, SignedUrlResponse
from ...identity import mask_user_id
from ...services import AssetService
from ..auth import viewer
from ..deps import get_asset_service

router = APIRouter(prefix="/api/assets", tags=["assets"])

ServiceDep = Annotated[AssetService, Depends(get_asset_service)]


class CombineRequest(BaseModel):
    asset_ids: list[str]
    filename: str = "combined.bin"
    content_type: str = "application/octet-stream"


class ShareRequest(BaseModel):
    # Emails to grant access to; pseudonymised to user_ids server-side.
    emails: list[str]


async def _require_visible(service: AssetService, request: Request, asset_id: str) -> AssetMetadata:
    """Fetch an asset, 404ing if it doesn't exist OR the caller may not see it (don't leak
    existence to unauthorised callers)."""
    meta = await service.get(asset_id)
    viewer_id, is_admin = viewer(request)
    if meta is None or not service.can_access(meta, viewer_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="asset not found")
    return meta


@router.post("", response_model=AssetMetadata, status_code=201)
async def upload_asset(
    service: ServiceDep,
    request: Request,
    file: Annotated[UploadFile, File(description="The asset to store")],
) -> AssetMetadata:
    data = await file.read()
    owner_id, _ = viewer(request)
    return await service.upload(
        data=data,
        filename=file.filename,
        content_type=file.content_type,
        owner_id=owner_id,
    )


@router.get("", response_model=list[AssetMetadata])
async def list_assets(service: ServiceDep, request: Request, limit: int = 100) -> list[AssetMetadata]:
    viewer_id, is_admin = viewer(request)
    return await service.list_visible(viewer_id, is_admin=is_admin, limit=limit)


@router.get("/{asset_id}", response_model=AssetMetadata)
async def get_asset(service: ServiceDep, request: Request, asset_id: str) -> AssetMetadata:
    return await _require_visible(service, request, asset_id)


@router.get("/{asset_id}/url", response_model=SignedUrlResponse)
async def get_asset_url(service: ServiceDep, request: Request, asset_id: str) -> SignedUrlResponse:
    await _require_visible(service, request, asset_id)
    url = await service.signed_url(asset_id)
    if url is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return SignedUrlResponse(asset_id=asset_id, url=url, expires_in_seconds=service.signed_url_ttl_seconds)


@router.get("/{asset_id}/content")
async def get_asset_content(service: ServiceDep, request: Request, asset_id: str) -> Response:
    await _require_visible(service, request, asset_id)
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


@router.post("/{asset_id}/share", response_model=AssetMetadata)
async def share_asset(service: ServiceDep, request: Request, asset_id: str, body: ShareRequest) -> AssetMetadata:
    actor_id, is_admin = viewer(request)
    user_ids = [mask_user_id(e) for e in body.emails if e.strip()]
    try:
        meta = await service.share(asset_id, actor_id=actor_id, is_admin=is_admin, with_user_ids=user_ids)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if meta is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return meta


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
        if not is_admin and meta.owner_id is not None and meta.owner_id != viewer_id:
            raise HTTPException(status_code=403, detail="only the owner or an admin may delete this asset")
        await service.delete(asset_id)
    return Response(status_code=204)
