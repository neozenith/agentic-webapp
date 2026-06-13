# ADR-0006: Assets have a single source of truth (the agent never uses ADK's artifact store)

**Status:** Accepted

## Context

We added agent tools that read uploaded assets (e.g. a fuel-receipt photo) and attach
them to the LLM so it can extract details. Google ADK ships its own **artifact service**
("native" agent file storage) — the obvious-looking way to do this via
`tool_context.save_artifact` / the built-in `load_artifacts` tool. But the project already
owns assets through **AssetService** (GCS blobs + an `AssetMetadataManager` catalogue),
surfaced in the web **Asset Manager**.

Using ADK's artifact store would create a **second, parallel asset store**, which breaks
two things we must optimise for:

- **Scale-to-zero (ADR-0001).** ADK's *default* artifact service is
  `PerAgentFileArtifactService` — local disk at `<agent>/.adk/artifacts/`, lost on cold
  start. Authoritative data on local disk violates the stateless principle.
- **A coherent view of assets.** ADK's GCS option (`GcsArtifactService`) namespaces blobs
  as `{app}/{user}/{session}/{file}/{version}` — a different catalogue the Asset Manager
  can't see. An asset attached in chat would be invisible on the Assets page, and
  vice-versa: the two views would diverge.

## Decision

1. **AssetService (GCS + metadata catalogue) is the single source of truth for assets.**
   The agent does **not** use ADK's artifact service: no `save_artifact`, no
   `load_artifacts`, no `--artifact_service_uri`. Verified by
   `grep -rn "save_artifact\|artifact_service" agent/agents` → no matches.
2. **Both upload paths write to the same `POST /api/assets`.** The web Asset Manager
   button and the chat composer's attach-photo affordance both upload there (the server
   mints the `asset_id` — ADR-0004 / server-authoritative ids). Chat then *references* the
   `asset_id` in the message text rather than streaming raw base64, so Firestore session
   events stay lean. One catalogue ⇒ an asset is visible in both views.
3. **Attaching to the LLM is transient.** `AttachAssetTool` (a custom `BaseTool`) injects
   the image inline in `process_llm_request` by re-fetching bytes from
   `GET /api/assets/{id}/content` (GCS) each turn, and persists nothing locally. The
   durable references are the `asset_id` (in the Firestore session event) + the GCS bytes;
   the injected image is rebuilt on demand. On session resume the agent re-attaches from
   GCS.

## Consequences

- No two-store reconciliation problem; the Asset Manager and the agent always agree.
- Cold-start safe: assets live in GCS, sessions in Firestore, extractions in the
  configured `DatabaseManager` — nothing authoritative in process memory or local disk.
- The agent reaches assets over HTTP (`BACKEND_BASE_URL`), so it needs no GCS credentials.
- Trade-off: an attached asset is re-fetched (and re-sent to the model) per turn while it
  remains in the session's attach list — a deliberate cost-for-statelessness choice.

## Lens

When the framework offers its own store for something we already persist, do **not** run
two stores and reconcile them — collapse to the one that is cloud-native and visible to
the rest of the app. A capability is only "ours" if it survives a cold start *and* every
view reads the same record. Prefer transient, re-fetched-from-source data over a second
durable copy.
