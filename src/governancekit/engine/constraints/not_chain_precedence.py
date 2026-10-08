"""
MP-DECLARE Not Chain Precedence constraint

Satisfied if no activation is immediately preceded by a matching target: the
last activity to complete before an activation must not be that target.

An ordering constraint: it hears about every completion and is asked on every
begin. Any other activity completing in between makes an activation fine again.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class NotChainPrecedenceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._last: Event | None = None  # last completed activity, any kind
        self._violated = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        d = self.definition
        if self._is_activation(event):
            # Fine once the time window has passed or something running completes in
            # between, unless that is a target it correlates with as well
            if self._target_last() and self._matches(event, self._last):
                if d.time_condition is not None or any(
                    not (r.activity == d.target_activity and self._correlates(event, r))
                    for instances in running.values()
                    for r in instances.values()
                ):
                    return Decision.WAIT
                return Decision.DENIED
            if any(
                self._correlates(event, t)
                for t in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
        elif event.activity == d.target_activity:
            # A running activation that began longer ago than the time window can't be
            # in it, however soon this target completes
            if any(
                self._is_activation(a)
                and self._correlates(a, event)
                and not self._too_late(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if (
            self._is_activation(event)
            and self._target_last()
            and self._matches(event, self._last)
        ):
            self._violated = True
        self._last = replace(event, timestamp=completed_at)

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

    def _target_last(self) -> bool:
        return (
            self._last is not None
            and self._last.activity == self.definition.target_activity
        )

    def _too_late(self, earlier: Event, event: Event) -> bool:
        """The event begins after the time window after the earlier one closed"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        _, high = time_condition.bounds
        return event.timestamp - earlier.timestamp > high

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
