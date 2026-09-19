"""
Shared interface of every consraint
"""

from enum import Enum
from typing import Protocol

from core.events import Event


class Verdict(Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"


class ConstraintInstance(Protocol):
    def check(self, event: Event) -> bool:
        """Checks if the event is acceptable according to the constraint"""

    def commit(self, event: Event) -> None:
        """Records that the specified event has been executed"""

    def verdict(self) -> Verdict:
        """Current status: SATISFIED / VIOLATED"""
