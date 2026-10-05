"""
Factory for instantiating constraints, used by TraceMonitor
"""

from governancekit.engine.constraints.base import ConstraintInstance
from governancekit.engine.constraints.existence import ExistenceInstance
from governancekit.engine.constraints.init import InitInstance
from governancekit.engine.constraints.precedence import PrecedenceInstance
from governancekit.engine.mp_declare_model import ConstraintDef
from governancekit.engine.templates import Template

_BUILDERS = {
    Template.EXISTENCE: ExistenceInstance,
    Template.INIT: InitInstance,
    Template.PRECEDENCE: PrecedenceInstance,
}


def build_instance(definition: ConstraintDef) -> ConstraintInstance:
    return _BUILDERS[definition.template](definition)
