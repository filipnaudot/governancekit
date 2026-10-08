from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_activation_needs_a_later_target():
    """A target before the activation doesn't count; one later target answers all earlier activations"""
    m = monitor("Response[a, b]")
    complete(m, "b")
    complete(m, "a")
    complete(m, "a")
    assert decision(m, "x") is Decision.ALLOWED
    assert m.violations() != []

    complete(m, "b")
    assert m.violations() == []


def test_only_correlating_targets_count():
    """A target only answers the activations it correlates with"""
    m = monitor("Response[a, b] | | same id |")
    complete(m, "a", id=1)
    complete(m, "a", id=2)
    complete(m, "b", id=1)
    assert m.violations() != []

    complete(m, "b", id=2)
    assert m.violations() == []


def test_target_must_begin_within_the_time_window():
    """The window runs from the activation's completion to the target's begin"""
    late = monitor("Response[a, b] | | | 0,1,h")
    complete(late, "a")
    complete(late, "b", hours(2))
    assert late.violations() != []

    in_time = monitor("Response[a, b] | | | 0,1,h")
    in_time.finish(run(in_time, "a"), completed=True, completed_at=hours(1))
    in_time.finish(run(in_time, "b", hours(1.5)), completed=True, completed_at=hours(3))
    assert in_time.violations() == []
