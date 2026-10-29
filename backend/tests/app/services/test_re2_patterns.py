"""What an answer pattern must be to be saved (common form_spec/re2_patterns.py,
``checked_pattern``): RE2 syntax. Here, in the backend, because the backend
is the service with ``google-re2`` and the one that saves forms."""

import time

import pytest
from common.form_spec.models import PATTERN_MAX_LENGTH, checked_pattern
from common.form_spec.re2_patterns import re2_problem, to_re2_syntax


@pytest.mark.parametrize(
    "pattern",
    [
        "^[1-9][0-9]{3} ?[A-Za-z]{2}$",
        r"^[\p{L} '-]+$",
        r"^-?\d+$",
        "^(a+)+$",  # a backtracking shape is no problem for RE2
        r"^café$",
    ],
)
def test_a_pattern_re2_can_use_is_kept(pattern):
    assert re2_problem(pattern) is None
    assert checked_pattern(f"  {pattern} ") == pattern


@pytest.mark.parametrize(
    "pattern, reason",
    [
        ("(a", "missing )"),
        ("^(?=a)b$", "invalid perl operator"),
        ("^(?<!a)b$", "invalid"),
        (r"(a)\1", "invalid escape sequence"),
        ("[a-", "missing ]"),
    ],
)
def test_a_pattern_re2_cannot_use_is_refused_with_its_reason(pattern, reason):
    assert reason in re2_problem(pattern)
    with pytest.raises(ValueError) as refused:
        checked_pattern(pattern)
    assert reason in str(refused.value)
    assert "no lookarounds and no backreferences" in str(refused.value)


def test_nesting_cannot_make_the_check_slow():
    # 117 characters; a shape analysis took 29 s and 2 GB on it
    nested = "^" + "(?:" * 16 + "a*b" + "){3}" * 16 + "$"
    assert len(nested) <= PATTERN_MAX_LENGTH
    started = time.perf_counter()
    assert "invalid repetition size" in re2_problem(nested)
    assert time.perf_counter() - started < 0.5


def test_too_long_and_empty_patterns_are_refused_before_anything_runs():
    with pytest.raises(ValueError, match="at most 200"):
        checked_pattern("a" * (PATTERN_MAX_LENGTH + 1))
    with pytest.raises(ValueError, match="empty"):
        checked_pattern("   ")


def test_javascript_escapes_are_rewritten_for_re2():
    assert to_re2_syntax("^caf\\u00e9$") == "^caf\\x{00e9}$"
