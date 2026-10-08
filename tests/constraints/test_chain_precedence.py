from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_activation_must_directly_follow_a_target():
    """b is DENIED unless the last completion is a; anything completing in between breaks it"""
    m = monitor("ChainPrecedence[a, b]")
    assert decision(m, "b") is Decision.DENIED

    complete(m, "a")
    assert decision(m, "b") is Decision.ALLOWED

    complete(m, "x")
    assert decision(m, "b") is Decision.DENIED
    assert m.violations() == []


def test_running_activities_give_wait():
    """b waits while a or x runs, and x waits while b runs"""
    m = monitor("ChainPrecedence[a, b]")
    a = run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=True)
    x = run(m, "x")
    assert decision(m, "b") is Decision.WAIT

    m.finish(x, completed=False)
    run(m, "b")
    assert decision(m, "x") is Decision.WAIT


def test_correlating_targets_run_alongside_the_activation():
    """b may begin while another a runs and a while b runs, but not with a time condition"""
    m = monitor("ChainPrecedence[a, b]")
    complete(m, "a")
    run(m, "a")
    assert decision(m, "b") is Decision.ALLOWED

    run(m, "b")
    assert decision(m, "a") is Decision.ALLOWED

    timed = monitor("ChainPrecedence[a, b] | | | 0,1,h")
    complete(timed, "a")
    run(timed, "a")
    assert decision(timed, "b") is Decision.WAIT


def test_time_window_is_measured_from_target_completion():
    """b is WAIT before the window opens, then DENIED, also while another b runs"""
    m = monitor("ChainPrecedence[a, b] | | | 1,2,h")
    m.finish(run(m, "a"), completed=True, completed_at=hours(1))

    assert decision(m, "b", hours(1.5)) is Decision.WAIT
    assert decision(m, "b", hours(2.5)) is Decision.ALLOWED
    assert decision(m, "b", hours(3.5)) is Decision.DENIED

    run(m, "b", hours(2.5))
    assert decision(m, "b", hours(3.5)) is Decision.DENIED
