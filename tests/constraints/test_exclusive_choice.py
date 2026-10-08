from conftest import complete, decision, monitor, run

from governancekit.engine.decision import Decision


def test_one_activity_excludes_the_other():
    """An empty trace is violated; after a completes, b is DENIED and a stays ALLOWED"""
    m = monitor("ExclusiveChoice[a, b]")
    assert m.violations() != []

    complete(m, "a")
    assert decision(m, "b") is Decision.DENIED
    assert decision(m, "a") is Decision.ALLOWED
    assert m.violations() == []


def test_running_counterpart_gives_wait():
    """WAIT while the other activity runs, ALLOWED again if it fails"""
    m = monitor("ExclusiveChoice[a, b]")
    b = run(m, "b")
    assert decision(m, "a") is Decision.WAIT

    m.finish(b, completed=False)
    assert decision(m, "a") is Decision.ALLOWED


def test_activation_condition_applies_to_both_activities():
    """Activities not matching the condition neither block nor are blocked"""
    m = monitor("ExclusiveChoice[a, b] | A.kind is hard | |")
    complete(m, "a", kind="hard")
    complete(m, "a", kind="soft")

    assert decision(m, "b", kind="soft") is Decision.ALLOWED
    assert decision(m, "b", kind="hard") is Decision.DENIED
