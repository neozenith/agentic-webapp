"""Output rendering: a compact table for list responses, pretty JSON for everything else
(or whenever --json is passed). Tables read dict keys straight from the server JSON."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value)


def _table(rows: list[dict[str, Any]], columns: Sequence[str]) -> None:
    widths = {c: len(c) for c in columns}
    cells = [{c: _cell(row.get(c)) for c in columns} for row in rows]
    for row in cells:
        for c in columns:
            widths[c] = max(widths[c], len(row[c]))
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for row in cells:
        print("  ".join(row[c].ljust(widths[c]) for c in columns))
    print(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''})")


def emit(args: argparse.Namespace, data: Any, *, columns: Sequence[str] | None = None) -> None:
    """Render an API response. List-of-objects with `columns` → table (unless --json);
    anything else → pretty JSON."""
    if not getattr(args, "json", False) and columns and isinstance(data, list):
        _table([row for row in data if isinstance(row, dict)], columns)
        return
    print(json.dumps(data, indent=2, default=str))
