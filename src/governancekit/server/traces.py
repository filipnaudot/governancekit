"""
Traces for the GovernanceKit web server, and the runtime endpoints agents use.

A Trace is a running trace: its model, the agents allowed to work on it, and
the history of what they did so far. RunningTraces keeps the running traces.
Both are managed by TraceMonitors (see monitors.py), which the endpoints call.

Agents start and end traces, and check, begin and finish activities on them.
Several activities may run at the same time on one trace. The agent that
starts a trace may work on it; admins can add more agents.
"""

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AwareDatetime, BaseModel, Field

from governancekit.engine.decision import Decision
from governancekit.engine.event_schema import InvalidEventError
from governancekit.engine.events import Event
from governancekit.server.audit import ActivityStatus, AuditEntry
from governancekit.server.auth import Principal, require_admin, require_agent
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["runtime"])


@dataclass
class Trace:
    """
    A running trace. Hold its lock while reading or changing it.
    """

    trace_id: str
    model_id: str
    agent_ids: set[str]  # The agents allowed to work on the trace
    started_at: datetime
    entries: list[AuditEntry] = field(default_factory=list)  # In recorded order
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class RunningTraces:
    """
    The running traces, kept in memory, keyed by trace ID.

    Thread-safe: requests are handled on several threads.
    """

    def __init__(self):
        self._traces: dict[str, Trace] = {}
        self._lock = threading.Lock()

    def add(self, trace: Trace) -> None:
        with self._lock:
            self._traces[trace.trace_id] = trace

    def remove(self, trace_id: str) -> Trace:
        """
        Raises:
            KeyError: If the trace is not running.
        """
        with self._lock:
            return self._traces.pop(trace_id)

    def get(self, trace_id: str) -> Trace | None:
        """The running trace, or None if it is not running."""
        with self._lock:
            return self._traces.get(trace_id)

    @property
    def traces(self) -> list[Trace]:
        """All running traces."""
        with self._lock:
            return list(self._traces.values())


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


class TraceSummary(BaseModel):
    trace_id: str
    model_id: str
    agent_ids: list[str]
    started_at: datetime
    ended_at: datetime | None = Field(description="None while the trace is running")
    violations: list[str] | None = Field(description="None while the trace is running")
    entry_count: int = Field(description="Number of entries in the trace's audit log")


class TraceListResponse(BaseModel):
    traces: list[TraceSummary]


class AddAgentRequest(BaseModel):
    agent_id: str


class TraceAgentsResponse(BaseModel):
    trace_id: str
    agent_ids: list[str]


# ---------- Endpoints ----------


def not_found(trace_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {trace_id!r}")


def invalid_event(error: InvalidEventError) -> HTTPException:
    # Not recorded in the trace's history: the engine raised before anything was recorded
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.problems)


def running_activity(instance_id: str, event: Event) -> RunningActivity:
    return RunningActivity(
        instance_id=instance_id,
        activity=event.activity,
        payload=event.payload,
        timestamp=event.timestamp,
    )


@router.post("/traces", status_code=status.HTTP_201_CREATED)
def start_trace(
    body: StartTraceRequest,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> TraceOut:
    """Start a trace on a model. The calling agent is its first agent."""
    try:
        trace_id = state.server_monitors.start_trace(
            model_id=body.model_id, agent_id=agent.id
        )
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown model: {e}") from e
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
    try:
        violations = state.server_monitors.end_trace(
            trace_id=trace_id, agent_id=agent.id, abort_running=abort_running
        )
    except KeyError as e:
        raise not_found(trace_id) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return EndTraceResponse(
        trace_id=trace_id, conformant=not violations, violations=violations
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
    event = Event(
        activity=body.activity, timestamp=body.timestamp, payload=body.payload
    )
    try:
        decision, blocking = state.server_monitors.check(
            trace_id=trace_id, agent_id=agent.id, event=event
        )
    except KeyError as e:
        raise not_found(trace_id) from e
    except InvalidEventError as e:
        raise invalid_event(e) from e
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
    event = Event(
        activity=body.activity, timestamp=body.timestamp, payload=body.payload
    )
    try:
        decision, instance_id, blocking = state.server_monitors.begin(
            trace_id=trace_id, agent_id=agent.id, event=event
        )
    except KeyError as e:
        raise not_found(trace_id) from e
    except InvalidEventError as e:
        raise invalid_event(e) from e
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
    try:
        state.server_monitors.finish(
            trace_id=trace_id,
            agent_id=agent.id,
            instance_id=instance_id,
            activity_status=body.status,
        )
    except KeyError as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Trace or activity not found: {e}"
        ) from e


@router.get("/traces/{trace_id}/activities")
def running_activities(
    trace_id: str,
    agent: Annotated[Principal, Depends(require_agent)],
    state: Annotated[ServerState, Depends(get_state)],
) -> RunningActivitiesResponse:
    """Activities that have begun but not finished on this trace."""
    try:
        running = state.server_monitors.unfinished(trace_id=trace_id, agent_id=agent.id)
    except KeyError as e:
        raise not_found(trace_id) from e
    return RunningActivitiesResponse(
        activities=[
            running_activity(instance_id, event)
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
    if body.agent_id not in state.agents.agents:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown agent: {body.agent_id!r}"
        )
    try:
        agent_ids = state.server_monitors.add_agent(
            trace_id=trace_id, agent_id=body.agent_id
        )
    except KeyError as e:
        raise not_found(trace_id) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return TraceAgentsResponse(trace_id=trace_id, agent_ids=sorted(agent_ids))


@router.get("/traces", tags=["management"], dependencies=[Depends(require_admin)])
def list_traces(
    state: Annotated[ServerState, Depends(get_state)],
    ended: bool | None = None,
) -> TraceListResponse:
    """Admin endpoint. All traces, newest first.

    ended=false gives only the running traces, ended=true only the ended ones.
    """
    # Keyed by trace ID: a trace that ends while we read is listed once, as ended
    summaries: dict[str, TraceSummary] = {}
    if ended is not True:
        for trace in state.server_monitors.running_traces.traces:
            with trace.lock:
                summaries[trace.trace_id] = TraceSummary(
                    trace_id=trace.trace_id,
                    model_id=trace.model_id,
                    agent_ids=sorted(trace.agent_ids),
                    started_at=trace.started_at,
                    ended_at=None,
                    violations=None,
                    entry_count=len(trace.entries),
                )
    if ended is not False:
        for record in state.server_audit.records:
            summaries[record.trace_id] = TraceSummary(
                trace_id=record.trace_id,
                model_id=record.model_id,
                agent_ids=sorted(record.agent_ids),
                started_at=record.started_at,
                ended_at=record.ended_at,
                violations=record.violations,
                entry_count=len(record.entries),
            )
    return TraceListResponse(
        traces=sorted(
            summaries.values(), key=lambda summary: summary.started_at, reverse=True
        )
    )
