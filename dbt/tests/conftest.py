"""Shared fixtures: point the runner at the REAL dbt project in this repo."""

from pathlib import Path

import pytest

# dbt/tests/conftest.py -> parents[1] is the dbt project root (holds dbt_project.yml).
PROJECT_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def project_dir() -> Path:
    return PROJECT_DIR
