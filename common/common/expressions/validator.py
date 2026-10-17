"""Expression AST validation (spec: docs/spec/expressions-v1.md).

Mirrors ``webapp/src/lib/expressions/validator.ts``: same walk order, same
problem codes, so the first problem is the same on both sides.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, List, Optional

from common.expressions.decimal_num import Dec

MAX_DEPTH = 32
MAX_NODES = 500
MAX_STRING_LENGTH = 1000
MAX_VAR_LENGTH = 200
# Caps on variable values (evaluator input); over-cap values become None.
MAX_INPUT_STRING_LENGTH = 10000
MAX_INPUT_LIST_ITEMS = 1000
_INF = float("inf")

# Allowed argument counts: (min, max); max ``inf`` = variadic.
OPERATORS = {
    "+": (2, _INF),
    "-": (1, 2),
    "*": (2, _INF),
    "/": (2, 2),
    "%": (2, 2),
    "min": (1, _INF),
    "max": (1, _INF),
    "round": (1, 2),
    "floor": (1, 1),
    "ceil": (1, 1),
    "abs": (1, 1),
    "==": (2, 2),
    "!=": (2, 2),
    "<": (2, 2),
    "<=": (2, 2),
    ">": (2, 2),
    ">=": (2, 2),
    "and": (2, _INF),
    "or": (2, _INF),
    "not": (1, 1),
    "if": (2, _INF),
    "concat": (1, _INF),
    "length": (1, 1),
    "lower": (1, 1),
    "upper": (1, 1),
    "contains": (2, 2),
    "sum": (1, _INF),
    "count": (1, _INF),
    "avg": (1, _INF),
    "date_diff_days": (2, 2),
    "today": (0, 0),
}


@dataclass(frozen=True)
class ExpressionProblem:
    code: str
    message: str
    # JSON Pointer to the node ("" is the root).
    path: str


class ExpressionError(ValueError):
    """Raised by ``evaluate`` for a malformed AST, never for user data."""

    def __init__(self, problem: ExpressionProblem):
        super().__init__(problem.message)
        self.code = problem.code
        self.path = problem.path


def _pointer(path: str, token: Any) -> str:
    return f"{path}/" + str(token).replace("~", "~0").replace("/", "~1")


def _is_number(node: Any) -> bool:
    return isinstance(node, (int, float, Decimal)) and not isinstance(node, bool)


def validate_expression(
    ast: Any, known_variables: Optional[Iterable[str]] = None
) -> List[ExpressionProblem]:
    """Check an AST against the v1 grammar and limits.

    Walks depth-first (pre-order), returns problems in that order and stops
    at the node limit. An empty list means the AST is well formed.
    """
    problems: List[ExpressionProblem] = []
    known = set(known_variables) if known_variables is not None else None
    state = {"nodes": 0, "stopped": False}

    def add(code: str, message: str, path: str) -> None:
        problems.append(ExpressionProblem(code, message, path))

    def visit(node: Any, path: str, depth: int) -> None:
        if state["stopped"]:
            return
        state["nodes"] += 1
        if state["nodes"] > MAX_NODES:
            add(
                "too_many_nodes",
                f"An expression can have at most {MAX_NODES} parts.",
                path,
            )
            state["stopped"] = True
            return
        if depth > MAX_DEPTH:
            add(
                "too_deep",
                f"An expression can be nested at most {MAX_DEPTH} levels deep.",
                path,
            )
            return
        if node is None or isinstance(node, bool):
            return
        if _is_number(node):
            if Dec.from_python(node) is None:
                add(
                    "invalid_literal",
                    "Numbers must be finite and smaller than 10^15.",
                    path,
                )
            return
        if isinstance(node, str):
            if len(node) > MAX_STRING_LENGTH:
                add(
                    "string_too_long",
                    f"Text can be at most {MAX_STRING_LENGTH} characters.",
                    path,
                )
            return
        if not isinstance(node, dict):
            add(
                "invalid_node",
                "Expected a number, text, true, false, null or an operator object.",
                path,
            )
            return
        if len(node) != 1:
            add("invalid_node", "An operator object must have exactly one key.", path)
            return
        op, value = next(iter(node.items()))
        op = str(op)
        op_path = _pointer(path, op)
        if op == "var":
            if not isinstance(value, str) or value == "" or len(value) > MAX_VAR_LENGTH:
                add(
                    "invalid_var",
                    "A variable reference needs a name of 1 to "
                    f"{MAX_VAR_LENGTH} characters.",
                    op_path,
                )
            elif known is not None and value not in known:
                add("unknown_variable", f'Unknown variable "{value}".', op_path)
            return
        arity = OPERATORS.get(op)
        if arity is None:
            add("unknown_operator", f'Unknown operator "{op}".', op_path)
            return
        if not isinstance(value, list):
            add("invalid_node", f'The arguments of "{op}" must be a list.', op_path)
            return
        low, high = arity
        if len(value) < low or len(value) > high:
            if low == high:
                expected = f"{low}"
            elif high == _INF:
                expected = f"at least {low}"
            else:
                expected = f"{low} to {high}"
            plural = "" if low == 1 and high == 1 else "s"
            add(
                "arity",
                f'"{op}" takes {expected} argument{plural}, got {len(value)}.',
                op_path,
            )
            return
        for index, arg in enumerate(value):
            visit(arg, _pointer(op_path, index), depth + 1)

    visit(ast, "", 1)
    return problems


def is_valid_expression(ast: Any, known_variables: Optional[Iterable[str]] = None):
    """True when ``ast`` is a well-formed expression."""
    return not validate_expression(ast, known_variables)
