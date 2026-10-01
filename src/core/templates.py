"""
Enum class for all MP-DECLARE Templates
"""

from enum import Enum


class Template(Enum):
    # Unary
    EXISTENCE = "existence"
    ABSENCE = "absence"
    EXACTLY = "exactly"
    INIT = "init"
    END = "end"

    # Choice
    CHOICE = "choice"
    EXCLUSIVE_CHOICE = "exclusive choice"

    # Relation
    RESPONDED_EXISTENCE = "responded existence"
    CO_EXISTENCE = "co-existence"
    RESPONSE = "response"
    ALTERNATE_RESPONSE = "alternate response"
    CHAIN_RESPONSE = "chain response"
    PRECEDENCE = "precedence"
    ALTERNATE_PRECEDENCE = "alternate precedence"
    CHAIN_PRECEDENCE = "chain precedence"
    SUCCESSION = "succession"
    ALTERNATE_SUCCESSION = "alternate succession"
    CHAIN_SUCCESSION = "chain succession"

    # Negative relation
    NOT_RESPONDED_EXISTENCE = "not responded existence"
    NOT_CO_EXISTENCE = "not co-existence"
    NOT_RESPONSE = "not response"
    NOT_CHAIN_RESPONSE = "not chain response"
    NOT_PRECEDENCE = "not precedence"
    NOT_CHAIN_PRECEDENCE = "not chain precedence"
    NOT_SUCCESSION = "not succession"
    NOT_CHAIN_SUCCESSION = "not chain succession"
