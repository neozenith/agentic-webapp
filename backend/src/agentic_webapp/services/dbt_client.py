"""DbtClient — the backend's window onto the dbt-core project.

Two real implementations on one interface (the same backend-axis pattern as DatabaseManager,
never a mock):

  - **FilesystemDbtClient** (local + tests): reads the on-disk ``dbt/`` project to list models
    offline, and shells out to the ``dbt`` CLI for run/test/build/compile when it is installed
    and a warehouse is configured. When the CLI is absent it returns an honest failure result —
    listing still works; execution is where the *sidecar* earns its keep.
  - **HttpDbtClient** (cloud + docker-compose): proxies to the dbt-core sidecar service over
    HTTP. The sidecar wraps the same dbt CLI against BigQuery (see ``dbt/`` at the repo root).

The backend picks one in deps.py: ``dbt_base_url`` set → HTTP; else filesystem.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
from agentic_core.models import DbtGantt, DbtInvocation, DbtModelInfo, DbtRunResult

_REF = re.compile(r"""ref\(\s*['"]([\w.]+)['"]""")
_SOURCE = re.compile(r"""source\(\s*['"]([\w.]+)['"]\s*,\s*['"]([\w.]+)['"]""")
_MATERIALIZED = re.compile(r"""materialized\s*=\s*['"](\w+)['"]""")


class DbtClient(ABC):
    """List the dbt project and run dbt commands. Async so the HTTP and CLI I/O don't block."""

    @abstractmethod
    async def project(self) -> dict[str, Any]:
        """Project metadata + its models (name, profile, target, models[])."""

    @abstractmethod
    async def list_models(self) -> list[DbtModelInfo]:
        """The models/seeds/sources in the project."""

    @abstractmethod
    async def run(self, *, select: str | None = None) -> DbtRunResult: ...

    @abstractmethod
    async def test(self, *, select: str | None = None) -> DbtRunResult: ...

    @abstractmethod
    async def build(self, *, select: str | None = None) -> DbtRunResult: ...

    @abstractmethod
    async def compile(self, *, select: str | None = None) -> DbtRunResult: ...

    @abstractmethod
    async def invocations(self, *, days: int = 30) -> list[DbtInvocation]:
        """Recent dbt runs from Elementary metadata (the observability overview)."""

    @abstractmethod
    async def gantt(self, invocation_id: str) -> DbtGantt:
        """One run's per-node execution timeline from Elementary `dbt_run_results`."""


class FilesystemDbtClient(DbtClient):
    def __init__(self, project_dir: Path, *, target: str | None = None) -> None:
        self._dir = Path(project_dir)
        self._target = target

    @property
    def available(self) -> bool:
        return self._dir.exists() and (self._dir / "dbt_project.yml").exists()

    async def project(self) -> dict[str, Any]:
        meta = self._project_meta()
        models = await self.list_models()
        return {
            **meta,
            "project_dir": str(self._dir),
            "dbt_cli_available": shutil.which("dbt") is not None,
            "model_count": len(models),
            "models": [m.model_dump() for m in models],
        }

    def _project_meta(self) -> dict[str, Any]:
        cfg = self._dir / "dbt_project.yml"
        text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        name = _first(re.search(r"""^\s*name:\s*['"]?([\w-]+)['"]?""", text, re.MULTILINE)) or "dbt_project"
        profile = _first(re.search(r"""^\s*profile:\s*['"]?([\w-]+)['"]?""", text, re.MULTILINE)) or name
        version = _first(re.search(r"""^\s*version:\s*['"]?([\w.]+)['"]?""", text, re.MULTILINE)) or "1.0.0"
        return {"name": name, "profile": profile, "version": version, "target": self._target or "dev"}

    async def list_models(self) -> list[DbtModelInfo]:
        models_dir = self._dir / "models"
        if not models_dir.exists():
            return []
        out: list[DbtModelInfo] = []
        for sql in sorted(models_dir.rglob("*.sql")):
            body = sql.read_text(encoding="utf-8")
            refs = sorted(set(_REF.findall(body)))
            sources = sorted({".".join(m) for m in _SOURCE.findall(body)})
            materialized = _first(_MATERIALIZED.search(body)) or _layer_default(sql, models_dir)
            out.append(DbtModelInfo(
                name=sql.stem,
                resource_type="model",
                db_schema=_layer(sql, models_dir),
                materialized=materialized,
                depends_on=refs + sources,
                tags=[_layer(sql, models_dir)],
                path=str(sql.relative_to(self._dir)),
            ))
        return out

    async def run(self, *, select: str | None = None) -> DbtRunResult:
        return await self._dbt("run", select)

    async def test(self, *, select: str | None = None) -> DbtRunResult:
        return await self._dbt("test", select)

    async def build(self, *, select: str | None = None) -> DbtRunResult:
        return await self._dbt("build", select)

    async def compile(self, *, select: str | None = None) -> DbtRunResult:
        return await self._dbt("compile", select)

    async def invocations(self, *, days: int = 30) -> list[DbtInvocation]:
        # Elementary metadata lives in the warehouse, populated by on-run-end in the cloud
        # sidecar — there is none to read from the local filesystem. Honest empty, not a fake.
        return []

    async def gantt(self, invocation_id: str) -> DbtGantt:
        return DbtGantt(invocation_id=invocation_id)

    async def _dbt(self, command: str, select: str | None) -> DbtRunResult:
        if shutil.which("dbt") is None:
            # Honest failure (NOT silent degradation): listing works offline, but executing dbt
            # needs the CLI + a warehouse — that is the sidecar's job in the deployed env.
            return DbtRunResult(
                command=command, success=False, return_code=127,
                stderr="dbt CLI not available in this environment; use the dbt sidecar (set DBT_BASE_URL).",
            )
        args = ["dbt", command, "--project-dir", str(self._dir), "--profiles-dir", str(self._dir)]
        if self._target:
            args += ["--target", self._target]
        if select:
            args += ["--select", select]
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        elapsed = time.monotonic() - started
        return DbtRunResult(
            command=command,
            success=proc.returncode == 0,
            return_code=proc.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            nodes=self._parse_run_results(),
            elapsed_seconds=round(elapsed, 3),
        )

    def _parse_run_results(self) -> list[dict[str, Any]]:
        results = self._dir / "target" / "run_results.json"
        if not results.exists():
            return []
        try:
            data = json.loads(results.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [
            {
                "name": r.get("unique_id", "").split(".")[-1],
                "status": r.get("status"),
                "execution_time": round(r.get("execution_time", 0.0), 3),
                "message": r.get("message"),
            }
            for r in data.get("results", [])
        ]


class HttpDbtClient(DbtClient):
    def __init__(self, base_url: str, *, timeout: float = 600.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    async def project(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base, timeout=30.0) as client:
            resp = await client.get("/project")
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def list_models(self) -> list[DbtModelInfo]:
        async with httpx.AsyncClient(base_url=self._base, timeout=30.0) as client:
            resp = await client.get("/models")
            resp.raise_for_status()
            return [DbtModelInfo.model_validate(m) for m in resp.json()]

    async def run(self, *, select: str | None = None) -> DbtRunResult:
        return await self._post("run", select)

    async def test(self, *, select: str | None = None) -> DbtRunResult:
        return await self._post("test", select)

    async def build(self, *, select: str | None = None) -> DbtRunResult:
        return await self._post("build", select)

    async def compile(self, *, select: str | None = None) -> DbtRunResult:
        return await self._post("compile", select)

    async def invocations(self, *, days: int = 30) -> list[DbtInvocation]:
        async with httpx.AsyncClient(base_url=self._base, timeout=30.0) as client:
            resp = await client.get("/observability/invocations", params={"days": days})
            resp.raise_for_status()
            return [DbtInvocation.model_validate(i) for i in resp.json()]

    async def gantt(self, invocation_id: str) -> DbtGantt:
        async with httpx.AsyncClient(base_url=self._base, timeout=30.0) as client:
            resp = await client.get(f"/observability/invocations/{invocation_id}")
            resp.raise_for_status()
            return DbtGantt.model_validate(resp.json())

    async def _post(self, command: str, select: str | None) -> DbtRunResult:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout) as client:
            resp = await client.post(f"/{command}", json={"select": select})
            resp.raise_for_status()
            return DbtRunResult.model_validate(resp.json())


def _first(match: re.Match[str] | None) -> str | None:
    return match.group(1) if match else None


def _layer(sql: Path, models_dir: Path) -> str:
    """The first sub-directory under models/ — the conventional dbt layer (staging/marts)."""
    rel = sql.relative_to(models_dir)
    return rel.parts[0] if len(rel.parts) > 1 else "models"


def _layer_default(sql: Path, models_dir: Path) -> str:
    """dbt's own default: staging → view, marts → table (mirrors our dbt_project.yml)."""
    return "table" if _layer(sql, models_dir) == "marts" else "view"
