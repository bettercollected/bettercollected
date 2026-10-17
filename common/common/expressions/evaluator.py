"""Expression evaluator (spec: docs/spec/expressions-v1.md).

Total on user data: a type error yields ``None``, never an exception. Only a
malformed AST raises (:class:`ExpressionError`). Mirrors
``webapp/src/lib/expressions/evaluator.ts``; both run the shared corpus
``docs/spec/expressions-v1.cases.json``.

Results use plain Python values: ``None``, ``bool``, ``str``, ``Decimal`` for
numbers, and ``list`` of those.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from common.expressions.decimal_num import CEIL, FLOOR, ZERO, Dec
from common.expressions.validator import (
    MAX_STRING_LENGTH,
    ExpressionError,
    validate_expression,
)

Scalar = Union[None, bool, str, Dec]
Value = Union[Scalar, List[Scalar]]

_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_ASCII_SPACE = " \t\n\r"


def _scalar_from_input(value: Any) -> Scalar:
    if value is None or isinstance(value, (bool, str)):
        return value
    return Dec.from_python(value)


def _from_input(value: Any) -> Value:
    if isinstance(value, (list, tuple)):
        return [
            None if isinstance(item, (list, tuple)) else _scalar_from_input(item)
            for item in value
        ]
    return _scalar_from_input(value)


def _cap(text: str) -> str:
    return text if len(text) <= MAX_STRING_LENGTH else text[:MAX_STRING_LENGTH]


def _to_num(value: Value) -> Optional[Dec]:
    if isinstance(value, Dec):
        return value
    if isinstance(value, str):
        parsed = Dec.parse(value.strip(_ASCII_SPACE))
        return parsed if isinstance(parsed, Dec) else None
    return None


def _is_numeric(value: Value) -> bool:
    return isinstance(value, Dec) or (
        isinstance(value, str) and _to_num(value) is not None
    )


def _to_text(value: Value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(t for t in (_to_text(item) for item in value) if t != "")
    if isinstance(value, Dec):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _truthy(value: Value) -> bool:
    if value is None or value is False or value == "":
        return False
    if isinstance(value, Dec):
        return not value.is_zero()
    if isinstance(value, list):
        return len(value) > 0
    return True


def _equals(a: Value, b: Value) -> Optional[bool]:
    if isinstance(a, list) or isinstance(b, list):
        return None
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, Dec) or isinstance(b, Dec):
        x, y = _to_num(a), _to_num(b)
        return x is not None and y is not None and x.cmp(y) == 0
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b


def _order(a: Value, b: Value) -> Optional[int]:
    if isinstance(a, list) or isinstance(b, list):
        return None
    if _is_numeric(a) and _is_numeric(b):
        return _to_num(a).cmp(_to_num(b))
    if isinstance(a, str) and isinstance(b, str):
        return -1 if a < b else 1 if a > b else 0
    return None


def _aggregate_items(values: List[Value]) -> List[Scalar]:
    items: List[Scalar] = []
    for value in values:
        for item in value if isinstance(value, list) else [value]:
            if item is not None and item != "":
                items.append(item)
    return items


def _aggregate_numbers(values: List[Value]) -> Optional[List[Dec]]:
    numbers: List[Dec] = []
    for item in _aggregate_items(values):
        number = _to_num(item)
        if number is None:
            return None
        numbers.append(number)
    return numbers


def _sum(numbers: List[Dec]) -> Optional[Dec]:
    total: Optional[Dec] = ZERO
    for number in numbers:
        total = total.add(number)
        if total is None:
            return None
    return total


def iso_day_number(value: Any) -> Optional[int]:
    """Day number of a valid ``YYYY-MM-DD`` date (proleptic Gregorian), else None."""
    if not isinstance(value, str):
        return None
    match = _ISO_DATE.fullmatch(value)
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    if year < 1 or month < 1 or month > 12 or day < 1:
        return None
    leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if day > month_days[month - 1]:
        return None
    if month <= 2:
        year -= 1
    era = year // 400
    year_of_era = year - era * 400
    day_of_year = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - 719468


def _fold(fn: Callable[[Dec, Dec], Optional[Dec]]):
    def run(args, ev, _context):
        acc = _to_num(ev(args[0]))
        for arg in args[1:]:
            if acc is None:
                return None
            nxt = _to_num(ev(arg))
            acc = None if nxt is None else fn(acc, nxt)
        return acc

    return run


def _unary(fn: Callable[[Dec], Optional[Dec]]):
    def run(args, ev, _context):
        number = _to_num(ev(args[0]))
        return None if number is None else fn(number)

    return run


def _comparison(test: Callable[[int], bool]):
    def run(args, ev, _context):
        result = _order(ev(args[0]), ev(args[1]))
        return None if result is None else test(result)

    return run


def _minus(args, ev, context):
    if len(args) == 1:
        return _unary(lambda n: n.neg())(args, ev, context)
    return _fold(lambda a, b: a.sub(b))(args, ev, context)


def _min_max(pick_lower: bool):
    def run(args, ev, _context):
        numbers = _aggregate_numbers([ev(arg) for arg in args])
        if not numbers:
            return None
        best = numbers[0]
        for number in numbers[1:]:
            c = number.cmp(best)
            if (c < 0) if pick_lower else (c > 0):
                best = number
        return best

    return run


def _round(args, ev, _context):
    number = _to_num(ev(args[0]))
    if number is None:
        return None
    if len(args) < 2:
        return number.round(0)
    digits = _to_num(ev(args[1]))
    places = digits.to_integer() if digits is not None else None
    if places is None:
        return None
    return number.round(min(max(places, -16), 15))


def _not_equals(args, ev, _context):
    result = _equals(ev(args[0]), ev(args[1]))
    return None if result is None else not result


def _if(args, ev, _context):
    i = 0
    while i + 1 < len(args):
        if _truthy(ev(args[i])):
            return ev(args[i + 1])
        i += 2
    return ev(args[i]) if i < len(args) else None


def _concat(args, ev, _context):
    text = ""
    for arg in args:
        text = _cap(text + _to_text(ev(arg)))
    return text


def _text_op(fn: Callable[[str], Any]):
    def run(args, ev, _context):
        value = ev(args[0])
        if value is None or isinstance(value, list):
            return None
        return fn(_to_text(value))

    return run


def _contains(args, ev, _context):
    haystack = ev(args[0])
    needle = ev(args[1])
    if isinstance(needle, list):
        return None
    if haystack is None or needle is None:
        return False
    target = _to_text(needle)
    if isinstance(haystack, list):
        return any(item is not None and _to_text(item) == target for item in haystack)
    return target.lower() in _to_text(haystack).lower()


def _sum_op(args, ev, _context):
    numbers = _aggregate_numbers([ev(arg) for arg in args])
    return None if numbers is None else _sum(numbers)


def _count(args, ev, _context):
    return Dec.from_int(len(_aggregate_items([ev(arg) for arg in args])))


def _avg(args, ev, _context):
    numbers = _aggregate_numbers([ev(arg) for arg in args])
    if not numbers:
        return None
    total = _sum(numbers)
    return None if total is None else total.div(Dec.from_int(len(numbers)))


def _date_diff_days(args, ev, _context):
    start = iso_day_number(ev(args[0]))
    end = iso_day_number(ev(args[1]))
    if start is None or end is None:
        return None
    return Dec.from_int(end - start)


def _today(_args, _ev, context):
    today = context.get("today")
    return today if iso_day_number(today) is not None else None


_OPS: Dict[str, Callable] = {
    "+": _fold(lambda a, b: a.add(b)),
    "*": _fold(lambda a, b: a.mul(b)),
    "-": _minus,
    "/": _fold(lambda a, b: a.div(b)),
    "%": _fold(lambda a, b: a.mod(b)),
    "min": _min_max(True),
    "max": _min_max(False),
    "round": _round,
    "floor": _unary(lambda n: n.round(0, FLOOR)),
    "ceil": _unary(lambda n: n.round(0, CEIL)),
    "abs": _unary(lambda n: n.abs()),
    "==": lambda args, ev, _c: _equals(ev(args[0]), ev(args[1])),
    "!=": _not_equals,
    "<": _comparison(lambda o: o < 0),
    "<=": _comparison(lambda o: o <= 0),
    ">": _comparison(lambda o: o > 0),
    ">=": _comparison(lambda o: o >= 0),
    "and": lambda args, ev, _c: all(_truthy(ev(arg)) for arg in args),
    "or": lambda args, ev, _c: any(_truthy(ev(arg)) for arg in args),
    "not": lambda args, ev, _c: not _truthy(ev(args[0])),
    "if": _if,
    "concat": _concat,
    "length": _text_op(lambda text: Dec.from_int(len(text))),
    "lower": _text_op(lambda text: _cap(text.lower())),
    "upper": _text_op(lambda text: _cap(text.upper())),
    "contains": _contains,
    "sum": _sum_op,
    "count": _count,
    "avg": _avg,
    "date_diff_days": _date_diff_days,
    "today": _today,
}


def _to_output(value: Value) -> Any:
    if isinstance(value, list):
        return [_to_output(item) for item in value]
    if isinstance(value, Dec):
        return value.to_decimal()
    if isinstance(value, str):
        return _cap(value)
    return value


def evaluate_expression(
    ast: Any,
    variables: Optional[Mapping[str, Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Evaluate a well-formed AST against variables and a context.

    ``context`` may hold ``today`` (``YYYY-MM-DD``). Raises
    :class:`ExpressionError` only for a malformed AST.
    """
    problems = validate_expression(ast)
    if problems:
        raise ExpressionError(problems[0])
    variables = variables or {}
    context = context or {}

    def ev(node: Any) -> Value:
        if node is None or isinstance(node, (bool, str)):
            return node
        if not isinstance(node, dict):
            return Dec.from_python(node)
        op, value = next(iter(node.items()))
        if op == "var":
            return _from_input(variables[value]) if value in variables else None
        return _OPS[op](value, ev, context)

    return _to_output(ev(ast))


def format_expression_value(value: Any) -> str:
    """Display text of a result: plain decimals, "true"/"false", "" for None,
    lists joined with ", "."""
    return _to_text(_from_input(value))
