# ADR-0005: Local development against cloud services

**Status:** Accepted · partially implemented

## Context

The default local loop uses the in-memory `StorageManager`/`DatabaseManager` (no GCP
needed) — great for speed and tests. But sometimes you need to run the server
**locally while integrating against the real cloud services** (GCS + BigQuery) to
reproduce cloud behaviour, debug data issues, or validate the GCP implementations
without a full deploy.

## Decision

- **Backends are config-selected** (`STORAGE_BACKEND`, `DATABASE_BACKEND`), so
  pointing the local server at the cloud is purely environment configuration —
  no code change:
  ```bash
  STORAGE_BACKEND=gcs DATABASE_BACKEND=bigquery \
  GCP_PROJECT=dbt-dev-jaffleshop \
  ASSETS_BUCKET=dbt-dev-jaffleshop-agentic-webapp-assets \
  BIGQUERY_DATASET=agentic_webapp \
  uv run --directory backend uvicorn agentic_webapp.main:app --reload
  ```
  Authentication uses the developer's **Application Default Credentials**
  (`gcloud auth application-default login`).
- This targets the **dev** project only (ADR-0003: dev holds no sensitive data), so
  local experimentation can't touch prod data.
- A `make -C backend dev-cloud` convenience target wraps the above.

## Consequences

- One codebase, two local modes: in-memory (fast, offline) and cloud-integrated.
- **Known limitation — signed URLs.** `GCSStorageManager.signed_url` signs via IAM
  using a signer SA. Locally, user ADC can't `signBlob` directly; to get real signed
  URLs locally you must impersonate the runtime SA (set `SIGNING_SERVICE_ACCOUNT`
  and hold `roles/iam.serviceAccountTokenCreator` on it). Otherwise use the
  `/api/assets/{id}/content` proxy route locally.

## Lens

Make "run locally against the cloud" a config flip, not a code branch — the
abstraction's whole point is that the same handlers run over in-memory or GCP
backends chosen by env. Keep local-against-cloud pinned to the dev tier so it can
never reach sensitive data.
