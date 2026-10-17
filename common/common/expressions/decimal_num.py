"""Decimal numbers for expressions (spec: docs/spec/expressions-v1.md, "Numbers").

A number is ``coef * 10**exp`` with an integer coefficient, kept to at most 15
significant digits and at most 15 decimal places, and ``|x| < 1e15``. Every
operation result is rounded back into that range half away from zero; a result
outside the range is ``None``.

This mirrors ``webapp/src/lib/expressions/decimal.ts`` step for step on plain
integers (not the ``decimal`` module's context arithmetic), so both
implementations agree digit for digit.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional, Union

MAX_DIGITS = 15
MAX_SCALE = 15
_MAX_ADJ = 14
_GUARD_EXP = -(MAX_SCALE + 2)
_NUMBER = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?")

HALF_AWAY = "half_away"
FLOOR = "floor"
CEIL = "ceil"


def _digit_count(value: int) -> int:
    return len(str(abs(value)))


def _trunc_div(a: int, b: int) -> int:
    """Integer division truncating toward zero (like JS BigInt ``/``)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _trunc_mod(a: int, b: int) -> int:
    """Remainder with the sign of the dividend (like JS BigInt ``%``)."""
    r = abs(a) % abs(b)
    return r if a >= 0 else -r


def _round_coef(coef: int, drop: int, mode: str) -> int:
    divisor = 10**drop
    quotient = _trunc_div(coef, divisor)
    remainder = _trunc_mod(coef, divisor)
    if remainder == 0:
        return quotient
    negative = coef < 0
    if mode == FLOOR:
        return quotient - 1 if negative else quotient
    if mode == CEIL:
        return quotient if negative else quotient + 1
    if abs(remainder) * 2 >= divisor:
        return quotient - 1 if negative else quotient + 1
    return quotient


class Dec:
    """An in-range decimal number; build with :meth:`make` or :meth:`parse`."""

    __slots__ = ("coef", "exp")

    def __init__(self, coef: int, exp: int):
        self.coef = coef
        self.exp = exp

    @staticmethod
    def make(coef: int, exp: int) -> Optional["Dec"]:
        if coef == 0:
            return ZERO
        adj = _digit_count(coef) - 1 + exp
        position = max(adj - (MAX_DIGITS - 1), -MAX_SCALE)
        if exp < position:
            coef = _round_coef(coef, position - exp, HALF_AWAY)
            exp = position
        if coef == 0:
            return ZERO
        if _digit_count(coef) - 1 + exp > _MAX_ADJ:
            return None
        while coef % 10 == 0:
            coef //= 10
            exp += 1
        return Dec(coef, exp)

    @staticmethod
    def from_int(value: int) -> "Dec":
        return Dec.make(value, 0)  # type: ignore[return-value]

    @staticmethod
    def parse(text: str) -> Union["Dec", None, bool]:
        """Parse a plain decimal; ``False`` = not a number, ``None`` = out of range."""
        match = _NUMBER.fullmatch(text)
        if not match:
            return False
        int_part = match.group(2)
        frac_part = match.group(3) or ""
        if int_part == "" and frac_part == "":
            return False
        negative = match.group(1) == "-"
        exp_text = match.group(4) or "0"
        exp_digits = exp_text.lstrip("+-").lstrip("0")
        if len(exp_digits) > 6:
            if exp_text.startswith("-"):
                return ZERO
            exp10 = None
        else:
            exp10 = int(exp_text)
        digits = (int_part + frac_part).lstrip("0")
        if digits == "":
            return ZERO
        if exp10 is None:
            return None
        exp = exp10 - len(frac_part)
        adj = len(digits) - 1 + exp
        if adj > _MAX_ADJ:
            return None
        if adj < _GUARD_EXP:
            return ZERO
        if exp < _GUARD_EXP:
            drop = _GUARD_EXP - exp
            digits = digits[: max(len(digits) - drop, 0)]
            exp = _GUARD_EXP
            if digits == "":
                return ZERO
        coef = int(digits)
        return Dec.make(-coef if negative else coef, exp)

    @staticmethod
    def from_python(value) -> Optional["Dec"]:
        """An ``int``/``float``/``Decimal`` as a decimal (``bool`` is not a number)."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            if abs(value) >= 10**15:
                return None
            return Dec.make(value, 0)
        if isinstance(value, float):
            if value != value or value in (float("inf"), float("-inf")):
                return None
            parsed = Dec.parse(repr(value))
        elif isinstance(value, Decimal):
            if not value.is_finite():
                return None
            parsed = Dec.parse(str(value))
        else:
            return None
        return parsed if isinstance(parsed, Dec) else None

    def is_zero(self) -> bool:
        return self.coef == 0

    def is_integer(self) -> bool:
        return self.exp >= 0

    def neg(self) -> "Dec":
        return self if self.coef == 0 else Dec(-self.coef, self.exp)

    def abs(self) -> "Dec":
        return Dec(-self.coef, self.exp) if self.coef < 0 else self

    def _aligned(self, other: "Dec"):
        e = min(self.exp, other.exp)
        return self.coef * 10 ** (self.exp - e), other.coef * 10 ** (other.exp - e), e

    def add(self, other: "Dec") -> Optional["Dec"]:
        a, b, e = self._aligned(other)
        return Dec.make(a + b, e)

    def sub(self, other: "Dec") -> Optional["Dec"]:
        return self.add(other.neg())

    def mul(self, other: "Dec") -> Optional["Dec"]:
        return Dec.make(self.coef * other.coef, self.exp + other.exp)

    def div(self, other: "Dec") -> Optional["Dec"]:
        if other.coef == 0:
            return None
        shift = self.exp - other.exp - _GUARD_EXP
        if shift >= 0:
            numerator, denominator = self.coef * 10**shift, other.coef
        else:
            numerator, denominator = self.coef, other.coef * 10 ** (-shift)
        return Dec.make(_trunc_div(numerator, denominator), _GUARD_EXP)

    def mod(self, other: "Dec") -> Optional["Dec"]:
        if other.coef == 0:
            return None
        a, b, e = self._aligned(other)
        return Dec.make(_trunc_mod(a, b), e)

    def round(self, places: int, mode: str = HALF_AWAY) -> Optional["Dec"]:
        position = -places
        if self.exp >= position:
            return self
        return Dec.make(_round_coef(self.coef, position - self.exp, mode), position)

    def cmp(self, other: "Dec") -> int:
        a, b, _ = self._aligned(other)
        return -1 if a < b else 1 if a > b else 0

    def to_integer(self) -> Optional[int]:
        if not self.is_integer():
            return None
        return self.coef * 10**self.exp

    def __str__(self) -> str:
        if self.coef == 0:
            return "0"
        negative = self.coef < 0
        digits = str(abs(self.coef))
        if self.exp >= 0:
            text = digits + "0" * self.exp
        else:
            places = -self.exp
            if len(digits) <= places:
                digits = "0" * (places - len(digits) + 1) + digits
            text = f"{digits[:-places]}.{digits[-places:]}"
        return f"-{text}" if negative else text

    def __repr__(self) -> str:
        return f"Dec({self})"

    def to_decimal(self) -> Decimal:
        return Decimal(str(self))


ZERO = Dec(0, 0)
