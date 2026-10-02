"""
Audit log for the GovernanceKit web server.

Records every trace started or ended by an admin and every event an agent
checks or commits, so it can later be reviewed who did what and when.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Action(StrEnum):
    """
    What the audited request did.
    """

    START_TRACE = "start_trace"
    END_TRACE = "end_trace"
    CHECK = "check"
    COMMIT = "commit"


@dataclass(frozen=True)
class AuditEntry:
    """
    One audited request. Frozen, so an entry cannot be changed once recorded.
    """

    received_at: datetime                   # Set by the server
    agent_id: str                           # The agent working on the trace
    trace_id: str
    action: Action
    activity: str | None = None             # None for start/end trace
    event_timestamp: datetime | None = None  # What the agent sent; None for start/end trace
    allowed: bool | None = None             # Only set for check
    violations: list[str] = field(default_factory=list)  # For check and end trace


class AuditLog:
    """
    In-memory, append-only list of audit entries in the order they were recorded.
    """

    entries: list[AuditEntry]

    def __init__(self):
        self.entries = []

    def add_audit(self, audit: AuditEntry) -> None:
        self.entries.append(audit)
