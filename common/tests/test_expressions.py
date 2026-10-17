"""Expressions v1: the shared conformance corpus plus Python-specific checks.

The corpus (docs/spec/expressions-v1.cases.json) is also run by the webapp's
vitest suite, so both implementations are held to the same results.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from common.expressions import (
    ExpressionError,
    evaluate_expression,
    format_expression_value,
    is_valid_expression,
    validate_expression,
)
from common.expressions.decimal_num import Dec

CORPUS = (
    Path(__file__).resolve().parents[2] / "docs" / "spec" / "expressions-v1.cases.json"
)
# Floats as JSON numbers arrive in production too (answers posted by the webapp).
CASES = json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]


def _same(actual, expected) -> bool:
    """Type-aware equality: numbers are Decimal results vs JSON numbers."""
    if expected is None or isinstance(expected, (bool, str)):
        return type(actual) is type(expected) and actual == expected
    if isinstance(expected, (int, float)):
        if not isinstance(actual, Decimal):
            return False
        return actual == Dec.from_python(expected).to_decimal()
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_same(a, e) for a, e in zip(actual, expected))
        )
    return False


def test_corpus_is_large_enough():
    assert len(CASES) >= 150
    assert len({case["name"] for case in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_corpus_case(case):
    run = lambda: evaluate_expression(  # noqa: E731
        case["ast"], case.get("vars", {}), case.get("context", {})
    )
    if "error" in case:
        with pytest.raises(ExpressionError) as info:
            run()
        assert info.value.code == case["error"]
        return
    result = run()
    assert _same(result, case["expected"]), f"{result!r} != {case['expected']!r}"


def test_numbers_come_back_as_normalised_decimals():
    assert evaluate_expression({"+": [0.1, 0.2]}) == Decimal("0.3")
    assert str(evaluate_expression({"*": [2.5, 4]})) == "10"
    assert str(evaluate_expression({"-": [0]})) == "0"


def test_python_number_inputs():
    assert evaluate_expression({"var": "x"}, {"x": Decimal("1.50")}) == Decimal("1.5")
    assert evaluate_expression({"var": "x"}, {"x": 10**20}) is None
    assert evaluate_expression({"var": "x"}, {"x": Decimal("NaN")}) is None
    assert evaluate_expression({"var": "x"}, {"x": float("inf")}) is None
    assert evaluate_expression({"var": "x"}, {"x": ("a", 1)}) == ["a", Decimal(1)]
    # bool is an int subclass in Python, but never a number here.
    assert evaluate_expression({"+": [{"var": "x"}, 1]}, {"x": True}) is None
    assert evaluate_expression({"+": [True, 1]}) is None


def test_decimal_literals_in_ast():
    assert evaluate_expression({"+": [Decimal("0.1"), Decimal("0.2")]}) == Decimal(
        "0.3"
    )
    problems = validate_expression({"+": [Decimal("1E+15"), 1]})
    assert [p.code for p in problems] == ["invalid_literal"]


def test_validator_reports_paths_and_all_problems():
    problems = validate_expression({"+": [{"var": ""}, {"/": [1]}, {"pow": [1, 2]}]})
    assert [(p.code, p.path) for p in problems] == [
        ("invalid_var", "/+/0/var"),
        ("arity", "/+/1/~1"),
        ("unknown_operator", "/+/2/pow"),
    ]


def test_validator_known_variables():
    ast = {"+": [{"var": "a"}, {"var": "b"}]}
    assert is_valid_expression(ast, known_variables={"a", "b"})
    problems = validate_expression(ast, known_variables=["a"])
    assert [(p.code, p.path) for p in problems] == [("unknown_variable", "/+/1/var")]


def test_deeply_nested_input_does_not_recurse_without_bound():
    node = 1
    for _ in range(100000):
        node = {"-": [node]}
    with pytest.raises(ExpressionError) as info:
        evaluate_expression(node)
    assert info.value.code == "too_deep"


def test_format_expression_value():
    assert format_expression_value(Decimal("1E-7")) == "0.0000001"
    assert format_expression_value(Decimal("1.50")) == "1.5"
    assert format_expression_value(True) == "true"
    assert format_expression_value(None) == ""
    assert format_expression_value(["a", None, Decimal(2)]) == "a, 2"


def test_error_message_is_neutral_and_has_path():
    with pytest.raises(ExpressionError) as info:
        evaluate_expression({"round": [1, 2, 3]})
    assert info.value.code == "arity"
    assert info.value.path == "/round"
    assert "round" in str(info.value)
