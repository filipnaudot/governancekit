"""
MP-DECLARE Init constraint

Satisfied if trace starts with the given activity
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class InitInstance:
    def __init__(self, definition: ConstraintDef):
        self.definition = definition
        self._decided = False
        self._satisfied = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
        last_completed: Event | None,
    ) -> Decision:
        # Until the first completion, only the activation may begin
        if last_completed is not None or self._is_activation(event):
            return Decision.ALLOWED
        return Decision.WAIT

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        # Only the first completion decides the constraint
        if not self._decided:
            self._decided = True
            self._satisfied = self._is_activation(event)

    def verdict(self) -> Verdict:
        return Verdict.SATISFIED if self._satisfied else Verdict.VIOLATED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )
