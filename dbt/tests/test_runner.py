"""Runner tests against the real dbt project files. No mocks, no warehouse."""

import json
from pathlib import Path

import pytest

from dbt_service.config import Settings
from dbt_service.runner import (
    DbtRunner,
    build_run_result,
    list_models,
    models_from_manifest,
    parse_run_results,
    read_dbt_project,
    scan_models,
)

EXPECTED_MODELS = {
    "stg_fuel_receipts",
    "stg_maintenance",
    "fct_fuel_purchases",
    "fct_maintenance",
    "agg_vehicle_costs_yearly",
    "stg_consulting__engagements",
    "stg_consulting__time_entries",
    "stg_consulting__financials",
    "stg_consulting__deliverables",
    "stg_consulting__invoices",
    "dim_engagements",
    "fct_time_entries",
    "fct_engagement_financials",
    "fct_deliverables",
    "fct_invoices",
}


def test_read_dbt_project(project_dir: Path) -> None:
    config = read_dbt_project(project_dir)
    assert config["name"] == "agentic_webapp_dbt"
    assert config["profile"] == "agentic_webapp_dbt"


def test_read_dbt_project_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_dbt_project(tmp_path)


def test_scan_models_finds_all(project_dir: Path) -> None:
    models = scan_models(project_dir)
    assert {m.name for m in models} == EXPECTED_MODELS
    for model in models:
        assert model.db_schema == "agentic_webapp"
        assert model.description, f"{model.name} should have a description from schema.yml"
        assert model.resource_type == "model"


def test_scan_models_materialization(project_dir: Path) -> None:
    by_name = {m.name: m for m in scan_models(project_dir)}
    assert by_name["stg_fuel_receipts"].materialized == "view"
    assert by_name["stg_maintenance"].materialized == "view"
    assert by_name["fct_fuel_purchases"].materialized == "table"
    assert by_name["agg_vehicle_costs_yearly"].materialized == "table"


def test_scan_models_nested_domain_materialization(project_dir: Path) -> None:
    # Nested domains resolve materialization from the TOP-level dir (staging|marts),
    # not the immediate parent (consulting).
    by_name = {m.name: m for m in scan_models(project_dir)}
    assert by_name["stg_consulting__engagements"].materialized == "view"
    assert by_name["dim_engagements"].materialized == "table"
    assert by_name["fct_invoices"].materialized == "table"


def test_scan_models_dependencies(project_dir: Path) -> None:
    by_name = {m.name: m for m in scan_models(project_dir)}
    assert by_name["stg_fuel_receipts"].depends_on == ["raw.extractions"]
    assert by_name["fct_fuel_purchases"].depends_on == ["stg_fuel_receipts"]
    assert by_name["fct_maintenance"].depends_on == ["stg_maintenance"]
    assert by_name["agg_vehicle_costs_yearly"].depends_on == [
        "fct_fuel_purchases",
        "fct_maintenance",
    ]
    assert by_name["stg_consulting__invoices"].depends_on == ["consulting_raw.raw_invoices"]
    assert by_name["dim_engagements"].depends_on == ["stg_consulting__engagements"]


def test_scan_models_paths(project_dir: Path) -> None:
    by_name = {m.name: m for m in scan_models(project_dir)}
    assert by_name["stg_fuel_receipts"].path == "models/staging/stg_fuel_receipts.sql"
    assert by_name["fct_maintenance"].path == "models/marts/fct_maintenance.sql"


def test_list_models_falls_back_to_scan(project_dir: Path) -> None:
    # No target/manifest.json exists in the committed project, so this scans.
    assert {m.name for m in list_models(project_dir)} == EXPECTED_MODELS


def test_list_models_missing_project(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list_models(tmp_path)


def test_models_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "nodes": {
            "model.agentic_webapp_dbt.fct_fuel_purchases": {
                "resource_type": "model",
                "name": "fct_fuel_purchases",
                "schema": "agentic_webapp",
                "description": "Fuel facts.",
                "config": {"materialized": "table", "tags": ["mart"]},
                "depends_on": {"nodes": ["model.agentic_webapp_dbt.stg_fuel_receipts"]},
                "original_file_path": "models/marts/fct_fuel_purchases.sql",
            },
            "model.agentic_webapp_dbt.stg_fuel_receipts": {
                "resource_type": "model",
                "name": "stg_fuel_receipts",
                "schema": "agentic_webapp",
                "description": "Staged receipts.",
                "config": {"materialized": "view"},
                "depends_on": {"nodes": ["source.agentic_webapp_dbt.raw.extractions"]},
                "original_file_path": "models/staging/stg_fuel_receipts.sql",
            },
            "test.agentic_webapp_dbt.some_test": {"resource_type": "test"},
        }
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    models = models_from_manifest(path)
    assert [m.name for m in models] == ["fct_fuel_purchases", "stg_fuel_receipts"]
    fct = models[0]
    assert fct.materialized == "table"
    assert fct.tags == ["mart"]
    assert fct.depends_on == ["stg_fuel_receipts"]
    stg = models[1]
    assert stg.depends_on == ["raw.extractions"]


def test_list_models_prefers_manifest(project_dir: Path, tmp_path: Path) -> None:
    # Copy just dbt_project.yml + a manifest into a temp dir; manifest wins.
    (tmp_path / "dbt_project.yml").write_text(
        (project_dir / "dbt_project.yml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    target = tmp_path / "target"
    target.mkdir()
    manifest = {
        "nodes": {
            "model.agentic_webapp_dbt.only_model": {
                "resource_type": "model",
                "name": "only_model",
                "schema": "agentic_webapp",
                "config": {"materialized": "table"},
                "depends_on": {"nodes": []},
                "original_file_path": "models/marts/only_model.sql",
            }
        }
    }
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert [m.name for m in list_models(tmp_path)] == ["only_model"]


def test_parse_run_results(tmp_path: Path) -> None:
    run_results = {
        "results": [
            {
                "unique_id": "model.agentic_webapp_dbt.fct_fuel_purchases",
                "status": "success",
                "execution_time": 1.5,
                "message": "CREATE TABLE (10 rows)",
            }
        ]
    }
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(run_results), encoding="utf-8")
    nodes = parse_run_results(path)
    assert nodes == [
        {
            "name": "fct_fuel_purchases",
            "status": "success",
            "execution_time": 1.5,
            "message": "CREATE TABLE (10 rows)",
        }
    ]


def test_parse_run_results_missing(tmp_path: Path) -> None:
    assert parse_run_results(tmp_path / "nope.json") == []


def test_build_run_result_success(tmp_path: Path) -> None:
    result = build_run_result(
        command="run",
        return_code=0,
        stdout="done",
        stderr="",
        run_results_path=tmp_path / "absent.json",
        elapsed_seconds=2.0,
    )
    assert result.success is True
    assert result.command == "run"
    assert result.nodes == []


def test_build_run_result_failure(tmp_path: Path) -> None:
    result = build_run_result(
        command="test",
        return_code=1,
        stdout="",
        stderr="boom",
        run_results_path=tmp_path / "absent.json",
        elapsed_seconds=0.1,
    )
    assert result.success is False
    assert result.return_code == 1


def test_runner_project_info(project_dir: Path) -> None:
    runner = DbtRunner(Settings(dbt_project_dir=project_dir, dbt_target="test"))
    info = runner.project_info()
    assert info.name == "agentic_webapp_dbt"
    assert info.profile == "agentic_webapp_dbt"
    assert info.version == "1.0.0"
    assert info.target == "test"
    assert info.model_count == len(EXPECTED_MODELS)
    assert isinstance(info.dbt_cli_available, bool)
    assert {m.name for m in info.models} == EXPECTED_MODELS


def test_runner_list_models(project_dir: Path) -> None:
    runner = DbtRunner(Settings(dbt_project_dir=project_dir))
    assert {m.name for m in runner.list_models()} == EXPECTED_MODELS
