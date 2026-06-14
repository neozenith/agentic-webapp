"""End-to-end CLI tests against the real backend. Each call goes over HTTP to a live server,
so RBAC, error surfacing, and exit codes are all genuine. Identity is chosen with --as.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from agentic_cli.app import main

ADMIN = "ada.admin@example.com"
ANALYST = "nina.analyst@example.com"
OPERATOR = "otto.operator@example.com"
VIEWER = "vera.viewer@example.com"


def run(capsys: pytest.CaptureFixture[str], url: str, *argv: str, as_user: str | None = None) -> tuple[int, str, str]:
    """Invoke the CLI; return (exit_code, stdout, stderr). exit_code 0 == success."""
    full = [*argv, "--base-url", url]
    if as_user is not None:
        full += ["--as", as_user]
    code = 0
    try:
        main(full)
    except SystemExit as exc:  # argparse usage (2) or ApiError (1)
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _json(capsys: pytest.CaptureFixture[str], url: str, *argv: str, as_user: str | None = None) -> Any:
    code, out, err = run(capsys, url, *argv, "--json", as_user=as_user)
    assert code == 0, err
    return json.loads(out)


# --- identity + RBAC simulation (requirement 5) ---


def test_me_resolves_roles_per_persona(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    assert _json(capsys, backend_url, "me", as_user=ADMIN)["roles"] == ["admin"]
    assert _json(capsys, backend_url, "me", as_user=VIEWER)["roles"] == ["viewer"]
    assert _json(capsys, backend_url, "me")["roles"] == []  # no --as → no identity


def test_personas_lists_test_users(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    emails = {p["email"] for p in _json(capsys, backend_url, "personas", as_user=ADMIN)}
    assert {ADMIN, ANALYST, OPERATOR, VIEWER} <= emails


def test_directory_is_a_mapping(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    assert isinstance(_json(capsys, backend_url, "directory", as_user=ADMIN), dict)


def test_admin_users_allowed_for_admin_denied_for_viewer(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    code, out, _ = run(capsys, backend_url, "admin", "users", "--json", as_user=ADMIN)
    assert code == 0 and isinstance(json.loads(out), list)
    code, _, err = run(capsys, backend_url, "admin", "users", as_user=VIEWER)
    assert code == 1 and "403" in err and "admin" in err


def test_analytics_denied_for_viewer_allowed_for_analyst(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    code, _, _ = run(capsys, backend_url, "analytics", "summary", as_user=ANALYST)
    assert code == 0
    code, _, err = run(capsys, backend_url, "analytics", "summary", as_user=VIEWER)
    assert code == 1 and "403" in err


def test_admin_usage_and_records_and_sessions(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    assert "totals" in _json(capsys, backend_url, "admin", "usage", as_user=ADMIN)
    assert isinstance(_json(capsys, backend_url, "admin", "usage-records", as_user=ADMIN), list)
    assert _json(capsys, backend_url, "admin", "sessions", "nobody", as_user=ADMIN) == []


def test_analytics_extractions_table(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    code, out, _ = run(capsys, backend_url, "analytics", "extractions", as_user=ANALYST)
    assert code == 0 and "extraction_id" in out  # table header even when empty


# --- asset + folder lifecycle with ownership visibility (requirement 5, data plane) ---


def test_asset_upload_share_visibility_and_delete(capsys: pytest.CaptureFixture[str], backend_url: str, tmp_path: Any) -> None:
    f = tmp_path / "receipt.txt"
    f.write_text("hello", encoding="utf-8")
    asset = _json(capsys, backend_url, "assets", "upload", str(f), as_user=OPERATOR)
    asset_id = asset["asset_id"]

    # Owner sees it; an unrelated viewer does not (visibility is server-enforced).
    owner_ids = {a["asset_id"] for a in _json(capsys, backend_url, "assets", "list", as_user=OPERATOR)}
    viewer_ids = {a["asset_id"] for a in _json(capsys, backend_url, "assets", "list", as_user=VIEWER)}
    assert asset_id in owner_ids and asset_id not in viewer_ids

    # Share it with the viewer (by email) → now visible.
    _json(capsys, backend_url, "assets", "share", asset_id, "--add-user", VIEWER, as_user=OPERATOR)
    viewer_ids_after = {a["asset_id"] for a in _json(capsys, backend_url, "assets", "list", as_user=VIEWER)}
    assert asset_id in viewer_ids_after

    # A viewer may not delete someone else's asset; the owner may.
    code, _, err = run(capsys, backend_url, "assets", "delete", asset_id, as_user=VIEWER)
    assert code == 1 and "403" in err
    code, out, _ = run(capsys, backend_url, "assets", "delete", asset_id, as_user=OPERATOR)
    assert code == 0 and "deleted" in out


def test_asset_get_url_move_combine(capsys: pytest.CaptureFixture[str], backend_url: str, tmp_path: Any) -> None:
    paths = []
    for name in ("a.txt", "b.txt"):
        p = tmp_path / name
        p.write_text(name, encoding="utf-8")
        paths.append(_json(capsys, backend_url, "assets", "upload", str(p), as_user=ADMIN)["asset_id"])

    # get + url
    assert _json(capsys, backend_url, "assets", "get", paths[0], as_user=ADMIN)["asset_id"] == paths[0]
    assert "url" in _json(capsys, backend_url, "assets", "url", paths[0], as_user=ADMIN)

    # move into a new folder
    folder = _json(capsys, backend_url, "folders", "create", "Trips", as_user=ADMIN)
    moved = _json(capsys, backend_url, "assets", "move", paths[0], "--folder-id", folder["folder_id"], as_user=ADMIN)
    assert moved["folder_id"] == folder["folder_id"]

    # combine the two
    combined = _json(capsys, backend_url, "assets", "combine", *paths, "--filename", "both.txt", as_user=ADMIN)
    assert combined["filename"] == "both.txt"


def test_folder_create_visibility_share_delete(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    folder = _json(capsys, backend_url, "folders", "create", "Private", as_user=OPERATOR)
    fid = folder["folder_id"]
    mine = {x["folder_id"] for x in _json(capsys, backend_url, "folders", "list", as_user=OPERATOR)}
    theirs = {x["folder_id"] for x in _json(capsys, backend_url, "folders", "list", as_user=VIEWER)}
    assert fid in mine and fid not in theirs
    # share with the viewer → now visible to them (folder sharing cascades server-side)
    _json(capsys, backend_url, "folders", "share", fid, "--add-user", VIEWER, as_user=OPERATOR)
    theirs_after = {x["folder_id"] for x in _json(capsys, backend_url, "folders", "list", as_user=VIEWER)}
    assert fid in theirs_after
    # owner may delete; the deletion is acknowledged
    code, out, _ = run(capsys, backend_url, "folders", "delete", fid, as_user=OPERATOR)
    assert code == 0 and "deleted" in out


def test_groups_discovery_and_admin_group_crud(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    created = _json(capsys, backend_url, "admin", "group-create", "Crew", "--member", ANALYST, as_user=ADMIN)
    gid = created["group_id"]
    # public discovery lists it (id + name only)
    listed = {x["group_id"] for x in _json(capsys, backend_url, "groups", "list", as_user=VIEWER)}
    assert gid in listed
    # non-admin may not create groups
    code, _, err = run(capsys, backend_url, "admin", "group-create", "Nope", as_user=VIEWER)
    assert code == 1 and "403" in err
    # admin deletes it
    code, out, _ = run(capsys, backend_url, "admin", "group-delete", gid, as_user=ADMIN)
    assert code == 0 and "deleted" in out


# --- CLI mechanics ---


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    code, out, _ = run(capsys, backend_url)
    assert code == 0 and "usage:" in out.lower()


def test_group_without_subcommand_prints_group_help(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    code, out, _ = run(capsys, backend_url, "assets")
    assert code == 0 and "list" in out and "share" in out


def test_unknown_asset_get_surfaces_404(capsys: pytest.CaptureFixture[str], backend_url: str) -> None:
    code, _, err = run(capsys, backend_url, "assets", "get", "does-not-exist", as_user=ADMIN)
    assert code == 1 and "404" in err
