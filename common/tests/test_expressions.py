"""Expressions v1: the shared conformance corpus plus Python-specific checks.

The corpus (docs/spec/expressions-v1.cases.json) is also run by the webapp's
vitest suite, so both implementations are held to the same results.
"""

import json
import time
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
from common.expressions import evaluator
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


def _build(spec):
    """Expand a corpus ``repeat`` spec into a value."""
    if isinstance(spec, dict) and "text" in spec:
        return spec["text"] * spec["times"]
    if isinstance(spec, dict) and "list" in spec:
        return [_build(spec["list"]) for _ in range(spec["times"])]
    return spec


def _vars(case):
    variables = dict(case.get("vars", {}))
    for key, spec in case.get("repeat", {}).items():
        variables[key] = _build(spec)
    return variables


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_corpus_case(case):
    run = lambda: evaluate_expression(  # noqa: E731
        case["ast"], _vars(case), case.get("context", {})
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


def test_input_caps():
    assert evaluate_expression({"var": "s"}, {"s": "a" * 10001}) is None
    assert evaluate_expression({"var": "xs"}, {"xs": ("a",) * 1001}) is None
    assert evaluate_expression({"var": "xs"}, {"xs": ["a" * 10001, "b"]}) == [
        None,
        "b",
    ]


def test_numeric_text_with_long_whitespace_runs():
    padding = " " * 4999
    assert evaluate_expression(
        {"+": [{"var": "s"}, 1]}, {"s": f"{padding}2{padding}"}
    ) == Decimal(3)
    assert evaluate_expression({"+": [{"var": "s"}, 1]}, {"s": " " * 10000}) is None


@pytest.mark.parametrize("size", [10000, 1000])
def test_large_list_referenced_many_times_is_fast(size, monkeypatch):
    """A large list referenced ~500 times: over-cap input is dropped once and
    each variable is normalised once per evaluation."""
    normalised, items = [], []
    real_from_input = evaluator._from_input
    real_scalar = evaluator._scalar_from_input
    monkeypatch.setattr(
        evaluator,
        "_from_input",
        lambda value: normalised.append(1) or real_from_input(value),
    )
    monkeypatch.setattr(
        evaluator,
        "_scalar_from_input",
        lambda value: items.append(1) or real_scalar(value),
    )
    ast = {"count": [{"var": "xs"} for _ in range(499)]}
    xs = list(range(size))
    started = time.perf_counter()
    result = evaluate_expression(ast, {"xs": xs})
    elapsed = time.perf_counter() - started
    assert result == (Decimal(0) if size > 1000 else Decimal(499 * size))
    # normalised once; an over-cap list is dropped without reading its items
    assert len(normalised) == 1
    assert len(items) == (0 if size > 1000 else size)
    # smoke check only, far above the expected time (shared CI runners vary)
    assert elapsed < 5


def test_list_variables_are_parsed_once_per_evaluation(monkeypatch):
    """A 500-node sum over a 50-item group answer parses each item once, not
    once per reference (mechanism, not wall time)."""
    from common.expressions import decimal_num, evaluator

    calls = {"parse": 0}
    original = decimal_num.Dec.parse

    def counting(text):
        calls["parse"] += 1
        return original(text)

    monkeypatch.setattr(decimal_num.Dec, "parse", staticmethod(counting))
    items = [str(i) for i in range(50)]
    ast = {"sum": [{"var": "g.amount"}] * 499}
    result = evaluator.evaluate_expression(ast, {"g.amount": items})
    assert result == 499 * sum(range(50))
    assert calls["parse"] == 50
    # a scalar text read by many nodes is parsed once
    calls["parse"] = 0
    ast = {"+": [{"var": "n"}] * 400}
    assert evaluator.evaluate_expression(ast, {"n": "2.5"}) == 1000
    assert calls["parse"] == 1
    # a list's text is joined once; the memo ends with the evaluation
    ast = {"concat": [{"var": "g.amount"}] * 2}
    assert evaluator.evaluate_expression(ast, {"g.amount": ["a", "b"]}) == "a, ba, b"
    assert evaluator._MEMO.get() is None
    # and the next evaluation starts afresh
    calls["parse"] = 0
    evaluator.evaluate_expression({"sum": [{"var": "g"}]}, {"g": items})
    assert calls["parse"] == 50
