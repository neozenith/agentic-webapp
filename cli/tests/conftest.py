"""Shared fixtures. Tests drive the CLI against the REAL backend (in-memory backends, IAP
identity simulation on) booted in-process on a loopback port via the backend's shared
`live_backend` helper — RBAC is exercised for real, no mocks (project rule)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from agentic_webapp.testing import live_backend


@pytest.fixture(scope="session")
def backend_url() -> Iterator[str]:
    with live_backend() as base_url:
        yield base_url
