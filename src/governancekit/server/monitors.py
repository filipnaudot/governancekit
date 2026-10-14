"""
Trace monitor endpoints for the GovernanceKit web server.

Admins list the engine's trace monitors, one per running trace, with what each
one keeps track of: the activities running on its trace and the constraints
that would be violated if the trace ended now. A monitor is keyed by its
trace's ID and is removed when the trace ends.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state
from governancekit.server.traces import RunningActivity

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])

# ---------- Request / response schemas ----------


class MonitorInfo(BaseModel):
    trace_id: str = Field(description="The monitored trace; also the monitor's ID")
    model_id: str
    agent_ids: list[str]
    started_at: datetime
    running: list[RunningActivity] = Field(description="Begun but not finished")
    violations: list[str] = Field(
        description="Constraints that would be violated if the trace ended now"
    )


class MonitorListResponse(BaseModel):
    monitors: list[MonitorInfo]


# ---------- Endpoints ----------


@router.get("/monitors")
def list_monitors(
    state: Annotated[ServerState, Depends(get_state)],
) -> MonitorListResponse:
    """Admin endpoint. The trace monitors of all running traces, newest first."""
    monitors = []
    # Copy the IDs, since traces may start or end while we read them
    for trace_id in list(state.registry.monitors):
        try:
            running = state.registry.unfinished(trace_id=trace_id)
            violations = state.registry.violations(trace_id=trace_id)
        except KeyError:
            continue  # The trace ended meanwhile
        record = state.audit.traces[trace_id]
        monitors.append(
            MonitorInfo(
                trace_id=trace_id,
                model_id=record.model_id,
                agent_ids=sorted(record.agent_ids),
                started_at=record.started_at,
                running=[
                    RunningActivity(
                        instance_id=instance_id,
                        activity=event.activity,
                        payload=event.payload,
                        timestamp=event.timestamp,
                    )
                    for instance_id, event in running.items()
                ],
                violations=violations,
            )
        )
    monitors.sort(key=lambda monitor: monitor.started_at, reverse=True)
    return MonitorListResponse(monitors=monitors)
