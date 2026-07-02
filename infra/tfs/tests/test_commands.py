"""cmd_create + cmd_gha_check against REAL tmp infra/repo roots (no mocks). These
were previously excluded from coverage; they are pure filesystem logic and ARE
testable. The terraform passthrough command builder is tested here too."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from tfs.commands.create import cmd_create
from tfs.commands.gha import cmd_gha_check
from tfs.commands.terraform import build_tf_command
from tfs.errors import TFStackCLIInputError


def _infra(tmp_path: Path) -> Path:
    root = tmp_path / "infra"
    (root / "stacks").mkdir(parents=True)
    (root / "config.yml").write_text(
        "layout: multi-project\n"
        "state_location: au\n"
        "environments:\n"
        "  dev:\n    project_id: proj-dev\n    state_bucket: bkt-dev\n"
        "  test:\n    project_id: proj-test\n    state_bucket: bkt-test\n"
        "  prod:\n    project_id: proj-prod\n    state_bucket: bkt-prod\n",
        encoding="utf-8",
    )
    return root


def _infra_single(tmp_path: Path) -> Path:
    root = tmp_path / "infra"
    (root / "stacks").mkdir(parents=True)
    (root / "config.yml").write_text(
        "layout: single-project\n"
        "state_location: au\n"
        "project_id: shared-proj\n"
        "state_bucket: shared-bkt\n"
        "environments: [dev, test, prod]\n",
        encoding="utf-8",
    )
    return root


# --- cmd_create ---------------------------------------------------------------


def test_create_scaffolds_stack_and_workflow(tmp_path):
    root = _infra(tmp_path)
    cmd_create(Namespace(stack="monitoring", infra_root=str(root)))

    stack = root / "stacks" / "monitoring"
    assert (stack / "main.tf").exists()
    assert (stack / "README.md").exists()
    for env in ("dev", "test", "prod"):
        cfg = (stack / "backends" / f"{env}.config").read_text()
        assert f'bucket = "bkt-{env}"' in cfg  # per-env state bucket
        assert f"terraform/state/{env}/monitoring" in cfg  # env-baked prefix (canonical, both layouts)
    # workflow scaffolded under the resolved repo root (.github lands at infra root here)
    wf = list(root.rglob("terraform-cicd-stack-monitoring.yml"))
    assert wf, "per-stack CI workflow not scaffolded"


def test_create_single_project_bakes_env_into_prefix(tmp_path):
    root = _infra_single(tmp_path)
    cmd_create(Namespace(stack="monitoring", infra_root=str(root)))

    stack = root / "stacks" / "monitoring"
    for env in ("dev", "test", "prod"):
        cfg = (stack / "backends" / f"{env}.config").read_text()
        assert 'bucket = "shared-bkt"' in cfg  # one shared bucket for every env
        assert f"terraform/state/{env}/monitoring" in cfg  # env-in-prefix convention


def test_create_existing_stack_noops(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    with pytest.raises(SystemExit) as e:
        cmd_create(Namespace(stack="webapp", infra_root=str(root)))
    assert e.value.code == 0  # already-exists is a clean no-op, not an error


# --- cmd_gha_check ------------------------------------------------------------


def _workflow(root: Path, stack: str) -> None:
    d = root / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"terraform-cicd-stack-{stack}.yml").write_text("name: x\n", encoding="utf-8")


def test_gha_check_passes_when_matched(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    _workflow(root, "webapp")  # .github at infra root -> find_repo_root falls back to it
    cmd_gha_check(Namespace(infra_root=str(root)))  # no SystemExit => matched


def test_gha_check_fails_on_stack_without_workflow(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)  # empty -> webapp has no workflow
    with pytest.raises(SystemExit):
        cmd_gha_check(Namespace(infra_root=str(root)))


def test_gha_check_fails_on_orphan_workflow(tmp_path):
    root = _infra(tmp_path)
    _workflow(root, "ghost")  # workflow with no matching stack
    with pytest.raises(SystemExit):
        cmd_gha_check(Namespace(infra_root=str(root)))


# --- build_tf_command (pure command construction) -----------------------------


def test_build_tf_command_dispatch(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    assert build_tf_command("init", "webapp", "dev", root).endswith("-reconfigure")
    assert "plan -no-color" in build_tf_command("plan", "webapp", "dev", root)
    assert build_tf_command("apply", "webapp", "test", root).endswith("-auto-approve")
    assert build_tf_command("output", "webapp", "dev", root).endswith("output -json")
    assert "force-unlock LID" in build_tf_command("force-unlock", "webapp", "dev", root, lock_id="LID")
    imp = build_tf_command("import", "webapp", "dev", root, tf_address="google_x.y", resource_id="rid")
    assert "import" in imp and "google_x.y" in imp and "rid" in imp


def test_build_tf_command_picks_up_tfvars(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    (root / "stacks" / "webapp" / "dev.tfvars").write_text("x = 1\n")
    assert "-var-file=dev.tfvars" in build_tf_command("plan", "webapp", "dev", root)


def test_build_tf_command_rejects_unknown_stack_and_command(tmp_path):
    root = _infra(tmp_path)
    (root / "stacks" / "webapp").mkdir()
    with pytest.raises(TFStackCLIInputError, match="does not exist"):
        build_tf_command("plan", "ghost", "dev", root)
    with pytest.raises(TFStackCLIInputError, match="Unsupported"):
        build_tf_command("destroy", "webapp", "dev", root)
