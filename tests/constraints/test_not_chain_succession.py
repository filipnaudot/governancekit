from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_b_may_not_directly_follow_a():
    """b directly after a is DENIED, also while another a runs; x in between allows it"""
    m = monitor("NotChainSuccession[a, b]")
    complete(m, "a")
    assert decision(m, "b") is Decision.DENIED

    a = run(m, "a")
    assert decision(m, "b") is Decision.DENIED

    m.finish(a, completed=False)
    complete(m, "x")
    assert decision(m, "b") is Decision.ALLOWED
    assert m.violations() == []


def test_running_activities_give_wait():
    """WAIT while something runs that could complete in between, or a counterpart that could complete first"""
    m = monitor("NotChainSuccession[a, b]")
    complete(m, "a")
    run(m, "x")
    assert decision(m, "b") is Decision.WAIT

    m = monitor("NotChainSuccession[a, b]")
    run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m = monitor("NotChainSuccession[a, b]")
    run(m, "b")
    assert decision(m, "a") is Decision.WAIT


def test_time_window_makes_the_block_temporary():
    """Blocks last only for the window: b after a completed, a after a running b began"""
    m = monitor("NotChainSuccession[a, b] | | | 0,1,h")
    complete(m, "a")

    assert decision(m, "b", hours(0.5)) is Decision.WAIT
    assert decision(m, "b", hours(2)) is Decision.ALLOWED

    run(m, "b", hours(2))
    assert decision(m, "a", hours(2.5)) is Decision.WAIT
    assert decision(m, "a", hours(3.5)) is Decision.ALLOWED
