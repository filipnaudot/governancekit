from conftest import complete, decision, monitor, run

from governancekit.engine.decision import Decision


def test_satisfied_only_with_exactly_n_completions():
    """Violated below n completions, satisfied at n"""
    m = monitor("Exactly[a, 2]")
    assert m.violations() != []

    complete(m, "a")
    assert m.violations() != []

    complete(m, "a")
    assert m.violations() == []


def test_running_instances_count_against_the_upper_limit():
    """WAIT while a running instance would reach n, DENIED once n completed"""
    m = monitor("Exactly[a]")
    a = run(m, "a")
    assert decision(m, "a") is Decision.WAIT

    m.finish(a, completed=True)
    assert decision(m, "a") is Decision.DENIED


def test_only_matching_activations_count():
    """Activations not matching the condition are allowed and don't count"""
    m = monitor("Exactly[a] | A.kind is hard | |")
    complete(m, "a", kind="soft")
    assert m.violations() != []

    complete(m, "a", kind="hard")
    assert decision(m, "a", kind="soft") is Decision.ALLOWED
    assert decision(m, "a", kind="hard") is Decision.DENIED
    assert m.violations() == []
