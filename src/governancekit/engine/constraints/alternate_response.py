"""
MP-DECLARE Alternate Response constraint

Satisfied if every activation is followed by a matching target before the next
activation.

Activations are exclusive while running. A pending activation whose time window
has passed can't be answered anymore and stops blocking.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from governancekit.engine.constraints.base import Verdict
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef


class AlternateResponseInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._pending: Event | None = None
        self._violated = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        d = self.definition
        if not self._is_activation(event):
            return Decision.ALLOWED
        # Two activations running at once could both complete before a target
        if any(
            self._is_activation(a)
            for a in running.get(d.activation_activity, {}).values()
        ):
            return Decision.WAIT
        if self._pending is not None:
            if any(
                self._matches(self._pending, t)
                for t in running.get(d.target_activity, {}).values()
            ):
                return Decision.WAIT
            if not self._too_late(self._pending, event):
                # With a time condition, the block ends once its window has passed
                return (
                    Decision.WAIT if d.time_condition is not None else Decision.DENIED
                )
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if (
            event.activity == self.definition.target_activity
            and self._pending is not None
            and self._matches(self._pending, event)
        ):
            self._pending = None
        if self._is_activation(event):
            if self._pending is not None:
                self._violated = True
            self._pending = replace(event, timestamp=completed_at)

    def verdict(self) -> Verdict:
        if self._violated or self._pending is not None:
            return Verdict.VIOLATED
        return Verdict.SATISFIED

    def _too_late(self, earlier: Event, event: Event) -> bool:
        """The event begins after the time window after the earlier one closed"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        _, high = time_condition.bounds
        return event.timestamp - earlier.timestamp > high

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
