"""
MP-DECLARE Existence constraint

Satisfied if specified activity appears n times in a trace (default n = 1)
"""

from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import ConstraintDef


class ExistenceInstance:
    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._count: int = 0

    def handle_event(self, event: Event) -> None:
        d = self.definition
        if event.activity == d.activation_activity:  # Add activation constraint later
            self._count += 1

    def verdict(self) -> Verdict:
        d = self.definition
        return Verdict.SATISFIED if self._count >= d.count else Verdict.VIOLATED
