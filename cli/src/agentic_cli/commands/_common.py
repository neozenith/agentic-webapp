"""Helpers shared across command modules."""

from __future__ import annotations

import argparse
from typing import Any

from ..client import ApiClient


def client_from(args: argparse.Namespace) -> ApiClient:
    """An ApiClient bound to the chosen base URL and impersonated persona (--as)."""
    return ApiClient(args.base_url, as_user=args.as_user)


def share_body(args: argparse.Namespace) -> dict[str, Any]:
    """The common share-request payload used by assets and folders (only supplied deltas)."""
    return {
        "add_user_emails": args.add_user or [],
        "add_group_ids": args.add_group or [],
        "remove_user_ids": args.remove_user or [],
        "remove_group_ids": args.remove_group or [],
    }
