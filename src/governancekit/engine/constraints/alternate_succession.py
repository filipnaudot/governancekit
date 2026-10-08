"""
MP-DECLARE Alternate Succession constraint

Satisfied if the two activities strictly alternate: every first activity is
followed by a matching second activity before the next first one (Alternate
Response), and every second activity is preceded by a matching first activity
since the previous second one (Alternate Precedence).

First activities are exclusive while running, and so are second activities. A
pending first activity whose time window has passed can't be answered anymore
and stops blocking.

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


class AlternateSuccessionInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._pending: Event | None = None
        self._violated = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        d = self.definition
        if self._is(event, d.activation_activity):
            # Two first activities running at once could both complete before a second one
            if any(
                self._is(a, d.activation_activity)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
            if self._pending is not None:
                if any(
                    self._is(b, d.target_activity) and self._matches(self._pending, b)
                    for b in running.get(d.target_activity, {}).values()
                ):
                    return Decision.WAIT
                if not self._too_late(self._pending, event):
                    # With a time condition, the block ends once its window has passed
                    return (
                        Decision.WAIT
                        if d.time_condition is not None
                        else Decision.DENIED
                    )
            return Decision.ALLOWED

        if self._is(event, d.target_activity):
            if self._pending is not None and self._matches(self._pending, event):
                decision = Decision.ALLOWED
            elif (
                self._pending is not None
                and self._correlates(self._pending, event)
                and self._too_early(self._pending, event)
            ) or any(
                self._is(a, d.activation_activity) and self._correlates(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                decision = Decision.WAIT
            else:
                return Decision.DENIED
            # Two second activities running at once could both answer the same first
            # one. The running one completing would answer it, so DENIED stays DENIED.
            if any(
                self._is(b, d.target_activity)
                for b in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
            return decision

        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if self._is(event, d.target_activity):
            if self._pending is not None and self._matches(self._pending, event):
                self._pending = None
            else:
                self._violated = True
        if self._is(event, d.activation_activity):
            if self._pending is not None:
                self._violated = True
            self._pending = replace(event, timestamp=completed_at)

    def verdict(self) -> Verdict:
        if self._violated or self._pending is not None:
            return Verdict.VIOLATED
        return Verdict.SATISFIED

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
