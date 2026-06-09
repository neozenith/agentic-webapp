"""cmd_validate + config helpers against REAL config.yml + backend config files in a
tmp infra root (no mocks). validate uses only the infra root, so no git/repo needed."""

from argparse import Namespace
from pathlib import Path

import pytest

from tfs.commands.validate import cmd_validate
from tfs.config import list_stacks


def _infra(tmp_path: Path) -> Path:
    root = tmp_path / "infra"
    (root / "stacks").mkdir(parents=True)
    (root / "config.yml").write_text(
        "environments:\n"
        "  dev:\n    state_bucket: bkt-dev\n"
        "  test:\n    state_bucket: bkt-test\n"
        "  prod:\n    state_bucket: bkt-prod\n",
        encoding="utf-8",
    )
    return root


def _backend(root: Path, stack: str, env: str, bucket: str, prefix: str) -> None:
    d = root / "stacks" / stack / "backends"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{env}.config").write_text(f'bucket = "{bucket}"\nprefix = "{prefix}"\n', encoding="utf-8")


def test_validate_accepts_conventional_config(tmp_path):
    root = _infra(tmp_path)
    _backend(root, "webapp", "dev", "bkt-dev", "terraform/state/webapp")
    cmd_validate(Namespace(infra_root=str(root)))  # no SystemExit => valid


def test_validate_rejects_wrong_bucket_and_prefix(tmp_path):
    root = _infra(tmp_path)
    _backend(root, "webapp", "dev", "WRONG", "also/wrong")
    with pytest.raises(SystemExit):
        cmd_validate(Namespace(infra_root=str(root)))


def test_validate_flags_invalid_environment(tmp_path):
    root = _infra(tmp_path)
    _backend(root, "webapp", "staging", "bkt-dev", "terraform/state/webapp")
    with pytest.raises(SystemExit):
        cmd_validate(Namespace(infra_root=str(root)))


def test_validate_warns_when_no_backend_files(tmp_path):
    cmd_validate(Namespace(infra_root=str(_infra(tmp_path))))  # warns, exits cleanly


def test_list_stacks(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    (root / "stacks" / "monitoring").mkdir()
    assert list_stacks(root) == ["monitoring", "webapp"]
    assert list_stacks(tmp_path / "absent") == []


def test_main_prints_help_without_a_command(monkeypatch, capsys):
    import sys

    from tfs.app import main

    monkeypatch.setattr(sys, "argv", ["tfs"])  # no subcommand -> top-level help via _help closure
    main()
    assert "usage" in capsys.readouterr().out.lower()
