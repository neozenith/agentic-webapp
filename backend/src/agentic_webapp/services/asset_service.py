"""AssetService — the application-facing layer that combines a StorageManager (the
bytes) with an AssetMetadataManager (the catalogue). The API talks to this, not to
the abstractions directly, so a route never has to coordinate the two stores."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from agentic_core.database import AssetMetadataManager
from agentic_core.models import AssetMetadata
from agentic_core.storage import StorageManager

log = logging.getLogger(__name__)

# Aliased at module scope so annotations don't resolve `list[...]` to AssetService.list
# (the method shadows the builtin inside the class body — same reason base.py has `Rows`).
AssetList = list[AssetMetadata]


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
        owner_id: str | None = None,
        folder_id: str | None = None,
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
            owner_id=owner_id,
            folder_id=folder_id,
            tags=tags or {},
        )
        await self._metadata.record(meta)
        log.info("stored asset %s owner=%s (%s, %s bytes)", asset_id, owner_id, meta.content_type, meta.size_bytes)
        return meta

    # --- Storage + metadata mutation (visibility lives in the routes via agentic_core.access) ---

    async def get(self, asset_id: str) -> AssetMetadata | None:
        return await self._metadata.get(asset_id)

    async def list(self, *, limit: int = 100) -> AssetList:
        return await self._metadata.list(limit=limit)

    async def set_share(
        self,
        meta: AssetMetadata,
        *,
        add_user_ids: Sequence[str] = (),
        add_group_ids: Sequence[str] = (),
        remove_user_ids: Sequence[str] = (),
        remove_group_ids: Sequence[str] = (),
    ) -> AssetMetadata:
        """Apply share add/remove deltas to the asset's principal lists and persist."""
        users = (set(meta.shared_user_ids) | {u for u in add_user_ids if u}) - set(remove_user_ids)
        groups = (set(meta.shared_group_ids) | {g for g in add_group_ids if g}) - set(remove_group_ids)
        meta.shared_user_ids = sorted(users)
        meta.shared_group_ids = sorted(groups)
        await self._metadata.update(meta)
        return meta

    async def move(self, asset_id: str, folder_id: str | None) -> AssetMetadata | None:
        """Move an asset into a folder (None = root). Returns the updated record, or None."""
        meta = await self._metadata.get(asset_id)
        if meta is None:
            return None
        meta.folder_id = folder_id
        await self._metadata.update(meta)
        return meta

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
        asset_ids: Sequence[str],
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
