"""Public interface for runtime conformance checking of MP-Declare models.

Registers models and monitors traces against them. Callers ask before an
activity begins and report when it finishes, so an agent action can be blocked
before it would permanently violate a constraint. Several activities may run
at the same time.
"""

import threading
from datetime import datetime

from governancekit.engine.decision import Decision
from governancekit.engine.decl_parser import parse_decl_text
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef, MPDeclareModel
from governancekit.engine.trace_monitor import TraceMonitor


class MonitorRegistry:
    """Registry of MP-Declare models and the traces monitored against them.

    Models are parsed once and shared by all traces that use them. Each
    trace gets its own monitor, created by start_monitor and removed by
    end_monitor.

    Typical use per activity: call begin_event. If it is ALLOWED, perform the
    activity and call finish_event with its instance id. If it is WAIT, ask
    again later; if it is DENIED, don't perform it.

    check_event and commit_event are the older one-step flow, kept for
    compatibility. They don't see running activities, so don't mix them with
    begin_event and finish_event on the same trace.

    Thread-safe: it starts no threads itself, but may be called from several.
    Calls on the same trace run one at a time; different traces don't wait
    for each other.

    Attributes:
        models: Parsed models, keyed by model ID.
        monitors: Active trace monitors, keyed by trace ID.
    """

    models: dict[str, MPDeclareModel]
    monitors: dict[str, TraceMonitor]

    def __init__(self):
        self.models = {}
        self.monitors = {}
        self._lock = threading.Lock()  # guards models, monitors and _trace_locks
        self._trace_locks: dict[str, threading.Lock] = {}

    def add_model(self, model_id: str, model_text: str) -> None:
        """
        Add a model to the monitor registry.

        Parses a model definition in MP-DECLARE syntax and adds it to the registry.

        Args:
            model_id: Unique key for the model.
            model_text: Model definition in MP-DECLARE syntax.

        Raises:
            ValueError: If model_id is already registrered or syntax error in
                        model definition.
        """
        constraints: list[ConstraintDef] = parse_decl_text(model_text)
        model = MPDeclareModel.build(constraints)
        with self._lock:
            if model_id in self.models:
                raise ValueError("Model id {model_id!r} is already registrered.")
            self.models[model_id] = model

    def start_monitor(self, model_id: str, trace_id: str) -> None:
        """
        Start monitoring a trace for conformance with a registered model.

        Creates a TraceMonitor for the model and stores it under trace_id.

        Args:
            trace_id: Unique key for the trace. Also used as the monitor key.
            model_id: ID of the model to check the trace against.

        Raises:
            KeyError: If model_id is not registered.
            ValueError: If a monitor for trace_id already exists.
        """
        with self._lock:
            if trace_id in self.monitors:
                raise ValueError(f"Trace id {trace_id!r} is already monitored.")
            if model_id not in self.models:
                raise KeyError(f"Model id {model_id!r} is not registered.")
            model: MPDeclareModel = self.models[model_id]
            self.monitors[trace_id] = TraceMonitor(model)
            self._trace_locks[trace_id] = threading.Lock()

    def end_monitor(
        self, trace_id: str, abort_running: bool = False
    ) -> dict[str, Event]:
        """
        Stop monitoring a trace and remove its monitor.

        Args:
            trace_id: Key of the trace to stop monitoring.
            abort_running: End the trace even if activities are still running;
                           they are aborted.

        Returns:
            The aborted activities (instance id -> event). Empty if nothing was running.

        Raises:
            KeyError: If trace_id is not being monitored.
            ValueError: If activities are still running and abort_running is False.
        """
        monitor, lock = self._monitor(trace_id)
        # Wait for ongoing calls on the trace. Taking the registry lock while holding
        # the trace lock is safe: the registry lock is never held while taking a trace lock.
        with lock:
            unfinished = monitor.unfinished()
            if unfinished and not abort_running:
                raise ValueError(
                    f"Trace id {trace_id!r} has {len(unfinished)} running activities."
                )
            with self._lock:
                if self.monitors.get(trace_id) is not monitor:
                    raise KeyError(f"Trace id {trace_id!r} is not monitored.")
                del self.monitors[trace_id]
                del self._trace_locks[trace_id]
        return unfinished

    def begin_event(
        self, trace_id: str, event: Event
    ) -> tuple[Decision, str | None, list[str]]:
        """
        Ask whether an activity may begin, and reserve it if allowed.

        Checking and reserving happen atomically, so no other call on the trace
        can come in between. Several activities may be running at once.

        Args:
            trace_id: Key of the monitored trace.
            event: The activity that wants to begin, with its final payload.

        Returns:
            A tuple (decision, instance_id, blocking). decision is ALLOWED,
            WAIT (may become allowed later) or DENIED (would permanently violate
            the model). instance_id is only set if ALLOWED and is needed for
            finish_event. blocking holds the source text of the constraints
            that did not allow it.

        Raises:
            KeyError: If trace_id is not being monitored.
        """
        monitor, lock = self._monitor(trace_id)
        with lock:
            return monitor.begin(event)

    def finish_event(
        self,
        trace_id: str,
        instance_id: str,
        completed: bool,
        completed_at: datetime | None = None,
    ) -> Event:
        """
        Finish an activity that was allowed by begin_event.

        Only a completed activity affects the constraints. A failed or aborted
        one is just released.

        Args:
            trace_id: Key of the monitored trace.
            instance_id: Returned by begin_event.
            completed: True if the activity completed successfully.
            completed_at: Completion time, defaults to now.

        Returns:
            The event the activity began with.

        Raises:
            KeyError: If trace_id is not being monitored or instance_id is not running.
        """
        monitor, lock = self._monitor(trace_id)
        with lock:
            return monitor.finish(instance_id, completed, completed_at)

    def check_event(self, trace_id: str, event: Event) -> tuple[bool, list[str]]:
        """
        Check whether an event can be committed without a permanent violation.

        Does not modify the trace. Temporary violations are allowed, since
        they can still be resolved by later events. Kept for compatibility:
        nothing is reserved, so prefer begin_event.

        Args:
            trace_id: Key of the monitored trace.
            event: Event to check.

        Returns:
            A tuple (allowed, violations). allowed is True if begin_event would
            answer ALLOWED. violations holds the source text of the constraints
            that don't allow it.

        Raises:
            KeyError: If trace_id is not being monitored.
        """
        monitor, lock = self._monitor(trace_id)
        with lock:
            return monitor.check(event)

    def violations(self, trace_id: str) -> list[str]:
        """Check whether a trace currently violates its model.

        Args:
            trace_id: Key of the monitored trace.

        Returns:
            List holding the source text of all constraints currently violated.

        Raises:
            KeyError: If trace_id is not being monitored.
        """
        monitor, lock = self._monitor(trace_id)
        with lock:
            return monitor.analyze()

    def unfinished(self, trace_id: str) -> dict[str, Event]:
        """Activities that have begun but not finished.

        Lets callers find activities that never finish and abort them with
        finish_event(..., completed=False).

        Args:
            trace_id: Key of the monitored trace.

        Returns:
            The running activities (instance id -> event, with its begin time).

        Raises:
            KeyError: If trace_id is not being monitored.
        """
        monitor, lock = self._monitor(trace_id)
        with lock:
            return monitor.unfinished()

    def commit_event(self, trace_id: str, event: Event) -> None:
        """Append an event to a monitored trace and update constraint states.

        Does not check the event first. Call check_event beforehand to
        reject events that would cause a permanent violation. Kept for
        compatibility: the event completes instantly at its own timestamp,
        bypassing running activities, so prefer begin_event and finish_event.

        Args:
            trace_id: Key of the monitored trace.
            event: Event to append.

        Raises:
            KeyError: If trace_id is not being monitored.
        """
        monitor, lock = self._monitor(trace_id)
        with lock:
            monitor.commit(event)

    def _monitor(self, trace_id: str) -> tuple[TraceMonitor, threading.Lock]:
        """The trace's monitor and its lock. Raises KeyError if not monitored."""
        with self._lock:
            if trace_id not in self.monitors:
                raise KeyError(f"Trace id {trace_id!r} is not monitored.")
            return self.monitors[trace_id], self._trace_locks[trace_id]
