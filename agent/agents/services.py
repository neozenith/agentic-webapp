"""ADK custom-service registration (auto-loaded by ADK's service registry).

ADK calls load_services_module() on the agents dir before it resolves
--session_service_uri, so registering the `firestore` scheme here lets
`--session_service_uri firestore://` select our durable FirestoreSessionService.
The Firestore (named) database id comes from FIRESTORE_DATABASE (falling back to the
URI host, then the default database); the project from the runtime env. Fails loud if
no project is configured — never silently degrades to a different store.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from google.adk.cli.service_registry import get_service_registry

from assistant.firestore_session import FirestoreSessionService


def _firestore_session_factory(uri: str, **_: object) -> FirestoreSessionService:
    project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("firestore:// session service requires GCP_PROJECT or GOOGLE_CLOUD_PROJECT")
    database = os.environ.get("FIRESTORE_DATABASE") or urlparse(uri).netloc or "(default)"
    return FirestoreSessionService(project=project, database=database)


get_service_registry().register_session_service("firestore", _firestore_session_factory)
