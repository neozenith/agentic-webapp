"""Shared pydantic models — the data contracts crossing the abstraction boundaries
and the API surface."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StoredAsset(BaseModel):
    """A reference to an object in blob storage (the StorageManager's currency)."""

    key: str
    size: int | None = None
    content_type: str | None = None
    updated: datetime | None = None


class Shareable(BaseModel):
    """Mixin of RBAC sharing fields used by both assets and folders. `owner_id` is the
    pseudonymous uploader (None = legacy/unowned, visible to all); `shared_user_ids` and
    `shared_group_ids` are the principals granted access. Admins see everything."""

    owner_id: str | None = None
    shared_user_ids: list[str] = Field(default_factory=list)
    shared_group_ids: list[str] = Field(default_factory=list)


class AssetMetadata(Shareable):
    """A catalogued asset: its storage location plus descriptive metadata. The first domain
    record managed via the DatabaseManager (AssetMetadataManager)."""

    asset_id: str
    storage_key: str
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime
    # The folder the asset lives in (None = root). Files inherit their folder's sharing.
    folder_id: str | None = None
    # Arbitrary, app-defined key/values. Kept generic on purpose.
    tags: dict[str, str] = Field(default_factory=dict)


class Folder(Shareable):
    """A real (named) folder in the Asset Manager. Folders nest via parent_id and carry
    their own sharing; contained assets (and sub-folders) inherit folder access."""

    folder_id: str
    name: str
    parent_id: str | None = None
    created_at: datetime


class Group(BaseModel):
    """A custom group of users (admin-managed). Assets/folders can be shared with a group;
    a member then inherits that access. member_ids are pseudonymous user_ids."""

    group_id: str
    name: str
    member_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class SignedUrlResponse(BaseModel):
    """A time-limited URL the frontend can use to fetch an asset directly."""

    asset_id: str
    url: str
    expires_in_seconds: int


class LlmUsageRecord(BaseModel):
    """One itemised LLM call for the bookkeeping inventory: who, when, which model,
    how many tokens, and the estimated cost. Written by the agent's ADK callback,
    read by the backend admin panel."""

    request_id: str
    app_name: str
    user_id: str
    session_id: str
    model_id: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    est_cost_usd: float = 0.0
    timestamp: datetime


class ExtractionRecord(BaseModel):
    """One structured-data extraction pulled from an asset by an agent tool — the
    common envelope for the 'extract from a document' tool category. `doc_type` plus
    the free-form `fields` payload is the extensible seam: a new extraction type (fuel
    receipt, invoice, business card, …) is a new `doc_type` + `fields` shape, never a
    schema change. Persisted via ExtractionManager to the same DatabaseManager backend
    as the rest of the analytics tables (in-memory locally, Firestore/BigQuery in cloud)."""

    extraction_id: str
    asset_id: str
    doc_type: str
    user_id: str
    session_id: str
    # The type-specific extracted key/values; serialised to fields_json at the row layer.
    fields: dict[str, Any] = Field(default_factory=dict)
    model_id: str | None = None
    created_at: datetime
