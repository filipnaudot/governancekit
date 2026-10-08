from conftest import complete, decision, monitor, run

from governancekit.engine.decision import Decision


def test_absence_without_count_forbids_the_activity():
    """Absence[a] never allows a; other activities are unaffected"""
    m = monitor("Absence[a]")

    assert decision(m, "a") is Decision.DENIED
    assert decision(m, "x") is Decision.ALLOWED


def test_running_instances_count_against_the_limit():
    """Absence[a, 3] allows two a's: WAIT while a running one would reach the limit, DENIED once completed"""
    m = monitor("Absence[a, 3]")
    complete(m, "a")
    second = run(m, "a")
    assert decision(m, "a") is Decision.WAIT

    m.finish(second, completed=False)
    assert decision(m, "a") is Decision.ALLOWED

    complete(m, "a")
    assert decision(m, "a") is Decision.DENIED
    assert m.violations() == []


def test_only_matching_activations_count():
    """Activations not matching the condition are allowed and don't count"""
    m = monitor("Absence[a, 2] | A.kind is hard | |")
    complete(m, "a", kind="soft")
    complete(m, "a", kind="hard")

    assert decision(m, "a", kind="soft") is Decision.ALLOWED
    assert decision(m, "a", kind="hard") is Decision.DENIED
