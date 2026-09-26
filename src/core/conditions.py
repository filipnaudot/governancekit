"""
Data conditions used for activation condition and correlation condition.
"""

import ast
import math
import re
from collections.abc import Callable
from datetime import timedelta
from types import FunctionType

from core.events import Event

__all__ = [
    "ConditionSyntaxError",
    "create_activation_condition",
    "create_correlation_condition",
    "create_time_condition",
]


def create_activation_condition(condition_text: str) -> Callable[[Event], bool] | None:
    return (
        _compile(condition_text, with_target=False) if condition_text.strip() else None
    )


def create_correlation_condition(
    condition_text: str,
) -> Callable[[Event, Event], bool] | None:
    return (
        _compile(condition_text, with_target=True) if condition_text.strip() else None
    )


def create_time_condition(condition_text: str) -> Callable[[Event, Event], bool] | None:
    """'min,max,unit' with unit s/m/h/d: f(A, T) holds if min <= |A.timestamp - T.timestamp| <= max.

    The returned function has .bounds = (min, max) as timedeltas; use max as the deadline
    for pending activations.
    """
    text = condition_text.strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 3 or parts[2].lower() not in _UNITS:
        raise ConditionSyntaxError(
            f"time condition must be 'min,max,unit' with unit s/m/h/d, got {text!r}"
        )
    unit = _UNITS[parts[2].lower()]
    try:
        low_seconds, high_seconds = float(parts[0]) * unit, float(parts[1]) * unit
    except ValueError:
        raise ConditionSyntaxError(
            f"time bounds must be numbers, got {text!r}"
        ) from None
    if not 0 <= low_seconds <= high_seconds < math.inf:
        raise ConditionSyntaxError(
            f"time bounds must satisfy 0 <= min <= max, got {text!r}"
        )
    low, high = timedelta(seconds=low_seconds), timedelta(seconds=high_seconds)

    def time_condition(A: Event, T: Event) -> bool:
        return low <= abs(A.timestamp - T.timestamp) <= high

    time_condition.__doc__ = text
    time_condition.bounds = (low, high)  # type: ignore[attr-defined]
    return time_condition


_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class ConditionSyntaxError(ValueError):
    """The condition text is not valid MP-DECLARE"""


# Tried in this order: quoted strings first, then symbols, then everything else as a word.
_TOKEN_KINDS = {
    "str": r'"(?:[^"\\]|\\.)*"|' + r"'(?:[^'\\]|\\.)*'",  # "double" or 'single' quoted
    "sym": r">=|<=|==|!=|=|<|>|[(),]",  # operators, brackets, comma
    "word": r"""[^\s()<>=!,"']+""",  # anything up to a space or symbol
}
_TOKEN = re.compile(
    r"\s*(?:"
    + "|".join(f"(?P<{kind}>{pattern})" for kind, pattern in _TOKEN_KINDS.items())
    + ")"
)
_REF = re.compile(
    r"[AaTtBb]\..+"
)  # A.x = activation event, T.x (or B.x) = target event
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_INTEGER = re.compile(r"[-+]?\d+")
_KEYWORDS = {"and", "or", "not", "is", "in", "same", "different", "true", "false"}
_OPERATORS = {">=", "<=", "==", "!=", "=", "<", ">"}
_END = ("end", "")


def _compile(text: str, with_target: bool) -> Callable[..., bool]:
    """Turn condition text into a function. For example 'A.grade > 90 and same resource' becomes:

    def condition(A, T):
        a = A.payload
        t = T.payload
        return (('grade' in a and a['grade'] > 90) and ('resource' in a and 'resource' in t and ...))
    """
    parser = Parser(text, with_target)
    expression = parser.parse()

    source = "def condition(A, T):\n" if with_target else "def condition(A):\n"
    source += "    a = A.payload\n"
    if parser.target_used:
        source += "    t = T.payload\n"
    source += f"    return {expression}\n"

    # Safe: `source` is built from fixed code fragments, and condition text only enters it
    # through repr() literals, so no input can inject code.
    module = compile(source, "<mp-declare condition>", "exec")
    # The module's first constant is the code of `def condition`. Build the function from it with
    # no builtins, so the generated code can't reach open(), __import__() etc.
    condition = FunctionType(module.co_consts[0], {"__builtins__": {}})
    condition.__doc__ = text  # original condition, for logs
    condition.source = source  # type: ignore[attr-defined]  # generated code, for debugging
    return condition


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens, pos, text = [], 0, text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            raise ConditionSyntaxError(
                f"unexpected character at position {pos}: {text[pos : pos + 10]!r}"
            )
        if m["str"] is not None:
            tokens.append(("str", ast.literal_eval(m["str"])))
        elif m["sym"] is not None:
            tokens.append(("sym", m["sym"]))
        else:
            tokens.append(("word", m["word"]))
        pos = m.end()
    return tokens


class Parser:
    def __init__(self, text: str, target_allowed: bool) -> None:
        self.tokens = tokenize(text)
        self.pos = 0
        self.target_allowed = target_allowed
        self.target_used = False

    def peek(self, offset: int = 0) -> tuple[str, str]:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else _END

    def take(self) -> tuple[str, str]:
        token = self.peek()
        self.pos += 1
        return token

    def at(self, text: str, offset: int = 0) -> bool:
        kind, value = self.peek(offset)
        return kind != "str" and value.lower() == text

    def expect(self, text: str) -> None:
        if not self.at(text):
            raise self.error(f"expected {text!r}")
        self.pos += 1

    def error(self, message: str) -> ConditionSyntaxError:
        kind, value = self.peek()
        got = "end of condition" if kind == "end" else repr(value)
        return ConditionSyntaxError(f"{message}, got {got}")

    # Grammar

    def parse(self) -> str:
        code = self.or_expr()
        if self.peek() != _END:
            raise self.error("unexpected input")
        return code

    def or_expr(self) -> str:
        parts = [self.and_expr()]
        while self.at("or"):
            self.pos += 1
            parts.append(self.and_expr())
        return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"

    def and_expr(self) -> str:
        parts = [self.not_expr()]
        while self.at("and"):
            self.pos += 1
            parts.append(self.not_expr())
        return parts[0] if len(parts) == 1 else "(" + " and ".join(parts) + ")"

    def not_expr(self) -> str:
        if self.at("not"):
            self.pos += 1
            return f"(not {self.not_expr()})"
        return self.atom()

    def atom(self) -> str:
        if self.at("("):
            self.pos += 1
            code = self.or_expr()
            self.expect(")")
            return code
        if self.at("true") or self.at("false"):
            return str(self.take()[1].lower() == "true")
        if self.at("same") or self.at("different"):
            op = "==" if self.take()[1].lower() == "same" else "!="
            name = self.value()
            return self.compare(self.ref("A." + name), op, self.ref("T." + name))
        kind, value = self.peek()
        if kind == "word" and _REF.fullmatch(value):
            self.pos += 1
            return self.predicate(self.ref(value))
        raise self.error("expected a condition")

    def predicate(self, left: tuple[str, str]) -> str:
        if self.at("is"):  # A.x is [not] some value
            self.pos += 1
            op = "=="
            if self.at("not"):
                self.pos += 1
                op = "!="
            return self.compare(left, op, repr(self.value()))
        if self.at("in") or (
            self.at("not") and self.at("in", 1)
        ):  # A.x [not] in (a, b)
            op = "in" if self.at("in") else "not in"
            self.pos += 1 if op == "in" else 2
            return self.compare(left, op, self.enumeration())
        kind, op = self.peek()  # A.x > 5, A.x = T.y, ...
        if kind != "sym" or op not in _OPERATORS:
            raise self.error("expected an operator, 'is' or 'in'")
        self.pos += 1
        return self.compare(left, "==" if op == "=" else op, self.operand())

    def value(self) -> str:
        """A quoted string, or bare words up to and/or/a symbol/the end: `is on hold` -> 'on hold'."""
        if self.peek()[0] == "str":
            return self.take()[1]
        words = []
        while self.peek()[0] == "word" and not (self.at("and") or self.at("or")):
            words.append(self.take()[1])
        if not words:
            raise self.error("expected a value")
        return " ".join(words)

    def enumeration(self) -> str:
        self.expect("(")
        items = [self.value()]
        while self.at(","):
            self.pos += 1
            items.append(self.value())
        self.expect(")")
        return (
            "{" + ", ".join(repr(item) for item in items) + "}"
        )  # compiled to a frozenset constant

    def operand(self) -> str | tuple[str, str]:
        """Right side of a comparison operator: another reference, a number, or a single value."""
        kind, value = self.peek()
        if kind == "str":
            self.pos += 1
            return repr(value)
        if kind != "word" or value.lower() in _KEYWORDS:
            raise self.error("expected a value")
        self.pos += 1
        if _REF.fullmatch(value):
            return self.ref(value)
        if _NUMBER.fullmatch(value):
            number = int(value) if _INTEGER.fullmatch(value) else float(value)
            if not math.isfinite(number):
                raise ConditionSyntaxError(f"number out of range: {value}")
            return repr(number)
        return repr(value)

    def ref(self, text: str) -> tuple[str, str]:
        """'A.org:group' -> ('a', 'org:group'). B. is an alias for T."""
        side = "a" if text[0] in "Aa" else "t"
        if side == "t":
            if not self.target_allowed:
                raise ConditionSyntaxError(
                    f"{text!r}: T. can't be used in an activation condition"
                )
            self.target_used = True
        return side, text[2:]

    def attr(self, ref: tuple[str, str]) -> tuple[str, str]:
        """Code that checks the attribute exists, and code that reads it."""
        side, name = ref
        return f"{name!r} in {side}", f"{side}[{name!r}]"

    def compare(
        self, left: tuple[str, str], op: str, right: str | tuple[str, str]
    ) -> str:
        """right is a code string (literal) or a ref tuple (attribute on the other side)."""
        left_guard, left_value = self.attr(left)
        if isinstance(right, tuple):
            right_guard, right_value = self.attr(right)
            return (
                f"({left_guard} and {right_guard} and {left_value} {op} {right_value})"
            )
        return f"({left_guard} and {left_value} {op} {right})"
