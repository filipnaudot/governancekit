"""
MP-DECLARE Precedence constraint

An activation arriving with no prior target is a permanent violation.
"""

from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import ConstraintDef


class PrecedenceInstance:
    _targets: list[Event]

    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._targets = []
        self._violated = False
        self._keep_all_targets = (
            definition.correlation_condition is not None
            or definition.time_condition is not None
        )

    def check(self, event: Event, last: Event | None) -> bool:
        return not self._is_activation(event) or any(
            self._matches(event, t) for t in self._targets
        )

    def commit(self, event: Event, last: Event | None) -> None:
        if not self.check(event, last):
            self._violated = True
        if event.activity == self.definition.target_activity and (
            self._keep_all_targets or not self._targets
        ):
            self._targets.append(event)

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _matches(self, activation: Event, target: Event) -> bool:
        d = self.definition
        return (
            d.correlation_condition is None
            or d.correlation_condition(activation, target)
        ) and (d.time_condition is None or d.time_condition(activation, target))
