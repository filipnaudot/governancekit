"""
Static MP-DECLARE Model
"""

from dataclasses import dataclass

from core.templates import Template


@dataclass(frozen=True)
class ConstraintDef:
    id: str
    template: Template
    activation_activity: str
    target_activity: str | None = None


@dataclass(frozen=True, slots=True)
class MPDeclareModel:
    constraints: tuple[ConstraintDef, ...]
    activity_index: dict[str, tuple[int, ...]]
