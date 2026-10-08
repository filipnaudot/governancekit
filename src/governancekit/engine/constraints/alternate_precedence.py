"""
MP-DECLARE Alternate Precedence constraint

Satisfied if every activation is preceded by a matching target that completed
after the previous activation: each activation uses up all targets before it.

Activations are exclusive while running.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class AlternatePrecedenceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        # Targets completed since the previous activation
        self._available: list[Event] = []
        self._violated = False
        self._keep_all = (
            definition.correlation_condition is not None
            or definition.time_condition is not None
        )

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        d = self.definition
        if not self._is_activation(event):
            return Decision.ALLOWED
        if any(self._matches(event, t) for t in self._available):
            decision = Decision.ALLOWED
        elif any(
            self._correlates(event, t) and self._too_early(t, event)
            for t in self._available
        ) or any(
            self._correlates(event, t)
            for t in running.get(d.target_activity, {}).values()
        ):
            decision = Decision.WAIT
        else:
            return Decision.DENIED
        # Two activations running at once could both complete after the same target.
        # The running one completing would use up the targets, so DENIED stays DENIED.
        if any(
            self._is_activation(a)
            for a in running.get(d.activation_activity, {}).values()
        ):
            return Decision.WAIT
        return decision

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._is_activation(event):
            if not any(self._matches(event, t) for t in self._available):
                self._violated = True
            self._available = []
        if event.activity == self.definition.target_activity and (
            self._keep_all or not self._available
        ):
            self._available.append(replace(event, timestamp=completed_at))

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

    def _too_early(self, earlier: Event, event: Event) -> bool:
        """The event begins before the time window after the earlier one opens"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        low, _ = time_condition.bounds
        return event.timestamp - earlier.timestamp < low

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _matches(self, activation: Event, target: Event) -> bool:
        d = self.definition
        return self._correlates(activation, target) and (
            d.time_condition is None or d.time_condition(activation, target)
        )

    def _correlates(self, activation: Event, target: Event) -> bool:
        d = self.definition
        return d.correlation_condition is None or d.correlation_condition(
            activation, target
        )
