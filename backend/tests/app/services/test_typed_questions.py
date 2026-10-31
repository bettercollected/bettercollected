"""The time, day and currency questions on the server: submission, response
edit, date rules, exports of answers and what an error may carry. The rules of
each type are in the shared cases (docs/spec/answer-validation.cases.json);
this covers the paths around them."""

import datetime as dt
import json

import pytest

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.date_rules import validate_date_rule_answers
from backend.app.services.ai.insights import _answer_text
from tests.app.controllers.data import testUser

SECRET_TIME = "13:37"
PAGES = [
    {
        "id": "p1",
        "type": "slide",
        "properties": {
            "fields": [
                {
                    "id": "arrival",
                    "type": "time",
                    "title": "Arrival",
                    "properties": {"minTime": "08:00", "maxTime": "17:30"},
                    "validations": {"required": True},
                },
                {
                    "id": "born",
                    "type": "day",
                    "title": "Born",
                    "properties": {
                        "dateRules": [{"comparison": "before", "target": "today"}]
                    },
                },
                {
                    "id": "budget",
                    "type": "currency",
                    "title": "Budget",
                    "properties": {"currencies": ["EUR", "GBP"]},
                    "validations": {"minValue": 10, "maxValue": 1000},
                },
            ]
        },
    }
]


def _form(pages=PAGES):
    return _parse_form_body(
        json.dumps({"title": "Typed", "builderVersion": "v2", "fields": pages})
    )


async def _published(workspace):
    service = container.workspace_form_service()
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


GOOD = {
    "arrival": {"type": "time", "time": "09:30"},
    "born": {"type": "date", "date": "1990-11-05"},
    "budget": {"type": "currency", "currency": {"code": "GBP", "amount": "250.50"}},
}


@pytest.mark.asyncio
async def test_a_valid_submission_is_stored(workspace):
    form = await _published(workspace)
    response = await _submit(workspace, form, GOOD)
    assert response.response_id


@pytest.mark.asyncio
async def test_problems_are_refused_with_ids_and_codes_never_the_answer(workspace):
    form = await _published(workspace)
    answers = {
        **GOOD,
        "arrival": {"type": "time", "time": "18:00"},
        "budget": {"type": "currency", "currency": {"code": "USD", "amount": "5"}},
    }
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, answers)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_answers"
    assert sorted((e["fieldId"], e["rule"]) for e in error.value.content["errors"]) == [
        ("arrival", "too_large"),
        ("budget", "currency"),
    ]
    assert "18:00" not in json.dumps(error.value.content)
    assert "USD" not in json.dumps(error.value.content)


@pytest.mark.asyncio
async def test_a_required_time_left_out_is_refused(workspace):
    form = await _published(workspace)
    answers = {k: v for k, v in GOOD.items() if k != "arrival"}
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, answers)
    assert error.value.content["errors"] == [{"fieldId": "arrival", "rule": "required"}]


@pytest.mark.asyncio
async def test_an_answer_in_another_types_slot_is_the_wrong_type(workspace):
    form = await _published(workspace)
    answers = {**GOOD, "arrival": {"type": "text", "text": SECRET_TIME}}
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, answers)
    assert {"fieldId": "arrival", "rule": "type"} in error.value.content["errors"]
    assert SECRET_TIME not in json.dumps(error.value.content)


def test_a_day_breaks_its_date_rule_like_a_date_does():
    form = _form()
    tomorrow = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=3)).isoformat()
    problems = validate_date_rule_answers(
        form, {"born": {"type": "date", "date": tomorrow}}
    )
    assert problems == ["'Born' must be before today."]
    assert validate_date_rule_answers(form, {"born": {"type": "date", "date": "1990-11-05"}}) == []


def test_an_impossible_day_is_not_a_valid_date_to_the_date_rules_either():
    problems = validate_date_rule_answers(
        _form(), {"born": {"type": "date", "date": "2026-02-30"}}
    )
    assert problems == ["The answer to 'Born' is not a valid date (YYYY-MM-DD)."]


def test_the_ai_insights_read_the_new_answers_as_plain_text():
    assert _answer_text(GOOD["arrival"], {}) == "09:30"
    assert _answer_text(GOOD["budget"], {}) == "GBP 250.50"
