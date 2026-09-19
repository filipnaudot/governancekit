"""
Text-to-MP-DECLARE parser
"""

import re
from collections import defaultdict

from core.mp_declare_model import ConstraintDef
from core.templates import Template

"""
For a line "Constraint[A, B] | ActCond | CorrCond | Deadline" it filters:
"Constraint", "A, B", "ActCond", "CorrCond", "Deadline"
"""
_CONSTRAINT_LINE = re.compile(r"^([^\[]+)\[([^\]]+)\]\s*\|([^|]*)\|([^|]*)\|(.*)$")


def parse_decl_text(text: str) -> list[ConstraintDef]:
    activities: set[str] = set()
    bindings: dict[str, set[str]] = defaultdict(set)
    domains: dict[str, set[str]] = defaultdict(set)
    constraint_lines: list[str] = []
    definitions: list[ConstraintDef] = []

    # Build symbol tables (Activities, Bindings, Domains)
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if line.startswith("activity "):
            _parse_activity(line, activities)

        elif line.startswith("bind "):
            _parse_binding(line, bindings)

        elif ":" in line and "[" not in line:
            _parse_domain(line, domains)

        else:
            constraint_lines.append(line)

    # Build Constraints
    for cl in constraint_lines:
        match = _CONSTRAINT_LINE.match(cl.strip())
        (
            template_name,
            bracket_body,
            activity_condition_text,
            correlation_condition_text,
            deadline_text,
        ) = match.groups()

        template = _parse_template(template_name)
        activation_activity, target_activity, count = _parse_bracket_body(
            bracket_body, activities
        )
        definitions.append(
            ConstraintDef(
                id=f"{template.value}_{len(definitions)}",
                template=template,
                activation_activity=activation_activity,
                target_activity=target_activity,
                count=count,
            )
        )

    return definitions


def _parse_activity(line: str, activities: set[str]) -> None:
    activities.add(line.removeprefix("activity ").strip())


def _parse_binding(line: str, bindings: dict[str, set[str]]) -> None:
    rest = line.removeprefix("bind ").strip()
    activity_name, attribute = rest.split(":", 1)
    bindings[activity_name.strip()].add(attribute.strip())


def _parse_domain(line: str, domains: dict[str, set[str]]) -> None:
    attribute, values = line.split(":", 1)
    for value in values.split(","):
        domains[attribute.strip()].add(value.strip())


def _parse_template(template_name: str):
    return Template[template_name.strip().upper().replace(" ", "_")]


def _parse_bracket_body(
    bracket_body: str, activities: set[str]
) -> tuple[str, str | None, int | None]:
    bracket_items = [item.strip() for item in bracket_body.split(",")]

    if not 1 <= len(bracket_items) <= 2:
        raise ValueError(
            f"expected 1 or 2 items, got {len(bracket_items)}: {bracket_body!r}"
        )

    activation = bracket_items[0]
    if activation not in activities:
        raise (ValueError(f"undeclared activity {activation!r} in {bracket_body!r}"))
    if len(bracket_items) == 1:
        return activation, None, None

    second = bracket_items[1]
    if second.isdigit():
        return activation, None, int(second)

    if second not in activities:
        raise (ValueError(f"undeclared activity {second!r} in {bracket_body!r}"))
    return activation, second, None


def _parse_activity_condition(activity_condition: str) -> None:
    pass


def _parse_correlation_condition(correlation_condition: str) -> None:
    pass


def _parse_deadline(deadline: str) -> None:
    pass
