"""Public group discovery — read-only group listing any signed-in user may see (so you can
find a group_id to share with). Group CRUD is admin-only; see the `admin` command group."""

from __future__ import annotations

import argparse

from ..formatting import emit
from ._common import client_from


def cmd_list(args: argparse.Namespace) -> None:
    """List groups (id + name, no membership) (GET /api/groups)."""
    with client_from(args) as client:
        emit(args, client.get("/api/groups"), columns=["group_id", "name"])
