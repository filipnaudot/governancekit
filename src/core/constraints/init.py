"""
MP-DECLARE Init constraint

Satisfied if trace starts with the given activity
"""

from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import ConstraintDef


class InitInstance:
    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._satisfied = False

    def check(self, event: Event, last: Event | None) -> bool:
        return last is not None or self._is_activation(event)

    def commit(self, event: Event, last: Event | None) -> None:
        if last is None:
            self._satisfied = self._is_activation(event)

    def verdict(self) -> Verdict:
        return Verdict.SATISFIED if self._satisfied else Verdict.VIOLATED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )
