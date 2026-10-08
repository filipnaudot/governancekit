"""
MP-DECLARE Exclusive Choice constraint

Satisfied if one of the two activities occurs, but not both.

The activation condition applies to both activities.
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class ExclusiveChoiceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._completed: set[str] = set()

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        d = self.definition
        if self._is(event, d.activation_activity):
            other = d.target_activity
        elif self._is(event, d.target_activity):
            other = d.activation_activity
        else:
            return Decision.ALLOWED
        if other in self._completed:
            return Decision.DENIED
        if any(self._is(e, other) for e in running.get(other, {}).values()):
            return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if self._is(event, d.activation_activity) or self._is(event, d.target_activity):
            self._completed.add(event.activity)

    def verdict(self) -> Verdict:
        return Verdict.SATISFIED if len(self._completed) == 1 else Verdict.VIOLATED

    def _is(self, event: Event, activity: str) -> bool:
        d = self.definition
        return event.activity == activity and (
            d.activation_condition is None or d.activation_condition(event)
        )
