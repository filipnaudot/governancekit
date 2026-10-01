"""
Behaviour of MonitorRegistry with concurrent activities, including calls from several threads.
"""

import threading
from datetime import UTC, datetime

import pytest

from core.decision import Decision
from core.events import Event
from core.monitor_registry import MonitorRegistry

MODEL = """
    activity authorize
    activity delete
    activity login
    Precedence[authorize, delete] |||
    Existence[login] |||
"""


@pytest.fixture
def registry() -> MonitorRegistry:
    registry = MonitorRegistry()
    registry.add_model("model", MODEL)
    registry.start_monitor("model", "trace")
    return registry


def _event(activity: str) -> Event:
    return Event(activity, datetime.now(UTC))


def test_begin_and_finish_event(registry):
    decision, iid, blocking = registry.begin_event("trace", _event("authorize"))
    assert (decision, blocking) == (Decision.ALLOWED, [])

    assert registry.begin_event("trace", _event("delete"))[0] is Decision.WAIT

    registry.finish_event("trace", iid, completed=True)
    assert registry.begin_event("trace", _event("delete"))[0] is Decision.ALLOWED


def test_unknown_trace_raises(registry):
    with pytest.raises(KeyError):
        registry.begin_event("nope", _event("login"))
    with pytest.raises(KeyError):
        registry.finish_event("nope", "iid", completed=True)


def test_unfinished_lists_running_activities(registry):
    _, iid, _ = registry.begin_event("trace", _event("login"))

    assert list(registry.unfinished("trace")) == [iid]


def test_end_with_running_activities_raises(registry):
    registry.begin_event("trace", _event("login"))

    with pytest.raises(ValueError):
        registry.end_monitor("trace")
    assert "trace" in registry.monitors


def test_end_with_abort_returns_running_activities(registry):
    _, iid, _ = registry.begin_event("trace", _event("login"))

    aborted = registry.end_monitor("trace", abort_running=True)

    assert list(aborted) == [iid]
    assert "trace" not in registry.monitors


def test_end_without_running_activities(registry):
    assert registry.end_monitor("trace") == {}
    with pytest.raises(KeyError):
        registry.end_monitor("trace")


def test_concurrent_calls_on_one_trace(registry):
    """Many threads begin and finish on the same trace; no update may be lost."""
    errors = []

    def agent():
        try:
            for _ in range(100):
                decision, iid, _ = registry.begin_event("trace", _event("login"))
                assert decision is Decision.ALLOWED
                registry.finish_event("trace", iid, completed=True)
        except Exception as e:  # collected, since exceptions in threads don't fail the test
            errors.append(e)

    threads = [threading.Thread(target=agent) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert registry.unfinished("trace") == {}
    assert registry.violations("trace") == []  # every login completed


def test_concurrent_end_succeeds_once(registry):
    results = []

    def end():
        try:
            registry.end_monitor("trace")
            results.append("ended")
        except KeyError:
            results.append("KeyError")

    threads = [threading.Thread(target=end) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["KeyError", "KeyError", "KeyError", "ended"]
