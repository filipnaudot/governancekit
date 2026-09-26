"""
TraceMonitor - runtime trace-level conformance checking.

Applies an MPDeclareModel to a trace.
"""

from core.constraint_factory import build_instance
from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import MPDeclareModel


class TraceMonitor:
    def __init__(self, model: MPDeclareModel) -> None:
        self.model = model
        self.instances = [build_instance(d) for d in model.constraints]
        self.last_event: Event | None = None

    def check(self, event: Event) -> tuple[bool, list[str]]:
        violations = [
            self.instances[i].definition.source
            for i in self._candidates(event)
            if not self.instances[i].check(event, self.last_event)
        ]
        return not violations, violations

    def commit(self, event: Event) -> None:
        for i in self._candidates(event):
            self.instances[i].commit(event, self.last_event)
        self.last_event = event

    def analyze(self) -> list[str]:
        return [
            i.definition.source
            for i in self.instances
            if i.verdict() != Verdict.SATISFIED
        ]

    def _candidates(self, event: Event) -> set[int]:
        indices = set(self.model.activity_index.get(event.activity, ()))
        if self.last_event is not None:
            indices.update(self.model.after_index.get(self.last_event.activity, ()))
        else:
            indices.update(self.model.init_constraints)
        return indices
