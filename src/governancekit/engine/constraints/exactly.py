"""
MP-DECLARE Exactly constraint

Satisfied if the activity occurs exactly n times (default n = 1).

Running instances count against the upper limit until they finish.
"""

from collections.abc import Mapping
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class ExactlyInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._n = definition.count or 1
        self._count = 0

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        if not self._is_activation(event):
            return Decision.ALLOWED
        if self._count >= self._n:
            return Decision.DENIED
        running_count = sum(
            self._is_activation(e)
            for e in running.get(self.definition.activation_activity, {}).values()
        )
        if self._count + running_count >= self._n:
            return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._is_activation(event):
            self._count += 1

    def verdict(self) -> Verdict:
        return Verdict.SATISFIED if self._count == self._n else Verdict.VIOLATED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )
