"""Currencies a ``currency`` question can take, and the amount rules.

An answer is ``{"code": "EUR", "amount": "12.50"}``: the ISO 4217 code and the
amount as a plain decimal string, with at most as many decimals as the
currency has (``CURRENCY_DECIMALS``). The webapp keeps the same table
(``webapp/src/utils/currency.ts``); ``docs/spec/currencies-v1.json`` is the
copy both tests compare with.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

# Currency -> number of decimals (the ISO 4217 minor unit exponent).
CURRENCY_DECIMALS = {
    "AED": 2,
    "ARS": 2,
    "AUD": 2,
    "BGN": 2,
    "BRL": 2,
    "CAD": 2,
    "CHF": 2,
    "CLP": 0,
    "CNY": 2,
    "COP": 2,
    "CZK": 2,
    "DKK": 2,
    "EGP": 2,
    "EUR": 2,
    "GBP": 2,
    "HKD": 2,
    "HUF": 2,
    "IDR": 2,
    "ILS": 2,
    "INR": 2,
    "ISK": 0,
    "JPY": 0,
    "KRW": 0,
    "KWD": 3,
    "MAD": 2,
    "MXN": 2,
    "MYR": 2,
    "NGN": 2,
    "NOK": 2,
    "NZD": 2,
    "PHP": 2,
    "PLN": 2,
    "RON": 2,
    "SAR": 2,
    "SEK": 2,
    "SGD": 2,
    "THB": 2,
    "TND": 3,
    "TRY": 2,
    "UAH": 2,
    "USD": 2,
    "VND": 0,
    "ZAR": 2,
}
DEFAULT_CURRENCY = "EUR"
# At most this many allowed currencies on one question.
CURRENCIES_MAX = 10
# An amount has at most this many digits before the decimal point.
AMOUNT_MAX_INTEGER_DIGITS = 12

_AMOUNT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


def is_currency_code(code: object) -> bool:
    return isinstance(code, str) and code in CURRENCY_DECIMALS


def currency_decimals(code: str) -> int:
    return CURRENCY_DECIMALS.get(code, 2)


def parse_amount(amount: object, code: Optional[str] = None) -> Optional[Decimal]:
    """``amount`` as a Decimal when it is a plain decimal string with at most
    the currency's number of decimals (any number when ``code`` is not given
    or not listed), else None. No ``+``, no thousands separators, no decimal
    comma, no exponent, no leading zeros ("007"), no more than
    ``AMOUNT_MAX_INTEGER_DIGITS`` integer digits (``fullmatch``: no trailing
    newline)."""
    if not isinstance(amount, str) or not _AMOUNT.fullmatch(amount):
        return None
    whole, _, fraction = amount.lstrip("-").partition(".")
    if len(whole) > AMOUNT_MAX_INTEGER_DIGITS:
        return None
    if is_currency_code(code) and len(fraction) > CURRENCY_DECIMALS[code]:
        return None
    try:
        return Decimal(amount)
    except InvalidOperation:  # pragma: no cover - the pattern rules this out
        return None


# A wall-clock time: "HH:MM", 24 hours, zero-padded.
_TIME = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")


def is_time(value: object) -> bool:
    return isinstance(value, str) and _TIME.fullmatch(value) is not None


def minutes_of(value: str) -> int:
    """Minutes since midnight of a valid ``HH:MM``."""
    return int(value[:2]) * 60 + int(value[3:])
