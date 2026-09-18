"""
Dataclass representing an event
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    activity: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)
