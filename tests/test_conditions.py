from datetime import UTC, datetime, timedelta

import pytest

from core.conditions import (
    ConditionSyntaxError,
    create_activation_condition,
    create_correlation_condition,
    create_time_condition,
)
from core.events import Event

START = datetime(2026, 1, 1, tzinfo=UTC)


def make_event(payload: dict[str, object], seconds: float = 0) -> Event:
    return Event(
        activity="act", timestamp=START + timedelta(seconds=seconds), payload=payload
    )


A = make_event({"grade": 90, "score": 2.5, "org:group": "G1", "resource": "agent1"})
T = make_event({"grade": 95, "score": 3, "org:group": "G1", "resource": "agent2"})


def test_numeric_comparison():
    assert create_activation_condition("A.grade >= 90")(A)
    assert create_activation_condition("A.grade == 90")(A)
    assert create_activation_condition("A.grade <= 100")(A)
    assert not create_activation_condition("A.grade != 90")(A)
    assert create_activation_condition("A.score > 2.4")(A)
    assert create_activation_condition("A.score == 2.5")(A)
    assert create_activation_condition("A.score < 2.7")(A)
    assert not create_activation_condition("A.score != 2.5")(A)


def test_enumerations():
    assert create_activation_condition("A.org:group in (G1, G2)")(A)
    assert not create_activation_condition("A.org:group in (G2, G3)")(A)


def test_correlation():
    assert create_correlation_condition("A.org:group == T.org:group")(A, T)
    assert create_correlation_condition(
        "A.org:group == T.org:group AND A.resource != T.resource"
    )(A, T)
    assert not create_correlation_condition("A.grade > T.grade")(A, T)


@pytest.mark.parametrize(
    "condition",
    [
        "A.grade >",  # missing value
        "(A.grade > 90",  # unclosed bracket
        "A.x in (a, b",  # unclosed enumeration
        "T.grade > 1",  # T. in an activation condition
        "same resource",  # needs a target event
        "__import__('os').system('ls')",  # code injection
        "A.x > 1; import os",  # code injection
    ],
)
def test_invalid_activation_condition_raises(condition: str):
    with pytest.raises(ConditionSyntaxError):
        create_activation_condition(condition)


def test_time_condition():
    cond = create_time_condition("1,5,m")
    assert cond(A, make_event({}, seconds=120))
    assert cond(make_event({}, seconds=120), A)
    assert not cond(A, make_event({}, seconds=30))
    assert not cond(A, make_event({}, seconds=301))
    assert cond.bounds == (timedelta(minutes=1), timedelta(minutes=5))  # type: ignore[attr-defined])
