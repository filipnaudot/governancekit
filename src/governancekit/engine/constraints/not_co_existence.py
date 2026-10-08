"""
MP-DECLARE Not Co-Existence constraint

Satisfied if no occurrence of either activity has a matching occurrence of the
other one anywhere in the trace.

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


class NotCoExistenceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._completed_a: list[Event] = []
        self._completed_b: list[Event] = []
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
        if self._is(event, d.activation_activity):
            if any(self._matches(event, b) for b in self._completed_b):
                return blocked
            if any(
                self._is(b, d.target_activity) and self._correlates(event, b)
                for b in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
        elif self._is(event, d.target_activity):
            if any(self._matches(a, event) for a in self._completed_a):
                return blocked
            if any(
                self._is(a, d.activation_activity) and self._correlates(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if self._is(event, d.activation_activity):
            if any(self._matches(event, b) for b in self._completed_b):
                self._violated = True
            if self._keep_all or not self._completed_a:
                self._completed_a.append(replace(event, timestamp=completed_at))
        elif self._is(event, d.target_activity):
            if any(self._matches(a, event) for a in self._completed_a):
                self._violated = True
            if self._keep_all or not self._completed_b:
                self._completed_b.append(replace(event, timestamp=completed_at))

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._violated else Verdict.SATISFIED

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
