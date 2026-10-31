"""The date range and tags questions on the server: submission, the date
rules of both ends of a range, answers read as conditions, in a repeating
group and by the AI insights. The rules of each type are in the shared cases
(docs/spec/answer-validation.cases.json); this covers the paths around them."""

import contextlib
import datetime as dt
import json

import pytest

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.ai.insights import _answer_text
from backend.app.services.date_rules import validate_date_rule_answers
from backend.app.services.repeating_groups import (
    comparable_answer_value,
    date_range_days,
    evaluate_condition,
)
from backend.config import settings
from tests.app.controllers.data import testUser

SECRET_TAG = "confidential-topic"
PAGES = [
    {
        "id": "p1",
        "type": "slide",
        "properties": {
            "fields": [
                {
                    "id": "stay",
                    "type": "date_range",
                    "title": "Stay",
                    "properties": {
                        "dateRules": [
                            {"comparison": "on_or_after", "target": "date", "date": "2026-01-01"},
                            {"comparison": "on_or_before", "target": "date", "date": "2030-12-31"},
                        ]
                    },
                    "validations": {"required": True},
                },
                {
                    "id": "topics",
                    "type": "tags",
                    "title": "Topics",
                    "validations": {"minChoices": 1, "maxChoices": 3, "maxLength": 20},
                },
            ]
        },
    }
]


def _form(pages=PAGES):
    return _parse_form_body(
        json.dumps({"title": "Ranged", "builderVersion": "v2", "fields": pages})
    )


@contextlib.contextmanager
def _switch(on: bool):
    before = settings.NEW_QUESTION_TYPES_ENABLED
    settings.NEW_QUESTION_TYPES_ENABLED = on
    try:
        yield
    finally:
        settings.NEW_QUESTION_TYPES_ENABLED = before


async def _published(workspace):
    service = container.workspace_form_service()
    with _switch(True):
        form = await service.create_form(workspace.id, _form(), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


async def _submit(workspace, form, answers):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=answers),
        testUser,
    )


def _range(start, end):
    return {"type": "date_range", "date_range": {"start": start, "end": end}}


GOOD = {
    "stay": _range("2026-11-03", "2026-11-07"),
    "topics": {"type": "tags", "tags": ["vegan", "quiet"]},
}


@pytest.mark.asyncio
async def test_a_valid_submission_is_stored_while_the_switch_is_off(workspace):
    form = await _published(workspace)
    assert settings.NEW_QUESTION_TYPES_ENABLED is False
    response = await _submit(workspace, form, GOOD)
    assert response.response_id


@pytest.mark.asyncio
async def test_problems_are_refused_with_ids_and_codes_never_the_answer(workspace):
    form = await _published(workspace)
    answers = {
        "stay": _range("2026-11-07", "2026-11-03"),
        "topics": {"type": "tags", "tags": [SECRET_TAG + "-a", SECRET_TAG + "-A"]},
    }
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, answers)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_answers"
    assert sorted((e["fieldId"], e["rule"]) for e in error.value.content["errors"]) == [
        ("stay", "range_order"),
        ("topics", "duplicate"),
    ]
    assert SECRET_TAG not in json.dumps(error.value.content)
    assert "2026-11-07" not in json.dumps(error.value.content)


@pytest.mark.asyncio
async def test_a_required_range_left_out_or_half_given_is_refused(workspace):
    form = await _published(workspace)
    for stay in (None, _range("2026-11-03", None)):
        answers = {k: v for k, v in GOOD.items() if k != "stay"}
        if stay:
            answers["stay"] = stay
        with pytest.raises(HTTPException) as error:
            await _submit(workspace, form, answers)
        assert error.value.content["errors"] == [{"fieldId": "stay", "rule": "required"}]


@pytest.mark.asyncio
async def test_answers_in_another_types_slot_are_the_wrong_type(workspace):
    form = await _published(workspace)
    answers = {
        "stay": {"type": "date", "date": "2026-11-03"},
        "topics": {"type": "text", "text": SECRET_TAG},
    }
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, answers)
    got = error.value.content["errors"]
    assert {"fieldId": "stay", "rule": "type"} in got
    assert {"fieldId": "topics", "rule": "type"} in got
    assert SECRET_TAG not in json.dumps(error.value.content)


def test_both_ends_of_a_range_meet_its_date_rules():
    form = _form()
    ok = validate_date_rule_answers(form, {"stay": _range("2026-11-03", "2026-11-07")})
    assert ok == []
    problems = validate_date_rule_answers(form, {"stay": _range("2025-12-31", "2031-01-01")})
    assert len(problems) == 2
    assert problems[0].startswith("The start of 'Stay' must be on or after")
    assert problems[1].startswith("The end of 'Stay' must be on or before")


def test_a_range_may_meet_its_rules_on_the_bounds_and_with_one_end_missing():
    form = _form()
    assert validate_date_rule_answers(form, {"stay": _range("2026-01-01", "2030-12-31")}) == []
    # the half-given range is the answer rules' to refuse; a missing end breaks no date rule
    assert validate_date_rule_answers(form, {"stay": _range("2026-11-03", None)}) == []
    assert validate_date_rule_answers(form, {"stay": _range("2025-01-01", None)}) != []


def test_a_range_follows_today_and_another_date_question():
    pages = [
        {
            "id": "p1",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "open", "type": "date", "title": "Opens"},
                    {
                        "id": "stay",
                        "type": "date_range",
                        "title": "Stay",
                        "properties": {
                            "dateRules": [{"comparison": "after", "target": "field", "fieldId": "open"}]
                        },
                    },
                ]
            },
        }
    ]
    form = _form(pages)
    answers = {"open": {"type": "date", "date": "2026-06-01"}}
    assert validate_date_rule_answers(form, {**answers, "stay": _range("2026-06-02", "2026-06-09")}) == []
    problems = validate_date_rule_answers(form, {**answers, "stay": _range("2026-06-01", "2026-06-09")})
    assert len(problems) == 1 and problems[0].startswith("The start of 'Stay'")
    tomorrow = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=3)).isoformat()
    in_range = _form(
        [
            {
                "id": "p1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "stay",
                            "type": "date_range",
                            "title": "Stay",
                            "properties": {"dateRules": [{"comparison": "before", "target": "today"}]},
                        }
                    ]
                },
            }
        ]
    )
    problems = validate_date_rule_answers(in_range, {"stay": _range("2020-01-01", tomorrow)})
    assert problems == ["The end of 'Stay' must be before today."]


def test_a_date_range_cannot_be_the_target_of_a_date_rule():
    from common.models.standard_form import date_rule_problems

    form = _form(
        [
            {
                "id": "p1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "stay", "type": "date_range", "title": "Stay"},
                        {
                            "id": "when",
                            "type": "date",
                            "title": "When",
                            "properties": {
                                "dateRules": [{"comparison": "after", "target": "field", "fieldId": "stay"}]
                            },
                        },
                    ]
                },
            }
        ]
    )
    problems = date_rule_problems(form.fields)
    assert len(problems) == 1 and "which is not a date question" in problems[0]


def test_the_ai_insights_read_the_new_answers_as_plain_text():
    assert _answer_text(GOOD["stay"], {}) == "2026-11-03/2026-11-07"
    assert _answer_text(GOOD["topics"], {}) == "vegan; quiet"


def test_the_days_and_tags_of_an_answer():
    assert date_range_days(GOOD["stay"]) == ("2026-11-03", "2026-11-07")
    assert date_range_days(_range("2026-11-03", "nonsense")) == ("2026-11-03", None)
    assert date_range_days(None) == (None, None)
    assert comparable_answer_value(GOOD["stay"], "date_range") == {"start": "2026-11-03", "end": "2026-11-07"}
    assert comparable_answer_value({}, "date_range") is None
    assert comparable_answer_value(GOOD["topics"], "tags") == ["vegan", "quiet"]
    assert comparable_answer_value({"type": "tags", "tags": "x"}, "tags") is None


def test_a_condition_reads_a_range_and_tags():
    answers = dict(GOOD)

    def holds(field_type, field_id, comparison, value=None):
        return evaluate_condition(
            answers,
            {"fieldId": field_id, "fieldType": field_type, "comparison": comparison, "value": value},
        )

    assert holds("date_range", "stay", "CONTAINS", "2026-11-05")
    assert not holds("date_range", "stay", "CONTAINS", "2026-11-08")
    assert holds("date_range", "stay", "DOES_NOT_CONTAIN", "2026-11-08")
    assert holds("date_range", "stay", "GREATER_THAN", "2026-11-02")
    assert not holds("date_range", "stay", "GREATER_THAN", "2026-11-03")
    assert holds("date_range", "stay", "LESS_THAN", "2026-11-08")
    assert not holds("date_range", "stay", "CONTAINS", "tomorrow")
    assert not holds("date_range", "stay", "IS_EQUAL", "2026-11-03")
    assert holds("tags", "topics", "CONTAINS", "VEGAN")
    assert holds("tags", "topics", "IS_NOT_EMPTY")
    assert not holds("tags", "topics", "CONTAINS", "halal")
    assert holds("tags", "missing", "IS_EMPTY")


def test_a_group_item_can_hold_a_range_and_tags():
    from backend.app.services.answer_validation import validate_answers

    form = _form(
        [
            {
                "id": "p1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "g",
                            "type": "group",
                            "title": "Guests",
                            "properties": {
                                "repeat": {"minItems": 1, "maxItems": 3},
                                "fields": [
                                    {"id": "stay", "type": "date_range", "title": "Stay", "validations": {"required": True}},
                                    {"id": "likes", "type": "tags", "title": "Likes"},
                                ],
                            },
                        }
                    ]
                },
            }
        ]
    )
    good = {"g": {"type": "group", "items": [{"stay": _range("2026-01-01", "2026-01-03"), "likes": {"type": "tags", "tags": ["a"]}}]}}
    assert validate_answers(form, good) == []
    bad = {"g": {"type": "group", "items": [{"stay": _range("2026-01-05", "2026-01-03"), "likes": {"type": "tags", "tags": ["a", "A"]}}]}}
    rules = sorted((p.field_id, p.rule) for p in validate_answers(form, bad))
    assert rules == [("likes", "duplicate"), ("stay", "range_order")]


# --- the limits of a tags question hold on every path --------------------------------


@pytest.mark.parametrize(
    "validations,message",
    [
        ({"maxChoices": 0}, "most tags is between 1 and 30"),
        ({"maxChoices": 31}, "most tags is between 1 and 30"),
        ({"minChoices": 31}, "fewest tags is between 0 and 30"),
        ({"minChoices": 5, "maxChoices": 3}, "fewest tags is more than the most"),
        ({"maxLength": 0}, "length of a tag is between 1 and 40"),
        ({"maxLength": 999}, "length of a tag is between 1 and 40"),
    ],
)
def test_a_tags_question_cannot_be_given_limits_that_leave_nothing_to_answer(validations, message):
    from pydantic import ValidationError

    from backend.app.models.dtos.response_dtos import StandardFormFieldCamelModel
    from common.form_spec.models import FormField
    from common.models.standard_form import StandardFormField

    field = {"id": "t", "type": "tags", "title": "Topics"}
    with pytest.raises(ValidationError, match=message):
        StandardFormField.model_validate({**field, "validations": _snake(validations)})
    with pytest.raises(ValidationError, match=message):
        StandardFormFieldCamelModel.model_validate({**field, "validations": validations})
    with pytest.raises(ValidationError, match=message):
        FormField.model_validate({"id": "t", "type": "tags", "title": "Topics", "validations": _snake(validations)})
    # the same limits on a question of another type are not this check's
    StandardFormField.model_validate({**field, "type": "multiple_choice", "validations": _snake(validations)})


def _snake(validations):
    names = {"minChoices": "min_choices", "maxChoices": "max_choices", "maxLength": "max_length"}
    return {names[key]: value for key, value in validations.items()}


def test_the_limits_within_the_caps_are_taken():
    from common.models.standard_form import StandardFormField

    for validations in ({"min_choices": 0}, {"max_choices": 30, "max_length": 40}, {"min_choices": 3, "max_choices": 3}, {"max_length": 1}):
        StandardFormField.model_validate({"id": "t", "type": "tags", "title": "Topics", "validations": validations})


def test_a_spec_document_with_impossible_tag_limits_is_not_valid():
    from backend.app.services.form_spec.checks import check_spec_document

    spec = {
        "specVersion": "1",
        "title": "T",
        "pages": [{"id": "p1", "fields": [{"id": "t", "type": "tags", "title": "Topics", "validations": {"maxChoices": 0, "maxLength": 999}}]}],
    }
    result = check_spec_document(spec)
    assert result["valid"] is False
    assert any("tags" in e["message"] for e in result["errors"])


# --- what a condition on these questions may ask -------------------------------------


@pytest.mark.parametrize("kind,comparison,allowed", [
    ("tags", "STARTS_WITH", False),
    ("tags", "ENDS_WITH", False),
    ("tags", "GREATER_THAN", False),
    ("tags", "CONTAINS", True),
    ("tags", "IS_EMPTY", True),
    ("date_range", "STARTS_WITH", False),
    ("date_range", "IS_EQUAL", False),
    ("date_range", "CONTAINS", True),
    ("date_range", "GREATER_THAN", True),
])
def test_the_spec_check_refuses_a_comparison_a_tags_or_range_question_cannot_make(kind, comparison, allowed):
    from backend.app.services.form_spec.checks import check_spec_document

    spec = {
        "specVersion": "1",
        "title": "T",
        "pages": [
            {
                "id": "p1",
                "fields": [
                    {"id": "src", "type": kind, "title": "Source"},
                    {
                        "id": "q2",
                        "type": "short_text",
                        "title": "Asked",
                        "logic": {"action": "SHOW", "conditions": [{"fieldId": "src", "comparison": comparison, "value": "2026-01-01" if kind == "date_range" else "vegan"}]},
                    },
                ],
            }
        ],
    }
    result = check_spec_document(spec)
    refused = [e for e in result["errors"] if e["path"].endswith("/comparison")]
    assert bool(refused) is (not allowed), result["errors"]


# --- a rule may not read its own range ----------------------------------------------


def test_a_rule_on_a_range_cannot_read_its_own_days():
    from backend.app.services.field_rules import field_rule_problems

    def form(variable):
        return _form(
            [
                {
                    "id": "p1",
                    "type": "slide",
                    "properties": {
                        "fields": [
                            {
                                "id": "stay",
                                "type": "date_range",
                                "title": "Stay",
                                "properties": {
                                    "rules": [
                                        {
                                            "id": "r1",
                                            "when": {"expression": {">": [{"date_diff_days": [{"var": variable}, {"var": "stay.end"}]}, 3]}},
                                            "then": {"required": True},
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                }
            ]
        )

    for variable in ("stay.start", "stay.end"):
        problems = field_rule_problems(form(variable))
        assert any("own value" in p.message for p in problems), variable
    # a rule on another question reads the range freely
    reader = {
        "id": "b",
        "type": "short_text",
        "title": "B",
        "properties": {"rules": [{"id": "r2", "when": {"expression": {">": [{"date_diff_days": [{"var": "s.start"}, {"var": "s.end"}]}, 3]}}, "then": {"required": True}}]},
    }
    other = _form([{"id": "p1", "type": "slide", "properties": {"fields": [{"id": "s", "type": "date_range", "title": "S"}, reader]}}])
    assert field_rule_problems(other) == []
