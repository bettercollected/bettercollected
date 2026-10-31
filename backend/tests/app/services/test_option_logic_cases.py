"""The shared cases of choice-level logic (docs/spec/option-logic.cases.json):
which options a question offers for a set of answers, the problems server
answer validation reports, and the warnings. The webapp's
src/utils/option-logic.cases.test.ts runs the same file with its own
evaluator, so the two cannot drift apart."""

import json
from pathlib import Path

import pytest

from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.answer_validation import answer_ids, validate_answers
from backend.app.services.field_rules import FieldRuleStates
from backend.app.services.option_logic import option_logic_warnings, option_states

CASES_FILE = Path(__file__).resolve().parents[4] / "docs/spec/option-logic.cases.json"
CASES = json.loads(CASES_FILE.read_text("utf-8"))["cases"]


def _form(case):
    return _parse_form_body(
        json.dumps({"title": "Options", "builderVersion": "v2", "fields": case["form"]})
    )


def _answers(case):
    return StandardFormResponseCamelModel(answers=case["answers"]).answers


def test_the_cases_are_uniquely_named_and_say_what_they_expect():
    names = [case["name"] for case in CASES]
    assert len(names) >= 40
    assert len(set(names)) == len(names)
    for case in CASES:
        assert "hidden" in case and "noneLeft" in case, case["name"]
        assert ("validate" in case["checks"]) == ("errors" in case), case["name"]
        assert ("clear" in case["checks"]) == ("answersAfter" in case), case["name"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_options_offered(case):
    form = _form(case)
    states = option_states(form, _answers(case), locked=case.get("locked", []))
    assert {key: sorted(value) for key, value in states.hidden.items()} == {
        key: sorted(value) for key, value in case["hidden"].items()
    }
    assert sorted(states.none_left) == sorted(case["noneLeft"])


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if "validate" in c["checks"]],
    ids=[c["name"] for c in CASES if "validate" in c["checks"]],
)
def test_server_validation(case):
    form = _form(case)
    states = FieldRuleStates(locked=set(case.get("locked", [])))
    found = validate_answers(
        form, _answers(case), known_ids=answer_ids(form), rule_states=states
    )
    assert sorted((p.field_id, p.rule) for p in found) == sorted(
        (e["fieldId"], e["rule"]) for e in case["errors"]
    )


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if "warnings" in c],
    ids=[c["name"] for c in CASES if "warnings" in c],
)
def test_warnings(case):
    found = option_logic_warnings(_form(case))
    assert sorted((w.field_id, w.code, w.option_id or "") for w in found) == sorted(
        (w["fieldId"], w["code"], w.get("optionId", "")) for w in case["warnings"]
    )
