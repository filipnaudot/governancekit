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
    def handle_event(self, event: Event) -> None:
        pass

    def verdict(self) -> Verdict:
        pass
