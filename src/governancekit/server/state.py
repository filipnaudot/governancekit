"""
In-memory state shared by the GovernanceKit web server's routers.

Created once by create_app and lost when the server restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import Request

# Only imported for type hints, since the routers import get_state from here
if TYPE_CHECKING:
    from governancekit.engine.monitor_registry import MonitorRegistry
    from governancekit.server.agents import AgentRegistry
    from governancekit.server.audit import AuditLog
    from governancekit.server.auth import Authenticator
    from governancekit.server.monitors import TraceMonitors
    from governancekit.server.updates import FrontendTraceUpdates


@dataclass
class ServerState:
    auth: Authenticator
    agents: AgentRegistry
    # The engine: the models, and a monitor per running trace
    engine_monitor: MonitorRegistry
    # The history of the ended traces
    server_audit: AuditLog
    # The running traces; starts, works on and ends them
    server_monitors: TraceMonitors
    # Tells the frontend's update streams that a trace changed
    frontend_updates: FrontendTraceUpdates
    # model ID -> .decl text it was added with
    model_texts: dict[str, str] = field(default_factory=dict)


def get_state(request: Request) -> ServerState:
    return request.app.state.gk
