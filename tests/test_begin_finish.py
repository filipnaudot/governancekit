"""
Behaviour of concurrent activities on TraceMonitor: begin, finish and unfinished.
"""

from datetime import UTC, datetime

import pytest
from conftest import existence_def

from governancekit.engine.decision import Decision
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef, MPDeclareModel
from governancekit.engine.trace_monitor import TraceMonitor

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _monitor(*definitions: ConstraintDef) -> TraceMonitor:
    return TraceMonitor(MPDeclareModel.build(list(definitions)))


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


def test_running_activity_does_not_count():
    monitor = _monitor(existence_def("close_ticket", "e"))
    _run(monitor, "close_ticket")

    assert monitor.violations() == ["placeholder"]
