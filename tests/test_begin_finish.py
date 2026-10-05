"""
Behaviour of concurrent activities on TraceMonitor: begin, finish and unfinished.
"""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import existence_def, init_def, precedence_def

from governancekit.engine.conditions import (
    create_correlation_condition,
    create_time_condition,
)
from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef, MPDeclareModel
from governancekit.engine.templates import Template
from governancekit.engine.trace_monitor import TraceMonitor

T0 = datetime(2026, 1, 1, tzinfo=UTC)
PRECEDENCE = "Precedence[authorize, delete]"


def _monitor(*definitions: ConstraintDef) -> TraceMonitor:
    return TraceMonitor(MPDeclareModel.build(list(definitions)))


def _authorized_delete(correlation: str = "", time: str = "") -> ConstraintDef:
    return ConstraintDef(
        id="authorized_delete",
        source=PRECEDENCE,
        template=Template.PRECEDENCE,
        activation_activity="delete",
        target_activity="authorize",
        correlation_condition=create_correlation_condition(correlation),
        time_condition=create_time_condition(time),
    )


def _run(monitor: TraceMonitor, activity: str, **payload) -> str:
    """Begin an activity that must be allowed, and return its instance id."""
    decision, iid, _ = monitor.begin(Event(activity, T0, payload))
    assert decision is Decision.ALLOWED
    return iid


# ---------- Lifecycle ----------


def test_allowed_begin_reserves_until_finish():
    monitor = _monitor()

    iid = _run(monitor, "login")
    assert set(monitor.running["login"]) == {iid}
    assert set(monitor.unfinished()) == {iid}

    monitor.finish(iid, completed=True)
    assert monitor.running == {}
    assert monitor.unfinished() == {}


def test_finish_returns_the_event_it_began_with():
    monitor = _monitor()
    iid = _run(monitor, "login", user="alice")

    event = monitor.finish(iid, completed=True)

    assert event == Event("login", T0, {"user": "alice"})


def test_same_activity_can_run_twice():
    monitor = _monitor()
    first = _run(monitor, "login")
    second = _run(monitor, "login")

    monitor.finish(first, completed=True)

    assert set(monitor.running["login"]) == {second}


def test_finish_unknown_instance_raises():
    with pytest.raises(KeyError):
        _monitor().finish("nope", completed=True)


def test_failed_activity_does_not_count():
    monitor = _monitor(existence_def("close_ticket", "e"))
    iid = _run(monitor, "close_ticket")

    monitor.finish(iid, completed=False)

    assert monitor.violations() == ["placeholder"]
    assert monitor.last_completed is None


def test_running_activity_does_not_count():
    monitor = _monitor(existence_def("close_ticket", "e"))
    _run(monitor, "close_ticket")

    assert monitor.violations() == ["placeholder"]


# ---------- Precedence ----------


def test_precedence_decisions_follow_the_target():
    monitor = _monitor(precedence_def("delete", "authorize", "p", PRECEDENCE))
    delete = Event("delete", T0)

    assert monitor.begin(delete) == (Decision.DENIED, None, [PRECEDENCE])

    authorize = _run(monitor, "authorize")
    assert monitor.begin(delete) == (Decision.WAIT, None, [PRECEDENCE])

    monitor.finish(authorize, completed=False)
    assert monitor.begin(delete) == (Decision.DENIED, None, [PRECEDENCE])

    monitor.finish(_run(monitor, "authorize"), completed=True)
    assert monitor.begin(delete)[0] is Decision.ALLOWED


def test_running_activation_does_not_block_target():
    monitor = _monitor(precedence_def("delete", "authorize", "p", PRECEDENCE))
    monitor.finish(_run(monitor, "authorize"), completed=True)
    _run(monitor, "delete")

    assert monitor.begin(Event("authorize", T0))[0] is Decision.ALLOWED


def test_unrelated_activity_is_allowed_while_target_runs():
    monitor = _monitor(precedence_def("delete", "authorize", "p", PRECEDENCE))
    _run(monitor, "authorize")

    assert monitor.begin(Event("view_account", T0))[0] is Decision.ALLOWED


def test_only_correlating_running_target_causes_wait():
    monitor = _monitor(_authorized_delete(correlation="same resource"))
    _run(monitor, "authorize", resource="db-1")

    same = monitor.begin(Event("delete", T0, {"resource": "db-1"}))
    other = monitor.begin(Event("delete", T0, {"resource": "db-2"}))

    assert same[0] is Decision.WAIT
    assert other[0] is Decision.DENIED


def test_time_condition_measures_from_target_completion():
    monitor = _monitor(_authorized_delete(time="0,1,h"))
    authorize = _run(monitor, "authorize")
    # Began at T0, but only completes an hour later
    monitor.finish(authorize, completed=True, completed_at=T0 + timedelta(hours=1))

    within = monitor.begin(Event("delete", T0 + timedelta(hours=1, minutes=30)))
    too_late = monitor.begin(Event("delete", T0 + timedelta(hours=2, minutes=30)))

    assert within[0] is Decision.ALLOWED
    assert too_late[0] is Decision.DENIED


def test_denied_wins_over_wait():
    monitor = _monitor(
        precedence_def("delete", "authorize", "p1", "Precedence[authorize, delete]"),
        precedence_def("delete", "backup", "p2", "Precedence[backup, delete]"),
    )
    _run(monitor, "authorize")  # running: p1 says WAIT, p2 says DENIED

    decision, iid, blocking = monitor.begin(Event("delete", T0))

    assert decision is Decision.DENIED
    assert iid is None
    assert sorted(blocking) == [
        "Precedence[authorize, delete]",
        "Precedence[backup, delete]",
    ]


def test_check_gives_begin_decision_without_reserving():
    monitor = _monitor(precedence_def("delete", "authorize", "p", PRECEDENCE))
    _run(monitor, "authorize")

    assert monitor.check(Event("delete", T0)) == (Decision.WAIT, [PRECEDENCE])
    assert monitor.check(Event("view_account", T0)) == (Decision.ALLOWED, [])
    assert set(monitor.running) == {"authorize"}


# ---------- Init ----------


def test_init_only_allows_its_activity_before_first_completion():
    monitor = _monitor(init_def("login", "i"))

    assert monitor.begin(Event("browse", T0)) == (Decision.WAIT, None, ["Init[login]"])

    login = _run(monitor, "login")
    assert monitor.begin(Event("browse", T0))[0] is Decision.WAIT

    monitor.finish(login, completed=True)
    assert monitor.begin(Event("browse", T0))[0] is Decision.ALLOWED
    assert monitor.violations() == []


def test_init_is_decided_by_first_completion_only():
    monitor = _monitor(init_def("login", "i"))
    first = _run(monitor, "login")
    second = _run(monitor, "login")

    monitor.finish(first, completed=True)
    monitor.finish(second, completed=False)

    assert monitor.violations() == []
