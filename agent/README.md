# `agent/` — ADK agent sidecar

A Google ADK agent run as a **sidecar** container alongside the FastAPI backend in
one Cloud Run service (both scale to zero together). The browser reaches it via the
backend's proxy (`/api/agent/*`); the ADK **debug UI** is at `/dev-ui/`.

- **Model:** `gemini-2.5-flash-lite` (cheapest) by default; override with `AGENT_MODEL`.
- **Auth:** keyless **Vertex AI** (`GOOGLE_GENAI_USE_VERTEXAI=True`), via the dedicated
  agent service account in cloud / your ADC locally.
- **Bookkeeping:** an ADK `after_model_callback` records token/cost usage per
  user + session + model via `agentic-core` (`LlmUsageManager`).

## Tools

The agent (`agents/assistant/`) has three tools (`tools.py`):

| Tool | What it does |
|---|---|
| `list_assets()` | Lists stored assets (id, filename, type, size, date) so the model can pick one. |
| `attach_asset(asset_id)` | Makes an asset's image/PDF visible to the model **this turn** by injecting it inline. Bytes are re-fetched from the backend (GCS) per turn and **never** saved to ADK's artifact store — see [ADR-0006](../docs/adr/adr-0006-assets-single-source-of-truth.md). |
| `record_extraction(asset_id, doc_type, fields_json)` | Persists extracted details to the analytics store via `agentic-core` `AnalyticsManager`. |

**Asset access** is over HTTP to the backend (the single source of truth for assets), at
`BACKEND_BASE_URL` (`http://localhost:8080` locally / Cloud Run; `http://backend:8080`
under docker compose). The agent has no GCS credentials by design. Per-turn image injection
(reliable image+text, no cross-turn leakage) lives in `attachments.py`'s before_model_callback.

**The analytics space (AnalyticsManager).** Analytics is a SEPARATE backend axis from the
operational Firestore stores (sessions, assets): `AnalyticsManager` uses **BigQuery in the
cloud and in-memory locally** (`build_analytics_database_from_env()`, selecting BigQuery when
`BIGQUERY_DATASET` is set). The `ExtractionRecord` model is a common envelope — `doc_type` +
a free-form `fields` payload (one `fields_json` column) — so a new extraction type (invoice,
business card, odometer…) is a new `doc_type` + `fields` shape, **no new table or schema**.

## Run locally

```bash
gcloud auth application-default login        # once, for Vertex
cp agent/.env.sample agent/.env              # once — sets GOOGLE_GENAI_USE_VERTEXAI=True + project/region
make -C agent install
make -C agent dev                            # http://localhost:8081  (UI at /dev-ui/)
curl localhost:8081/list-apps                # -> ["assistant"]
```

> **Without `agent/.env`** (or the `GOOGLE_GENAI_USE_VERTEXAI=True` flag) the
> `google-genai` SDK defaults to the Gemini Developer API and the chat fails asking
> for a `GOOGLE_API_KEY`. `adk web` auto-loads `.env` by walking up from
> `agents/assistant/`. (Under `docker compose` the flag is set in the container env,
> so no `.env` is needed there.)

## Layout

```
agent/
├── agents/assistant/{__init__.py, agent.py}   # root_agent (ADK discovers ./agents)
├── pyproject.toml      # google-adk; [tool.uv] package=false (app, not a lib)
├── Dockerfile          # runs `adk web` on :8081 (repo-root build context)
└── cloudbuild.yaml
```
