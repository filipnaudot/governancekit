from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_second_activity_needs_a_completed_first():
    """b is DENIED without an a, WAIT while one runs, and ALLOWED once one completed"""
    m = monitor("Succession[a, b]")
    assert decision(m, "b") is Decision.DENIED

    a = run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=True)
    assert decision(m, "b") is Decision.ALLOWED


def test_first_activity_needs_a_later_second():
    """Violated while an a has no b after it"""
    m = monitor("Succession[a, b]")
    complete(m, "a")
    assert m.violations() != []

    complete(m, "b")
    assert m.violations() == []

    complete(m, "a")
    assert m.violations() != []


def test_time_window_is_measured_from_first_completion():
    """b is WAIT before the window opens and DENIED after it closed"""
    m = monitor("Succession[a, b] | | | 1,2,h")
    m.finish(run(m, "a"), completed=True, completed_at=hours(1))

    assert decision(m, "b", hours(1.5)) is Decision.WAIT
    assert decision(m, "b", hours(2.5)) is Decision.ALLOWED
    assert decision(m, "b", hours(3.5)) is Decision.DENIED
