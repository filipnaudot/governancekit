"""
Enum class for the answer to whether an activity may begin
"""

from enum import Enum


class Decision(Enum):
    ALLOWED = "allowed"  # may run now
    WAIT = "wait"  # not now, may become allowed later
    DENIED = "denied"  # would permanently violate the model
