from conftest import complete, decision, monitor, run

from governancekit.engine.decision import Decision


def test_satisfied_after_n_completions():
    """Violated until the activity completed n times; running and failed instances don't count"""
    m = monitor("Existence[a, 2]")
    complete(m, "a")
    m.finish(run(m, "a"), completed=False)
    run(m, "a")
    assert m.violations() == ["Existence[a, 2] | | |"]

    complete(m, "a")
    assert m.violations() == []


def test_never_blocks_and_counts_only_matching_activations():
    """Always ALLOWED, and completions not matching the activation condition don't count"""
    m = monitor("Existence[a] | A.kind is hard | |")
    assert decision(m, "a") is Decision.ALLOWED

    complete(m, "a", kind="soft")
    assert m.violations() != []

    complete(m, "a", kind="hard")
    assert m.violations() == []
