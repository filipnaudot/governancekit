"""
MP-DECLARE Init constraint

Satisfied if the first completed activity is a matching activation.

An ordering constraint: it hears about every completion and is asked on every
begin.
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class InitInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._decided = False
        self._satisfied = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        if self._decided or self._is_activation(event):
            return Decision.ALLOWED
        if any(
            self._is_activation(a)
            for a in running.get(self.definition.activation_activity, {}).values()
        ):
            return Decision.WAIT
        return Decision.DENIED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
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
