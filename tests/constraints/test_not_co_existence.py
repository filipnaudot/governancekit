from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_completed_counterpart_blocks_in_both_directions():
    """After a completes, b is DENIED, and after b completes, a is DENIED"""
    for first, second in (("a", "b"), ("b", "a")):
        m = monitor("NotCoExistence[a, b]")
        complete(m, first)
        assert decision(m, second) is Decision.DENIED
        assert decision(m, first) is Decision.ALLOWED
        assert m.violations() == []


def test_running_counterpart_gives_wait():
    """WAIT while the counterpart runs, ALLOWED again if it fails"""
    m = monitor("NotCoExistence[a, b]")
    b = run(m, "b")
    assert decision(m, "a") is Decision.WAIT

    m.finish(b, completed=False)
    assert decision(m, "a") is Decision.ALLOWED


def test_activation_condition_applies_to_both_activities():
    """Activities not matching the condition neither block nor are blocked"""
    m = monitor("NotCoExistence[a, b] | A.kind is hard | |")
    complete(m, "b", kind="soft")
    assert decision(m, "a", kind="hard") is Decision.ALLOWED

    complete(m, "b", kind="hard")
    assert decision(m, "a", kind="soft") is Decision.ALLOWED
    assert decision(m, "a", kind="hard") is Decision.DENIED


def test_time_window_makes_the_block_temporary():
    """Within the window the counterpart gives WAIT, after it ALLOWED"""
    m = monitor("NotCoExistence[a, b] | | | 0,1,h")
    complete(m, "b")

    assert decision(m, "a", hours(0.5)) is Decision.WAIT
    assert decision(m, "a", hours(2)) is Decision.ALLOWED
