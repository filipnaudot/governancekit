from datetime import UTC, datetime

import pytest
from conftest import precedence_def

from core.events import Event
from core.mp_declare_model import ConstraintDef, MPDeclareModel
from core.templates import Template
from core.trace_monitor import TraceMonitor


def _model(n: int) -> MPDeclareModel:
    return MPDeclareModel.build(
        [
            ConstraintDef(
                id=f"c{i}",
                template=Template.PRECEDENCE,
                activation_activity=f"delete_{i}",
                target_activity=f"authorize_{i}",
            )
            for i in range(n)
        ]
    )


def _model_shared_activity(n: int) -> MPDeclareModel:
    return MPDeclareModel.build(
        [
            ConstraintDef(
                id=f"c{i}",
                template=Template.PRECEDENCE,
                activation_activity="delete",
                target_activity=f"authorize_{i}",
            )
            for i in range(n)
        ]
    )


def test_blocks_precedence_without_target():
    model = MPDeclareModel.build(
        [
            precedence_def("delete", "authorize", "authorized_delete"),
            precedence_def("add", "authorize", "authorized_add"),
        ]
    )
    monitor = TraceMonitor(model)
    decision = monitor.check(Event("delete", datetime.now(UTC)))
    assert decision.allowed == False
    assert len(decision.violations) == 1
    assert decision.violations[0].constraint_id == "authorized_delete"


def test_allows_precedence_with_target():
    model = MPDeclareModel.build(
        [
            precedence_def("delete", "authorize_d", "authorized_delete"),
            precedence_def("add", "authorize_a", "authorized_add"),
        ]
    )
    monitor = TraceMonitor(model)
    monitor.commit(Event("authorize_d", datetime.now(UTC)))
    decision = monitor.check(Event("delete", datetime.now(UTC)))
    assert decision.allowed == True
    assert len(decision.violations) == 0


@pytest.mark.benchmark
@pytest.mark.parametrize("n_constraints", [1, 10, 100, 1000])
def test_check_scaling(benchmark, n_constraints):
    monitor = TraceMonitor(_model(n_constraints))
    monitor.commit(Event("authorize_0", datetime.now(UTC)))
    e = Event("delete_0", datetime.now(UTC))

    benchmark(monitor.check, e)


@pytest.mark.benchmark
@pytest.mark.parametrize("n_constraints", [1, 10, 100, 1000])
def test_check_scaling_shared_activity(benchmark, n_constraints):
    monitor = TraceMonitor(_model_shared_activity(n_constraints))
    for i in range(n_constraints):
        monitor.commit(Event(f"authorize_{i}", datetime.now(UTC)))
    e = Event("delete", datetime.now(UTC))

    benchmark(monitor.check, e)
