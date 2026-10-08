"""
MP-DECLARE Chain Succession constraint

Satisfied if every first activity is immediately followed by a matching second
activity (Chain Response), and every second activity is immediately preceded by
a matching first activity (Chain Precedence).

An ordering constraint: it hears about every completion and is asked on every
begin. A first activity may only begin when nothing else runs, and nothing else
may begin while either activity runs. After a first activity completes, only a
matching second activity may begin, until its time window has passed.

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


class ChainSuccessionInstance:
    def __init__(self, definition: ConstraintDef) -> None:
        self.definition = definition
        self._last: Event | None = None  # last completed activity, any kind
        self._violated = False

    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
    ) -> Decision:
        d = self.definition
        if self._is(event, d.target_activity):
            if (
                self._activation_last()
                and self._correlates(self._last, event)
                and not self._too_late(self._last, event)
            ):
                if self._too_early(self._last, event):
                    return Decision.WAIT
                # Anything running could complete between the first activity and this one
                return Decision.WAIT if any(running.values()) else Decision.ALLOWED
            # Only a running first activity completing right before it could still help
            if any(
                self._is(a, d.activation_activity) and self._correlates(a, event)
                for a in running.get(d.activation_activity, {}).values()
            ):
                return Decision.WAIT
            return Decision.DENIED

        # Nothing else may begin while either runs: it could complete in between
        if any(
            self._is(a, d.activation_activity)
            for a in running.get(d.activation_activity, {}).values()
        ) or any(
            self._is(b, d.target_activity)
            for b in running.get(d.target_activity, {}).values()
        ):
            return Decision.WAIT

        if self._activation_last() and not self._too_late(self._last, event):
            # With a time condition, the block ends once its window has passed
            return Decision.WAIT if d.time_condition is not None else Decision.DENIED
        # Anything running could complete between the first activity and the second
        if self._is(event, d.activation_activity) and any(running.values()):
            return Decision.WAIT
        return Decision.ALLOWED

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        if self._is(event, self.definition.target_activity):
            # Chain Precedence: a second activity must directly follow its first one
            if not (self._activation_last() and self._matches(self._last, event)):
                self._violated = True
        elif self._activation_last():
            # Chain Response: a waiting first activity must be directly followed by its second one
            self._violated = True
        self._last = replace(event, timestamp=completed_at)

    def verdict(self) -> Verdict:
        if self._violated or self._activation_last():
            return Verdict.VIOLATED
        return Verdict.SATISFIED

    def _activation_last(self) -> bool:
        return self._last is not None and self._is(
            self._last, self.definition.activation_activity
        )

    def _too_early(self, earlier: Event, event: Event) -> bool:
        """The event begins before the time window after the earlier one opens"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        low, _ = time_condition.bounds
        return event.timestamp - earlier.timestamp < low

    def _too_late(self, earlier: Event, event: Event) -> bool:
        """The event begins after the time window after the earlier one closed"""
        time_condition = self.definition.time_condition
        if time_condition is None:
            return False
        _, high = time_condition.bounds
        return event.timestamp - earlier.timestamp > high

    def _is(self, event: Event, activity: str) -> bool:
        d = self.definition
        return event.activity == activity and (
            d.activation_condition is None or d.activation_condition(event)
        )

    def _matches(self, a: Event, b: Event) -> bool:
        d = self.definition
        return self._correlates(a, b) and (
            d.time_condition is None or d.time_condition(a, b)
        )

    def _correlates(self, a: Event, b: Event) -> bool:
        d = self.definition
        return d.correlation_condition is None or d.correlation_condition(a, b)
