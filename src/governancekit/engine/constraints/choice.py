"""
MP-DECLARE Choice constraint

Satisfied if at least one of the two activities occurs.

The activation condition applies to both activities.
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class ChoiceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._satisfied = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if self._is(event, d.activation_activity) or self._is(event, d.target_activity):
            self._satisfied = True

    def verdict(self) -> Verdict:
        return Verdict.SATISFIED if self._satisfied else Verdict.VIOLATED

    def _is(self, event: Event, activity: str) -> bool:
        d = self.definition
        return event.activity == activity and (
            d.activation_condition is None or d.activation_condition(event)
        )
