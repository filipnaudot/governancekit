from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_only_a_target_may_directly_follow_the_activation():
    """After a, other activities are DENIED, WAIT while b runs, and ALLOWED once b completed"""
    m = monitor("ChainResponse[a, b]")
    complete(m, "a")
    assert decision(m, "x") is Decision.DENIED
    assert decision(m, "a") is Decision.DENIED
    assert m.violations() != []

    b = run(m, "b")
    assert decision(m, "x") is Decision.WAIT

    m.finish(b, completed=True)
    assert decision(m, "x") is Decision.ALLOWED
    assert m.violations() == []


def test_only_targets_run_alongside_the_activation():
    """a waits while x runs but not while b runs; while a runs x waits but b may begin"""
    m = monitor("ChainResponse[a, b]")
    x = run(m, "x")
    assert decision(m, "a") is Decision.WAIT

    m.finish(x, completed=True)
    b = run(m, "b")
    assert decision(m, "a") is Decision.ALLOWED

    m.finish(b, completed=False)
    run(m, "a")
    assert decision(m, "x") is Decision.WAIT
    assert decision(m, "b") is Decision.ALLOWED


def test_waiting_activation_stops_blocking_after_its_window():
    """Within the window b may be too early and others wait; after it, others are allowed"""
    m = monitor("ChainResponse[a, b] | | | 1,2,h")
    complete(m, "a")
    assert decision(m, "b", hours(0.5)) is Decision.WAIT
    assert decision(m, "x", hours(0.5)) is Decision.WAIT
    assert decision(m, "x", hours(3)) is Decision.ALLOWED

    run(m, "b", hours(1.5))
    assert decision(m, "x", hours(3)) is Decision.WAIT


def test_with_a_time_condition_targets_dont_run_alongside_the_activation():
    """b waits while a runs and a while b runs, as their completion times decide the window"""
    m = monitor("ChainResponse[a, b] | | | 0,1,h")
    a = run(m, "a")
    assert decision(m, "b") is Decision.WAIT

    m.finish(a, completed=False)
    run(m, "b")
    assert decision(m, "a") is Decision.WAIT
