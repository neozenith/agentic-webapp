"""AssetService — the application-facing layer that combines a StorageManager (the
bytes) with an AssetMetadataManager (the catalogue). The API talks to this, not to
the abstractions directly, so a route never has to coordinate the two stores."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from ..database.asset_metadata import AssetMetadataManager
from ..models import AssetMetadata
from ..storage.base import StorageManager

log = logging.getLogger(__name__)


class AssetService:
    def __init__(
        self,
        storage: StorageManager,
        metadata: AssetMetadataManager,
        *,
        signed_url_ttl_seconds: int = 900,
    ) -> None:
        self._storage = storage
        self._metadata = metadata
        self._ttl = signed_url_ttl_seconds

    @property
    def signed_url_ttl_seconds(self) -> int:
        return self._ttl

    async def upload(
        self,
        *,
        data: bytes,
        filename: str | None = None,
        content_type: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> AssetMetadata:
        """Store the bytes AND record their metadata. Returns the catalogue record."""
        asset_id = uuid4().hex
        key = self._storage_key(asset_id, filename)
        stored = await self._storage.put(key, data, content_type=content_type)
        now = datetime.now(timezone.utc)
        meta = AssetMetadata(
            asset_id=asset_id,
            storage_key=key,
            filename=filename,
            content_type=content_type or stored.content_type,
            size_bytes=stored.size if stored.size is not None else len(data),
            created_at=now,
            updated_at=now,
            tags=tags or {},
        )
        await self._metadata.record(meta)
        log.info("stored asset %s (%s, %s bytes)", asset_id, meta.content_type, meta.size_bytes)
        return meta

    async def get(self, asset_id: str) -> AssetMetadata | None:
        return await self._metadata.get(asset_id)

    async def list(self, *, limit: int = 100) -> list[AssetMetadata]:
        return await self._metadata.list(limit=limit)

    async def signed_url(self, asset_id: str) -> str | None:
        meta = await self._metadata.get(asset_id)
        if meta is None:
            return None
        return await self._storage.signed_url(meta.storage_key, expires_in=timedelta(seconds=self._ttl))

    async def content(self, asset_id: str) -> tuple[bytes, str | None] | None:
        """Return (bytes, content_type) for proxying through the server."""
        meta = await self._metadata.get(asset_id)
        if meta is None:
            return None
        return await self._storage.get(meta.storage_key), meta.content_type

    async def content_by_key(self, key: str) -> bytes:
        return await self._storage.get(key)

    async def delete(self, asset_id: str) -> bool:
        meta = await self._metadata.get(asset_id)
        if meta is None:
            return False
        await self._storage.delete(meta.storage_key)
        await self._metadata.delete(asset_id)
        return True

    async def combine(
        self,
        asset_ids: list[str],
        *,
        separator: bytes = b"",
        filename: str = "combined.bin",
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> AssetMetadata:
        """Pull each source asset to a local temp file, concatenate the bytes, and
        store the result as a new asset. This is the canonical demonstration of
        StorageManager.download_to_temp — the pattern for combining several assets
        into something new (the real work would be image/PDF processing)."""
        parts: list[bytes] = []
        for asset_id in asset_ids:
            meta = await self._metadata.get(asset_id)
            if meta is None:
                raise KeyError(asset_id)
            local_path: Path = await self._storage.download_to_temp(meta.storage_key)
            parts.append(local_path.read_bytes())
        combined = separator.join(parts)
        return await self.upload(
            data=combined,
            filename=filename,
            content_type=content_type,
            tags={**(tags or {}), "combined_from": ",".join(asset_ids)},
        )

    @staticmethod
    def _storage_key(asset_id: str, filename: str | None) -> str:
        suffix = ""
        if filename and "." in filename:
            suffix = "." + filename.rsplit(".", 1)[-1].lower()
        return f"assets/{asset_id}{suffix}"
