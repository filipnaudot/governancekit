"""
MP-DECLARE Precedence constraint

An activation arriving with no prior target is a permanent violation.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


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

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
        last_completed: Event | None,
    ) -> Decision:
        if not self._is_activation(event) or any(
            self._matches(event, t) for t in self._targets
        ):
            return Decision.ALLOWED
        # A running target may still complete before the activation is asked again.
        # Its time condition can then always be met, so only correlation matters here.
        running_targets = running.get(self.definition.target_activity)
        if running_targets and any(
            self._correlates(event, t) for t in running_targets.values()
        ):
            return Decision.WAIT
        return Decision.DENIED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._is_activation(event) and not any(
            self._matches(event, t) for t in self._targets
        ):
            self._violated = True
        if event.activity == self.definition.target_activity and (
            self._keep_all_targets or not self._targets
        ):
            # Time conditions compare the target's completion time with the activation's begin time
            self._targets.append(replace(event, timestamp=completed_at))

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

    def _correlates(self, activation: Event, target: Event) -> bool:
        d = self.definition
        return d.correlation_condition is None or d.correlation_condition(
            activation, target
        )
