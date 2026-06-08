# `backend/` — agentic-webapp FastAPI service

Async FastAPI backend built around two **general, swappable abstractions** so this
project can be the base for many others:

- **`StorageManager`** — object storage for blobs (images, PDFs, anything).
  Concrete: `GCSStorageManager` (prod), `InMemoryStorageManager` (tests/local).
- **`DatabaseManager`** — generic tabular store. Concrete: `BigQueryDatabaseManager`
  (prod), `InMemoryDatabaseManager` (tests/local). The first domain manager built on
  it is **`AssetMetadataManager`**.

`AssetService` composes a `StorageManager` + an `AssetMetadataManager`: it stores the
bytes and catalogues the metadata together, generates signed URLs for the frontend,
and can pull assets into a temp dir to combine them into new assets.

## Architecture

```
                 ┌──────────────── AssetService ────────────────┐
   HTTP (FastAPI)│  upload · signed_url · content · combine      │
        │        └───────┬───────────────────────┬──────────────┘
        ▼                ▼                        ▼
   api/routes/     StorageManager (ABC)     AssetMetadataManager
                    ├ GCSStorageManager        │ (composes)
                    └ InMemoryStorageManager    ▼
                                           DatabaseManager (ABC)
                                            ├ BigQueryDatabaseManager
                                            └ InMemoryDatabaseManager
```

The backend a request uses is chosen by config (`STORAGE_BACKEND`,
`DATABASE_BACKEND`) — explicit, validated, no silent fallback.

## Run locally (no GCP needed)

Defaults are the in-memory backends, so it runs with zero cloud setup:

```bash
make -C backend install      # uv sync (first time)
make -C backend dev          # http://localhost:8080  (reload)
```

- UI: http://localhost:8080 · API docs: http://localhost:8080/docs · health: `/health`
- Try it:
  ```bash
  curl -F file=@some.png http://localhost:8080/api/assets        # -> AssetMetadata
  curl http://localhost:8080/api/assets                          # list
  curl http://localhost:8080/api/assets/<id>/url                 # signed/proxy URL
  ```

## Simulating users (ADR-0004)

Identity comes from the IAP header `X-Goog-Authenticated-User-Email`. IAP sets it in
prod (and strips client copies); locally there's no IAP, so you can set it yourself
to simulate any user:

```bash
curl -H 'X-Goog-Authenticated-User-Email: accounts.google.com:alice@example.com' \
     http://localhost:8080/
```

Set `TRUST_FORWARDED_USER=false` to ignore client-supplied identity.

## Run locally against cloud services (ADR-0005)

```bash
gcloud auth application-default login      # once
make -C backend dev-cloud                  # GCS + BigQuery in the dev project, via your ADC
```

Same handlers, real cloud backends — chosen purely by config. (Signed URLs locally
need impersonation of the signer SA; otherwise use the `/api/assets/{id}/content`
proxy. See ADR-0005.)

## Use the GCP backends

Set in `.env` (or via Cloud Run env — the webapp Terraform stack wires these):

```bash
STORAGE_BACKEND=gcs
DATABASE_BACKEND=bigquery
GCP_PROJECT=dbt-dev-jaffleshop
ASSETS_BUCKET=dbt-dev-jaffleshop-agentic-webapp-assets
BIGQUERY_DATASET=agentic_webapp
SIGNING_SERVICE_ACCOUNT=agentic-webapp-run@dbt-dev-jaffleshop.iam.gserviceaccount.com
```

Signed URLs on Cloud Run are produced via IAM signing (no key file); the runtime SA
must hold `roles/iam.serviceAccountTokenCreator` on itself — granted in the stack.

## Tests

Real implementations only — **no mocks** (project rule). The same contract suite
runs against the in-memory `StorageManager`/`DatabaseManager`, and the API is tested
through FastAPI's `TestClient` with in-memory backends injected.

```bash
make -C backend test
```

## Layout

```
backend/src/agentic_webapp/
├── main.py            # FastAPI app factory + root page (shows IAP user)
├── config.py          # pydantic-settings env registry
├── models.py          # StoredAsset, AssetMetadata, SignedUrlResponse
├── storage/           # StorageManager ABC + gcs / memory impls
├── database/          # DatabaseManager ABC + bigquery / memory + AssetMetadataManager
├── services/          # AssetService (storage + metadata)
└── api/               # deps (DI) + routes (health, assets)
```
