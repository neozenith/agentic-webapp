"""FastAPI app exposing the dbt project over HTTP (the backend's hard contract)."""

from functools import lru_cache

from fastapi import Depends, FastAPI

from .config import Settings
from .runner import DbtRunner
from .schemas import DbtModelInfo, DbtProjectInfo, DbtRunResult, HealthResponse, RunRequest


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, read once from the environment."""
    return Settings()


def get_runner(settings: Settings = Depends(get_settings)) -> DbtRunner:
    """A DbtRunner bound to the configured project directory."""
    return DbtRunner(settings)


def create_app() -> FastAPI:
    """Build the FastAPI application and wire up the routes."""
    app = FastAPI(title="dbt sidecar", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/project", response_model=DbtProjectInfo)
    def project(runner: DbtRunner = Depends(get_runner)) -> DbtProjectInfo:
        return runner.project_info()

    @app.get("/models", response_model=list[DbtModelInfo])
    def models(runner: DbtRunner = Depends(get_runner)) -> list[DbtModelInfo]:
        return runner.list_models()

    @app.post("/run", response_model=DbtRunResult)
    def run(body: RunRequest, runner: DbtRunner = Depends(get_runner)) -> DbtRunResult:
        return runner.run("run", body.select)

    @app.post("/test", response_model=DbtRunResult)
    def test(body: RunRequest, runner: DbtRunner = Depends(get_runner)) -> DbtRunResult:
        return runner.run("test", body.select)

    @app.post("/build", response_model=DbtRunResult)
    def build(body: RunRequest, runner: DbtRunner = Depends(get_runner)) -> DbtRunResult:
        return runner.run("build", body.select)

    @app.post("/compile", response_model=DbtRunResult)
    def compile_(body: RunRequest, runner: DbtRunner = Depends(get_runner)) -> DbtRunResult:
        return runner.run("compile", body.select)

    return app


app = create_app()
