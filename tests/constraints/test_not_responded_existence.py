from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_completed_counterpart_blocks_in_both_directions():
    """After a completes, b is DENIED, and after b completes, a is DENIED"""
    for first, second in (("a", "b"), ("b", "a")):
        m = monitor("NotRespondedExistence[a, b]")
        complete(m, first)
        assert decision(m, second) is Decision.DENIED
        assert decision(m, first) is Decision.ALLOWED
        assert m.violations() == []


def test_running_counterpart_gives_wait():
    """WAIT while the counterpart runs, ALLOWED again if it fails"""
    m = monitor("NotRespondedExistence[a, b]")
    a = run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=False)
    assert decision(m, "b") is Decision.ALLOWED


def test_only_correlating_counterparts_block():
    """A counterpart only blocks activities it correlates with"""
    m = monitor("NotRespondedExistence[a, b] | | same id |")
    complete(m, "a", id=1)

    assert decision(m, "b", id=1) is Decision.DENIED
    assert decision(m, "b", id=2) is Decision.ALLOWED


def test_time_window_makes_the_block_temporary():
    """Within the window the counterpart gives WAIT, after it ALLOWED"""
    m = monitor("NotRespondedExistence[a, b] | | | 0,1,h")
    complete(m, "a")

    assert decision(m, "b", hours(0.5)) is Decision.WAIT
    assert decision(m, "b", hours(2)) is Decision.ALLOWED
