"""Answer patterns a backtracking browser must not be handed
(common/form_spec/pattern_safety.py). The table of cases is shared with the
webapp: docs/spec/pattern-safety.cases.json. The check looks at the shape of
the pattern only, so these tests never run a pattern against a text."""

import json
import re
from pathlib import Path

import pytest
from common.form_spec.models import PATTERN_MAX_LENGTH, checked_pattern
from common.form_spec.pattern_safety import (
    HAZARD_MESSAGES,
    HAZARDS,
    pattern_hazard,
    pattern_hazard_message,
)

CASES = json.loads(
    (
        Path(__file__).resolve().parents[2] / "docs/spec/pattern-safety.cases.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("pattern", CASES["safe"])
def test_safe_patterns_are_accepted(pattern):
    assert pattern_hazard(pattern) is None


@pytest.mark.parametrize(
    "case", CASES["unsafe"], ids=lambda c: c["hazard"] + ":" + c["pattern"][:30]
)
def test_unsafe_patterns_are_refused_with_their_hazard(case):
    assert pattern_hazard(case["pattern"]) == case["hazard"]


def test_the_cases_cover_every_hazard():
    assert {c["hazard"] for c in CASES["unsafe"]} == set(HAZARDS)
    assert set(HAZARD_MESSAGES) == set(HAZARDS)


def test_no_pattern_is_no_hazard():
    assert pattern_hazard(None) is None
    assert pattern_hazard("") is None
    assert pattern_hazard_message("^a+$") is None


def test_checked_pattern_refuses_an_unsafe_pattern_with_its_message():
    for case in CASES["unsafe"]:
        pattern = case["pattern"]
        if len(pattern) > PATTERN_MAX_LENGTH:
            continue
        try:
            re.compile(pattern)
        except re.error:
            continue  # refused earlier as not a valid pattern
        with pytest.raises(ValueError) as refused:
            checked_pattern(pattern)
        assert str(refused.value) == HAZARD_MESSAGES[case["hazard"]]


def test_checked_pattern_keeps_a_safe_pattern():
    for pattern in CASES["safe"]:
        try:
            re.compile(pattern)
        except re.error:
            continue  # the webapp's syntax (\\p{L}, \\u{...}): not a Python pattern
        assert checked_pattern(f"  {pattern} ") == pattern
