"""Admin commands over LLM bookkeeping + group management. All 403 unless --as resolves to
an admin role — the clearest demonstration of RBAC: same command, different persona, different
outcome."""

from __future__ import annotations

import argparse

from ..formatting import emit
from ._common import client_from


def cmd_users(args: argparse.Namespace) -> None:
    """Per-user usage roll-up, most expensive first (GET /api/admin/users)."""
    with client_from(args) as client:
        emit(
            args,
            client.get("/api/admin/users", params={"limit": args.limit}),
            columns=["user_id", "email", "sessions", "calls", "total_tokens", "est_cost_usd"],
        )


def cmd_usage(args: argparse.Namespace) -> None:
    """Aggregate token/cost usage overall and by model + user (GET /api/admin/usage)."""
    with client_from(args) as client:
        emit(args, client.get("/api/admin/usage", params={"limit": args.limit}))


def cmd_usage_records(args: argparse.Namespace) -> None:
    """Most-recent itemised usage records (GET /api/admin/usage/records)."""
    with client_from(args) as client:
        emit(
            args,
            client.get("/api/admin/usage/records", params={"limit": args.limit}),
            columns=["request_id", "user_id", "model_id", "total_tokens", "est_cost_usd", "timestamp"],
        )


def cmd_sessions(args: argparse.Namespace) -> None:
    """Per-session roll-up for one user (GET /api/admin/users/{user_id}/sessions)."""
    with client_from(args) as client:
        emit(
            args,
            client.get(f"/api/admin/users/{args.user_id}/sessions"),
            columns=["session_id", "calls", "total_tokens", "est_cost_usd", "last_timestamp"],
        )


def cmd_group_create(args: argparse.Namespace) -> None:
    """Create a group with optional member emails (POST /api/admin/groups)."""
    body = {"name": args.name, "member_emails": args.member or []}
    with client_from(args) as client:
        emit(args, client.post("/api/admin/groups", json=body))


def cmd_group_delete(args: argparse.Namespace) -> None:
    """Delete a group (DELETE /api/admin/groups/{group_id})."""
    with client_from(args) as client:
        client.delete(f"/api/admin/groups/{args.group_id}")
    print(f"deleted group {args.group_id}")
