"""
Trace monitoring for the GovernanceKit web server.

TraceMonitors is the one place traces are started, worked on and ended. For
every request it checks that the agent may work on the trace, asks the
engine's trace monitor, and records the request in the trace's history. When
the trace ends, its history is moved to the audit log. After every change it
tells the frontend's update streams.

Admins list the trace monitors, one per running trace, with what each one
keeps track of: the activities running on its trace and the constraints that
would be violated if the trace ended now.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.monitor_registry import MonitorRegistry
from governancekit.server.audit import Action, ActivityStatus, AuditEntry, AuditLog
from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state
from governancekit.server.traces import (
    RunningActivity,
    RunningTraces,
    Trace,
    running_activity,
)
from governancekit.server.updates import FrontendTraceUpdates

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])


class TraceMonitors:
    """
    Wrapper for the engine.

    Monitors the running traces and records everything agents do on them.

    Requests on one trace run one at a time, under the trace's lock, so its
    history is in the order the engine handled them. Different traces don't
    wait for each other.

    Attributes:
        engine_monitor: The engine, with the models and a monitor per running trace.
        audit: Where the history of a trace is kept once it has ended.
        updates: Told after every change, once the trace's lock is released.
        running_traces: The traces that have started and not yet ended.
    """

    def __init__(
        self, engine_monitor: MonitorRegistry, audit: AuditLog, updates: FrontendTraceUpdates
    ):
        self.engine_monitor = engine_monitor
        self.audit = audit
        self.updates = updates
        self.running_traces = RunningTraces()

    def start_trace(self, model_id: str, agent_id: str) -> str:
        """
        Start a trace on a model, with agent_id as its first agent.

        Returns:
            The new trace's ID.

        Raises:
            KeyError: If the model is not registered.
        """
        trace_id = str(uuid.uuid4())
        self.engine_monitor.start_monitor(model_id=model_id, trace_id=trace_id)
        trace = Trace(
            trace_id=trace_id,
            model_id=model_id,
            agent_ids={agent_id},
            started_at=datetime.now(UTC),
        )
        self._record(trace, agent_id, Action.START_TRACE)
        self.running_traces.add(trace)
        self.updates.notify()
        return trace_id

    def end_trace(self, trace_id: str, agent_id: str, abort_running: bool) -> list[str]:
        """
        End a trace and move its history to the audit log.

        Returns:
            The constraints the trace violated.

        Raises:
            KeyError: If agent_id may not work on the trace.
            ValueError: If activities are still running and abort_running is False.
        """
        with self._working_on(trace_id, agent_id) as trace:
            violations = self.engine_monitor.violations(trace_id=trace_id)
            aborted = self.engine_monitor.end_monitor(
                trace_id=trace_id, abort_running=abort_running
            )
            for instance_id, event in aborted.items():
                self._record(
                    trace,
                    agent_id,
                    Action.FINISH,
                    activity=event.activity,
                    event_timestamp=event.timestamp,
                    instance_id=instance_id,
                    status=ActivityStatus.ABORTED,
                )
            self._record(trace, agent_id, Action.END_TRACE, violations=violations)
            # Into the audit log before leaving the running traces, so the
            # trace is always found in one of them
            self.audit.add(trace, ended_at=datetime.now(UTC), violations=violations)
            self.running_traces.remove(trace_id)
        self.updates.notify()
        return violations

    def check(
        self, trace_id: str, agent_id: str, event: Event
    ) -> tuple[Decision, list[str]]:
        """
        Whether an activity may begin now, and the constraints that don't allow it.

        Raises:
            KeyError: If agent_id may not work on the trace.
        """
        with self._working_on(trace_id, agent_id) as trace:
            decision, blocking = self.engine_monitor.check_event(
                trace_id=trace_id, event=event
            )
            self._record(
                trace,
                agent_id,
                Action.CHECK,
                activity=event.activity,
                event_timestamp=event.timestamp,
                decision=decision,
                violations=blocking,
            )
        self.updates.notify()
        return decision, blocking

    def begin(
        self, trace_id: str, agent_id: str, event: Event
    ) -> tuple[Decision, str | None, list[str]]:
        """
        Begin an activity if allowed.

        Returns:
            The decision, the instance ID (only if allowed) and the constraints
            that don't allow it.

        Raises:
            KeyError: If agent_id may not work on the trace.
        """
        with self._working_on(trace_id, agent_id) as trace:
            decision, instance_id, blocking = self.engine_monitor.begin_event(
                trace_id=trace_id, event=event
            )
            self._record(
                trace,
                agent_id,
                Action.BEGIN,
                activity=event.activity,
                event_timestamp=event.timestamp,
                decision=decision,
                instance_id=instance_id,
                violations=blocking,
            )
        self.updates.notify()
        return decision, instance_id, blocking

    def finish(
        self,
        trace_id: str,
        agent_id: str,
        instance_id: str,
        activity_status: ActivityStatus,
    ) -> None:
        """
        Finish a running activity. Only completed ones affect the constraints.

        Raises:
            KeyError: If agent_id may not work on the trace, or the activity
                is not running.
        """
        with self._working_on(trace_id, agent_id) as trace:
            event = self.engine_monitor.finish_event(
                trace_id=trace_id,
                instance_id=instance_id,
                completed=activity_status is ActivityStatus.COMPLETED,
            )
            self._record(
                trace,
                agent_id,
                Action.FINISH,
                activity=event.activity,
                event_timestamp=event.timestamp,
                instance_id=instance_id,
                status=activity_status,
            )
        self.updates.notify()

    def unfinished(self, trace_id: str, agent_id: str) -> dict[str, Event]:
        """
        The activities that have begun but not finished, by instance ID.

        Raises:
            KeyError: If agent_id may not work on the trace.
        """
        with self._working_on(trace_id, agent_id):
            return self.engine_monitor.unfinished(trace_id=trace_id)

    def add_agent(self, trace_id: str, agent_id: str) -> set[str]:
        """
        Let another agent work on a running trace.

        Returns:
            The agents allowed to work on the trace.

        Raises:
            KeyError: If the trace was never started.
            ValueError: If the trace has ended.
        """
        try:
            with self._locked(trace_id) as trace:
                trace.agent_ids.add(agent_id)
                agent_ids = set(trace.agent_ids)
        except KeyError:
            if self.audit.get(trace_id) is not None:
                raise ValueError(f"Trace has ended: {trace_id!r}") from None
            raise
        self.updates.notify()
        return agent_ids

    def entries(self, trace_id: str) -> list[AuditEntry] | None:
        """A trace's history, running or ended, or None if it was never started."""
        trace = self.running_traces.get(trace_id)
        if trace is not None:
            with trace.lock:
                return list(trace.entries)
        record = self.audit.get(trace_id)
        return None if record is None else record.entries

    def all_entries(self) -> list[AuditEntry]:
        """The history of all traces, running or ended, oldest first."""
        by_trace: dict[str, list[AuditEntry]] = {}
        for trace in self.running_traces.traces:
            with trace.lock:
                by_trace[trace.trace_id] = list(trace.entries)
        # A trace that ended meanwhile is replaced by its record
        for record in self.audit.records:
            by_trace[record.trace_id] = record.entries
        return sorted(
            (entry for entries in by_trace.values() for entry in entries),
            key=lambda entry: entry.received_at,
        )

    @contextmanager
    def _locked(self, trace_id: str) -> Iterator[Trace]:
        """
        Hold the lock of a running trace.

        Raises:
            KeyError: If the trace is not running.
        """
        trace = self.running_traces.get(trace_id)
        if trace is None:
            raise KeyError(trace_id)
        with trace.lock:
            # It may have ended while we waited for the lock
            if self.running_traces.get(trace_id) is not trace:
                raise KeyError(trace_id)
            yield trace

    @contextmanager
    def _working_on(self, trace_id: str, agent_id: str) -> Iterator[Trace]:
        """
        Hold the lock of a running trace that agent_id may work on.

        Raises:
            KeyError: If the trace is not running or agent_id is not on it. A
                trace the agent is not on is reported as missing, so its ID is
                not revealed.
        """
        with self._locked(trace_id) as trace:
            if agent_id not in trace.agent_ids:
                raise KeyError(trace_id)
            yield trace

    @staticmethod
    def _record(trace: Trace, agent_id: str, action: Action, **fields: Any) -> None:
        """Add an entry to the trace's history. Hold the trace's lock."""
        trace.entries.append(
            AuditEntry(
                received_at=datetime.now(UTC),
                agent_id=agent_id,
                trace_id=trace.trace_id,
                action=action,
                **fields,
            )
        )


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
    for trace in state.server_monitors.running_traces.traces:
        with trace.lock:
            try:
                running = state.engine_monitor.unfinished(trace_id=trace.trace_id)
                violations = state.engine_monitor.violations(trace_id=trace.trace_id)
            except KeyError:
                continue  # The trace ended meanwhile
            monitors.append(
                MonitorInfo(
                    trace_id=trace.trace_id,
                    model_id=trace.model_id,
                    agent_ids=sorted(trace.agent_ids),
                    started_at=trace.started_at,
                    running=[
                        running_activity(instance_id, event)
                        for instance_id, event in running.items()
                    ],
                    violations=violations,
                )
            )
    monitors.sort(key=lambda monitor: monitor.started_at, reverse=True)
    return MonitorListResponse(monitors=monitors)
