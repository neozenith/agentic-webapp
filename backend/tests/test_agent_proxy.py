"""Unit tests for the agent reverse-proxy header handling. No live sidecar needed:
forward_headers is a pure function, so we test the real filtering behavior directly."""

from agentic_webapp.api.routes.agent import forward_headers


def test_forward_headers_drops_browser_origin_and_referer():
    """The browser sends Origin/Referer pointing at the public site; ADK's origin
    guard rejects those ("Forbidden: origin not allowed"). The proxy must strip them
    so the localhost hop is treated as same-origin."""
    incoming = {
        "origin": "https://agentic-webapp-xyz.a.run.app",
        "referer": "https://agentic-webapp-xyz.a.run.app/chat",
        "content-type": "application/json",
        "x-goog-authenticated-user-email": "accounts.google.com:user@example.com",
    }
    out = forward_headers(incoming)
    assert "origin" not in {k.lower() for k in out}
    assert "referer" not in {k.lower() for k in out}
    # Non-dropped headers (incl. the IAP identity for bookkeeping) pass through.
    assert out["content-type"] == "application/json"
    assert out["x-goog-authenticated-user-email"] == "accounts.google.com:user@example.com"


def test_forward_headers_drops_hop_by_hop():
    incoming = {"host": "example.com", "connection": "keep-alive", "accept": "*/*"}
    out = forward_headers(incoming)
    assert {k.lower() for k in out} == {"accept"}
