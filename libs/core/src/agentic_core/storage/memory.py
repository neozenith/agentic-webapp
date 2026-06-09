"""InMemoryStorageManager — a real, dependency-free StorageManager for tests and
the GCP-free local loop. Not for production (state is lost on restart).

signed_url returns a relative path to this server's content-proxy route rather than
a true signed URL — locally there is nothing to sign against, and the frontend can
still fetch the asset through that endpoint.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from ..models import StoredAsset
from .base import AssetNotFoundError, StorageManager


@dataclass
class _Entry:
    data: bytes
    content_type: str | None
    updated: datetime


class InMemoryStorageManager(StorageManager):
    def __init__(self, *, temp_dir: Path = Path("tmp")) -> None:
        self._objects: dict[str, _Entry] = {}
        self._temp_dir = temp_dir

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredAsset:
        entry = _Entry(data=data, content_type=content_type, updated=datetime.now(timezone.utc))
        self._objects[key] = entry
        return StoredAsset(key=key, size=len(data), content_type=content_type, updated=entry.updated)

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[key].data
        except KeyError as exc:
            raise AssetNotFoundError(key) from exc

    async def exists(self, key: str) -> bool:
        return key in self._objects

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    async def list(self, prefix: str = "") -> list[StoredAsset]:
        return [
            StoredAsset(key=k, size=len(e.data), content_type=e.content_type, updated=e.updated)
            for k, e in sorted(self._objects.items())
            if k.startswith(prefix)
        ]

    async def download_to_temp(self, key: str, *, into: Path | None = None) -> Path:
        if key not in self._objects:
            raise AssetNotFoundError(key)
        base = into or self._temp_dir
        target_dir = base / "assets" / uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / (key.rsplit("/", 1)[-1] or "asset")
        path.write_bytes(self._objects[key].data)
        return path

    async def signed_url(self, key: str, *, expires_in: timedelta, method: str = "GET") -> str:  # noqa: ARG002
        if key not in self._objects:
            raise AssetNotFoundError(key)
        return f"/api/assets/content/{quote(key)}"
