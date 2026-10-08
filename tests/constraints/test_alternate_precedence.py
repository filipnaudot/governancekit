from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_each_activation_needs_its_own_target():
    """b needs an a completed since the previous b: DENIED, WAIT while a runs, ALLOWED once completed"""
    m = monitor("AlternatePrecedence[a, b]")
    assert decision(m, "b") is Decision.DENIED

    a = run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=True)
    complete(m, "b")
    assert decision(m, "b") is Decision.DENIED
    assert m.violations() == []


def test_activations_are_exclusive_while_running():
    """A second b waits while one runs, as both could use the same a"""
    m = monitor("AlternatePrecedence[a, b]")
    complete(m, "a")
    run(m, "b")

    assert decision(m, "b") is Decision.WAIT


def test_running_activation_doesnt_hide_a_denial():
    """While a b runs, another b waits if it has a target, and is DENIED if it has none"""
    m = monitor("AlternatePrecedence[a, b] | | same id |")
    complete(m, "a", id=1)
    run(m, "b", id=1)

    assert decision(m, "b", id=1) is Decision.WAIT
    assert decision(m, "b", id=2) is Decision.DENIED


def test_time_window_is_measured_from_target_completion():
    """b is WAIT before the window opens and DENIED after it closed"""
    m = monitor("AlternatePrecedence[a, b] | | | 1,2,h")
    m.finish(run(m, "a"), completed=True, completed_at=hours(1))

    assert decision(m, "b", hours(1.5)) is Decision.WAIT
    assert decision(m, "b", hours(2.5)) is Decision.ALLOWED
    assert decision(m, "b", hours(3.5)) is Decision.DENIED
