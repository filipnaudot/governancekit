from conftest import complete, hours, monitor, run


def test_each_activity_needs_the_other():
    """An empty trace is satisfied; either activity alone is violated; both together satisfy it"""
    m = monitor("CoExistence[a, b]")
    assert m.violations() == []

    complete(m, "b")
    assert m.violations() != []

    complete(m, "a")
    assert m.violations() == []


def test_every_occurrence_needs_a_correlating_partner():
    """Occurrences only satisfy each other if they correlate, in either order"""
    m = monitor("CoExistence[a, b] | | same id |")
    complete(m, "a", id=1)
    complete(m, "b", id=2)
    assert m.violations() != []

    complete(m, "b", id=1)
    complete(m, "a", id=2)
    assert m.violations() == []


def test_time_window_is_measured_from_completion_to_begin():
    """The window runs from the earlier activity's completion to the later one's begin"""
    too_early = monitor("CoExistence[a, b] | | | 1,2,h")
    complete(too_early, "b", hours(1.5))
    too_early.finish(
        run(too_early, "a", hours(1.5)), completed=True, completed_at=hours(3)
    )
    assert too_early.violations() != []

    in_time = monitor("CoExistence[a, b] | | | 0,1,h")
    in_time.finish(run(in_time, "a"), completed=True, completed_at=hours(1.5))
    in_time.finish(run(in_time, "b", hours(2)), completed=True, completed_at=hours(3))
    assert in_time.violations() == []
