from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_activities_must_alternate():
    """b can't come first; after a only b, after b only a"""
    m = monitor("AlternateSuccession[a, b]")
    assert decision(m, "b") is Decision.DENIED

    complete(m, "a")
    assert decision(m, "a") is Decision.DENIED
    assert decision(m, "b") is Decision.ALLOWED
    assert m.violations() != []

    complete(m, "b")
    assert decision(m, "b") is Decision.DENIED
    assert decision(m, "a") is Decision.ALLOWED
    assert m.violations() == []


def test_each_activity_is_exclusive_while_running():
    """While a runs, a and b wait; while b runs, b waits"""
    m = monitor("AlternateSuccession[a, b]")
    a = run(m, "a")
    assert decision(m, "a") is Decision.WAIT
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=True)
    run(m, "b")
    assert decision(m, "b") is Decision.WAIT


def test_running_second_activity_doesnt_hide_a_denial():
    """While a b runs, another b waits if it answers the pending a, and is DENIED if not"""
    m = monitor("AlternateSuccession[a, b] | | same id |")
    complete(m, "a", id=1)
    run(m, "b", id=1)

    assert decision(m, "b", id=1) is Decision.WAIT
    assert decision(m, "b", id=2) is Decision.DENIED


def test_time_window_after_the_first_activity():
    """b is WAIT before the window opens and DENIED after it closed; then a pending a stops blocking"""
    m = monitor("AlternateSuccession[a, b] | | | 1,2,h")
    complete(m, "a")

    assert decision(m, "b", hours(0.5)) is Decision.WAIT
    assert decision(m, "b", hours(1.5)) is Decision.ALLOWED
    assert decision(m, "b", hours(3)) is Decision.DENIED
    assert decision(m, "a", hours(3)) is Decision.ALLOWED
