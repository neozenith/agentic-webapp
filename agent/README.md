# `agent/` — ADK agent sidecar

A Google ADK agent run as a **sidecar** container alongside the FastAPI backend in
one Cloud Run service (both scale to zero together). The browser reaches it via the
backend's proxy (`/api/agent/*`); the ADK **debug UI** is at `/dev-ui/`.

- **Model:** `gemini-2.5-flash-lite` (cheapest) by default; override with `AGENT_MODEL`.
- **Auth:** keyless **Vertex AI** (`GOOGLE_GENAI_USE_VERTEXAI=True`), via the dedicated
  agent service account in cloud / your ADC locally.
- **Bookkeeping (PR3):** an ADK `after_model_callback` will record token/cost usage per
  user + session + model to BigQuery via `agentic-core`.

## Run locally

```bash
gcloud auth application-default login        # once, for Vertex
make -C agent install
make -C agent dev                            # http://localhost:8081  (UI at /dev-ui/)
curl localhost:8081/list-apps                # -> ["assistant"]
```

## Layout

```
agent/
├── agents/assistant/{__init__.py, agent.py}   # root_agent (ADK discovers ./agents)
├── pyproject.toml      # google-adk; [tool.uv] package=false (app, not a lib)
├── Dockerfile          # runs `adk web` on :8081 (repo-root build context)
└── cloudbuild.yaml
```
