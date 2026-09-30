"""
Benchmarks for begin and finish with concurrent activities.

Each benchmark answers one question: how does the cost grow with N?
Run with: pytest --ignore=tests/test_api.py -m benchmark tests/test_begin_finish_benchmark.py
"""

from datetime import UTC, datetime

import pytest
from conftest import init_def, precedence_def

from core.conditions import create_correlation_condition
from core.decision import Decision
from core.events import Event
from core.mp_declare_model import ConstraintDef, MPDeclareModel
from core.templates import Template
from core.trace_monitor import TraceMonitor

SIZES = [1, 10, 100, 1000]
NOW = datetime.now(UTC)


def _monitor(definitions: list[ConstraintDef]) -> TraceMonitor:
    return TraceMonitor(MPDeclareModel.build(definitions))


def _complete(monitor: TraceMonitor, event: Event) -> None:
    decision, iid, _ = monitor.begin(event)
    assert decision is Decision.ALLOWED
    monitor.finish(iid, completed=True)


def _begin_and_abort(monitor: TraceMonitor, event: Event) -> None:
    """Begin an allowed activity and abort it, so every round starts from the same state."""
    _, iid, _ = monitor.begin(event)
    monitor.finish(iid, completed=False)


@pytest.mark.benchmark
@pytest.mark.parametrize("n_running", SIZES)
def test_begin_with_unrelated_running(benchmark, n_running):
    """Running activities the constraint doesn't mention must not cost anything."""
    monitor = _monitor([precedence_def("delete", "authorize", "p", "src")])
    _complete(monitor, Event("authorize", NOW))
    for i in range(n_running):
        monitor.begin(Event(f"task_{i}", NOW))

    delete = Event("delete", NOW)
    assert monitor.begin(delete)[0] is Decision.ALLOWED
    benchmark(_begin_and_abort, monitor, delete)


@pytest.mark.benchmark
@pytest.mark.parametrize("n_running", SIZES)
def test_begin_with_running_targets(benchmark, n_running):
    """Precedence with a correlation condition scans the running targets: linear in N."""
    monitor = _monitor(
        [
            ConstraintDef(
                id="p",
                source="src",
                template=Template.PRECEDENCE,
                activation_activity="delete",
                target_activity="authorize",
                correlation_condition=create_correlation_condition("same resource"),
            )
        ]
    )
    # N authorizations running, none for the resource being deleted
    for i in range(n_running):
        monitor.begin(Event("authorize", NOW, {"resource": f"db-{i}"}))

    delete = Event("delete", NOW, {"resource": "other"})
    assert monitor.begin(delete)[0] is Decision.DENIED  # nothing is reserved
    benchmark(monitor.begin, delete)


@pytest.mark.benchmark
@pytest.mark.parametrize("n_ordering", SIZES)
def test_begin_with_ordering_constraints(benchmark, n_ordering):
    """Every ordering constraint (Init, Chain*) is asked on every begin: linear in N."""
    monitor = _monitor([init_def("login", f"i{i}") for i in range(n_ordering)])
    _complete(monitor, Event("login", NOW))

    browse = Event("browse", NOW)
    assert monitor.begin(browse)[0] is Decision.ALLOWED
    benchmark(_begin_and_abort, monitor, browse)


@pytest.mark.benchmark
@pytest.mark.parametrize("n_constraints", SIZES)
def test_begin_and_complete(benchmark, n_constraints):
    """A full begin + successful finish, with N constraints mentioning the activity."""
    monitor = _monitor(
        [
            precedence_def(f"delete_{i}", "authorize", f"p{i}", "src")
            for i in range(n_constraints)
        ]
    )
    _complete(monitor, Event("authorize", NOW))  # later completions don't add state

    benchmark(_complete, monitor, Event("authorize", NOW))
