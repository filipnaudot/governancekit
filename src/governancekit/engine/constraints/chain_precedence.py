"""
MP-DECLARE Chain Precedence constraint

Satisfied if every activation is immediately preceded by a matching target: the
last activity to complete before it must be that target.

An ordering constraint: it hears about every completion and is asked on every
begin. An activation may only begin right after a matching target completed.
Nothing else may complete between the two, so an activation only runs alongside
targets that correlate with it, and only without a time condition.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class ChainPrecedenceInstance:
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
        if not self._is_activation(event):
            # It could complete right before a running activation
            if any(
                self._is_activation(a) and not self._may_complete_before(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
            return Decision.ALLOWED

        if (
            self._target_last()
            and self._correlates(event, self._last)
            and not self._too_late(self._last, event)
        ):
            if self._too_early(self._last, event):
                return Decision.WAIT
            # Anything running could complete between the target and this activation
            if any(
                not self._may_complete_before(event, r)
                for instances in running.values()
                for r in instances.values()
            ):
                return Decision.WAIT
            return Decision.ALLOWED
        # Only a running target completing right before it could still help
        if any(
            self._correlates(event, t)
            for t in running.get(d.target_activity, {}).values()
        ):
            return Decision.WAIT
        return Decision.DENIED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._is_activation(event) and not (
            self._target_last() and self._matches(event, self._last)
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

    def _may_complete_before(self, activation: Event, event: Event) -> bool:
        """The event can complete right before the activation without breaking it: a
        correlating target, and no time condition (its completion time is unknown)"""
        return (
            event.activity == self.definition.target_activity
            and self._correlates(activation, event)
            and self.definition.time_condition is None
        )

    def _too_early(self, earlier: Event, event: Event) -> bool:
        """The event begins before the time window after the earlier one opens"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        low, _ = time_condition.bounds
        return event.timestamp - earlier.timestamp < low

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
