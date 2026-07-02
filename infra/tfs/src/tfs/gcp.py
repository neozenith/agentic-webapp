"""GCP guardrail — proves the active gcloud credentials can see the target
project before any state-touching terraform call.

The project to check is resolved from config.yml via config.project_for, so the
guardrail is correct in BOTH layouts: single-project checks the one shared project
for every env; multi-project checks the env's own project (e.g. dbt-<env>-jaffleshop
in this repo, which deliberately reuses the sibling dbt projects)."""

import logging
import subprocess
from pathlib import Path

from tfs.config import load_config, project_for
from tfs.errors import TFStackGCPConfigurationError

log = logging.getLogger(__name__)


def check_project(environment: str, infra_root: Path) -> None:
    """Prove you're authenticated against the env's GCP project (resolved from
    config.yml + its layout). Hard failure (no silent skip): if gcloud can't
    describe the project, stop."""
    project_id = project_for(load_config(infra_root), environment)
    try:
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id, "--format=value(projectId)"],
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise TFStackGCPConfigurationError("gcloud CLI not found on PATH — install the Google Cloud SDK") from e
    except subprocess.CalledProcessError as e:
        raise TFStackGCPConfigurationError(
            f"Cannot access project '{project_id}' with the active gcloud credentials.\n"
            f"  Authenticate first (e.g. `gcloud auth login` / ADC impersonation), then retry.\n"
            f"  gcloud said: {e.stderr.strip()}"
        ) from e
    log.debug("gcloud sees project: %s", result.stdout.strip())
