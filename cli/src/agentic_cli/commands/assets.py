"""Asset commands — list/get/url/upload/share/move/delete/combine. Visibility + owner-only
mutation are enforced server-side per the --as persona; the CLI just forwards the call."""

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from ..formatting import emit
from ._common import client_from, share_body

_COLUMNS = ["asset_id", "filename", "owner_id", "folder_id", "content_type"]


def cmd_list(args: argparse.Namespace) -> None:
    """List assets visible to the persona (GET /api/assets)."""
    with client_from(args) as client:
        emit(args, client.get("/api/assets", params={"limit": args.limit}), columns=_COLUMNS)


def cmd_get(args: argparse.Namespace) -> None:
    """Show one asset's metadata (GET /api/assets/{id})."""
    with client_from(args) as client:
        emit(args, client.get(f"/api/assets/{args.asset_id}"))


def cmd_url(args: argparse.Namespace) -> None:
    """Get a time-limited signed URL for an asset (GET /api/assets/{id}/url)."""
    with client_from(args) as client:
        emit(args, client.get(f"/api/assets/{args.asset_id}/url"))


def cmd_upload(args: argparse.Namespace) -> None:
    """Upload a file as a new asset (POST /api/assets)."""
    path = Path(args.file)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    files = {"file": (path.name, path.read_bytes(), content_type)}
    data = {"folder_id": args.folder_id} if args.folder_id else {}
    with client_from(args) as client:
        emit(args, client.post("/api/assets", files=files, data=data))


def cmd_share(args: argparse.Namespace) -> None:
    """Grant/revoke access for users (by email) and groups (POST /api/assets/{id}/share)."""
    with client_from(args) as client:
        emit(args, client.post(f"/api/assets/{args.asset_id}/share", json=share_body(args)))


def cmd_move(args: argparse.Namespace) -> None:
    """Move an asset to a folder (or root with no --folder-id) (POST /api/assets/{id}/move)."""
    with client_from(args) as client:
        emit(args, client.post(f"/api/assets/{args.asset_id}/move", json={"folder_id": args.folder_id}))


def cmd_combine(args: argparse.Namespace) -> None:
    """Concatenate two or more assets into a new one (POST /api/assets/combine)."""
    body = {"asset_ids": args.asset_ids, "filename": args.filename, "content_type": args.content_type}
    with client_from(args) as client:
        emit(args, client.post("/api/assets/combine", json=body))


def cmd_delete(args: argparse.Namespace) -> None:
    """Delete an asset (owner/admin only) (DELETE /api/assets/{id})."""
    with client_from(args) as client:
        client.delete(f"/api/assets/{args.asset_id}")
    print(f"deleted asset {args.asset_id}")
