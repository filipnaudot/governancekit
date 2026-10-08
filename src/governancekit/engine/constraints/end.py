"""
MP-DECLARE End constraint

Satisfied if the last completed activity is a matching activation.

An ordering constraint: it hears about every completion and is asked on every
begin.
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class EndInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._ends_with_activation = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        self._ends_with_activation = self._is_activation(event)

    def verdict(self) -> Verdict:
        return Verdict.SATISFIED if self._ends_with_activation else Verdict.VIOLATED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )
