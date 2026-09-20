"""
MP-DECLARE Existence constraint

An activation arriving with no prior target is a permanent violation.
"""

from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import ConstraintDef


class PrecedenceInstance:
    # TODO: Implement handling of MP DECLARE conditions
    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._target_seen = False
        self._violated = False

    def check(self, event: Event) -> bool:
        if event.activity != self.definition.activation_activity:
            return True
        return self._target_seen

    def commit(self, event: Event) -> None:
        d = self.definition
        if event.activity == d.target_activity:
            self._target_seen = True
        elif event.activity == d.activation_activity and not self._target_seen:
            self._violated = True

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED
