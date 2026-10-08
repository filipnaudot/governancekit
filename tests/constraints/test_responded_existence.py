from conftest import complete, decision, monitor

from governancekit.engine.decision import Decision


def test_activation_needs_a_target_before_or_after():
    """Violated while an activation has no target; a target before or after it satisfies it"""
    m = monitor("RespondedExistence[a, b]")
    complete(m, "a")
    assert m.violations() != []

    complete(m, "b")
    complete(m, "a")
    assert m.violations() == []


def test_never_blocks_and_only_correlating_targets_count():
    """Always ALLOWED; a target only satisfies activations it correlates with"""
    m = monitor("RespondedExistence[a, b] | | same id |")
    complete(m, "b", id=1)
    complete(m, "a", id=2)
    assert decision(m, "a", id=3) is Decision.ALLOWED
    assert m.violations() != []

    complete(m, "b", id=2)
    assert m.violations() == []
