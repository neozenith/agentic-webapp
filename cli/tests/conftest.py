"""Shared fixtures. Tests drive the CLI against the REAL backend (in-memory backends, IAP
identity simulation on) booted in-process on a loopback port — RBAC is exercised for real,
no mocks (project rule)."""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="session")
def backend_url() -> Iterator[str]:
    from agentic_webapp.config import get_settings
    from agentic_webapp.main import create_app

    port = _free_port()
    keys = ("ENVIRONMENT", "TRUST_FORWARDED_USER", "SELF_BASE_URL", "PORT")
    prev = {k: os.environ.get(k) for k in keys}
    os.environ.update(
        ENVIRONMENT="dev",
        TRUST_FORWARDED_USER="true",
        SELF_BASE_URL=f"http://127.0.0.1:{port}",
        PORT=str(port),
    )
    get_settings.cache_clear()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:  # pragma: no cover — startup spin
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
