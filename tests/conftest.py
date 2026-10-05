from governancekit.engine.mp_declare_model import ConstraintDef
from governancekit.engine.templates import Template


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
