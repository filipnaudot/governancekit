"""
MP-DECLARE Existence constraint

Satisfied if specified activity appears n times in a trace (default n = 1)
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class ExistenceInstance:
    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._count: int = 0

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
        last_completed: Event | None,
    ) -> Decision:
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        d = self.definition
        if event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        ):
            self._count += 1

    def verdict(self) -> Verdict:
        d = self.definition
        return Verdict.SATISFIED if self._count >= (d.count or 1) else Verdict.VIOLATED
