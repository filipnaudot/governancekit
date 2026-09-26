import pytest

from core.decl_parser import parse_decl_text
from core.templates import Template


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
