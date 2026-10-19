"""
Model management endpoints for the GovernanceKit web server.

Admins add MP-Declare models as .decl text, list them and read them back.
Agents start traces on these models.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])

# ---------- Request / response schemas ----------


class AddModelRequest(BaseModel):
    decl: str = Field(description="MP-DECLARE model as .decl text")
    validate_payloads: bool = Field(
        default=False,
        description="Reject events with an undeclared activity, a missing bound"
        " attribute or a value outside its domain (422)",
    )


class AddModelResponse(BaseModel):
    model_id: str


class ModelInfo(BaseModel):
    model_id: str
    constraint_count: int
    validate_payloads: bool


class ModelListResponse(BaseModel):
    models: list[ModelInfo]


class ModelResponse(BaseModel):
    model_id: str
    decl: str = Field(description="The model's .decl text, as it was added")


# ---------- Endpoints ----------


@router.post("/models", status_code=status.HTTP_201_CREATED)
def add_model(
    body: AddModelRequest,
    state: Annotated[ServerState, Depends(get_state)],
) -> AddModelResponse:
    """Register an MP-Declare model and return its generated ID."""
    model_id = str(uuid.uuid4())
    try:
        state.engine_monitor.add_model(
            model_id=model_id,
            model_text=body.decl,
            validate_payloads=body.validate_payloads,
        )
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unable to add model: {e}"
        ) from e
    """TODO Perhaps implement something of our own that can be used with the regristry parsed model instead of the delcare text."""
    state.model_texts[model_id] = body.decl
    return AddModelResponse(model_id=model_id)


@router.get("/models")
def list_models(state: Annotated[ServerState, Depends(get_state)]) -> ModelListResponse:
    """Admin endpoint. Returns the known models."""
    return ModelListResponse(
        models=[
            ModelInfo(
                model_id=model_id,
                constraint_count=len(model.constraints),
                validate_payloads=model.schema is not None,
            )
            for model_id, model in state.engine_monitor.models.items()
        ]
    )


@router.get("/models/{model_id}")
def get_model(
    model_id: str,
    state: Annotated[ServerState, Depends(get_state)],
) -> ModelResponse:
    """Admin endpoint. Returns a model's .decl text."""
    if model_id not in state.model_texts:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown model: {model_id!r}")
    return ModelResponse(model_id=model_id, decl=state.model_texts[model_id])
