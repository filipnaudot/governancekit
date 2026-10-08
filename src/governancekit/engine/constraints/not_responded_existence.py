"""
MP-DECLARE Not Responded Existence constraint

Satisfied if no activation has a matching target anywhere in the trace, before
or after it.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class NotRespondedExistenceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._activations: list[Event] = []
        self._targets: list[Event] = []
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
        # With a time condition, the block ends once its window has passed
        blocked = Decision.WAIT if d.time_condition is not None else Decision.DENIED
        if self._is_activation(event):
            if any(self._matches(event, t) for t in self._targets):
                return blocked
            if any(
                self._correlates(event, t)
                for t in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
        elif event.activity == d.target_activity:
            if any(self._matches(a, event) for a in self._activations):
                return blocked
            if any(
                self._is_activation(a) and self._correlates(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._is_activation(event):
            if any(self._matches(event, t) for t in self._targets):
                self._violated = True
            if self._keep_all or not self._activations:
                self._activations.append(replace(event, timestamp=completed_at))
        elif event.activity == self.definition.target_activity:
            if any(self._matches(a, event) for a in self._activations):
                self._violated = True
            if self._keep_all or not self._targets:
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
        return self._correlates(activation, target) and (
            d.time_condition is None or d.time_condition(activation, target)
        )

    def _correlates(self, activation: Event, target: Event) -> bool:
        d = self.definition
        return d.correlation_condition is None or d.correlation_condition(
            activation, target
        )
