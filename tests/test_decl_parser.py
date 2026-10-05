import pytest

from governancekit.engine.decl_parser import parse_decl_text
from governancekit.engine.templates import Template


def test_parse_unary():
    definitions = parse_decl_text("""
        activity login
        Existence[login] |||
    """)

    assert len(definitions) == 1
    assert definitions[0].template == Template.EXISTENCE
    assert definitions[0].activation_activity == "login"


def test_parse_unary_with_count():
    definitions = parse_decl_text("""
        activity login
        Existence[login, 5] |||
    """)

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
    definitions = parse_decl_text(f"activity a\n{line}")

    assert definitions[0].template == template
    assert definitions[0].activation_activity == "a"
    assert definitions[0].target_activity is None


def test_parse_absence_with_count():
    definitions = parse_decl_text("activity a\nAbsence[a, 2] |||")

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
    definitions = parse_decl_text(f"activity a\nactivity b\n{name}[a, b] |||")

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
    definitions = parse_decl_text(f"activity a\nactivity b\n{name}[a, b] |||")

    assert definitions[0].activation_activity == "b"
    assert definitions[0].target_activity == "a"


def test_response_activates_on_first_activity():
    definitions = parse_decl_text("activity a\nactivity b\nResponse[a, b] |||")

    assert definitions[0].activation_activity == "a"
    assert definitions[0].target_activity == "b"


def test_undeclared_activity_raises():
    with pytest.raises(ValueError):
        parse_decl_text("Existence[login, 5] |||")


@pytest.mark.parametrize("bracket", ["", "a, b, c"])
def test_invalid_bracket_item_count_raises(bracket):
    with pytest.raises(ValueError):
        parse_decl_text("""
            activity a
            activity b
            activity c
            Existence[{bracket}] |||
        """)
