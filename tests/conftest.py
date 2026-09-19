from core.mp_declare_model import ConstraintDef
from core.templates import Template


def existence_def(activation: str, id: str) -> ConstraintDef:
    return ConstraintDef(
        id=id, template=Template.EXISTENCE, activation_activity=activation, count=1
    )
