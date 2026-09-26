from datetime import UTC, datetime

import pytest
from conftest import precedence_def

from core.conditions import create_activation_condition, create_correlation_condition
from core.events import Event
from core.mp_declare_model import ConstraintDef, MPDeclareModel
from core.templates import Template
from core.trace_monitor import TraceMonitor


def _model(n: int) -> MPDeclareModel:
    return MPDeclareModel.build(
        [
            ConstraintDef(
                id=f"c{i}",
                source="placeholder",
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
                source="placeholder",
                template=Template.PRECEDENCE,
                activation_activity="delete",
                target_activity=f"authorize_{i}",
            )
            for i in range(n)
        ]
    )


ACTIVATION_CONDITION = "A.risk > 5 and A.role is admin"
CORRELATION_CONDITION = "same resource and T.status is approved"


def _model_shared_activity_with_conditions(n: int) -> MPDeclareModel:
    return MPDeclareModel.build(
        [
            ConstraintDef(
                id=f"c{i}",
                source="placeholder",
                template=Template.PRECEDENCE,
                activation_activity="delete",
                target_activity=f"authorize_{i}",
                activation_condition=create_activation_condition(ACTIVATION_CONDITION),
                correlation_condition=create_correlation_condition(
                    CORRELATION_CONDITION
                ),
            )
            for i in range(n)
        ]
    )


def test_blocks_precedence_without_target():
    model = MPDeclareModel.build(
        [
            precedence_def("delete", "authorize", "authorized_delete", "src1"),
            precedence_def("add", "authorize", "authorized_add", "src2"),
        ]
    )
    monitor = TraceMonitor(model)
    decision = monitor.check(Event("delete", datetime.now(UTC)))
    assert decision[0] == False
    assert len(decision[1]) == 1
    assert decision[1][0] == "src1"


def test_allows_precedence_with_target():
    model = MPDeclareModel.build(
        [
            precedence_def("delete", "authorize_d", "authorized_delete", "src1"),
            precedence_def("add", "authorize_a", "authorized_add", "src2"),
        ]
    )
    monitor = TraceMonitor(model)
    monitor.commit(Event("authorize_d", datetime.now(UTC)))
    decision = monitor.check(Event("delete", datetime.now(UTC)))
    assert decision[0] == True
    assert len(decision[1]) == 0


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


@pytest.mark.benchmark
@pytest.mark.parametrize("n_constraints", [1, 10, 100, 1000])
@pytest.mark.parametrize("n_non_matching", [0, 10])
def test_check_scaling_shared_activity_with_conditions(
    benchmark, n_constraints, n_non_matching
):
    monitor = TraceMonitor(_model_shared_activity_with_conditions(n_constraints))
    now = datetime.now(UTC)
    for i in range(n_constraints):
        # Seen targets for another resource: stored, but rejected by the correlation condition.
        for _ in range(n_non_matching):
            monitor.commit(
                Event(f"authorize_{i}", now, {"resource": "db-2", "status": "approved"})
            )
        # The matching target comes last, so check has to scan past the non-matching ones first.
        monitor.commit(
            Event(f"authorize_{i}", now, {"resource": "db-1", "status": "approved"})
        )
    e = Event("delete", now, {"resource": "db-1", "risk": 9, "role": "admin"})

    benchmark(monitor.check, e)
