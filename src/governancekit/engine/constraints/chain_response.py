"""
MP-DECLARE Chain Response constraint

Satisfied if every activation is immediately followed by a matching target: the
next activity to complete must be that target.

An ordering constraint: it hears about every completion and is asked on every
begin. Anything completing right after an activation must be its target, so an
activation only runs alongside targets that correlate with it, and only without
a time condition. After it completes, only a matching target may begin, until
its time window has passed.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class ChainResponseInstance:
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
        # It could complete right after a running activation
        if any(
            self._is_activation(a) and not self._may_complete_after(a, event)
            for a in running.get(d.activation_activity, {}).values()
        ):
            return Decision.WAIT

        if self._activation_last():
            if (
                event.activity == d.target_activity
                and self._correlates(self._last, event)
                and not self._too_late(self._last, event)
            ):
                if self._too_early(self._last, event):
                    return Decision.WAIT
                return Decision.ALLOWED
            if any(
                self._matches(self._last, t)
                for t in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
            if not self._too_late(self._last, event):
                # With a time condition, the block ends once its window has passed
                return (
                    Decision.WAIT if d.time_condition is not None else Decision.DENIED
                )

        # Anything running could complete right after this activation
        if self._is_activation(event) and any(
            not self._may_complete_after(event, r)
            for instances in running.values()
            for r in instances.values()
        ):
            return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._activation_last() and not (
            event.activity == self.definition.target_activity
            and self._matches(self._last, event)
        ):
            self._violated = True
        self._last = replace(event, timestamp=completed_at)

    def verdict(self) -> Verdict:
        if self._violated or self._activation_last():
            return Verdict.VIOLATED
        return Verdict.SATISFIED

    def _activation_last(self) -> bool:
        return self._last is not None and self._is_activation(self._last)

    def _may_complete_after(self, activation: Event, event: Event) -> bool:
        """The event can complete right after the activation without breaking it: a
        correlating target, and no time condition (the activation's completion time
        is unknown)"""
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
