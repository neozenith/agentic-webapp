"""Asset endpoints — upload/list/get/signed-url/content/combine/delete. These are
thin: all coordination lives in AssetService, injected via Depends so tests can
swap an in-memory service in."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from ...models import AssetMetadata, SignedUrlResponse
from ...services import AssetService
from ..deps import get_asset_service

router = APIRouter(prefix="/api/assets", tags=["assets"])

ServiceDep = Annotated[AssetService, Depends(get_asset_service)]


class CombineRequest(BaseModel):
    asset_ids: list[str]
    filename: str = "combined.bin"
    content_type: str = "application/octet-stream"


@router.post("", response_model=AssetMetadata, status_code=201)
async def upload_asset(
    service: ServiceDep,
    file: Annotated[UploadFile, File(description="The asset to store")],
) -> AssetMetadata:
    data = await file.read()
    return await service.upload(
        data=data,
        filename=file.filename,
        content_type=file.content_type,
    )


@router.get("", response_model=list[AssetMetadata])
async def list_assets(service: ServiceDep, limit: int = 100) -> list[AssetMetadata]:
    return await service.list(limit=limit)


@router.get("/{asset_id}", response_model=AssetMetadata)
async def get_asset(service: ServiceDep, asset_id: str) -> AssetMetadata:
    meta = await service.get(asset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return meta


@router.get("/{asset_id}/url", response_model=SignedUrlResponse)
async def get_asset_url(service: ServiceDep, asset_id: str) -> SignedUrlResponse:
    url = await service.signed_url(asset_id)
    if url is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return SignedUrlResponse(asset_id=asset_id, url=url, expires_in_seconds=service.signed_url_ttl_seconds)


@router.get("/{asset_id}/content")
async def get_asset_content(service: ServiceDep, asset_id: str) -> Response:
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
async def delete_asset(service: ServiceDep, asset_id: str) -> Response:
    await service.delete(asset_id)
    return Response(status_code=204)
