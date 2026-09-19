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


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    violations: tuple[Violation, ...]


class TraceMonitor:
    def __init__(self, model: MPDeclareModel):
        self.model = model
        self.instances = [build_instance(d) for d in model.constraints]

    def check(self, event: Event) -> Decision:
        indices = self.model.activity_index.get(event.activity(), ())
        violations = [
            Violation(constraint_id=self.instances[i].definition.id)
            for i in indices
            if not self.instances[i].check(event)
        ]
        return Decision(allowed=not violations, violations=tuple(violations))

    def commit(self, event: Event) -> None:
        indices = self.model.activity_index.get(event.activity(), ())
        for i in indices:
            self.instances[i].commit(event)

    def analyze(self) -> list[Violation]:
        return [
            Violation(i.definition.id, event=None)
            for i in self.instances
            if i.verdict != Verdict.SATISFIED
        ]
