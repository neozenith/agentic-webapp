"""Shared pydantic models — the data contracts crossing the abstraction boundaries
and the API surface."""

from datetime import datetime

from pydantic import BaseModel, Field


class StoredAsset(BaseModel):
    """A reference to an object in blob storage (the StorageManager's currency)."""

    key: str
    size: int | None = None
    content_type: str | None = None
    updated: datetime | None = None


class AssetMetadata(BaseModel):
    """A catalogued asset: its storage location plus descriptive metadata. This is
    the first domain record managed via the DatabaseManager (AssetMetadataManager)."""

    asset_id: str
    storage_key: str
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime
    # Arbitrary, app-defined key/values. Kept generic on purpose.
    tags: dict[str, str] = Field(default_factory=dict)


class SignedUrlResponse(BaseModel):
    """A time-limited URL the frontend can use to fetch an asset directly."""

    asset_id: str
    url: str
    expires_in_seconds: int
