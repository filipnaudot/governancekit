"""
Dataclass representing an event
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class Event:
    activity: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def now(cls, activity: str, payload: dict[str, Any] | None = None) -> Self:
        """Create an event timestamped with the current UTC time"""
        return cls(activity, datetime.now(UTC), payload or {})
