"""
MP-DECLARE Precedence constraint

An activation arriving with no prior target is a permanent violation.
"""

from core.constraints.base import Verdict
from core.events import Event
from core.mp_declare_model import ConstraintDef


class PrecedenceInstance:
    _targets: list[Event]

    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._targets = []
        self._violated = False
        self._keep_all_targets = (
            definition.correlation_condition is not None
            or definition.time_condition is not None
        )

    def check(self, event: Event, last: Event | None) -> bool:
        return not self._is_activation(event) or self._has_matching_target(event)

    def commit(self, event: Event, last: Event | None) -> None:
        d = self.definition
        if event.activity == d.target_activity:
            if self._keep_all_targets or not self._targets:
                self._targets.append(event)
        elif not self.check(event):
            self._violated = True

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _has_matching_target(self, activation: Event) -> bool:
        d = self.definition
        return any(
            (
                d.correlation_condition is None
                or d.correlation_condition(activation, target)
            )
            and (d.time_condition is None or d.time_condition(activation, target))
            for target in self._targets
        )
