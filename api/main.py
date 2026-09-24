"""
GovernanceKit web server.

Management endpoints: add/remove models, start/end traces.
Runtime endpoints: check and commit agent actions against a trace.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from core.decl_parser import parse_decl_text
from core.events import Event
from core.mp_declare_model import ConstraintDef, MPDeclareModel
from core.trace_monitor import Decision, TraceMonitor, Violation


# ---------- Request / response schemas ----------


class AddModelRequest(BaseModel):
    decl: str = Field(description="MP-DECLARE model as .decl text")


class ConstraintOut(BaseModel):
    id: str
    template: str
    activation_activity: str
    target_activity: str | None
    count: int | None


class ModelOut(BaseModel):
    model_id: str
    constraints: list[ConstraintOut]


class StartTraceRequest(BaseModel):
    model_id: str


class TraceOut(BaseModel):
    trace_id: str
    model_id: str


class EventIn(BaseModel):
    activity: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = Field(
        default=None, description="Defaults to the server's current time"
    )

    def to_event(self) -> Event:
        return Event(
            activity=self.activity,
            timestamp=self.timestamp or datetime.now(UTC),
            payload=self.payload,
        )


class ViolationOut(BaseModel):
    constraint_id: str


class DecisionOut(BaseModel):
    allowed: bool
    violations: list[ViolationOut]


class EndTraceOut(BaseModel):
    trace_id: str
    conformant: bool
    violations: list[ViolationOut]


# ---------- Conversions from core objects ----------


def _constraint_out(c: ConstraintDef) -> ConstraintOut:
    return ConstraintOut(
        id=c.id,
        template=c.template.value,
        activation_activity=c.activation_activity,
        target_activity=c.target_activity,
        count=c.count,
    )


def _violations_out(violations: tuple[Violation, ...] | list[Violation]):
    return [ViolationOut(constraint_id=v.constraint_id) for v in violations]


def _decision_out(decision: Decision) -> DecisionOut:
    return DecisionOut(
        allowed=decision.allowed, violations=_violations_out(decision.violations)
    )


# ---------- App ----------


def create_app() -> FastAPI:
    app = FastAPI(title="GovernanceKit")

    # In-memory state: lost when the server restarts
    models: dict[str, MPDeclareModel] = {}
    traces: dict[str, tuple[str, TraceMonitor]] = {}

    def get_model(model_id: str) -> MPDeclareModel:
        if model_id not in models:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown model {model_id!r}")
        return models[model_id]

    def get_monitor(trace_id: str) -> TraceMonitor:
        if trace_id not in traces:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown trace {trace_id!r}")
        return traces[trace_id][1]

    # --- Management ---

    @app.post("/models", status_code=status.HTTP_201_CREATED, tags=["management"])
    def add_model(body: AddModelRequest) -> ModelOut:
        """
        Endpoint for adding models to the server. Generates model_id and returns it to agent.
        """
        try:
            definitions = parse_decl_text(body.decl)
        except Exception as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"invalid .decl model: {e}"
            ) from e

        model_id = str(uuid.uuid4())

        # Track the declare models in memory.
        models[model_id] = MPDeclareModel.build(definitions)
        return ModelOut(
            model_id=model_id, constraints=[_constraint_out(d) for d in definitions]
        )

    @app.delete("/models/{model_id}",
                status_code=status.HTTP_204_NO_CONTENT,
                tags=["management"],)
    def remove_model(model_id: str) -> None:
        # Traces already started on this model keep working until they end
        get_model(model_id)
        del models[model_id]

    @app.post("/traces", status_code=status.HTTP_201_CREATED, tags=["management"])
    def start_trace(body: StartTraceRequest) -> TraceOut:
        model = get_model(body.model_id)
        trace_id = str(uuid.uuid4())
        traces[trace_id] = (body.model_id, TraceMonitor(model))
        return TraceOut(trace_id=trace_id, model_id=body.model_id)

    @app.post("/traces/{trace_id}/end", tags=["management"])
    def end_trace(trace_id: str) -> EndTraceOut:
        monitor = get_monitor(trace_id)
        violations = monitor.analyze()
        del traces[trace_id]
        return EndTraceOut(
            trace_id=trace_id,
            conformant=not violations,
            violations=_violations_out(violations),
        )

    # --- Runtime ---

    @app.post("/traces/{trace_id}/check", tags=["runtime"])
    def check(trace_id: str, body: EventIn) -> DecisionOut:
        return _decision_out(get_monitor(trace_id).check(body.to_event()))

    @app.post(
        "/traces/{trace_id}/commit",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["runtime"],
    )
    def commit(trace_id: str, body: EventIn) -> None:
        get_monitor(trace_id).commit(body.to_event())

    return app


app = create_app()
