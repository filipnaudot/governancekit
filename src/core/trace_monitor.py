"""
TraceMonitor - runtime trace-level conformance checking.

Applies an MPDeclareModel to a trace.
"""

from core.constraint_factory import build_instance
from core.constraints.base import Verdict
from core.decision import Decision
from core.events import Event
from core.mp_declare_model import MPDeclareModel


class TraceMonitor:
    def __init__(self, model: MPDeclareModel) -> None:
        self.model = model
        self.instances = [build_instance(d) for d in model.constraints]
        self.running: dict[str, dict[str, Event]] = {}
        self.last_completed: Event | None = None

    def check(self, event: Event) -> tuple[bool, list[str]]:
        violations = [
            self.instances[i].definition.source
            for i in self._candidates(event)
            if self.instances[i].can_begin(event, self.running, self.last_completed)
            is not Decision.ALLOWED
        ]
        return not violations, violations

    def commit(self, event: Event) -> None:
        # A committed event is instantaneous: it completes at its own timestamp
        for i in self._candidates(event):
            self.instances[i].on_finish(event, event.timestamp)
        self.last_completed = event

    def analyze(self) -> list[str]:
        return [
            i.definition.source
            for i in self.instances
            if i.verdict() != Verdict.SATISFIED
        ]

    def _candidates(self, event: Event) -> set[int]:
        indices = set(self.model.activity_index.get(event.activity, ()))
        if self.last_completed is None:
            indices.update(self.model.init_constraints)
        return indices
