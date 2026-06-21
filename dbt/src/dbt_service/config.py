"""Runtime configuration for the dbt sidecar, sourced from environment variables."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default to the dbt project root: this file is src/dbt_service/config.py, so
# parents[2] is the directory that holds dbt_project.yml. The Dockerfile sets
# DBT_PROJECT_DIR=/app explicitly, which overrides this.
_DEFAULT_PROJECT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Sidecar settings. Field names map case-insensitively to env vars."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dbt_project_dir: Path = _DEFAULT_PROJECT_DIR
    dbt_target: str = "dev"
    port: int = 8082

    # BigQuery coordinates for the observability endpoints. gcp_project mirrors
    # GCP_PROJECT; bigquery_dataset mirrors BIGQUERY_DATASET (same defaults as the
    # dbt profile). elementary_dataset defaults to <bigquery_dataset>_elementary —
    # the dataset Elementary writes its artifact tables into.
    gcp_project: str = ""
    bigquery_dataset: str = "agentic_webapp"
    elementary_dataset: str = ""

    @model_validator(mode="after")
    def _default_elementary_dataset(self) -> "Settings":
        """Derive elementary_dataset from bigquery_dataset unless set explicitly."""
        if not self.elementary_dataset:
            self.elementary_dataset = f"{self.bigquery_dataset}_elementary"
        return self
