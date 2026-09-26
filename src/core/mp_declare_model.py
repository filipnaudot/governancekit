"""
Static MP-DECLARE Model
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from core.events import Event
from core.templates import Template

AFTER_TEMPLATES = frozenset({Template.CHAIN_RESPONSE, Template.CHAIN_SUCCESSION})


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
    activity_index: dict[str, tuple[int, ...]]  # activity -> candidate constraints
    after_index: dict[str, tuple[int, ...]]  # activation -> chain response constraints
    init_constraints: frozenset[int]  # init contraints

    @classmethod
    def build(cls, constraints: list[ConstraintDef]) -> Self:
        activity_index: dict[str, list[int]] = defaultdict(list)
        after_index: dict[str, list[int]] = defaultdict(list)
        init_constraints: set[int] = set()

        for i, c in enumerate(constraints):
            activity_index[c.activation_activity].append(i)
            if c.target_activity and c.target_activity != c.activation_activity:
                activity_index[c.target_activity].append(i)

            if c.template in AFTER_TEMPLATES:
                after_index[c.activation_activity].append(i)
            elif c.template is Template.INIT:
                init_constraints.add(i)

        return cls(
            constraints=tuple(constraints),
            activity_index={k: tuple(v) for k, v in activity_index.items()},
            after_index={k: tuple(v) for k, v in after_index.items()},
            init_constraints=frozenset(init_constraints),
        )
