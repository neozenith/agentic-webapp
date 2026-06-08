"""GCSStorageManager — Google Cloud Storage implementation of StorageManager.

The google-cloud-storage SDK is synchronous, so every blocking call is offloaded
with asyncio.to_thread to keep the FastAPI event loop free.

Signed URLs: on Cloud Run there is no key file to sign with, so V4 signing is done
via the IAM credentials API. When `signing_service_account` is set we pass that SA
email plus a fresh OAuth access token to generate_signed_url; the SDK then calls
IAM signBlob. That SA must hold roles/iam.serviceAccountTokenCreator on itself
(granted in the webapp Terraform stack).
"""

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as AuthRequest
from google.cloud import storage
from google.cloud.exceptions import NotFound

from ..models import StoredAsset
from .base import AssetNotFoundError, StorageManager


class GCSStorageManager(StorageManager):
    def __init__(
        self,
        bucket: str,
        *,
        signing_service_account: str | None = None,
        temp_dir: Path = Path("tmp"),
        client: storage.Client | None = None,
    ) -> None:
        self._client = client or storage.Client()
        self._bucket = self._client.bucket(bucket)
        self._signing_sa = signing_service_account
        self._temp_dir = temp_dir

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredAsset:
        def _put() -> StoredAsset:
            blob = self._bucket.blob(key)
            blob.upload_from_string(data, content_type=content_type)
            blob.reload()
            return StoredAsset(key=key, size=blob.size, content_type=blob.content_type, updated=blob.updated)

        return await asyncio.to_thread(_put)

    async def get(self, key: str) -> bytes:
        def _get() -> bytes:
            try:
                return self._bucket.blob(key).download_as_bytes()
            except NotFound as exc:
                raise AssetNotFoundError(key) from exc

        return await asyncio.to_thread(_get)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._bucket.blob(key).exists)

    async def delete(self, key: str) -> None:
        def _delete() -> None:
            try:
                self._bucket.blob(key).delete()
            except NotFound:
                pass

        await asyncio.to_thread(_delete)

    async def list(self, prefix: str = "") -> list[StoredAsset]:
        def _list() -> list[StoredAsset]:
            return [
                StoredAsset(key=b.name, size=b.size, content_type=b.content_type, updated=b.updated)
                for b in self._client.list_blobs(self._bucket, prefix=prefix)
            ]

        return await asyncio.to_thread(_list)

    async def download_to_temp(self, key: str, *, into: Path | None = None) -> Path:
        base = into or self._temp_dir

        def _download() -> Path:
            blob = self._bucket.blob(key)
            if not blob.exists():
                raise AssetNotFoundError(key)
            target_dir = base / "assets" / uuid4().hex
            target_dir.mkdir(parents=True, exist_ok=True)
            path = target_dir / (key.rsplit("/", 1)[-1] or "asset")
            blob.download_to_filename(str(path))
            return path

        return await asyncio.to_thread(_download)

    async def signed_url(self, key: str, *, expires_in: timedelta, method: str = "GET") -> str:
        def _sign() -> str:
            blob = self._bucket.blob(key)
            kwargs: dict = {"version": "v4", "expiration": expires_in, "method": method}
            if self._signing_sa:
                creds, _ = google_auth_default()
                creds.refresh(AuthRequest())
                kwargs["service_account_email"] = self._signing_sa
                kwargs["access_token"] = creds.token
            return blob.generate_signed_url(**kwargs)

        return await asyncio.to_thread(_sign)
