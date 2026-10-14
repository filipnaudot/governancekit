"""
Runtime endpoints for the GovernanceKit web server.

Agents start and end traces, and check, begin and finish activities on them.
Several activities may run at the same time on one trace. The agent that
starts a trace may work on it; admins can add more agents. Every request is
recorded in the audit log.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AwareDatetime, BaseModel, Field

from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.server.audit import Action, ActivityStatus, AuditEntry
from governancekit.server.auth import Principal, require_admin, require_agent
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["runtime"])

# ---------- Request / response schemas ----------


class StartTraceRequest(BaseModel):
    model_id: str


class TraceOut(BaseModel):
    trace_id: str
    model_id: str
    agent_id: str


class EventRequest(BaseModel):
    activity: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Defaults to the server's current time",
    )


class CheckResponse(BaseModel):
    decision: Decision
    blocking: list[str] = Field(description="Constraints that don't allow it")


class BeginResponse(BaseModel):
    decision: Decision
    instance_id: str | None = Field(
        description="Only set if allowed; needed to finish the activity"
    )
    blocking: list[str] = Field(description="Constraints that don't allow it")


class FinishRequest(BaseModel):
    status: ActivityStatus


class RunningActivity(BaseModel):
    instance_id: str
    activity: str
    payload: dict[str, Any]
    timestamp: datetime = Field(description="When the activity began")


class RunningActivitiesResponse(BaseModel):
    activities: list[RunningActivity]


class EndTraceResponse(BaseModel):
    trace_id: str
    conformant: bool
    violations: list[str]


class AddAgentRequest(BaseModel):
    agent_id: str


class TraceAgentsResponse(BaseModel):
    trace_id: str
    agent_ids: list[str]


# ---------- Helpers ----------


def check_trace_access(state: ServerState, trace_id: str, agent: Principal) -> None:
    """Allow only the agents added to a running trace."""
    record = state.audit.traces.get(trace_id)
    # A trace the agent is not on is reported as missing, so its ID is not revealed
    if record is None or record.ended_at is not None or agent.id not in record.agent_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {trace_id!r}")


# ---------- Endpoints ----------


@router.post("/traces", status_code=status.HTTP_201_CREATED)
def start_trace(
    body: StartTraceRequest,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> TraceOut:
    """Start a trace on a model. The calling agent is its first agent."""

    # Generate the trace ID
    trace_id = str(uuid.uuid4())

    # Start the monitoring of a trace.
    try:
        state.registry.start_monitor(model_id=body.model_id, trace_id=trace_id)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown model: {e}") from e

    # Update server state, and add a audit to the audit log.
    state.audit.start_trace(trace_id=trace_id, model_id=body.model_id, agent_id=agent.id)

    # Log start trace as an action in audit log.
    state.audit.add_audit(
        # Create the entry
        AuditEntry(
            received_at=datetime.now(UTC),
            agent_id=agent.id,
            trace_id=trace_id,
            action=Action.START_TRACE,
        )
    )
    return TraceOut(trace_id=trace_id, model_id=body.model_id, agent_id=agent.id)


@router.post("/traces/{trace_id}/end")
def end_trace(
    trace_id: str,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
    abort_running: bool = False,
) -> EndTraceResponse:
    """End a trace the calling agent is on and return the final verdict.

    If activities are still running, the request is rejected with 409,
    unless abort_running is true; then they are aborted first.
    """
    check_trace_access(state, trace_id, agent)
    try:
        violations = state.registry.violations(trace_id=trace_id)
        aborted = state.registry.end_monitor(
            trace_id=trace_id, abort_running=abort_running
        )
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {e}") from e
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e

    for instance_id, event in aborted.items():
        state.audit.add_audit(
            AuditEntry(
                received_at=datetime.now(UTC),
                agent_id=agent.id,
                trace_id=trace_id,
                action=Action.FINISH,
                activity=event.activity,
                event_timestamp=event.timestamp,
                instance_id=instance_id,
                status=ActivityStatus.ABORTED,
            )
        )

    # Log an End trace.
    state.audit.add_audit(
        AuditEntry(
            received_at=datetime.now(UTC),
            agent_id=agent.id,
            trace_id=trace_id,
            action=Action.END_TRACE,
            violations=violations,
        )
    )
    # Update the state to end trace.
    state.audit.end_trace(trace_id)

    return EndTraceResponse(
        trace_id=trace_id,
        conformant=not violations,
        violations=violations,
    )


@router.post("/traces/{trace_id}/check")
def check(
    trace_id: str,
    body: EventRequest,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> CheckResponse:
    """Ask whether an activity may begin now, without reserving it.

    The answer can be outdated by the time the agent acts; begin the
    activity before performing it.
    """
    check_trace_access(state, trace_id, agent)
    event = Event(activity=body.activity, timestamp=body.timestamp, payload=body.payload)
    try:
        decision, blocking = state.registry.check_event(trace_id=trace_id, event=event)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {e}") from e

    state.audit.add_audit(
        AuditEntry(
            received_at=datetime.now(UTC),
            agent_id=agent.id,
            trace_id=trace_id,
            action=Action.CHECK,
            activity=body.activity,
            event_timestamp=body.timestamp,
            decision=decision,
            violations=blocking,
        )
    )
    return CheckResponse(decision=decision, blocking=blocking)


@router.post("/traces/{trace_id}/activities")
def begin(
    trace_id: str,
    body: EventRequest,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> BeginResponse:
    """Ask to begin an activity, and reserve it if allowed.

    allowed: perform it, then finish it with the returned instance_id.
    wait: not now, ask again later. denied: don't perform it.
    """
    check_trace_access(state, trace_id, agent)
    event = Event(activity=body.activity, timestamp=body.timestamp, payload=body.payload)
    try:
        decision, instance_id, blocking = state.registry.begin_event(
            trace_id=trace_id, event=event
        )
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {e}") from e

    state.audit.add_audit(
        AuditEntry(
            received_at=datetime.now(UTC),
            agent_id=agent.id,
            trace_id=trace_id,
            action=Action.BEGIN,
            activity=body.activity,
            event_timestamp=body.timestamp,
            decision=decision,
            instance_id=instance_id,
            violations=blocking,
        )
    )
    return BeginResponse(decision=decision, instance_id=instance_id, blocking=blocking)


@router.post(
    "/traces/{trace_id}/activities/{instance_id}/finish",
    status_code=status.HTTP_204_NO_CONTENT,
)
def finish(
    trace_id: str,
    instance_id: str,
    body: FinishRequest,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> None:
    """Report how a running activity ended. Only completed ones count."""
    check_trace_access(state, trace_id, agent)
    try:
        event = state.registry.finish_event(
            trace_id=trace_id,
            instance_id=instance_id,
            completed=body.status is ActivityStatus.COMPLETED,
        )
    except KeyError as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Trace or activity not found: {e}"
        ) from e

    state.audit.add_audit(
        AuditEntry(
            received_at=datetime.now(UTC),
            agent_id=agent.id,
            trace_id=trace_id,
            action=Action.FINISH,
            activity=event.activity,
            event_timestamp=event.timestamp,
            instance_id=instance_id,
            status=body.status,
        )
    )


@router.get("/traces/{trace_id}/activities")
def running_activities(
    trace_id: str,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> RunningActivitiesResponse:
    """Activities that have begun but not finished on this trace."""
    check_trace_access(state, trace_id, agent)
    try:
        running = state.registry.unfinished(trace_id=trace_id)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {e}") from e
    return RunningActivitiesResponse(
        activities=[
            RunningActivity(
                instance_id=instance_id,
                activity=event.activity,
                payload=event.payload,
                timestamp=event.timestamp,
            )
            for instance_id, event in running.items()
        ]
    )


@router.post(
    "/traces/{trace_id}/agents",
    tags=["management"],
    dependencies=[Depends(require_admin)],
)
def add_agent(
    trace_id: str,
    body: AddAgentRequest,
    state: Annotated[ServerState, Depends(get_state)],
) -> TraceAgentsResponse:
    """Admin endpoint. Let another agent work on a running trace."""
    record = state.audit.traces.get(trace_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {trace_id!r}")
    if record.ended_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Trace has ended: {trace_id!r}")
    if body.agent_id not in state.agents.agents:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown agent: {body.agent_id!r}"
        )
    record.agent_ids.add(body.agent_id)
    return TraceAgentsResponse(trace_id=trace_id, agent_ids=sorted(record.agent_ids))
