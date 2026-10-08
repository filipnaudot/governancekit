"""
MP-DECLARE Responded Existence constraint

Satisfied if every activation has a matching target somewhere in the trace,
before or after it.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class RespondedExistenceInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._pending: list[Event] = []
        self._targets: list[Event] = []
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
        if (
            self._is_activation(event)
            and not any(self._matches(event, t) for t in self._targets)
            and (self._keep_all or not self._pending)
        ):
            self._pending.append(replace(event, timestamp=completed_at))
        if event.activity == self.definition.target_activity:
            self._pending = [a for a in self._pending if not self._matches(a, event)]
            if self._keep_all or not self._targets:
                self._targets.append(replace(event, timestamp=completed_at))

    def verdict(self) -> Verdict:
        return Verdict.VIOLATED if self._pending else Verdict.SATISFIED

    def _is_activation(self, event: Event) -> bool:
        d = self.definition
        return event.activity == d.activation_activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _matches(self, activation: Event, target: Event) -> bool:
        d = self.definition
        return (
            d.correlation_condition is None
            or d.correlation_condition(activation, target)
        ) and (d.time_condition is None or d.time_condition(activation, target))
