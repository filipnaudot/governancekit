"""
Static MP-DECLARE Model
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from core.events import Event
from core.templates import Template

# Can never be permanently violated by an event, so never block an activity from beginning
NEVER_BLOCKING_TEMPLATES = frozenset(
    {
        Template.EXISTENCE,
        Template.END,
        Template.CHOICE,
        Template.RESPONDED_EXISTENCE,
        Template.CO_EXISTENCE,
        Template.RESPONSE,
    }
)

# Constrain which activity completes first or next, so any activity can violate them
ORDERING_TEMPLATES = frozenset(
    {
        Template.INIT,
        Template.CHAIN_RESPONSE,
        Template.CHAIN_PRECEDENCE,
        Template.CHAIN_SUCCESSION,
    }
)


@dataclass(frozen=True)
class ConstraintDef:
    id: str
    source: str
    template: Template
    activation_activity: str
    target_activity: str | None = None
    count: int | None = None
    activation_condition: Callable[[Event], bool] | None = None
    correlation_condition: Callable[[Event, Event], bool] | None = None
    time_condition: Callable[[Event, Event], bool] | None = None


@dataclass(frozen=True, slots=True)
class MPDeclareModel:
    constraints: tuple[ConstraintDef, ...]
    begin_index: dict[str, tuple[int, ...]]  # activity -> blocking constraints mentioning it
    finish_index: dict[str, tuple[int, ...]]  # activity -> non-ordering constraints mentioning it
    ordering_constraints: tuple[int, ...]  # asked on every begin and finish

    @classmethod
    def build(cls, constraints: list[ConstraintDef]) -> Self:
        begin_index: dict[str, list[int]] = defaultdict(list)
        finish_index: dict[str, list[int]] = defaultdict(list)
        ordering_constraints: list[int] = []

        for i, c in enumerate(constraints):
            if c.template in ORDERING_TEMPLATES:
                ordering_constraints.append(i)
                continue

            activities = {c.activation_activity}
            if c.target_activity:
                activities.add(c.target_activity)
            for activity in activities:
                finish_index[activity].append(i)
                if c.template not in NEVER_BLOCKING_TEMPLATES:
                    begin_index[activity].append(i)

        return cls(
            constraints=tuple(constraints),
            begin_index={k: tuple(v) for k, v in begin_index.items()},
            finish_index={k: tuple(v) for k, v in finish_index.items()},
            ordering_constraints=tuple(ordering_constraints),
        )
