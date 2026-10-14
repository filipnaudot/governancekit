"""
Audit log for the GovernanceKit web server.

Keeps a record of every trace: its model, the agents working on it, and every
request they made (starting or ending the trace, and checking, beginning or
finishing activities), so it can later be reviewed who did what and when.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from governancekit.engine.decision import Decision
from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])


class Action(StrEnum):
    """
    What the audited request did.
    """

    START_TRACE = "start_trace"
    END_TRACE = "end_trace"
    CHECK = "check"
    BEGIN = "begin"
    FINISH = "finish"


class ActivityStatus(StrEnum):
    """
    How a running activity ended. Only completed activities affect the constraints.
    """

    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass(frozen=True)
class AuditEntry:
    """
    One audited request. Frozen, so an entry cannot be changed once recorded.
    """

    received_at: datetime  # Set by the server
    agent_id: str  # The agent that made the request
    trace_id: str
    action: Action
    activity: str | None = None  # None for start/end trace
    event_timestamp: datetime | None = (
        None  # What the agent sent; None for start/end trace
    )
    decision: Decision | None = None  # Only set for check and begin
    instance_id: str | None = None  # Set for an allowed begin, and for finish
    status: ActivityStatus | None = None  # Only set for finish
    violations: list[str] = field(default_factory=list)  # For check, begin and end trace


@dataclass
class TraceRecord:
    """
    What the server keeps about one trace: who works on it and what they did.

    Created when the trace starts and kept after it ends, unlike the trace's
    monitor, which is removed when the trace ends.
    """

    trace_id: str
    model_id: str
    agent_ids: set[str]  # The agents allowed to work on the trace
    started_at: datetime
    ended_at: datetime | None = None  # None while the trace is running
    entries: list[AuditEntry] = field(default_factory=list)  # In recorded order


class AuditLog:
    """
    In-memory record of every trace, running or ended.

    Attributes:
        traces: Records of all traces, keyed by trace ID.
    """

    traces: dict[str, TraceRecord]

    def __init__(self):
        self.traces = {}

    def start_trace(self, trace_id: str, model_id: str, agent_id: str) -> None:
        """Create the record of a new trace, with agent_id as its first agent."""
        self.traces[trace_id] = TraceRecord(
            trace_id=trace_id,
            model_id=model_id,
            agent_ids={agent_id},
            started_at=datetime.now(UTC),
        )

    def end_trace(self, trace_id: str) -> None:
        self.traces[trace_id].ended_at = datetime.now(UTC)

    def add_audit(self, audit: AuditEntry) -> None:
        """
        Raises:
            KeyError: If the entry's trace was never started.
        """
        self.traces[audit.trace_id].entries.append(audit)

    @property
    def entries(self) -> list[AuditEntry]:
        """All traces' entries, ordered by when they were received."""
        return sorted(
            (entry for trace in self.traces.values() for entry in trace.entries),
            key=lambda entry: entry.received_at,
        )


# ---------- Request / response schemas ----------


class AuditResponse(BaseModel):
    auditLog: list[AuditEntry]


# ---------- Endpoints ----------


@router.get("/audit")
def get_audit(state: Annotated[ServerState, Depends(get_state)]) -> AuditResponse:
    """
    Admin endpoint for checking the complete audit log currently recorded.
    """
    return AuditResponse(auditLog=state.audit.entries)


@router.get("/traces/{trace_id}/audit")
def get_trace_audit(
    trace_id: str,
    state: Annotated[ServerState, Depends(get_state)],
) -> AuditResponse:
    """
    Admin endpoint. Returns one trace's audit log, also after the trace has ended.
    """
    record = state.audit.traces.get(trace_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {trace_id!r}")
    return AuditResponse(auditLog=record.entries)
