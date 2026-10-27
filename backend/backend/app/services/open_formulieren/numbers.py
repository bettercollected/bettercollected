"""Numbers from the file, read defensively: a value that is huge, not finite,
not ASCII digits or too long is "not a number" (None), never an exception."""

from __future__ import annotations

import math
from typing import Any, Optional

from backend.app.services.open_formulieren import limits


def to_number(value: Any) -> Optional[float]:
    """A finite number of sensible size from a JSON number or a numeric
    string, else None (booleans are not numbers)."""
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, int):
            number = float(value) if abs(value) <= limits.MAX_NUMBER_VALUE else None
        elif isinstance(value, float):
            number = value
        elif isinstance(value, str):
            text = value.strip()
            if not text or len(text) > limits.MAX_NUMBER_TEXT or not text.isascii():
                return None
            number = float(text)
        else:
            return None
    except (ValueError, OverflowError):
        return None
    if number is None or not math.isfinite(number):
        return None
    return number if abs(number) <= limits.MAX_NUMBER_VALUE else None


def to_int(value: Any) -> Optional[int]:
    """A whole number of sensible size from a JSON number or a string of
    ASCII digits (optionally negative), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        digits = text[1:] if text.startswith("-") else text
        if not (
            0 < len(digits) <= 18 and digits.isascii() and digits.isdigit()
        ):
            return None
        return int(text)
    number = to_number(value)
    if number is None or number != int(number):
        return None
    return int(number)


def as_plain(number: float) -> Any:
    """``number`` as an int when it is whole (so 5.0 reads 5)."""
    return int(number) if number == int(number) else number
