"""
Text-to-MP-DECLARE parser
"""

import re
from collections import defaultdict
from dataclasses import dataclass

from governancekit.engine.conditions import (
    create_activation_condition,
    create_correlation_condition,
    create_time_condition,
)
from governancekit.engine.event_schema import Domain, EnumDomain, RangeDomain
from governancekit.engine.mp_declare_model import ConstraintDef
from governancekit.engine.templates import Template


class DeclSyntaxError(ValueError):
    """The .decl text is not valid MP-DECLARE"""


@dataclass(frozen=True, slots=True)
class ParsedDecl:
    constraints: list[ConstraintDef]
    activities: frozenset[str]
    bindings: dict[str, frozenset[str]]  # activity -> attributes of its payload
    domains: dict[str, Domain]  # attribute -> allowed values


"""
For a line "Constraint[A, B] | ActCond | CorrCond | Deadline" it filters:
"Constraint", "A, B", "ActCond", "CorrCond", "Deadline"
"""
_CONSTRAINT_LINE = re.compile(r"^([^\[]+)\[([^\]]+)\]\s*\|([^|]*)\|([^|]*)\|(.*)$")

"""
A quoted string (kept, so a # inside it is not a comment) or a comment (removed)
"""
_COMMENT = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|#.*""")

"""
For a domain "integer between 0 and 50000" it filters: "integer", "0", "50000"
"""
_RANGE = re.compile(r"(integer|float)\s+between\s+(\S+)\s+and\s+(\S+)", re.IGNORECASE)

"""
Position of activation activity within the bracket body of a constraint (default 0)
"""
_ACTIVATION_ARG = {
    Template.PRECEDENCE: 1,
    Template.ALTERNATE_PRECEDENCE: 1,
    Template.CHAIN_PRECEDENCE: 1,
    Template.NOT_PRECEDENCE: 1,
    Template.NOT_CHAIN_PRECEDENCE: 1,
}

"""
Unary constraints that take an optional count
"""
_COUNTED = {
    Template.EXISTENCE,
    Template.ABSENCE,
    Template.EXACTLY,
}

"""
Unary constraints
"""
_UNARY = _COUNTED | {
    Template.INIT,
    Template.END,
}

"""
Symmetric constraints: the activation condition applies to both activities
"""
_SYMMETRIC = {
    Template.CHOICE,
    Template.EXCLUSIVE_CHOICE,
    Template.CO_EXISTENCE,
    Template.SUCCESSION,
    Template.ALTERNATE_SUCCESSION,
    Template.CHAIN_SUCCESSION,
    Template.NOT_CO_EXISTENCE,
    Template.NOT_SUCCESSION,
}

"""
Template names are matched ignoring case, spaces and hyphens, as in Declare4Py:
"Chain Response", "ChainResponse" and "Co-Existence" all work
"""
_TEMPLATES_BY_NAME = {t.value.replace(" ", "").replace("-", ""): t for t in Template}


def parse_decl_text(text: str) -> ParsedDecl:
    """Parse .decl text into its constraints, activities, bindings and domains.

    Raises DeclSyntaxError (a ValueError) with the line number for any invalid line.
    """
    activities: set[str] = set()
    bindings: dict[str, set[str]] = defaultdict(set)
    domains: dict[str, Domain] = {}
    constraints: list[ConstraintDef] = []

    lines = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = _COMMENT.sub(lambda m: m[1] or "", raw_line).strip()
        if line:
            lines.append((line_no, _kind(line), line))

    # Each kind needs the ones before it, so declarations may appear anywhere in the text
    for kind in ("activity", "bind", "domain", "constraint"):
        for line_no, line_kind, line in lines:
            if line_kind != kind:
                continue
            try:
                if kind == "activity":
                    activities.add(line.removeprefix("activity ").strip())
                elif kind == "bind":
                    _parse_binding(line, activities, bindings)
                elif kind == "domain":
                    _parse_domain(line, bindings, domains)
                else:
                    constraints.append(
                        _parse_constraint(
                            line, len(constraints), activities, bindings, domains
                        )
                    )
            except (ValueError, TypeError) as e:
                raise DeclSyntaxError(f"line {line_no}: {e} in {line!r}") from e

    return ParsedDecl(
        constraints=constraints,
        activities=frozenset(activities),
        bindings={activity: frozenset(attrs) for activity, attrs in bindings.items()},
        domains=domains,
    )


def _kind(line: str) -> str:
    if line.startswith("activity "):
        return "activity"
    if line.startswith("bind "):
        return "bind"
    if ":" in line and "[" not in line:
        return "domain"
    return "constraint"


def _parse_binding(
    line: str, activities: set[str], bindings: dict[str, set[str]]
) -> None:
    activity, colon, attributes = line.removeprefix("bind ").partition(":")
    names = [name.strip() for name in attributes.split(",")]
    if not colon or not all(names):
        raise ValueError("expected 'bind activity: attribute, ...'")
    bindings[_require_declared_activity(activity.strip(), activities)].update(names)


def _parse_domain(
    line: str, bindings: dict[str, set[str]], domains: dict[str, Domain]
) -> None:
    attribute, _, text = line.partition(":")
    attribute = attribute.strip()
    if not any(attribute in attributes for attributes in bindings.values()):
        raise ValueError(f"attribute {attribute!r} is not bound to any activity")
    if attribute in domains:
        raise ValueError(f"attribute {attribute!r} already has a domain")
    domains[attribute] = _parse_domain_values(text.strip())


def _parse_domain_values(text: str) -> Domain:
    if match := _RANGE.fullmatch(text):
        kind, low_text, high_text = match.groups()
        number = int if kind.lower() == "integer" else float
        try:
            low, high = number(low_text), number(high_text)
        except ValueError:
            raise ValueError(
                f"range bounds must be {kind.lower()} numbers, got {text!r}"
            ) from None
        if not low <= high:
            raise ValueError(f"range must satisfy low <= high, got {text!r}")
        return RangeDomain(number, low, high)

    values = [value.strip() for value in text.split(",")]
    if not all(values):
        raise ValueError("expected 'attribute: value, ...'")
    return EnumDomain(frozenset(values))


def _parse_constraint(
    line: str,
    index: int,
    activities: set[str],
    bindings: dict[str, set[str]],
    domains: dict[str, Domain],
) -> ConstraintDef:
    match = _CONSTRAINT_LINE.match(line)
    if match is None:
        raise ValueError(
            "expected 'Template[activities] | activation condition"
            " | correlation condition | time window'"
        )
    (
        template_name,
        bracket_body,
        activation_condition_text,
        correlation_condition_text,
        deadline_text,
    ) = match.groups()

    template = _parse_template(template_name)
    activation_activity, target_activity, count = _parse_bracket_body(
        template, bracket_body, activities
    )
    definition = ConstraintDef(
        id=f"{template.value}_{index}",
        source=line,
        template=template,
        activation_activity=activation_activity,
        target_activity=target_activity,
        count=count,
        activation_condition=create_activation_condition(activation_condition_text),
        correlation_condition=create_correlation_condition(correlation_condition_text),
        time_condition=create_time_condition(deadline_text),
    )
    _check_conditions(definition, bindings, domains)
    return definition


def _parse_template(template_name: str) -> Template:
    template = _TEMPLATES_BY_NAME.get(
        template_name.replace(" ", "").replace("-", "").lower()
    )
    if template is None:
        raise ValueError(f"unknown template {template_name.strip()!r}")
    return template


def _parse_bracket_body(
    template: Template, bracket_body: str, activities: set[str]
) -> tuple[str, str | None, int | None]:
    bracket_items = [item.strip() for item in bracket_body.split(",")]
    if not all(bracket_items):
        raise ValueError(f"empty item in [{bracket_body}]")

    if template in _UNARY:
        if len(bracket_items) > 2:
            raise ValueError(
                f"{template.value} takes one activity and an optional count,"
                f" got [{bracket_body}]"
            )
        activity = _require_declared_activity(bracket_items[0], activities)
        if len(bracket_items) == 1:
            return activity, None, None
        if template not in _COUNTED:
            raise ValueError(f"{template.value} takes no count")
        return activity, None, _parse_count(bracket_items[1])

    if len(bracket_items) != 2:
        raise ValueError(f"{template.value} takes two activities, got [{bracket_body}]")

    for item in bracket_items:
        _require_declared_activity(item, activities)

    activation_index = _ACTIVATION_ARG.get(template, 0)
    return bracket_items[activation_index], bracket_items[1 - activation_index], None


def _parse_count(item: str) -> int:
    if not (item.isascii() and item.isdigit()) or int(item) < 1:
        raise ValueError(f"count must be a positive integer, got {item!r}")
    return int(item)


def _check_conditions(
    definition: ConstraintDef,
    bindings: dict[str, set[str]],
    domains: dict[str, Domain],
) -> None:
    """Every attribute in a condition must be bound to the activity it refers to,
    and every value it is compared with must fit the attribute's domain."""
    activation, target = definition.activation_activity, definition.target_activity
    activation_sides = {
        "a": (activation, target)
        if definition.template in _SYMMETRIC
        else (activation,)
    }
    correlation_sides = {"a": (activation,), "t": (target,)}

    for condition, sides in (
        (definition.activation_condition, activation_sides),
        (definition.correlation_condition, correlation_sides),
    ):
        if condition is None:
            continue
        for side, name in condition.attributes:
            for activity in sides[side]:
                if name not in bindings.get(activity, ()):
                    raise ValueError(
                        f"attribute {name!r} is not bound to activity {activity!r}"
                    )
        for _, name, value in condition.values:
            _check_value(name, value, domains.get(name))


def _check_value(name: str, value: str | float, domain: Domain | None) -> None:
    # is/in compare text, so enum values are compared as text
    if isinstance(domain, EnumDomain) and str(value) not in domain.values:
        raise ValueError(f"{value!r} is not in the domain of {name!r}")
    if isinstance(domain, RangeDomain) and isinstance(value, str):
        raise TypeError(f"{name!r} is a number, got {value!r}")


def _require_declared_activity(activity: str, activities: set[str]) -> str:
    if activity not in activities:
        raise ValueError(f"undeclared activity {activity!r}")
    return activity
