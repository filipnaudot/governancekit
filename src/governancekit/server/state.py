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

"""
TODO Active traces should be kept in a new class (TraceRegistry). 
They should not be kept in the audit class, it is confusing. Auditlog should only 
manage the logs that have finished and the recording of such events. 

The new class should keep track of Traces, and for each trace trusted agents are allowed
to work on the trace without an admins approval. In traces.py, the server state is not updated
when an agent is added. 
"""
@dataclass
class ServerState:
    auth: Authenticator
    agents: AgentRegistry
    # The engine's monitors of running traces
    registry: MonitorRegistry
    # Records of all traces, running or ended: their agents and audit entries
    audit: AuditLog
    # model ID -> .decl text it was added with
    model_texts: dict[str, str] = field(default_factory=dict)


def get_state(request: Request) -> ServerState:
    return request.app.state.gk
