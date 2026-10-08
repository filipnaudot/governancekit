from conftest import complete, decision, monitor, run

from governancekit.engine.decision import Decision


def test_satisfied_if_the_last_completion_is_the_activation():
    """An empty trace is violated; any later completion undoes it; failures don't count"""
    m = monitor("End[a]")
    assert m.violations() == ["End[a] | | |"]

    complete(m, "a")
    assert m.violations() == []

    m.finish(run(m, "x"), completed=False)
    assert m.violations() == []

    complete(m, "x")
    assert m.violations() == ["End[a] | | |"]


def test_never_blocks_and_counts_only_matching_activations():
    """Always ALLOWED; a last activation not matching the condition doesn't satisfy it"""
    m = monitor("End[a] | A.kind is hard | |")
    assert decision(m, "x") is Decision.ALLOWED

    complete(m, "a", kind="soft")
    assert m.violations() != []

    complete(m, "a", kind="hard")
    assert m.violations() == []
