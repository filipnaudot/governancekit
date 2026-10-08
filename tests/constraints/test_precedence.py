from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_activation_needs_a_completed_target():
    """DENIED without a target, WAIT while one runs, and only a completed target allows it"""
    m = monitor("Precedence[a, b]")
    assert decision(m, "b") is Decision.DENIED

    a = run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=False)
    assert decision(m, "b") is Decision.DENIED

    complete(m, "a")
    complete(m, "b")
    assert m.violations() == []


def test_only_matching_activations_are_blocked():
    """Targets, unrelated activities and activations not matching the condition are allowed"""
    m = monitor("Precedence[a, b] | A.kind is hard | |")

    assert decision(m, "b", kind="soft") is Decision.ALLOWED
    assert decision(m, "b", kind="hard") is Decision.DENIED
    assert decision(m, "a") is Decision.ALLOWED
    assert decision(m, "x") is Decision.ALLOWED


def test_correlation_only_counts_matching_targets():
    """Completed and running targets only count for activations they correlate with"""
    m = monitor("Precedence[a, b] | | same id |")
    complete(m, "a", id=1)
    run(m, "a", id=2)

    assert decision(m, "b", id=1) is Decision.ALLOWED
    assert decision(m, "b", id=2) is Decision.WAIT
    assert decision(m, "b", id=3) is Decision.DENIED


def test_time_window_is_measured_from_target_completion():
    """Too early gives WAIT, too late gives DENIED, measured from when the target completed"""
    m = monitor("Precedence[a, b] | | | 1,2,h")
    m.finish(run(m, "a"), completed=True, completed_at=hours(1))

    assert decision(m, "b", hours(1.5)) is Decision.WAIT
    assert decision(m, "b", hours(2.5)) is Decision.ALLOWED
    assert decision(m, "b", hours(3.5)) is Decision.DENIED
