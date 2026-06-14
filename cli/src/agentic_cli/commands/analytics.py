"""Analytics commands over the extraction warehouse. Require the analytics area (analyst or
admin); a viewer/operator persona is 403'd server-side."""

from __future__ import annotations

import argparse

from ..formatting import emit
from ._common import client_from


def cmd_summary(args: argparse.Namespace) -> None:
    """Aggregate extraction analytics (GET /api/analytics/summary)."""
    with client_from(args) as client:
        emit(args, client.get("/api/analytics/summary", params={"limit": args.limit}))


def cmd_extractions(args: argparse.Namespace) -> None:
    """Recent structured extractions (GET /api/analytics/extractions)."""
    with client_from(args) as client:
        emit(
            args,
            client.get("/api/analytics/extractions", params={"limit": args.limit}),
            columns=["extraction_id", "doc_type", "asset_id", "user_id", "created_at"],
        )
