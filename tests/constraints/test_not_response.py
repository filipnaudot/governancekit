from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_target_may_not_follow_an_activation():
    """b after a is DENIED; a after b is ALLOWED"""
    m = monitor("NotResponse[a, b]")
    complete(m, "b")
    assert decision(m, "a") is Decision.ALLOWED

    complete(m, "a")
    assert decision(m, "b") is Decision.DENIED
    assert m.violations() == []


def test_running_counterpart_gives_wait():
    """Either one running makes the other wait, as it could complete first"""
    m = monitor("NotResponse[a, b]")
    run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m = monitor("NotResponse[a, b]")
    run(m, "b")
    assert decision(m, "a") is Decision.WAIT


def test_time_window_makes_the_block_temporary():
    """Blocks last only for the window: b after a completed, a after a running b began"""
    m = monitor("NotResponse[a, b] | | | 0,1,h")
    complete(m, "a")

    assert decision(m, "b", hours(0.5)) is Decision.WAIT
    assert decision(m, "b", hours(2)) is Decision.ALLOWED

    run(m, "b", hours(2))
    assert decision(m, "a", hours(2.5)) is Decision.WAIT
    assert decision(m, "a", hours(3.5)) is Decision.ALLOWED
