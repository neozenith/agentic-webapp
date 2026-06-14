"""Test utility: boot the real app on a loopback port for integration tests.

Shipped in the package (not under tests/) so other subprojects' suites — the CLI, the agent
harness — can drive the real backend over HTTP without copying the boot protocol. The protocol
(in-memory backends, IAP identity simulation on, the MCP loopback pinned to the chosen port,
and the get_settings cache reset) lives here once; callers just need the base URL. Real server,
no mocks (project rule).
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn

from .config import get_settings
from .main import create_app

# Non-prod identity simulation: trust the IAP header so a persona can be chosen per request.
_SIM_ENV = {"ENVIRONMENT": "dev", "TRUST_FORWARDED_USER": "true"}


def free_port() -> int:
    """An OS-assigned free TCP port on loopback."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    sock.close()
    return port


@contextmanager
def live_backend() -> Iterator[str]:
    """Run the real app on a free loopback port (in-memory backends, identity simulation on,
    MCP loopback pinned to that port). Yields the base URL; restores os.environ + the settings
    cache on exit so suites stay isolated."""
    port = free_port()
    env = {**_SIM_ENV, "SELF_BASE_URL": f"http://127.0.0.1:{port}", "PORT": str(port)}
    prev = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    get_settings.cache_clear()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:  # pragma: no cover — tight startup spin
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:  # pragma: no cover — only when the var was already set in the environment
                os.environ[key] = value
        get_settings.cache_clear()
