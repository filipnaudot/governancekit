"""
Audit log for the GovernanceKit web server.

Records every trace started or ended by an agent and every activity an agent
checks, begins or finishes, so it can later be reviewed who did what and when.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends
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
    agent_id: str  # The agent working on the trace
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


class AuditLog:
    """
    In-memory, append-only list of audit entries in the order they were recorded.
    """

    entries: list[AuditEntry]

    def __init__(self):
        self.entries = []

    def add_audit(self, audit: AuditEntry) -> None:
        self.entries.append(audit)


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
