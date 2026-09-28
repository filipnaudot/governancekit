"""
GovernanceKit web server.

Management endpoints: add/remove models, start/end traces.
Runtime endpoints: check and commit agent actions against a trace.
"""

"""
    TODO: When someone calls the server, how can we verify that the someone is a admin or just regular agent.

    TODO: Maybe the check and commit should be in the same request. No one should be able to be committing between a check and a commit.

    TODO: Should use Felix's manager class instead of the core functionality.
    """

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import AwareDatetime, BaseModel, Field

from core.events import Event
from core.monitor_registry import MonitorRegistry

# ---------- Request / response schemas ----------


class AddModelRequest(BaseModel):
    decl: str = Field(description="MP-DECLARE model as .decl text")


class AddModelResponse(BaseModel):
    model_id: str


class StartTraceRequest(BaseModel):
    model_id: str


class TraceOut(BaseModel):
    trace_id: str
    model_id: str


class EventRequest(BaseModel):
    activity: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Defaults to the server's current time",
    )


class CheckResponse(BaseModel):
    allowed: bool
    violations: list[str]


class EndTraceResponse(BaseModel):
    trace_id: str
    conformant: bool
    violations: list[str]


# ---------- App ----------


def create_app() -> FastAPI:
    app = FastAPI(title="GovernanceKit")

    # In-memory state: lost when the server restarts
    registry = MonitorRegistry()

    # --- Management ---

    @app.post("/models", status_code=status.HTTP_201_CREATED, tags=["management"])
    def add_model(body: AddModelRequest) -> AddModelResponse:
        """Register an MP-Declare model and return its generated ID."""
        model_id = str(uuid.uuid4())
        try:
            registry.add_model(model_id=model_id, model_text=body.decl)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Unable to add model: {e}"
            ) from e
        return AddModelResponse(model_id=model_id)

    @app.post("/traces", status_code=status.HTTP_201_CREATED, tags=["management"])
    def start_trace(body: StartTraceRequest) -> TraceOut:
        trace_id = str(uuid.uuid4())
        try:
            registry.start_monitor(model_id=body.model_id, trace_id=trace_id)
        except KeyError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown model: {e}") from e
        return TraceOut(trace_id=trace_id, model_id=body.model_id)

    @app.post("/traces/{trace_id}/end", tags=["management"])
    def end_trace(trace_id: str) -> EndTraceResponse:
        try:
            violations = registry.violations(trace_id=trace_id)
            registry.end_monitor(trace_id=trace_id)
        except KeyError as e:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {e}"
            ) from e
        return EndTraceResponse(
            trace_id=trace_id,
            conformant=not violations,
            violations=violations,
        )

    # --- Runtime ---

    @app.post("/traces/{trace_id}/check", tags=["runtime"])
    def check(trace_id: str, body: EventRequest) -> CheckResponse:
        event = Event(
            activity=body.activity, timestamp=body.timestamp, payload=body.payload
        )
        try:
            allowed, violations = registry.check_event(trace_id=trace_id, event=event)
        except KeyError as e:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {e}"
            ) from e
        return CheckResponse(allowed=allowed, violations=violations)

    @app.post(
        "/traces/{trace_id}/commit",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["runtime"],
    )
    def commit(trace_id: str, body: EventRequest) -> None:
        event = Event(
            activity=body.activity, timestamp=body.timestamp, payload=body.payload
        )
        try:
            registry.commit_event(trace_id=trace_id, event=event)
        except KeyError as e:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {e}"
            ) from e

    return app


app = create_app()
