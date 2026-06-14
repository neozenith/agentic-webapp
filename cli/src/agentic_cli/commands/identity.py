"""Identity + RBAC introspection: who am I, which personas exist, the user directory."""

from __future__ import annotations

import argparse

from ..formatting import emit
from ._common import client_from


def cmd_me(args: argparse.Namespace) -> None:
    """Show the caller's resolved identity, roles, and permissions (GET /api/me)."""
    with client_from(args) as client:
        emit(args, client.get("/api/me"))


def cmd_personas(args: argparse.Namespace) -> None:
    """List the switchable test personas (non-prod) you can pass to --as."""
    with client_from(args) as client:
        emit(args, client.get("/api/auth/personas"), columns=["email", "name", "roles"])


def cmd_directory(args: argparse.Namespace) -> None:
    """Show the pseudonymous-id → {email,name} directory (GET /api/directory)."""
    with client_from(args) as client:
        emit(args, client.get("/api/directory"))
