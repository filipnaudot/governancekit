from conftest import complete, decision, hours, monitor, run

from governancekit.engine.decision import Decision


def test_activities_must_directly_follow_each_other():
    """b only directly after a, and after a only b"""
    m = monitor("ChainSuccession[a, b]")
    assert decision(m, "b") is Decision.DENIED

    complete(m, "a")
    assert decision(m, "x") is Decision.DENIED
    assert decision(m, "b") is Decision.ALLOWED
    assert m.violations() != []

    complete(m, "b")
    assert decision(m, "b") is Decision.DENIED
    assert decision(m, "x") is Decision.ALLOWED
    assert m.violations() == []


def test_both_activities_run_alone():
    """Nothing may begin while a or b runs, and a waits while anything runs"""
    m = monitor("ChainSuccession[a, b]")
    a = run(m, "a")
    assert decision(m, "x") is Decision.WAIT

    m.finish(a, completed=True)
    b = run(m, "b")
    assert decision(m, "x") is Decision.WAIT

    m.finish(b, completed=True)
    run(m, "x")
    assert decision(m, "a") is Decision.WAIT


def test_running_first_activity_only_helps_a_correlating_second():
    """While a runs, a correlating b waits for it and any other b is DENIED"""
    m = monitor("ChainSuccession[a, b] | | same id |")
    run(m, "a", id=1)

    assert decision(m, "b", id=1) is Decision.WAIT
    assert decision(m, "b", id=2) is Decision.DENIED


def test_waiting_first_activity_stops_blocking_after_its_window():
    """Within the window others wait; after it, others are allowed and b is DENIED"""
    m = monitor("ChainSuccession[a, b] | | | 1,2,h")
    complete(m, "a")

    assert decision(m, "b", hours(0.5)) is Decision.WAIT
    assert decision(m, "x", hours(0.5)) is Decision.WAIT
    assert decision(m, "x", hours(3)) is Decision.ALLOWED
    assert decision(m, "b", hours(3)) is Decision.DENIED
