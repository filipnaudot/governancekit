"""
Declared activities, bindings and domains of a model, and checking events against them
"""

import math
from dataclasses import dataclass
from typing import Any

from governancekit.engine.events import Event


class InvalidEventError(ValueError):
    """The event does not fit the model's activities, bindings or domains"""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True, slots=True)
class EnumDomain:
    """attribute: v1, v2, ..."""

    values: frozenset[str]

    def contains(self, value: Any) -> bool:
        # Compared as text, like is/in in conditions
        return str(value) in self.values

    def __str__(self) -> str:
        return "one of " + ", ".join(sorted(self.values))


@dataclass(frozen=True, slots=True)
class RangeDomain:
    """attribute: integer between low and high, or float between low and high"""

    type: type[int] | type[float]
    low: int | float
    high: int | float

    def contains(self, value: Any) -> bool:
        # bool is a subclass of int, but True is not the number 1 here
        if isinstance(value, bool):
            return False
        allowed = int if self.type is int else (int, float)
        if not isinstance(value, allowed) or math.isnan(value):
            return False
        return self.low <= value <= self.high

    def __str__(self) -> str:
        kind = "an integer" if self.type is int else "a float"
        return f"{kind} between {self.low} and {self.high}"


Domain = EnumDomain | RangeDomain


@dataclass(frozen=True, slots=True)
class EventSchema:
    activities: frozenset[str]
    bindings: dict[str, frozenset[str]]  # activity -> attributes of its payload
    domains: dict[str, Domain]  # attribute -> allowed values

    def validate(self, event: Event) -> None:
        """Raise InvalidEventError listing every problem with the event.

        The activity must be declared, every bound attribute present and not
        null, and its value in the attribute's domain. Other attributes are ignored.
        """
        if event.activity not in self.activities:
            raise InvalidEventError([f"undeclared activity {event.activity!r}"])

        problems = []
        for name in sorted(self.bindings.get(event.activity, ())):
            value = event.payload.get(name)
            domain = self.domains.get(name)
            if value is None:
                problems.append(f"missing attribute {name!r}")
            elif domain is not None and not domain.contains(value):
                problems.append(f"{name!r} is not {domain}: {value!r}")
        if problems:
            raise InvalidEventError(problems)
