"""Parse the dbt project and shell out to the dbt CLI.

Model listing prefers dbt's compiled manifest (target/manifest.json) for rich
metadata, and falls back to scanning the .sql + schema.yml files when no
manifest is present. A missing project directory is a hard error — never a
silent empty result.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from .config import Settings
from .schemas import DbtModelInfo, DbtProjectInfo, DbtRunResult

logger = logging.getLogger(__name__)

_REF_RE = re.compile(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)")
_SOURCE_RE = re.compile(r"source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)")
_MATERIALIZED_RE = re.compile(r"materialized\s*=\s*['\"]([^'\"]+)['\"]")

# Default materialization per model subdirectory (mirrors dbt_project.yml).
_DIR_MATERIALIZED = {"staging": "view", "marts": "table"}

_DEFAULT_DATASET = "agentic_webapp"


def _target_dataset() -> str:
    """The BigQuery dataset models land in, matching the profile's `dataset`."""
    return os.environ.get("BIGQUERY_DATASET", _DEFAULT_DATASET)


def read_dbt_project(project_dir: Path) -> dict[str, Any]:
    """Load and validate dbt_project.yml. Raises if the project is missing."""
    path = project_dir / "dbt_project.yml"
    if not path.exists():
        raise FileNotFoundError(f"dbt project not found (no dbt_project.yml at {path})")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid dbt_project.yml at {path}: expected a mapping")
    return data


def _load_schema_docs(project_dir: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Map model name -> description and model name -> tags from every schema.yml."""
    descriptions: dict[str, str] = {}
    tags: dict[str, list[str]] = {}
    for schema_file in sorted((project_dir / "models").rglob("schema.yml")):
        data = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for model in data.get("models", []) or []:
            name = model.get("name")
            if not name:
                continue
            descriptions[name] = (model.get("description") or "").strip()
            config = model.get("config") or {}
            tags[name] = list(config.get("tags") or [])
    return descriptions, tags


def scan_models(project_dir: Path) -> list[DbtModelInfo]:
    """Build the model list by scanning .sql files and schema.yml descriptions."""
    models_dir = project_dir / "models"
    if not models_dir.exists():
        raise FileNotFoundError(f"models directory not found at {models_dir}")
    descriptions, tags = _load_schema_docs(project_dir)
    dataset = _target_dataset()
    infos: list[DbtModelInfo] = []
    for sql_path in sorted(models_dir.rglob("*.sql")):
        sql = sql_path.read_text(encoding="utf-8")
        name = sql_path.stem
        refs = sorted(set(_REF_RE.findall(sql)))
        sources = sorted({f"{src}.{table}" for src, table in _SOURCE_RE.findall(sql)})
        materialized_match = _MATERIALIZED_RE.search(sql)
        if materialized_match:
            materialized = materialized_match.group(1)
        else:
            materialized = _DIR_MATERIALIZED.get(sql_path.parent.name, "view")
        infos.append(
            DbtModelInfo(
                name=name,
                db_schema=dataset,
                materialized=materialized,
                description=descriptions.get(name, ""),
                depends_on=sorted(sources + refs),
                tags=tags.get(name, []),
                path=sql_path.relative_to(project_dir).as_posix(),
            )
        )
    return infos


def models_from_manifest(manifest_path: Path) -> list[DbtModelInfo]:
    """Build the model list from dbt's compiled target/manifest.json."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes") or {}
    infos: list[DbtModelInfo] = []
    for key, node in nodes.items():
        if node.get("resource_type") != "model":
            continue
        config = node.get("config") or {}
        depends_on: list[str] = []
        for dep in (node.get("depends_on") or {}).get("nodes", []) or []:
            parts = dep.split(".")
            # "source.proj.raw.extractions" -> "raw.extractions"; "model.proj.x" -> "x".
            depends_on.append(".".join(parts[2:]) if dep.startswith("source.") else parts[-1])
        infos.append(
            DbtModelInfo(
                name=node.get("name") or key.split(".")[-1],
                db_schema=node.get("schema") or _target_dataset(),
                materialized=config.get("materialized") or "view",
                description=(node.get("description") or "").strip(),
                depends_on=sorted(depends_on),
                tags=list(config.get("tags") or []),
                path=node.get("original_file_path") or "",
            )
        )
    return sorted(infos, key=lambda info: info.name)


def list_models(project_dir: Path) -> list[DbtModelInfo]:
    """Prefer the compiled manifest; fall back to scanning source files."""
    if not (project_dir / "dbt_project.yml").exists():
        raise FileNotFoundError(f"dbt project not found (no dbt_project.yml at {project_dir})")
    manifest = project_dir / "target" / "manifest.json"
    if manifest.exists():
        models = models_from_manifest(manifest)
        if models:
            return models
        logger.warning("manifest at %s had no models; scanning source files instead", manifest)
    return scan_models(project_dir)


def parse_run_results(run_results_path: Path) -> list[dict[str, Any]]:
    """Extract per-node outcomes from dbt's target/run_results.json."""
    if not run_results_path.exists():
        return []
    data = json.loads(run_results_path.read_text(encoding="utf-8"))
    nodes: list[dict[str, Any]] = []
    for result in data.get("results") or []:
        nodes.append(
            {
                "name": (result.get("unique_id") or "").split(".")[-1],
                "status": result.get("status", ""),
                "execution_time": result.get("execution_time", 0.0),
                "message": result.get("message"),
            }
        )
    return nodes


def build_run_result(
    *,
    command: str,
    return_code: int,
    stdout: str,
    stderr: str,
    run_results_path: Path,
    elapsed_seconds: float,
) -> DbtRunResult:
    """Assemble a DbtRunResult from a completed dbt invocation."""
    return DbtRunResult(
        command=command,
        success=return_code == 0,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        nodes=parse_run_results(run_results_path),
        elapsed_seconds=elapsed_seconds,
    )


class DbtRunner:
    """Resolves and executes dbt operations against a single project directory."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.project_dir = Path(settings.dbt_project_dir)

    def project_info(self) -> DbtProjectInfo:
        """Project metadata plus the full model list."""
        config = read_dbt_project(self.project_dir)
        models = list_models(self.project_dir)
        return DbtProjectInfo(
            name=str(config.get("name", "")),
            profile=str(config.get("profile", "")),
            version=str(config.get("version", "")),
            target=self.settings.dbt_target,
            project_dir=str(self.project_dir),
            dbt_cli_available=shutil.which("dbt") is not None,
            model_count=len(models),
            models=models,
        )

    def list_models(self) -> list[DbtModelInfo]:
        """The project's models (manifest-preferred, scan fallback)."""
        return list_models(self.project_dir)

    def run(self, command: str, select: str | None = None) -> DbtRunResult:  # pragma: no cover
        """Shell out to `dbt <command>` against the project (needs a live warehouse)."""
        args = [
            "dbt",
            command,
            "--project-dir",
            str(self.project_dir),
            "--profiles-dir",
            str(self.project_dir),
            "--target",
            self.settings.dbt_target,
        ]
        if select:
            args += ["--select", select]
        start = time.monotonic()
        proc = subprocess.run(args, capture_output=True, text=True, cwd=str(self.project_dir), check=False)
        elapsed = time.monotonic() - start
        return build_run_result(
            command=command,
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            run_results_path=self.project_dir / "target" / "run_results.json",
            elapsed_seconds=elapsed,
        )
