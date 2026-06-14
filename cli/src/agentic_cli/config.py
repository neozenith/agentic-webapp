"""CLI defaults + the identity header. Nothing reads os.environ elsewhere."""

from __future__ import annotations

import os

# The local backend's default address (`make -C backend dev`). Override with --base-url.
DEFAULT_BASE_URL = os.environ.get("AGENTIC_BASE_URL", "http://localhost:8080")

# The IAP identity header the backend trusts in non-prod to simulate "who is signed in"
# (ADR-0004). Setting it via --as is how the CLI exercises RBAC as a given persona.
IAP_USER_HEADER = "X-Goog-Authenticated-User-Email"
