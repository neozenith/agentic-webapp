"""Pseudonymous user identity.

The raw IAP email is the caller's identity but must never become a storage key
(Firestore session owner, bookkeeping user_id). We derive a stable, opaque id with
UUIDv5: deterministic (same email always maps to the same id, so durable session
resume is stable across restarts) and one-way (the email can't be recovered from the
id without the namespace + a brute-force guess). Computed once here, at the backend
boundary; everything downstream passes the opaque id through.
"""

from __future__ import annotations

import uuid

# Fixed application namespace for user-id hashing. Stable forever — changing it would
# re-pseudonymise every existing user and orphan their sessions.
APP_NAMESPACE = uuid.UUID("8f3a6c2e-5b41-5d9a-9e7c-2a1f4b6d8c30")


def mask_user_id(email: str) -> str:
    """Deterministic, opaque user id for an email. Normalised (lowercased, trimmed) so
    the same identity always yields the same id regardless of casing."""
    return str(uuid.uuid5(APP_NAMESPACE, email.strip().lower()))
