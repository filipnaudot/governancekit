"""
Audit log for the GovernanceKit web server.

Keeps the history of every trace that has ended: its model, the agents that
worked on it, its verdict, and every request they made (starting or ending the
trace, and checking, beginning or finishing activities), so it can later be
reviewed who did what and when.

While a trace runs, its history is kept on the trace itself (see traces.py);
TraceMonitors (see monitors.py) moves it here when the trace ends.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from governancekit.engine.decision import Decision
from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state

# Only imported for type hints, since traces imports from here
if TYPE_CHECKING:
    from governancekit.server.traces import Trace

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


@dataclass(frozen=True)
class TraceRecord:
    """
    The history of a trace that has ended.
    """

    trace_id: str
    model_id: str
    agent_ids: frozenset[str]  # The agents that were allowed to work on the trace
    started_at: datetime
    ended_at: datetime
    violations: list[str]  # The final verdict
    entries: list[AuditEntry]  # In recorded order


class AuditLog:
    """
    In-memory history of the traces that have ended.

    Thread-safe: requests are handled on several threads.
    """

    def __init__(self):
        self._records: dict[str, TraceRecord] = {}
        self._lock = threading.Lock()

    def add(self, trace: "Trace", ended_at: datetime, violations: list[str]) -> None:
        """Keep the history of a trace that has ended."""
        record = TraceRecord(
            trace_id=trace.trace_id,
            model_id=trace.model_id,
            agent_ids=frozenset(trace.agent_ids),
            started_at=trace.started_at,
            ended_at=ended_at,
            violations=violations,
            entries=list(trace.entries),
        )
        with self._lock:
            self._records[trace.trace_id] = record

    def get(self, trace_id: str) -> TraceRecord | None:
        """The ended trace's record, or None if no such trace has ended."""
        with self._lock:
            return self._records.get(trace_id)

    @property
    def records(self) -> list[TraceRecord]:
        """The records of all ended traces."""
        with self._lock:
            return list(self._records.values())


# ---------- Request / response schemas ----------


class AuditResponse(BaseModel):
    auditLog: list[AuditEntry]


# ---------- Endpoints ----------


@router.get("/audit")
def get_audit(state: Annotated[ServerState, Depends(get_state)]) -> AuditResponse:
    """
    Admin endpoint. The entries of all traces, running or ended, oldest first.
    """
    return AuditResponse(auditLog=state.server_monitors.all_entries())


@router.get("/traces/{trace_id}/audit")
def get_trace_audit(
    trace_id: str,
    state: Annotated[ServerState, Depends(get_state)],
) -> AuditResponse:
    """
    Admin endpoint. One trace's entries, while it runs and after it has ended.
    """
    entries = state.server_monitors.entries(trace_id)
    if entries is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace not found: {trace_id!r}")
    return AuditResponse(auditLog=entries)
