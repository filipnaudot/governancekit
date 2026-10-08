"""
MP-DECLARE Not Succession constraint

Satisfied if no first activity is followed by a matching second activity.

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


class NotSuccessionInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._completed_a: list[Event] = []
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
        if self._is(event, d.activation_activity):
            # A running second activity that began longer ago than the time window
            # can't be in it, however soon this one completes
            if any(
                self._is(b, d.target_activity)
                and self._correlates(event, b)
                and not self._too_late(b, event)
                for b in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
        elif self._is(event, d.target_activity):
            if any(self._matches(a, event) for a in self._completed_a):
                # With a time condition, the block ends once its window has passed
                return (
                    Decision.WAIT if d.time_condition is not None else Decision.DENIED
                )
            if any(
                self._is(a, d.activation_activity) and self._correlates(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if self._is(event, d.target_activity) and any(
            self._matches(a, event) for a in self._completed_a
        ):
            self._violated = True
        if self._is(event, d.activation_activity) and (
            self._keep_all or not self._completed_a
        ):
            self._completed_a.append(replace(event, timestamp=completed_at))

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

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
