"""HTTP client for the core API.

A thin wrapper over httpx that forwards the chosen persona as the IAP identity header, so
the server's existing RBAC engine decides what each call may do — the CLI itself enforces
nothing. Non-2xx responses become an `ApiError` carrying the server's `detail`, which the
app surfaces and exits non-zero on (so `--as vera.viewer admin users` prints the 403).
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from .config import IAP_USER_HEADER


class ApiError(RuntimeError):
    """A non-2xx API response. `status_code` + `detail` come straight from the server."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _detail(response: httpx.Response) -> str:
    """The server's error detail if it sent JSON `{"detail": ...}`, else the raw body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)[:200]


class ApiClient:
    """Synchronous client bound to a base URL and (optionally) an impersonated persona."""

    def __init__(self, base_url: str, *, as_user: str | None = None, timeout: float = 30.0) -> None:
        headers = {IAP_USER_HEADER: as_user} if as_user else {}
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._client.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise ApiError(response.status_code, _detail(response))
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)
