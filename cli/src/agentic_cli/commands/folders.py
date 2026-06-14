"""Folder commands — list/create/share/delete. Folders cascade their sharing to contained
assets; visibility + owner-only mutation are enforced server-side per the --as persona."""

from __future__ import annotations

import argparse

from ..formatting import emit
from ._common import client_from, share_body

_COLUMNS = ["folder_id", "name", "parent_id", "owner_id"]


def cmd_list(args: argparse.Namespace) -> None:
    """List folders visible to the persona (GET /api/folders)."""
    with client_from(args) as client:
        emit(args, client.get("/api/folders"), columns=_COLUMNS)


def cmd_create(args: argparse.Namespace) -> None:
    """Create a folder (POST /api/folders)."""
    with client_from(args) as client:
        emit(args, client.post("/api/folders", json={"name": args.name, "parent_id": args.parent_id}))


def cmd_share(args: argparse.Namespace) -> None:
    """Grant/revoke folder access for users + groups (POST /api/folders/{id}/share)."""
    with client_from(args) as client:
        emit(args, client.post(f"/api/folders/{args.folder_id}/share", json=share_body(args)))


def cmd_delete(args: argparse.Namespace) -> None:
    """Delete a folder (owner/admin only) (DELETE /api/folders/{id})."""
    with client_from(args) as client:
        client.delete(f"/api/folders/{args.folder_id}")
    print(f"deleted folder {args.folder_id}")
