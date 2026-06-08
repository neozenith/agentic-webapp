# ADR-0001: Stateless servers; state in cloud-native primitives

**Status:** Accepted · implemented

## Context

The service runs on Cloud Run scaled to zero. Instances are created and destroyed
constantly: a request after an idle period hits a **cold start** on a brand-new
instance, and any number of instances may serve concurrently. Anything held in
process memory or on local disk is therefore ephemeral and per-instance — it cannot
be relied on across requests, instances, or restarts.

## Decision

**Servers are stateless. All durable state lives in cloud-native managed primitives
and is written immediately, not buffered in the process:**

- **Blob/object state → GCS** (the assets bucket), via `StorageManager`.
- **Structured/tabular state → BigQuery** (the app dataset), via `DatabaseManager`
  (first use: `AssetMetadataManager`).
- The process keeps **no** authoritative state. Local disk (`download_to_temp`) is
  used only as scratch for a single in-flight operation, then discarded.
- A new (cold-started) instance reconstructs everything it needs by reading from
  GCS/BigQuery — there is no warm-up state to lose.

Writes are persisted as part of handling the request (e.g. upload = `put` to GCS +
`record` to BigQuery) so a crash or scale-down immediately after never loses data.

## Consequences

- Scale-to-zero is safe and cheap: instances are disposable.
- Horizontal scale is free: any instance can serve any request.
- The in-memory `StorageManager`/`DatabaseManager` implementations are for tests and
  local dev **only** — they are explicitly *not* durable and never used in cloud envs.
- Cost/latency: every read/write is a cloud call; acceptable for this workload, and
  cacheable later if a hot path emerges (cache must remain non-authoritative).
- BigQuery streaming-insert visibility is near-immediate but not transactional; the
  metadata catalogue tolerates this (ADR may revisit if strong read-after-write is needed).

## Lens

When tempted to keep state in the process (a dict, a file, a global), ask "does this
survive a cold start on a different instance?" If it must, it belongs in GCS or
BigQuery, written now — not in memory. Treat every instance as disposable.
