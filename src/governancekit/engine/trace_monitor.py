"""
TraceMonitor - runtime trace-level conformance checking.

Applies an MPDeclareModel to a trace.
"""

import uuid
from datetime import UTC, datetime

from governancekit.engine.constraint_factory import build_instance
from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import MPDeclareModel


class TraceMonitor:
    """Monitors one trace, in which several activities may run at the same time.

    An activity asks begin() and, if allowed, reports finish() with its
    instance id. Only completed activities affect the constraints.

    Not thread-safe; MonitorRegistry serialises the calls per trace.
    """

    def __init__(self, model: MPDeclareModel) -> None:
        self.model = model
        self.instances = [build_instance(d) for d in model.constraints]
        self.running: dict[str, dict[str, Event]] = {}  # activity -> {iid -> event}
        self.last_completed: Event | None = None
        self._in_flight: dict[str, Event] = {}  # iid -> event

    def begin(self, event: Event) -> tuple[Decision, str | None, list[str]]:
        """Decide if the event may begin, and reserve it if allowed.

        Returns the decision, the instance id (only if allowed) and the source
        of every constraint that did not allow it.
        """
        decisions = [
            (
                self.instances[i].definition.source,
                self.instances[i].can_begin(event, self.running, self.last_completed),
            )
            for i in self._begin_candidates(event)
        ]
        blocking = [source for source, d in decisions if d is not Decision.ALLOWED]
        if blocking:
            denied = any(d is Decision.DENIED for _, d in decisions)
            return (Decision.DENIED if denied else Decision.WAIT), None, blocking

        iid = str(uuid.uuid4())
        self.running.setdefault(event.activity, {})[iid] = event
        self._in_flight[iid] = event
        return Decision.ALLOWED, iid, []

    def finish(
        self, iid: str, completed: bool, completed_at: datetime | None = None
    ) -> Event:
        """Finish a running activity and return its event.

        Only a completed activity affects the constraints. A failed or aborted
        one is just removed from the running activities.
        """
        event = self._in_flight.pop(iid)
        same_activity = self.running[event.activity]
        del same_activity[iid]
        if not same_activity:
            del self.running[event.activity]

        if completed:
            if completed_at is None:
                completed_at = datetime.now(UTC)
            for i in self._finish_candidates(event):
                self.instances[i].on_finish(event, completed_at)
            self.last_completed = event
        return event

    def check(self, event: Event) -> tuple[bool, list[str]]:
        """Like begin(), but reserves nothing. Kept for compatibility."""
        violations = [
            self.instances[i].definition.source
            for i in self._begin_candidates(event)
            if self.instances[i].can_begin(event, self.running, self.last_completed)
            is not Decision.ALLOWED
        ]
        return not violations, violations

    def commit(self, event: Event) -> None:
        """Record a completed event without checking it or seeing running
        activities. Kept for compatibility; don't mix with begin()/finish()."""
        # A committed event is instantaneous: it completes at its own timestamp
        for i in self._finish_candidates(event):
            self.instances[i].on_finish(event, event.timestamp)
        self.last_completed = event

    def analyze(self) -> list[str]:
        return [
            i.definition.source
            for i in self.instances
            if i.verdict() != Verdict.SATISFIED
        ]

    def unfinished(self) -> dict[str, Event]:
        """Activities that have begun but not finished (iid -> event).

        They are not part of analyze(), since only completed activities count.
        """
        return dict(self._in_flight)

    def _begin_candidates(self, event: Event) -> tuple[int, ...]:
        return (
            self.model.begin_index.get(event.activity, ())
            + self.model.ordering_constraints
        )

    def _finish_candidates(self, event: Event) -> tuple[int, ...]:
        # Ordering constraints hear about every completion, e.g. Init needs the first one
        return (
            self.model.finish_index.get(event.activity, ())
            + self.model.ordering_constraints
        )
