from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_next_activation_needs_a_target_first():
    """After a, the next a is DENIED, WAIT while b runs, and ALLOWED once b completed"""
    m = monitor("AlternateResponse[a, b]")
    complete(m, "a")
    assert decision(m, "a") is Decision.DENIED
    assert m.violations() != []

    b = run(m, "b")
    assert decision(m, "a") is Decision.WAIT

    m.finish(b, completed=True)
    assert decision(m, "a") is Decision.ALLOWED
    assert m.violations() == []


def test_activations_are_exclusive_while_running():
    """A second a waits while one runs; other activities are allowed"""
    m = monitor("AlternateResponse[a, b]")
    run(m, "a")

    assert decision(m, "a") is Decision.WAIT
    assert decision(m, "b") is Decision.ALLOWED
    assert decision(m, "x") is Decision.ALLOWED


def test_only_a_correlating_target_answers_the_activation():
    """A target that doesn't correlate leaves the activation pending"""
    m = monitor("AlternateResponse[a, b] | | same id |")
    complete(m, "a", id=1)
    complete(m, "b", id=2)

    assert decision(m, "a", id=3) is Decision.DENIED


def test_pending_activation_stops_blocking_after_its_window():
    """WAIT within the window, ALLOWED after it, unless a target that began in time still runs"""
    m = monitor("AlternateResponse[a, b] | | | 0,1,h")
    complete(m, "a")
    assert decision(m, "a", hours(0.5)) is Decision.WAIT
    assert decision(m, "a", hours(2)) is Decision.ALLOWED

    run(m, "b", hours(0.5))
    assert decision(m, "a", hours(2)) is Decision.WAIT
