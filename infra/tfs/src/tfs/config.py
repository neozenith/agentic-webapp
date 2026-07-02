"""Convention + config helpers: the config.yml, the state-prefix rule, and stack
enumeration. Everything here is a pure function of the infra root.

tfs supports TWO project layouts, declared by the required `layout:` key in
config.yml (escalators-not-stairs: an unknown/missing layout is a loud failure,
never a silent guess):

  layout: multi-project   # one GCP project + tfstate bucket PER environment.
      environments is a MAP {env: {project_id, state_bucket}}. State is isolated by
      living in a different project/bucket per env, so the prefix is per-stack only:
      terraform/state/<stack>.

  layout: single-project  # ONE GCP project + ONE tfstate bucket for every env.
      environments is a LIST [dev, test, prod] and project_id/state_bucket sit at
      the top level. dev/test/prod are partitioned by the GCS PREFIX instead:
      terraform/state/<env>/<stack>.

The layout drives three things — the GCP project checked (gcp.check_project), the
state bucket, and the prefix — so all three stay consistent. Consumers ask this
module (project_for/bucket_for/expected_prefix); they never branch on layout
themselves."""

import logging
from pathlib import Path
from typing import Any

import ruamel.yaml

from tfs.errors import TFStackCLIInputError

log = logging.getLogger(__name__)

VALID_ENVS = ["dev", "test", "prod"]
TF_COMMANDS = ["init", "plan", "apply", "force-unlock", "output", "import"]

SINGLE_PROJECT = "single-project"
MULTI_PROJECT = "multi-project"
VALID_LAYOUTS = [SINGLE_PROJECT, MULTI_PROJECT]


def load_config(infra_root: Path) -> dict[str, Any]:
    yaml = ruamel.yaml.YAML()
    result: dict[str, Any] = yaml.load((infra_root / "config.yml").read_text())
    return result


def layout_of(config: dict[str, Any]) -> str:
    """The declared project layout. Raises if the `layout:` key is missing or not
    one of VALID_LAYOUTS — the mode selection is explicit, never inferred."""
    layout = config.get("layout")
    if layout not in VALID_LAYOUTS:
        raise TFStackCLIInputError(
            f"config.yml must declare `layout:` as one of {VALID_LAYOUTS}; got {layout!r}. "
            "Add e.g. `layout: multi-project` (project+bucket per env) or "
            "`layout: single-project` (one project+bucket, env in the state prefix)."
        )
    return str(layout)


def validate_config_shape(config: dict[str, Any]) -> None:
    """Assert config.yml's shape matches its declared layout, failing loudly on a
    mismatch (a half-single/half-multi config is a configuration bug, not a mode)."""
    layout = layout_of(config)
    envs = config.get("environments")
    if layout == SINGLE_PROJECT:
        if not isinstance(envs, list) or not envs:
            raise TFStackCLIInputError(
                "single-project layout requires `environments:` as a non-empty list of env names."
            )
        for key in ("project_id", "state_bucket"):
            if not isinstance(config.get(key), str):
                raise TFStackCLIInputError(f"single-project layout requires a top-level `{key}:` string.")
    else:  # MULTI_PROJECT
        if not isinstance(envs, dict) or not envs:
            raise TFStackCLIInputError(
                "multi-project layout requires `environments:` as a map of env -> {project_id, state_bucket}."
            )
        for env, cfg in envs.items():
            if (
                not isinstance(cfg, dict)
                or not isinstance(cfg.get("project_id"), str)
                or not isinstance(cfg.get("state_bucket"), str)
            ):
                raise TFStackCLIInputError(
                    f"multi-project env '{env}' needs both `project_id:` and `state_bucket:` strings."
                )


def environments_of(config: dict[str, Any]) -> list[str]:
    """The environment names, regardless of layout (map keys or list items)."""
    envs = config["environments"]
    return list(envs.keys()) if isinstance(envs, dict) else list(envs)


def project_for(config: dict[str, Any], environment: str) -> str:
    """The GCP project a given env deploys into: the shared one (single-project) or
    the env's own (multi-project)."""
    if layout_of(config) == SINGLE_PROJECT:
        return str(config["project_id"])
    return str(config["environments"][environment]["project_id"])


def bucket_for(config: dict[str, Any], environment: str) -> str:
    """The tfstate bucket a given env's state lives in: the shared one
    (single-project) or the env's own (multi-project)."""
    if layout_of(config) == SINGLE_PROJECT:
        return str(config["state_bucket"])
    return str(config["environments"][environment]["state_bucket"])


def expected_prefix(stack_name: str, environment: str, *, layout: str) -> str:
    """The GCS backend prefix a stack's state MUST live under. In single-project the
    environment is part of the prefix (that is what partitions dev/test/prod within
    the one shared bucket); in multi-project each env has its own bucket, so the
    prefix is per-stack only."""
    if layout == SINGLE_PROJECT:
        return f"terraform/state/{environment}/{stack_name}"
    return f"terraform/state/{stack_name}"


def list_stacks(infra_root: Path) -> list[str]:
    stacks_path = infra_root / "stacks"
    if not stacks_path.is_dir():
        return []
    return sorted(s.name for s in stacks_path.iterdir() if s.is_dir())
