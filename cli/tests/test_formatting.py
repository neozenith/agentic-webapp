"""Output rendering: table vs JSON, and cell coercion of None/list values."""

from __future__ import annotations

import argparse
import json

import pytest

from agentic_cli.formatting import emit


def _args(*, json_mode: bool) -> argparse.Namespace:
    return argparse.Namespace(json=json_mode)


def test_table_renders_rows_with_none_and_list_cells(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [
        {"id": "a1", "owner": None, "tags": ["x", "y"]},
        {"id": "a2", "owner": "u1", "tags": []},
    ]
    emit(_args(json_mode=False), rows, columns=["id", "owner", "tags"])
    out = capsys.readouterr().out
    assert "id" in out and "owner" in out  # header
    assert "x,y" in out  # list cell joined
    assert "a1" in out and "a2" in out
    assert "(2 rows)" in out


def test_json_mode_overrides_columns(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"id": "a1"}]
    emit(_args(json_mode=True), rows, columns=["id"])
    assert json.loads(capsys.readouterr().out) == rows


def test_non_list_data_is_always_json(capsys: pytest.CaptureFixture[str]) -> None:
    emit(_args(json_mode=False), {"roles": ["admin"]}, columns=["whatever"])
    assert json.loads(capsys.readouterr().out) == {"roles": ["admin"]}


def test_singular_row_count(capsys: pytest.CaptureFixture[str]) -> None:
    emit(_args(json_mode=False), [{"id": "only"}], columns=["id"])
    assert "(1 row)" in capsys.readouterr().out
