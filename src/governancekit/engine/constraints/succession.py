"""
MP-DECLARE Succession constraint

Satisfied if every first activity is followed by a matching second activity
(Response), and every second activity is preceded by a matching first activity
(Precedence).

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


class SuccessionInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        # Precedence part: every completed first activity
        self._completed_a: list[Event] = []
        # Response part: first activities still waiting for a second one
        self._pending: list[Event] = []
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
        if not self._is(event, d.target_activity) or any(
            self._matches(a, event) for a in self._completed_a
        ):
            return Decision.ALLOWED
        if any(
            self._correlates(a, event) and self._too_early(a, event)
            for a in self._completed_a
        ):
            return Decision.WAIT
        if any(
            self._is(a, d.activation_activity) and self._correlates(a, event)
            for a in running.get(d.activation_activity, {}).values()
        ):
            return Decision.WAIT
        return Decision.DENIED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if self._is(event, d.target_activity):
            if not any(self._matches(a, event) for a in self._completed_a):
                self._violated = True
            self._pending = [a for a in self._pending if not self._matches(a, event)]
        if self._is(event, d.activation_activity):
            stored = replace(event, timestamp=completed_at)
            if self._keep_all or not self._pending:
                self._pending.append(stored)
            if self._keep_all or not self._completed_a:
                self._completed_a.append(stored)

    def verdict(self) -> Verdict:
        if self._violated or self._pending:
            return Verdict.VIOLATED
        return Verdict.SATISFIED

    def _too_early(self, earlier: Event, event: Event) -> bool:
        """The event begins before the time window after the earlier one opens"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        low, _ = time_condition.bounds
        return event.timestamp - earlier.timestamp < low

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
