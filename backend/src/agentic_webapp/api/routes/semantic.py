"""Semantic-layer API over the SemanticManager — the logical data model and its query surface.

This is the top-down modelling endpoint: author SemanticModels (entities → dimensions +
measures) and run backend-agnostic SemanticQueries against them. Because the whole /api/*
surface auto-projects as MCP tools, ``semantic_query`` and ``semantic_models`` become tools
any agent can call — the "queryable semantic layer in our MCP" — with the same RBAC as REST.
Area-gated (``semantic``) in main.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from agentic_core.database import SemanticManager, SemanticQueryError
from agentic_core.models import SemanticEntity, SemanticModel, SemanticQuery, SemanticQueryResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_semantic_manager

router = APIRouter(prefix="/api/semantic", tags=["semantic"])

SemanticDep = Annotated[SemanticManager, Depends(get_semantic_manager)]


class SemanticModelUpsert(BaseModel):
    """Author/replace a semantic model. `model_id`/timestamps are server-authoritative."""

    name: str
    description: str = ""
    entities: list[SemanticEntity] = Field(default_factory=list)


class SemanticQueryRequest(BaseModel):
    """Ask a question of a model's logical entities."""

    model_id: str
    query: SemanticQuery


@router.get("/models", response_model=list[SemanticModel])
async def list_models(manager: SemanticDep) -> list[SemanticModel]:
    """All semantic models (the domain catalogue)."""
    return await manager.list_models()


@router.get("/models/{model_id}", response_model=SemanticModel)
async def get_model(model_id: str, manager: SemanticDep) -> SemanticModel:
    model = await manager.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="semantic model not found")
    return model


@router.post("/models", response_model=SemanticModel, status_code=201)
async def create_model(body: SemanticModelUpsert, manager: SemanticDep) -> SemanticModel:
    """Create a model. The id is minted server-side (never client-supplied)."""
    now = datetime.now(timezone.utc)
    model = SemanticModel(
        model_id=uuid4().hex, name=body.name, description=body.description,
        entities=body.entities, created_at=now, updated_at=now,
    )
    return await manager.create_model(model)


@router.put("/models/{model_id}", response_model=SemanticModel)
async def update_model(model_id: str, body: SemanticModelUpsert, manager: SemanticDep) -> SemanticModel:
    """Replace a model's definition, preserving its id and created_at."""
    existing = await manager.get_model(model_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="semantic model not found")
    updated = SemanticModel(
        model_id=model_id, name=body.name, description=body.description, entities=body.entities,
        created_at=existing.created_at, updated_at=datetime.now(timezone.utc),
    )
    return await manager.update_model(updated)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(model_id: str, manager: SemanticDep) -> None:
    await manager.delete_model(model_id)


@router.post("/query", response_model=SemanticQueryResult)
async def query(body: SemanticQueryRequest, manager: SemanticDep) -> SemanticQueryResult:
    """Run a SemanticQuery against a model — the agent/dashboard entry point. Returns the rows
    plus the compiled SQL. 404 for an unknown model; 400 for an invalid query (unknown
    entity/dimension/measure)."""
    model = await manager.get_model(body.model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="semantic model not found")
    try:
        return await manager.run_query(model, body.query)
    except SemanticQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
