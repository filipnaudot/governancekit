"""Public interface for runtime conformance checking of MP-Declare models.

Registers models and monitors traces against them. Callers check events
before committing them, so an agent action can be blocked before it would
permanently violate a constraint.
"""

import threading

from core.decl_parser import parse_decl_text
from core.events import Event
from core.mp_declare_model import ConstraintDef, MPDeclareModel
from core.trace_monitor import TraceMonitor


class MonitorRegistry:
    """Registry of MP-Declare models and the traces monitored against them.

    Models are parsed once and shared by all traces that use them. Each
    trace gets its own monitor, created by start_monitor and removed by
    end_monitor.

    Typical use per event: call check_event, and if the event is allowed,
    perform the action and call commit_event.

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

    def end_monitor(self, trace_id: str) -> None:
        """
        Stop monitoring a trace and remove its monitor.

        Args:
            trace_id: Key of the trace to stop monitoring.

        Raises:
            KeyError: If trace_id is not being monitored.
        """
        with self._lock:
            if trace_id not in self.monitors:
                raise KeyError(f"Trace id {trace_id!r} is not monitored.")
            del self.monitors[trace_id]
            del self._trace_locks[trace_id]

    def check_event(self, trace_id: str, event: Event) -> tuple[bool, list[str]]:
        """
        Check whether an event can be committed without a permanent violation.

        Does not modify the trace. Temporary violations are allowed, since
        they can still be resolved by later events.

        Args:
            trace_id: Key of the monitored trace.
            event: Event to check.

        Returns:
            A tuple (allowed, violations). allowed is True if committing the
            event would not permanently violate any constraint. violations
            holds the source text of the constraints it would violate.

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

    def commit_event(self, trace_id: str, event: Event) -> None:
        """Append an event to a monitored trace and update constraint states.

        Does not check the event first. Call check_event beforehand to
        reject events that would cause a permanent violation.

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
