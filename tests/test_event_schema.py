"""
Checking events against a model's declared activities, bindings and domains.
"""

from datetime import UTC, datetime

import pytest

from governancekit.engine.event_schema import (
    EnumDomain,
    EventSchema,
    InvalidEventError,
    RangeDomain,
)
from governancekit.engine.events import Event

SCHEMA = EventSchema(
    activities=frozenset({"refund", "login"}),
    bindings={"refund": frozenset({"amount", "status"})},
    domains={
        "amount": RangeDomain(int, 0, 100),
        "status": EnumDomain(frozenset({"open", "closed"})),
    },
)


def _problems(activity: str, payload: dict) -> list[str]:
    with pytest.raises(InvalidEventError) as error:
        SCHEMA.validate(Event(activity, datetime.now(UTC), payload))
    return error.value.problems


@pytest.mark.parametrize("value", [0, 50, 100])
def test_integer_range_accepts_ints_within_bounds(value):
    assert RangeDomain(int, 0, 100).contains(value)


@pytest.mark.parametrize("value", [-1, 101, 50.0, "50", True])
def test_integer_range_rejects_other_values(value):
    assert not RangeDomain(int, 0, 100).contains(value)


@pytest.mark.parametrize("value", [0, 1, 0.5])
def test_float_range_accepts_numbers_within_bounds(value):
    assert RangeDomain(float, 0.0, 1.0).contains(value)


@pytest.mark.parametrize("value", [1.5, "0.5", True, float("nan")])
def test_float_range_rejects_other_values(value):
    assert not RangeDomain(float, 0.0, 1.0).contains(value)


def test_enum_domain_compares_as_text():
    domain = EnumDomain(frozenset({"1", "open"}))

    assert domain.contains(1) and domain.contains("open")
    assert not domain.contains("closed")


def test_valid_event_passes_and_extra_attributes_are_ignored():
    SCHEMA.validate(
        Event("refund", datetime.now(UTC), {"amount": 5, "status": "open", "note": "x"})
    )
    SCHEMA.validate(Event("login", datetime.now(UTC), {"user": "alice"}))


def test_undeclared_activity():
    assert _problems("delete", {}) == ["undeclared activity 'delete'"]


def test_all_problems_are_reported_and_null_counts_as_missing():
    assert _problems("refund", {"amount": 500, "status": None}) == [
        "'amount' is not an integer between 0 and 100: 500",
        "missing attribute 'status'",
    ]
