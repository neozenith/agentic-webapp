#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-cloud-firestore",
#   "google-cloud-storage",
# ]
# ///
"""Reset state for a DEV/TEST environment: delete all chat sessions and all assets.

DESTRUCTIVE. DEV/TEST ONLY. Refuses to run unless GCP_PROJECT contains "dev" or
"test" so production can never be wiped by this tool.

What it deletes:
  - Firestore `adk_sessions` documents AND each document's `events` subcollection.
  - Firestore `adk_user_state` and `adk_app_state` documents (ADK session state).
  - Firestore `asset_metadata` documents.
  - GCS blobs under the `assets/` prefix in ASSETS_BUCKET.

What it KEEPS (analytics / bookkeeping):
  - Firestore `extractions` and `llm_usage` collections are never touched.

Config (environment variables):
  GCP_PROJECT          GCP project id (must contain "dev" or "test").
  FIRESTORE_DATABASE   Firestore database id (e.g. "agentic-webapp").
  ASSETS_BUCKET        GCS bucket holding assets/ blobs.

Usage:
  uv run scripts/reset_state.py            # dry-run: prints counts, deletes nothing
  uv run scripts/reset_state.py --yes      # actually delete

Requires Application Default Credentials (gcloud auth application-default login).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from google.cloud import firestore, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("reset_state")

# Firestore collections we delete.
SESSIONS_COLLECTION = "adk_sessions"
EVENTS_SUBCOLLECTION = "events"
USER_STATE_COLLECTION = "adk_user_state"
APP_STATE_COLLECTION = "adk_app_state"
ASSET_METADATA_COLLECTION = "asset_metadata"

# GCS prefix under which all assets live.
ASSETS_PREFIX = "assets/"

# Firestore allows at most 500 writes per batch.
BATCH_LIMIT = 500


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        log.error("Missing required environment variable: %s", name)
        sys.exit(2)
    return value


def _assert_non_prod(project: str) -> None:
    """Refuse to run against anything that does not look like dev/test."""
    lowered = project.lower()
    if "dev" not in lowered and "test" not in lowered:
        log.error(
            "SAFETY ABORT: GCP_PROJECT=%r does not contain 'dev' or 'test'. "
            "This script is DEV/TEST ONLY and will never run against prod.",
            project,
        )
        sys.exit(3)


def _delete_collection_docs(
    db: firestore.Client,
    collection: str,
    *,
    apply: bool,
    delete_subcollection: str | None = None,
) -> int:
    """Delete every document in a top-level collection.

    If `delete_subcollection` is given, every document in that named
    subcollection is deleted first (e.g. adk_sessions/{id}/events/{event}).
    Returns the number of top-level documents counted (dry-run) or deleted.
    """
    coll_ref = db.collection(collection)
    doc_count = 0
    sub_count = 0
    batch = db.batch()
    pending = 0

    def _flush() -> None:
        nonlocal batch, pending
        if pending and apply:
            batch.commit()
            batch = db.batch()
        pending = 0

    for doc in coll_ref.stream():
        doc_count += 1

        if delete_subcollection is not None:
            for sub_doc in doc.reference.collection(delete_subcollection).stream():
                sub_count += 1
                if apply:
                    batch.delete(sub_doc.reference)
                    pending += 1
                    if pending >= BATCH_LIMIT:
                        _flush()

        if apply:
            batch.delete(doc.reference)
            pending += 1
            if pending >= BATCH_LIMIT:
                _flush()

    _flush()

    if delete_subcollection is not None:
        log.info(
            "%s: %s docs, %s %s docs %s",
            collection,
            doc_count,
            sub_count,
            delete_subcollection,
            "deleted" if apply else "would delete (dry-run)",
        )
    else:
        log.info(
            "%s: %s docs %s",
            collection,
            doc_count,
            "deleted" if apply else "would delete (dry-run)",
        )
    return doc_count


def _delete_gcs_prefix(bucket_name: str, prefix: str, *, apply: bool) -> int:
    """Delete every blob under a prefix in a bucket. Returns blob count."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    count = 0
    for blob in client.list_blobs(bucket, prefix=prefix):
        count += 1
        if apply:
            blob.delete()
    log.info(
        "gs://%s/%s*: %s blobs %s",
        bucket_name,
        prefix,
        count,
        "deleted" if apply else "would delete (dry-run)",
    )
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete. Without this flag the script is a dry-run.",
    )
    args = parser.parse_args()
    apply = bool(args.yes)

    project = _require_env("GCP_PROJECT")
    database = _require_env("FIRESTORE_DATABASE")
    bucket = _require_env("ASSETS_BUCKET")

    _assert_non_prod(project)

    mode = "DELETE" if apply else "DRY-RUN (no changes)"
    log.info("=== reset_state: %s ===", mode)
    log.info("GCP_PROJECT=%s FIRESTORE_DATABASE=%s ASSETS_BUCKET=%s", project, database, bucket)

    db = firestore.Client(project=project, database=database)

    log.info("--- Sessions ---")
    sessions = _delete_collection_docs(
        db, SESSIONS_COLLECTION, apply=apply, delete_subcollection=EVENTS_SUBCOLLECTION
    )
    user_state = _delete_collection_docs(db, USER_STATE_COLLECTION, apply=apply)
    app_state = _delete_collection_docs(db, APP_STATE_COLLECTION, apply=apply)

    log.info("--- Assets ---")
    asset_docs = _delete_collection_docs(db, ASSET_METADATA_COLLECTION, apply=apply)
    blobs = _delete_gcs_prefix(bucket, ASSETS_PREFIX, apply=apply)

    log.info("=== Summary (%s) ===", mode)
    log.info(
        "sessions=%s user_state=%s app_state=%s asset_docs=%s gcs_blobs=%s",
        sessions,
        user_state,
        app_state,
        asset_docs,
        blobs,
    )
    log.info("Kept (untouched): extractions, llm_usage")
    if not apply:
        log.info("Dry-run only. Re-run with --yes to delete.")


if __name__ == "__main__":
    main()
