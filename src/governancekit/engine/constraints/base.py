"""
Shared interface of every constraint

Conventions of all implementations:
- Only successful completions count, in completion order.
- Stored events get their completion time as timestamp, while the new event keeps
  its begin time, so time conditions compare the earlier activity's completion
  with the later one's begin.
- A target is never used up: it satisfies every activation it matches (except in
  the Alternate templates).
- Without correlation and time conditions every pair matches, so one stored event
  per list stands for all of them (`_keep_all`).
- An earlier activity that is still running has no completion time yet, so only
  its correlation can be checked. A later activity that is already running has a
  known begin time, so its time condition is checked too.
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
    ) -> Decision:
        """Decides if the event may begin, given the running activities
        (activity -> {instance id -> event}).

        ALLOWED: the event completing can't permanently violate the constraint,
            whatever the running activities do (complete in any order, fail or abort).
        WAIT: not allowed now, but a running activity finishing or a time window
            passing could make it allowed.
        DENIED: neither; the event completing would permanently violate the
            constraint, unless other activities happen first.
        An obligation that can no longer be met (its time window has passed)
        doesn't block anything.
        """

    def on_finish(self, event: Event, completed_at: datetime) -> None:
        """Records that the event completed successfully"""

    def verdict(self) -> Verdict:
        """Current status: SATISFIED / VIOLATED"""
