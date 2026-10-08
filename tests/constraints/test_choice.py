from conftest import complete, decision, monitor

from governancekit.engine.decision import Decision


def test_satisfied_once_either_activity_completes():
    """An empty trace is violated; a or b satisfies it; nothing is ever blocked"""
    for activity in ("a", "b"):
        m = monitor("Choice[a, b]")
        assert m.violations() != []
        assert decision(m, activity) is Decision.ALLOWED

        complete(m, activity)
        assert m.violations() == []


def test_activation_condition_applies_to_both_activities():
    """Completions not matching the condition don't count, for either activity"""
    m = monitor("Choice[a, b] | A.kind is hard | |")
    complete(m, "a", kind="soft")
    complete(m, "b", kind="soft")
    assert m.violations() != []

    complete(m, "b", kind="hard")
    assert m.violations() == []
