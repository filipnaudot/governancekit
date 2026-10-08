from datetime import UTC, datetime, timedelta

from governancekit.engine.decision import Decision
from governancekit.engine.decl_parser import parse_decl_text
from governancekit.engine.events import Event
from governancekit.engine.mp_declare_model import ConstraintDef, MPDeclareModel
from governancekit.engine.templates import Template
from governancekit.engine.trace_monitor import TraceMonitor

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def hours(h: float) -> datetime:
    return T0 + timedelta(hours=h)


def existence_def(activation: str, id: str) -> ConstraintDef:
    return ConstraintDef(
        id=id,
        source="placeholder",
        template=Template.EXISTENCE,
        activation_activity=activation,
        count=1,
    )


def init_def(activation: str, id: str) -> ConstraintDef:
    return ConstraintDef(
        id=id,
        source=f"Init[{activation}]",
        template=Template.INIT,
        activation_activity=activation,
    )


def precedence_def(activation: str, target: str, id: str, source: str) -> ConstraintDef:
    return ConstraintDef(
        id=id,
        source=source,
        template=Template.PRECEDENCE,
        activation_activity=activation,
        target_activity=target,
    )


def monitor(*constraints: str) -> TraceMonitor:
    """A monitor for constraints written as .decl lines, e.g. "Response[a, b] | | | 0,1,h".
    The condition columns may be left out; the activities are declared automatically."""
    lines = [c if "|" in c else c + " | | |" for c in constraints]
    activities = {
        item.strip()
        for line in lines
        for item in line[line.index("[") + 1 : line.index("]")].split(",")
        if not item.strip().isdigit()
    }
    text = "\n".join([f"activity {a}" for a in sorted(activities)] + lines)
    return TraceMonitor(MPDeclareModel.build(parse_decl_text(text)))


def decision(monitor: TraceMonitor, activity: str, at=T0, **payload) -> Decision:
    """The decision for beginning the activity, without reserving it"""
    return monitor.check(Event(activity, at, payload))[0]


def run(monitor: TraceMonitor, activity: str, at=T0, **payload) -> str:
    """Begin an activity that must be allowed, and return its instance id"""
    d, iid, _ = monitor.begin(Event(activity, at, payload))
    assert d is Decision.ALLOWED, f"{activity}: {d}"
    return iid


def complete(monitor: TraceMonitor, activity: str, at=T0, **payload) -> None:
    """Begin an activity that must be allowed, and complete it at the same time"""
    monitor.finish(
        run(monitor, activity, at, **payload), completed=True, completed_at=at
    )
