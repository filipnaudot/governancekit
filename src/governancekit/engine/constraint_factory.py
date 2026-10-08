"""
Factory for instantiating constraints, used by TraceMonitor
"""

from governancekit.engine.constraints.absence import AbsenceInstance
from governancekit.engine.constraints.alternate_precedence import (
    AlternatePrecedenceInstance,
)
from governancekit.engine.constraints.alternate_response import (
    AlternateResponseInstance,
)
from governancekit.engine.constraints.alternate_succession import (
    AlternateSuccessionInstance,
)
from governancekit.engine.constraints.base import ConstraintInstance
from governancekit.engine.constraints.chain_precedence import ChainPrecedenceInstance
from governancekit.engine.constraints.chain_response import ChainResponseInstance
from governancekit.engine.constraints.chain_succession import ChainSuccessionInstance
from governancekit.engine.constraints.choice import ChoiceInstance
from governancekit.engine.constraints.end import EndInstance
from governancekit.engine.constraints.co_existence import CoExistenceInstance
from governancekit.engine.constraints.exactly import ExactlyInstance
from governancekit.engine.constraints.exclusive_choice import ExclusiveChoiceInstance
from governancekit.engine.constraints.existence import ExistenceInstance
from governancekit.engine.constraints.init import InitInstance
from governancekit.engine.constraints.not_chain_precedence import (
    NotChainPrecedenceInstance,
)
from governancekit.engine.constraints.not_chain_response import (
    NotChainResponseInstance,
)
from governancekit.engine.constraints.not_chain_succession import (
    NotChainSuccessionInstance,
)
from governancekit.engine.constraints.not_co_existence import NotCoExistenceInstance
from governancekit.engine.constraints.not_precedence import NotPrecedenceInstance
from governancekit.engine.constraints.not_responded_existence import (
    NotRespondedExistenceInstance,
)
from governancekit.engine.constraints.not_response import NotResponseInstance
from governancekit.engine.constraints.not_succession import NotSuccessionInstance
from governancekit.engine.constraints.precedence import PrecedenceInstance
from governancekit.engine.constraints.responded_existence import (
    RespondedExistenceInstance,
)
from governancekit.engine.constraints.response import ResponseInstance
from governancekit.engine.constraints.succession import SuccessionInstance
from governancekit.engine.mp_declare_model import ConstraintDef
from governancekit.engine.templates import Template

_BUILDERS = {
    Template.ABSENCE: AbsenceInstance,
    Template.ALTERNATE_PRECEDENCE: AlternatePrecedenceInstance,
    Template.ALTERNATE_RESPONSE: AlternateResponseInstance,
    Template.ALTERNATE_SUCCESSION: AlternateSuccessionInstance,
    Template.CHAIN_PRECEDENCE: ChainPrecedenceInstance,
    Template.CHAIN_RESPONSE: ChainResponseInstance,
    Template.CHAIN_SUCCESSION: ChainSuccessionInstance,
    Template.CHOICE: ChoiceInstance,
    Template.CO_EXISTENCE: CoExistenceInstance,
    Template.END: EndInstance,
    Template.EXACTLY: ExactlyInstance,
    Template.EXCLUSIVE_CHOICE: ExclusiveChoiceInstance,
    Template.EXISTENCE: ExistenceInstance,
    Template.INIT: InitInstance,
    Template.NOT_CHAIN_PRECEDENCE: NotChainPrecedenceInstance,
    Template.NOT_CHAIN_RESPONSE: NotChainResponseInstance,
    Template.NOT_CHAIN_SUCCESSION: NotChainSuccessionInstance,
    Template.NOT_CO_EXISTENCE: NotCoExistenceInstance,
    Template.NOT_PRECEDENCE: NotPrecedenceInstance,
    Template.NOT_RESPONDED_EXISTENCE: NotRespondedExistenceInstance,
    Template.NOT_RESPONSE: NotResponseInstance,
    Template.NOT_SUCCESSION: NotSuccessionInstance,
    Template.PRECEDENCE: PrecedenceInstance,
    Template.RESPONDED_EXISTENCE: RespondedExistenceInstance,
    Template.RESPONSE: ResponseInstance,
    Template.SUCCESSION: SuccessionInstance,
}


def build_instance(definition: ConstraintDef) -> ConstraintInstance:
    return _BUILDERS[definition.template](definition)
