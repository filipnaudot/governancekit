"""
MP-DECLARE Not Chain Succession constraint

Satisfied if no first activity is immediately followed by a matching second
activity: the next activity to complete after a first one must not be that
second one.

An ordering constraint: it hears about every completion and is asked on every
begin. Any other activity completing in between makes a second activity fine
again.

The activation condition applies to both activities. The correlation condition
always gets the first activity as A and the second as T.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class NotChainSuccessionInstance:
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
        if self._is(event, d.target_activity):
            # Fine once the time window has passed or something running completes in
            # between, unless that is a first activity it correlates with as well
            if self._activation_last() and self._matches(self._last, event):
                if d.time_condition is not None or any(
                    not (
                        self._is(r, d.activation_activity)
                        and self._correlates(r, event)
                    )
                    for instances in running.values()
                    for r in instances.values()
                ):
                    return Decision.WAIT
                return Decision.DENIED
            if any(
                self._is(a, d.activation_activity) and self._correlates(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
        elif self._is(event, d.activation_activity):
            # A running second activity that began longer ago than the time window
            # can't be in it, however soon this one completes
            if any(
                self._is(b, d.target_activity)
                and self._correlates(event, b)
                and not self._too_late(b, event)
                for b in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if (
            self._is(event, self.definition.target_activity)
            and self._activation_last()
            and self._matches(self._last, event)
        ):
            self._violated = True
        self._last = replace(event, timestamp=completed_at)

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

    def _activation_last(self) -> bool:
        return self._last is not None and self._is(
            self._last, self.definition.activation_activity
        )

    def _too_late(self, earlier: Event, event: Event) -> bool:
        """The event begins after the time window after the earlier one closed"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        _, high = time_condition.bounds
        return event.timestamp - earlier.timestamp > high

    def _is(self, event: Event, activity: str) -> bool:
        d = self.definition
        return event.activity == activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _matches(self, a: Event, b: Event) -> bool:
        d = self.definition
        return self._correlates(a, b) and (
            d.time_condition is None or d.time_condition(a, b)
        )

    def _correlates(self, a: Event, b: Event) -> bool:
        d = self.definition
        return d.correlation_condition is None or d.correlation_condition(a, b)
