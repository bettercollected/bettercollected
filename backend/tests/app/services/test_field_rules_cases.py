"""The shared cases of field rules (docs/spec/field-rules.cases.json): what
the rules decide for a set of answers (the answers they leave and the states
they give the questions). The webapp's src/lib/field-rules.cases.test.ts runs
the same file with its own evaluator, so the two cannot drift apart; cases
that also check validation are in docs/spec/answer-validation.cases.json."""

import json
from pathlib import Path

import pytest

from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.field_rules import resolve_field_rules

CASES_FILE = Path(__file__).resolve().parents[4] / "docs/spec/field-rules.cases.json"
CASES = json.loads(CASES_FILE.read_text("utf-8"))["cases"]


def _form(case):
    body = {"title": "Rules", "builderVersion": "v2", "fields": case["form"]}
    if case.get("hiddenFields"):
        body["hiddenFields"] = case["hiddenFields"]
    return _parse_form_body(json.dumps(body))


def _dump_states(states):
    """The states as the cases write them: question id (``group/question/item``
    inside a repeating group) -> locked, required, title, description."""
    found = {}

    def at(field_id, group_id=None, item=None):
        key = field_id if group_id is None else f"{group_id}/{field_id}/{item}"
        return found.setdefault(key, {})

    for field_id in states.locked:
        at(field_id)["locked"] = True
    for (field_id, group_id, item), required in states.required.items():
        at(field_id, group_id, item)["required"] = required
    for (field_id, group_id, item), texts in states.texts.items():
        at(field_id, group_id, item).update(texts)
    return found


def _stored(answers):
    plain = {
        key: (
            value.model_dump(exclude_none=True)
            if hasattr(value, "model_dump")
            else value
        )
        for key, value in answers.items()
    }
    # the respondent page's answers carry no question id: the cases leave it out
    return {
        key: {k: v for k, v in value.items() if k != "field"}
        for key, value in plain.items()
    }


def test_the_cases_are_uniquely_named_and_say_what_they_expect():
    names = [case["name"] for case in CASES]
    assert len(names) >= 40
    assert len(set(names)) == len(names)
    for case in CASES:
        assert "states" in case and "answersAfter" in case, case["name"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_shared_case(case):
    answers = StandardFormResponseCamelModel(answers=case["answers"]).answers
    resolved, states = resolve_field_rules(
        _form(case),
        answers,
        case.get("hiddenValues") or {},
        today=case.get("today"),
    )
    assert _dump_states(states) == case["states"]
    stored = _stored(resolved)
    for key, expected in case["answersAfter"].items():
        if expected is None:
            assert key not in stored, key
        else:
            assert stored.get(key) == expected, key
