"""StorageManager — the abstract object-storage interface.

Deliberately generic: it stores opaque blobs (images, PDFs, anything) by key. It
knows nothing about asset metadata — that's the DatabaseManager's job. Concrete
implementations: GCSStorageManager (production), InMemoryStorageManager (tests/local).
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path

from ..models import StoredAsset


class AssetNotFoundError(KeyError):
    """Raised when a key does not exist in the store."""


class StorageManager(ABC):
    """Async object storage keyed by string. All methods are awaitable so blocking
    SDK calls can be offloaded to threads without changing the interface."""

    @abstractmethod
    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredAsset:
        """Store bytes at key, returning a reference. Overwrites if key exists."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the bytes at key. Raises AssetNotFoundError if missing."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """True if an object exists at key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object at key. No-op if it does not exist."""

    @abstractmethod
    async def list(self, prefix: str = "") -> list[StoredAsset]:
        """List objects whose key starts with prefix."""

    @abstractmethod
    async def download_to_temp(self, key: str, *, into: Path | None = None) -> Path:
        """Pull a copy of the object onto local disk and return its path. Used when
        the server needs the bytes as a file (e.g. to combine several assets into a
        new one). `into` overrides the default temp directory."""

    @abstractmethod
    async def signed_url(self, key: str, *, expires_in: timedelta, method: str = "GET") -> str:
        """Return a time-limited URL the frontend can use to fetch (or upload) the
        object directly, without proxying bytes through this server."""
