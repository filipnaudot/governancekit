"""
Enum class for all supported MP-DECLARE Templates
"""

from enum import Enum


class Template(Enum):
    INIT = "init"
    EXISTENCE = "existence"
    PRECEDENCE = "precedence"
    CHAIN_RESPONSE = "chain response"
    CHAIN_SUCCESSION = "chain succession"
