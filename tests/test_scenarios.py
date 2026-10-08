"""
Several constraints together: combining decisions, which constraints are asked, and a parsed model.
"""

from conftest import T0, complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision
from governancekit.engine.events import Event


def test_strictest_decision_wins_and_every_blocker_is_reported():
    """DENIED beats WAIT, WAIT beats ALLOWED, and blocking lists every constraint that didn't allow it"""
    m = monitor("Precedence[a, c]", "Precedence[b, c]", "Existence[c]")
    run(m, "a")
    assert m.begin(Event("c", T0)) == (
        Decision.DENIED,
        None,
        ["Precedence[a, c] | | |", "Precedence[b, c] | | |"],
    )

    complete(m, "b")
    assert m.check(Event("c", T0)) == (Decision.WAIT, ["Precedence[a, c] | | |"])


def test_check_reserves_nothing():
    """check gives the same answer as begin, but only begin makes the activity running"""
    m = monitor("Absence[a, 2]")
    assert m.check(Event("a", T0)) == (Decision.ALLOWED, [])
    assert m.running == {}

    run(m, "a")
    assert decision(m, "a") is Decision.WAIT


def test_ordering_constraints_hear_about_every_activity():
    """Init and End are affected by unrelated activities; other constraints only by their own"""
    m = monitor("Init[s]", "End[e]", "Response[a, b]")
    assert decision(m, "x") is Decision.DENIED

    complete(m, "s")
    complete(m, "e")
    assert m.violations() == []

    complete(m, "x")
    assert m.violations() == ["End[e] | | |"]


def test_unrelated_activities_run_concurrently():
    """Activities only wait for running ones that can affect them"""
    m = monitor(
        "Precedence[a, b]",
        "Absence[c, 3]",
        "NotCoExistence[d, e] | | same id |",
    )
    a = run(m, "a")
    run(m, "c")
    run(m, "c")
    run(m, "d", id=1)

    assert decision(m, "b") is Decision.WAIT
    assert decision(m, "c") is Decision.WAIT
    assert decision(m, "e", id=1) is Decision.WAIT
    assert decision(m, "e", id=2) is Decision.ALLOWED
    assert decision(m, "x") is Decision.ALLOWED

    m.finish(a, completed=True)
    assert decision(m, "b") is Decision.ALLOWED


def test_support_agent_flow():
    """A refund needs a login and a verified customer, at most one large refund, and a notification within an hour"""
    m = monitor(
        "Init[login]",
        "Precedence[verify, refund] | | same customer |",
        "Absence[refund, 2] | A.amount > 100 | |",
        "Response[refund, notify] | | same customer | 0,1,h",
        "NotCoExistence[escalate, refund] | | same customer |",
    )
    assert decision(m, "refund", customer=1, amount=500) is Decision.DENIED

    complete(m, "login")
    verify = run(m, "verify", customer=1)
    assert decision(m, "refund", customer=1, amount=500) is Decision.WAIT
    assert decision(m, "refund", customer=2, amount=500) is Decision.DENIED

    m.finish(verify, completed=True)
    complete(m, "refund", customer=1, amount=500)
    assert m.violations() == ["Response[refund, notify] | | same customer | 0,1,h"]

    assert decision(m, "refund", customer=1, amount=200) is Decision.DENIED
    assert decision(m, "refund", customer=1, amount=20) is Decision.ALLOWED
    assert decision(m, "escalate", customer=1) is Decision.DENIED
    assert decision(m, "escalate", customer=2) is Decision.ALLOWED

    complete(m, "notify", hours(0.5), customer=1)
    assert m.violations() == []
