"""
MP-DECLARE Co-Existence constraint

Satisfied if every occurrence of either activity has a matching occurrence of
the other one somewhere in the trace, before or after it.

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


class CoExistenceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._completed_a: list[Event] = []
        self._completed_b: list[Event] = []
        # Completed activities without a matching partner yet
        self._pending_a: list[Event] = []
        self._pending_b: list[Event] = []
        self._keep_all = (
            definition.correlation_condition is not None
            or definition.time_condition is not None
        )

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        # A pair is compared when its later activity completes, while that one still
        # has its begin time
        d = self.definition
        stored = replace(event, timestamp=completed_at)
        if self._is(event, d.activation_activity):
            self._pending_b = [
                b for b in self._pending_b if not self._matches(event, b)
            ]
            if not any(self._matches(event, b) for b in self._completed_b) and (
                self._keep_all or not self._pending_a
            ):
                self._pending_a.append(stored)
            if self._keep_all or not self._completed_a:
                self._completed_a.append(stored)
        elif self._is(event, d.target_activity):
            self._pending_a = [
                a for a in self._pending_a if not self._matches(a, event)
            ]
            if not any(self._matches(a, event) for a in self._completed_a) and (
                self._keep_all or not self._pending_b
            ):
                self._pending_b.append(stored)
            if self._keep_all or not self._completed_b:
                self._completed_b.append(stored)

    def verdict(self) -> Verdict:
        if self._pending_a or self._pending_b:
            return Verdict.VIOLATED
        return Verdict.SATISFIED

    def _is(self, event: Event, activity: str) -> bool:
        d = self.definition
        return event.activity == activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _matches(self, a: Event, b: Event) -> bool:
        d = self.definition
        return (d.correlation_condition is None or d.correlation_condition(a, b)) and (
            d.time_condition is None or d.time_condition(a, b)
        )
