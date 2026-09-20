"""
Factory for instantiating constraints, used by TraceMonitor
"""

from core.constraints.base import ConstraintInstance
from core.constraints.existence import ExistenceInstance
from core.constraints.precedence import PrecedenceInstance
from core.mp_declare_model import ConstraintDef
from core.templates import Template

_BUILDERS = {
    Template.EXISTENCE: ExistenceInstance,
    Template.PRECEDENCE: PrecedenceInstance,
}


def build_instance(definition: ConstraintDef) -> ConstraintInstance:
    return _BUILDERS[definition.template](definition)
