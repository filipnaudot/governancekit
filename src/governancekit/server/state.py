"""
In-memory state shared by the GovernanceKit web server's routers.

Created once by create_app and lost when the server restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import Request

# Only imported for type hints, since auth and audit import get_state from here
if TYPE_CHECKING:
    from governancekit.engine.monitor_registry import MonitorRegistry
    from governancekit.server.audit import AuditLog
    from governancekit.server.auth import Authenticator


@dataclass
class ServerState:
    auth: Authenticator
    registry: MonitorRegistry
    # Server logs trace starts/ends, and checked, begun and finished activities
    audit: AuditLog
    # trace ID -> ID of the agent working on it
    trace_agents: dict[str, str] = field(default_factory=dict)
    # model ID -> .decl text it was added with
    model_texts: dict[str, str] = field(default_factory=dict)


def get_state(request: Request) -> ServerState:
    return request.app.state.gk
