from conftest import decision, monitor, run

from governancekit.engine.decision import Decision


def test_only_the_activation_may_begin_before_the_first_completion():
    """Other activities are DENIED, WAIT while an activation runs, and ALLOWED after it completed"""
    m = monitor("Init[a]")
    assert decision(m, "x") is Decision.DENIED

    a = run(m, "a")
    assert decision(m, "x") is Decision.WAIT

    m.finish(a, completed=True)
    assert decision(m, "x") is Decision.ALLOWED
    assert m.violations() == []


def test_decided_by_the_first_completion_only():
    """An empty trace is violated; the first completion decides, a later failure changes nothing"""
    m = monitor("Init[a]")
    assert m.violations() == ["Init[a] | | |"]

    first, second = run(m, "a"), run(m, "a")
    m.finish(first, completed=True)
    m.finish(second, completed=False)
    assert m.violations() == []


def test_activation_condition_applies():
    """An activation not matching the condition counts as any other activity"""
    m = monitor("Init[a] | A.kind is hard | |")

    assert decision(m, "a", kind="soft") is Decision.DENIED
    assert decision(m, "a", kind="hard") is Decision.ALLOWED
