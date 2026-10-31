"""Currencies and amounts of the currency question (common/currencies.py)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from common.currencies import (
    AMOUNT_MAX_INTEGER_DIGITS,
    CURRENCIES_MAX,
    CURRENCY_DECIMALS,
    currency_decimals,
    is_currency_code,
    is_time,
    minutes_of,
    parse_amount,
)

SHARED = json.loads(
    (Path(__file__).resolve().parents[2] / "docs/spec/currencies-v1.json").read_text()
)


def test_the_table_is_the_shared_one():
    # the webapp's table is compared with the same file
    assert SHARED["decimals"] == CURRENCY_DECIMALS
    assert SHARED["maxCurrencies"] == CURRENCIES_MAX
    assert SHARED["maxIntegerDigits"] == AMOUNT_MAX_INTEGER_DIGITS


def test_codes_and_decimals():
    assert is_currency_code("EUR") and is_currency_code("JPY")
    assert not is_currency_code("eur") and not is_currency_code("XXX")
    assert not is_currency_code(None) and not is_currency_code(978)
    assert [currency_decimals(c) for c in ("EUR", "JPY", "KWD")] == [2, 0, 3]
    assert currency_decimals("???") == 2


@pytest.mark.parametrize(
    "amount,code,expected",
    [
        ("12.50", "EUR", Decimal("12.50")),
        ("12", "EUR", Decimal("12")),
        ("0", "EUR", Decimal("0")),
        ("0.05", "EUR", Decimal("0.05")),
        ("-5", "EUR", Decimal("-5")),
        ("1000", "JPY", Decimal("1000")),
        ("1.234", "KWD", Decimal("1.234")),
        ("12.50", None, Decimal("12.50")),
        ("12.505", None, Decimal("12.505")),
        ("9" * AMOUNT_MAX_INTEGER_DIGITS, "EUR", Decimal("9" * AMOUNT_MAX_INTEGER_DIGITS)),
    ],
)
def test_amounts_that_are_plain_decimals(amount, code, expected):
    assert parse_amount(amount, code) == expected


@pytest.mark.parametrize(
    "amount,code",
    [
        ("12,50", "EUR"),
        ("12.505", "EUR"),
        ("100.5", "JPY"),
        ("1.2345", "KWD"),
        ("1,250.00", "EUR"),
        ("1e3", "EUR"),
        ("+5", "EUR"),
        ("007", "EUR"),
        ("-", "EUR"),
        ("12.", "EUR"),
        (".5", "EUR"),
        (" 12", "EUR"),
        ("12\n", "EUR"),
        ("", "EUR"),
        ("NaN", "EUR"),
        ("1" + "0" * AMOUNT_MAX_INTEGER_DIGITS, "EUR"),
        (12, "EUR"),
        (None, "EUR"),
        (12.5, "EUR"),
    ],
)
def test_amounts_that_are_not(amount, code):
    assert parse_amount(amount, code) is None


@pytest.mark.parametrize("value", ["00:00", "09:30", "12:00", "23:59"])
def test_times(value):
    assert is_time(value)


@pytest.mark.parametrize(
    "value", ["24:00", "12:60", "9:30", "09:30:00", "0930", "noon", "", "09:30\n", None, 930]
)
def test_not_times(value):
    assert not is_time(value)


def test_minutes():
    assert minutes_of("00:00") == 0
    assert minutes_of("09:30") == 570
    assert minutes_of("23:59") == 1439
