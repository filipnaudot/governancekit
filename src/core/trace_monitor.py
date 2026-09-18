"""
TraceMonitor - runtime trace-level conformance checking.

Applies a MPDeclareModel on a trace.
"""

from dataclasses import dataclass

from core.constraint_factory import build_instance
from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import MPDeclareModel


@dataclass(frozen=True, slots=True)
class Violation:
    constraint_id: str
    event: Event | None


class TraceMonitor:
    def __init__(self, model: MPDeclareModel):
        self.model = model
        self.instances = [build_instance(d) for d in model.constraints]

    def handle_event(self, event: Event) -> list[Violation]:
        indices = self.model.activity_index.get(event.activity())
        for i in indices:
            self.instances[i].handle_event(event)
            res = self.instances[i].verdict()
            print(res)
            # TODO: Add logging for accepted / rejected events

    def analyze(self) -> list[Violation]:
        return [
            Violation(i.definition.id, event=None)
            for i in self.instances
            if i.verdict != Verdict.SATISFIED
        ]
