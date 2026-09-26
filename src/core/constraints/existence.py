"""
MP-DECLARE Existence constraint

Satisfied if specified activity appears n times in a trace (default n = 1)
"""

from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import ConstraintDef


class ExistenceInstance:
    # TODO: Implement handling of MP DECLARE conditions
    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._count: int = 0

    def check(self, event: Event | None) -> bool:
        return True

    def commit(self, event: Event, last: Event | None) -> None:
        d = self.definition
        if event.activity == d.activation_activity:
            self._count += 1

    def verdict(self) -> Verdict:
        d = self.definition
        return Verdict.SATISFIED if self._count >= d.count else Verdict.VIOLATED
