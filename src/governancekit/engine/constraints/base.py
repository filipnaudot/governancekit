"""
Shared interface of every constraint
"""

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Protocol

from governancekit.engine.decision import Decision
from governancekit.engine.events import Event


class Verdict(Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"


class ConstraintInstance(Protocol):
    def can_begin(
        self,
        event: Event,
        running: Mapping[str, Mapping[str, Event]],
        last_completed: Event | None,
    ) -> Decision:
        """Decides if the event may begin, given the running activities
        (activity -> {instance id -> event}) and the last completed activity"""

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        """Records that the event completed successfully"""

    def verdict(self) -> Verdict:
        """Current status: SATISFIED / VIOLATED"""
