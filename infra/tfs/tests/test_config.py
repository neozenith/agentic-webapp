"""Layout-aware config helpers (both project layouts) — pure functions, no IO."""

import pytest

from tfs.config import (
    acceptable_prefixes,
    bucket_for,
    environments_of,
    expected_prefix,
    layout_of,
    project_for,
    validate_config_shape,
)
from tfs.errors import TFStackCLIInputError

MULTI = {
    "layout": "multi-project",
    "environments": {
        "dev": {"project_id": "proj-dev", "state_bucket": "bkt-dev"},
        "prod": {"project_id": "proj-prod", "state_bucket": "bkt-prod"},
    },
}
SINGLE = {
    "layout": "single-project",
    "project_id": "shared-proj",
    "state_bucket": "shared-bkt",
    "environments": ["dev", "test", "prod"],
}


def test_layout_of_returns_declared_layout():
    assert layout_of(MULTI) == "multi-project"
    assert layout_of(SINGLE) == "single-project"


@pytest.mark.parametrize("bad", [{}, {"layout": "hybrid"}, {"layout": None}])
def test_layout_of_rejects_missing_or_unknown(bad):
    with pytest.raises(TFStackCLIInputError, match="layout"):
        layout_of(bad)


def test_environments_of_handles_both_shapes():
    assert environments_of(MULTI) == ["dev", "prod"]
    assert environments_of(SINGLE) == ["dev", "test", "prod"]


def test_project_for_resolves_per_layout():
    assert project_for(MULTI, "dev") == "proj-dev"
    assert project_for(MULTI, "prod") == "proj-prod"
    assert project_for(SINGLE, "dev") == "shared-proj"
    assert project_for(SINGLE, "prod") == "shared-proj"  # one project for every env


def test_bucket_for_resolves_per_layout():
    assert bucket_for(MULTI, "dev") == "bkt-dev"
    assert bucket_for(SINGLE, "dev") == "shared-bkt"
    assert bucket_for(SINGLE, "prod") == "shared-bkt"  # one bucket for every env


def test_expected_prefix_is_env_baked_for_both_layouts():
    # the canonical prefix no longer depends on layout — both collapse to env-baked
    assert expected_prefix("webapp", "dev") == "terraform/state/dev/webapp"
    assert expected_prefix("monitoring", "prod") == "terraform/state/prod/monitoring"


def test_acceptable_prefixes_multi_tolerates_legacy_single_does_not():
    # multi-project: canonical env-baked PLUS the legacy env-less form (safe — per-env bucket)
    multi = acceptable_prefixes("webapp", "dev", layout="multi-project")
    assert multi == ["terraform/state/dev/webapp", "terraform/state/webapp"]
    # single-project: canonical only — an env-less prefix would collide in the shared bucket
    single = acceptable_prefixes("webapp", "dev", layout="single-project")
    assert single == ["terraform/state/dev/webapp"]


def test_validate_config_shape_accepts_valid():
    validate_config_shape(MULTI)  # no raise
    validate_config_shape(SINGLE)  # no raise


@pytest.mark.parametrize(
    "bad",
    [
        {"layout": "multi-project", "environments": ["dev"]},  # list under multi
        {"layout": "multi-project", "environments": {"dev": {"project_id": "p"}}},  # missing state_bucket
        {"layout": "multi-project", "environments": {}},  # empty
        {
            "layout": "single-project",
            "project_id": "p",
            "state_bucket": "b",
            "environments": {"dev": {}},
        },  # dict under single
        {"layout": "single-project", "state_bucket": "b", "environments": ["dev"]},  # missing project_id
    ],
)
def test_validate_config_shape_rejects_mismatch(bad):
    with pytest.raises(TFStackCLIInputError):
        validate_config_shape(bad)
