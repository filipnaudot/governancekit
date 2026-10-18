import re

import pytest

from governancekit.engine.decl_parser import (
    DeclSyntaxError,
    EnumDomain,
    RangeDomain,
    parse_decl_text,
)
from governancekit.engine.templates import Template


def test_parse_unary():
    definitions = parse_decl_text("""
        activity login
        Existence[login] |||
    """).constraints

    assert len(definitions) == 1
    assert definitions[0].template == Template.EXISTENCE
    assert definitions[0].activation_activity == "login"


def test_parse_unary_with_count():
    definitions = parse_decl_text("""
        activity login
        Existence[login, 5] |||
    """).constraints

    assert len(definitions) == 1
    assert definitions[0].template == Template.EXISTENCE
    assert definitions[0].activation_activity == "login"
    assert definitions[0].count == 5


@pytest.mark.parametrize(
    ("line", "template"),
    [
        ("Init[a] |||", Template.INIT),
        ("End[a] |||", Template.END),
        ("Absence[a] |||", Template.ABSENCE),
        ("Exactly[a] |||", Template.EXACTLY),
    ],
)
def test_parse_unary_templates(line, template):
    definitions = parse_decl_text(f"activity a\n{line}").constraints

    assert definitions[0].template == template
    assert definitions[0].activation_activity == "a"
    assert definitions[0].target_activity is None


def test_parse_absence_with_count():
    definitions = parse_decl_text("activity a\nAbsence[a, 2] |||").constraints

    assert definitions[0].count == 2


@pytest.mark.parametrize(
    ("name", "template"),
    [
        ("Chain Response", Template.CHAIN_RESPONSE),
        ("ChainResponse", Template.CHAIN_RESPONSE),
        ("Co-Existence", Template.CO_EXISTENCE),
        ("Not Co-Existence", Template.NOT_CO_EXISTENCE),
    ],
)
def test_template_names_ignore_spaces_and_hyphens(name, template):
    definitions = parse_decl_text(f"activity a\nactivity b\n{name}[a, b] |||").constraints

    assert definitions[0].template == template


@pytest.mark.parametrize("template", list(Template), ids=lambda t: t.value)
def test_every_template_parses_by_its_name(template):
    unary = {
        Template.EXISTENCE,
        Template.ABSENCE,
        Template.EXACTLY,
        Template.INIT,
        Template.END,
    }
    args = "a" if template in unary else "a, b"
    definitions = parse_decl_text(
        f"activity a\nactivity b\n{template.value}[{args}] |||"
    ).constraints

    assert definitions[0].template == template


@pytest.mark.parametrize(
    "name",
    [
        "Precedence",
        "Alternate Precedence",
        "Chain Precedence",
        "Not Precedence",
        "Not Chain Precedence",
    ],
)
def test_precedence_templates_activate_on_second_activity(name):
    definitions = parse_decl_text(f"activity a\nactivity b\n{name}[a, b] |||").constraints

    assert definitions[0].activation_activity == "b"
    assert definitions[0].target_activity == "a"


def test_response_activates_on_first_activity():
    definitions = parse_decl_text("activity a\nactivity b\nResponse[a, b] |||").constraints

    assert definitions[0].activation_activity == "a"
    assert definitions[0].target_activity == "b"


def test_undeclared_activity_raises():
    with pytest.raises(ValueError):
        parse_decl_text("Existence[login, 5] |||")


@pytest.mark.parametrize("bracket", ["", "a, b, c"])
def test_invalid_bracket_item_count_raises(bracket):
    with pytest.raises(ValueError):
        parse_decl_text(f"""
            activity a
            activity b
            activity c
            Existence[{bracket}] |||
        """)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("Response[a, b]", "expected 'Template"),
        ("Foo[a, b] |||", "unknown template 'Foo'"),
        ("Absence[a, x] |||", "count must be a positive integer, got 'x'"),
        ("Absence[a, 0] |||", "count must be a positive integer, got '0'"),
        ("Init[a, 3] |||", "init takes no count"),
        ("Absence[a, ] |||", "empty item"),
        ("bind a", "expected 'bind activity: attribute, ...'"),
        ("bind x: n", "undeclared activity 'x'"),
    ],
)
def test_invalid_line_raises_with_line_number(line, message):
    """Every invalid line raises DeclSyntaxError with its line number and a clear reason."""
    with pytest.raises(DeclSyntaxError, match=f"^line 3: {re.escape(message)}"):
        parse_decl_text(f"activity a\nactivity b\n{line}")


@pytest.mark.parametrize(
    "line",
    [
        "Response[a, b] | A.n > 1 | |",
        "Response[a, b] | | T.n > 1 |",
        "Response[a, b] | | same n |",
    ],
)
def test_attribute_must_be_bound_to_its_activity(line):
    """A. refers to the activation activity and T. to the target; same/different to both."""
    with pytest.raises(DeclSyntaxError, match="attribute 'n' is not bound"):
        parse_decl_text(f"activity a\nactivity b\nbind a: m\nbind b: m\n{line}")

    parse_decl_text(f"activity a\nactivity b\nbind a: n\nbind b: n\n{line}")


def test_symmetric_activation_condition_needs_both_bindings():
    """In a symmetric template the activation condition applies to both activities."""
    text = "activity a\nactivity b\nbind a: n\n"
    with pytest.raises(DeclSyntaxError, match="'n' is not bound to activity 'b'"):
        parse_decl_text(text + "Choice[a, b] | A.n > 1 | |")

    parse_decl_text(text + "Response[a, b] | A.n > 1 | |")


def test_bindings_and_domains_are_returned():
    """Bound attributes are split on commas; domains are enumerations or ranges."""
    parsed = parse_decl_text("""
        activity a
        bind a: status, amount
        bind a: score
        status: open, closed
        amount: integer between 0 and 100
        score: float between 0 and 1.5
    """)

    assert parsed.activities == {"a"}
    assert parsed.bindings == {"a": {"status", "amount", "score"}}
    assert parsed.domains == {
        "status": EnumDomain(frozenset({"open", "closed"})),
        "amount": RangeDomain(int, 0, 100),
        "score": RangeDomain(float, 0.0, 1.5),
    }


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ("n: 1, 2", "attribute 'n' is not bound to any activity"),
        ("bind a: n\nn: 1\nn: 2", "attribute 'n' already has a domain"),
        ("bind a: n\nn: integer between 5 and 1", "low <= high"),
        ("bind a: n\nn: integer between a and b", "must be integer numbers"),
        ("bind a: n\nn: 1, , 2", "expected 'attribute: value, ...'"),
    ],
)
def test_invalid_domain_raises(lines, message):
    """A domain must belong to a bound attribute, be declared once and be well-formed."""
    with pytest.raises(DeclSyntaxError, match=re.escape(message)):
        parse_decl_text(f"activity a\n{lines}")


@pytest.mark.parametrize(
    ("domain", "condition", "message"),
    [
        ("open, closed", "A.n is opn", "'opn' is not in the domain of 'n'"),
        ("open, closed", "A.n in (open, shut)", "'shut' is not in the domain of 'n'"),
        ("integer between 0 and 9", "A.n > big", "'n' is a number, got 'big'"),
    ],
)
def test_condition_value_must_fit_domain(domain, condition, message):
    """Values compared with an attribute must be in its enumeration, or numbers for a range."""
    text = f"activity a\nactivity b\nbind a: n\nn: {domain}\n"
    with pytest.raises(DeclSyntaxError, match=re.escape(message)):
        parse_decl_text(text + f"Response[a, b] | {condition} | |")


def test_values_are_not_checked_without_domain_or_outside_range():
    """No domain means any value; a number outside a range is allowed."""
    text = "activity a\nactivity b\nbind a: n, m\nm: integer between 0 and 9\n"

    parse_decl_text(text + "Response[a, b] | A.n is anything and A.m > 100 | |")


def test_hash_inside_quotes_is_not_a_comment():
    """A # inside a quoted value is kept; one outside quotes starts a comment."""
    parsed = parse_decl_text(
        'activity a\nactivity b\nbind a: ref\nResponse[a, b] | A.ref is "#1" | | # note'
    )

    assert parsed.constraints[0].source == 'Response[a, b] | A.ref is "#1" | |'
