"""Central settings (the env-var registry for the backend). Everything reads from
here via get_settings(); nothing reads os.environ directly."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

StorageBackend = Literal["memory", "gcs"]
DatabaseBackend = Literal["memory", "bigquery"]


class Settings(BaseSettings):
    """Backend configuration. Pulled from environment / .env.

    The two *_BACKEND switches select which concrete implementation of the
    abstractions to wire. Selection is explicit and validated — a GCP backend with
    missing config fails loud at startup rather than silently degrading.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"

    # Default to the GCP-free in-memory backends so a bare local run / test needs
    # no cloud. Cloud Run sets these to gcs/bigquery via env (see the webapp stack).
    storage_backend: StorageBackend = "memory"
    database_backend: DatabaseBackend = "memory"

    # GCP — required only when the corresponding backend is selected.
    gcp_project: str | None = None
    assets_bucket: str | None = None
    bigquery_dataset: str | None = None
    asset_metadata_table: str = "asset_metadata"
    # SA whose identity signs V4 URLs via IAM (needed on Cloud Run, which has no key
    # file). Usually the Cloud Run runtime SA; it must hold Token Creator on itself.
    signing_service_account: str | None = None

    # Project-local scratch dir for download_to_temp (see repo tmp/ rule). Resolves
    # to <cwd>/tmp; in the container WORKDIR=/app so it's /app/tmp.
    temp_dir: Path = Path("tmp")
    signed_url_ttl_seconds: int = 900

    # Trust the X-Goog-Authenticated-User-Email header as the caller identity. IAP
    # sets it (and strips client-supplied copies) in prod; in non-prod a client may
    # set it to simulate users — see ADR-0004. Set false to ignore client identity.
    trust_forwarded_user: bool = True

    log_level: str = "INFO"
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    """Singleton settings. lru_cache so every caller shares one instance."""
    return Settings()
