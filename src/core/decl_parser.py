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

"""
Position of activation activity within the bracket body of a constraint
"""
_ACTIVATION_ARG = {
    Template.EXISTENCE: 0,
    Template.PRECEDENCE: 1,
}

"""
Unary constraints
"""
_UNARY = {
    Template.EXISTENCE,
}


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
            template, bracket_body, activities
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
    template: Template, bracket_body: str, activities: set[str]
) -> tuple[str, str | None, int | None]:
    bracket_items = [item.strip() for item in bracket_body.split(",")]

    if not 1 <= len(bracket_items) <= 2:
        raise ValueError(
            f"expected 1 or 2 items, got {len(bracket_items)}: {bracket_body!r}"
        )

    if template in _UNARY:
        activity = _require_declared_activity(
            bracket_items[0], activities, bracket_body
        )
        count = int(bracket_items[1]) if len(bracket_items) == 2 else None
        return activity, None, count

    if len(bracket_items != 2):
        raise ValueError(f"{template} requires 2 activities: {bracket_body!r}")

    for item in bracket_items:
        _require_declared_activity(item, activities, bracket_body)

    activation_index = _ACTIVATION_ARG.get(template, 0)
    return bracket_items[activation_index], bracket_items[1 - activation_index], None


def _parse_activity_condition(activity_condition: str) -> None:
    pass


def _parse_correlation_condition(correlation_condition: str) -> None:
    pass


def _parse_deadline(deadline: str) -> None:
    pass


def _require_declared_activity(
    activity: str, activities: set[str], context: str
) -> str:
    if activity not in activities:
        raise (ValueError(f"undeclared activity {activity!r} in {context!r}"))
    return activity
