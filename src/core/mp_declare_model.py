"""
Static MP-DECLARE Model
"""

from collections import defaultdict
from dataclasses import dataclass

from core.templates import Template


@dataclass(frozen=True)
class ConstraintDef:
    id: str
    template: Template
    activation_activity: str
    target_activity: str | None = None
    count: int | None = None


@dataclass(frozen=True, slots=True)
class MPDeclareModel:
    constraints: tuple[ConstraintDef, ...]
    activity_index: dict[str, tuple[int, ...]]

    @classmethod
    def build(cls, constraints: list[ConstraintDef]):
        constraints = tuple(constraints)
        index: dict[str, list[int]] = defaultdict(list)

        for i, c in enumerate(constraints):
            index[c.activation_activity].append(i)
            if c.target_activity and c.target_activity != c.activation_activity:
                index[c.target_activity].append(i)

        return cls(
            constraints=constraints,
            activity_index={k: tuple(v) for k, v in index.items()},
        )
