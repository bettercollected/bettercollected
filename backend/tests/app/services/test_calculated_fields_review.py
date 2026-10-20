"""Calculated fields, review follow-ups: the per-form cap, placement and
Required, empty submissions, the respondent's "today", draft-only
calculations, evaluation off the event loop, and calculations kept from
respondents in every copy of their answers."""

import datetime as dt
import json

import pytest
from common.models.standard_form import StandardForm
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services import workspace_form_service as wfs
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.calculated_fields import (
    MAX_CALCULATED_FIELDS,
    apply_calculated_fields,
    calculated_field_problems,
    drop_draft_calculations,
    respondent_today,
)
from backend.app.services.form_spec.checks import check_spec_document
from common.form_spec import form_to_spec_dict
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser2

V = lambda key: {"var": key}  # noqa: E731
QTY = {"id": "qty", "type": "number", "title": "Quantity"}


def _calc(field_id, expression, title=None, **properties):
    return {
        "id": field_id,
        "type": "calculated",
        "title": title or field_id,
        "properties": {"expression": expression, **properties},
    }


def _form(*pages, top=None):
    fields = [
        {"id": f"p{i}", "type": "slide", "index": i, "properties": {"fields": fields}}
        for i, fields in enumerate(pages)
    ] + list(top or [])
    return StandardForm.model_validate({"builder_version": "v2", "fields": fields})


def _num(value):
    return {"type": "number", "number": value}


def _places_holding(value, node, path="$"):
    """Where ``value`` appears in decoded JSON: as a number, or as a whole
    string (so a hidden result is caught however it is serialised, while ids,
    uuids and timestamps that merely contain its digits are not)."""
    if isinstance(node, dict):
        return [
            hit
            for key, child in node.items()
            for hit in _places_holding(value, child, f"{path}.{key}")
        ]
    if isinstance(node, list):
        return [
            hit
            for index, child in enumerate(node)
            for hit in _places_holding(value, child, f"{path}[{index}]")
        ]
    if isinstance(node, bool):
        return []
    if isinstance(node, (int, float)) and node == value:
        return [path]
    if isinstance(node, str) and node.strip() == str(value):
        return [path]
    return []


# --- cap, placement, Required -------------------------------------------------


def test_at_most_50_calculations_per_form():
    calcs = [_calc(f"c{i}", 1) for i in range(MAX_CALCULATED_FIELDS)]
    assert calculated_field_problems(_form(calcs)) == []
    problems = calculated_field_problems(_form(calcs + [_calc("one_more", 1)]))
    assert [p.message for p in problems] == [
        "A form can have at most 50 calculated fields; this one has 51."
    ]


async def test_saving_more_than_50_is_422(workspace):
    calcs = [_calc(f"c{i}", 1) for i in range(MAX_CALCULATED_FIELDS + 1)]
    with pytest.raises(HTTPException) as error:
        await container.workspace_form_service().create_form(
            workspace.id, _form(calcs), testUser
        )
    assert error.value.status_code == 422
    assert "at most 50 calculated fields" in error.value.content["message"]


def test_ops_and_spec_refuse_the_51st():
    form = _form([_calc(f"c{i}", 1) for i in range(MAX_CALCULATED_FIELDS)])
    _, results = apply_form_ops(
        form,
        parse_ops(
            [
                {
                    "op": "add_field",
                    "pageId": "p0",
                    "field": {"title": "x", "type": "calculated", "expression": 1},
                }
            ]
        ),
    )
    assert not results[0].ok and "at most 50" in results[0].message
    document = form_to_spec_dict(form)
    document["pages"][0]["fields"].append(
        {"id": "c_extra", "type": "calculated", "expression": 1}
    )
    result = check_spec_document(document)
    assert any("at most 50" in e["message"] for e in result["errors"])


def test_calculations_must_be_on_a_page():
    group = {
        "id": "g",
        "type": "group",
        "title": "Group",
        "properties": {"fields": [_calc("inner", 1, "Inner")]},
    }
    problems = calculated_field_problems(
        _form([QTY, group], top=[_calc("loose", 1, "Loose")])
    )
    messages = sorted(p.message for p in problems)
    assert messages == [
        "'Inner' must be on a page: calculations cannot be placed inside a group or in a form without pages.",
        "'Loose' must be on a page: calculations cannot be placed inside a group or in a form without pages.",
    ]
    # an imported form without pages keeps what its provider gave it
    imported = StandardForm.model_validate({"fields": [_calc("legacy", None)]})
    assert calculated_field_problems(imported) == []


def test_a_calculation_cannot_be_required():
    calc = {**_calc("c", 1, "Total"), "validations": {"required": True}}
    [problem] = calculated_field_problems(_form([calc]))
    assert (
        problem.message
        == "'Total' is a calculation: it is computed, never answered, so it cannot be required."
    )


# --- empty submissions --------------------------------------------------------


def test_no_answers_at_all_still_computes():
    form = _form(
        [
            QTY,
            _calc("total", {"sum": [V("qty")]}),
            _calc("n", {"count": [V("qty")]}, unansweredAsZero=False),
        ]
    )
    assert apply_calculated_fields(form, None) == {
        "total": {"field": {"id": "total"}, "type": "number", "number": 0},
        "n": {"field": {"id": "n"}, "type": "number", "number": 0},
    }


async def test_an_empty_submission_is_held_to_logic_on_a_calculation(workspace):
    why = {
        "id": "why",
        "type": "short_text",
        "title": "Why so few?",
        "validations": {"required": True},
        "properties": {
            "logic": {
                "action": "SHOW",
                "conditions": [
                    {
                        "fieldId": "total",
                        "fieldType": "calculated",
                        "comparison": "LESS_THAN",
                        "value": 10,
                    }
                ],
            }
        },
    }
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id, _form([QTY, _calc("total", {"sum": [V("qty")]}), why]), testUser
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    with pytest.raises(HTTPException) as error:
        await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers=None),
            testUser,
        )
    assert error.value.status_code == 422
    assert {"fieldId": "why", "rule": "required"} in error.value.content["errors"]


# --- the respondent's today ---------------------------------------------------


def test_the_respondents_today_within_a_day_is_used():
    utc = dt.datetime.now(dt.timezone.utc).date()
    for day in (utc - dt.timedelta(days=1), utc, utc + dt.timedelta(days=1)):
        assert respondent_today(day.isoformat()) == day.isoformat()
    assert respondent_today((utc + dt.timedelta(days=3)).isoformat()) == utc.isoformat()
    assert respondent_today("not a date") == utc.isoformat()
    assert respondent_today(None) == utc.isoformat()


async def test_a_submission_is_computed_with_the_respondents_today(workspace):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id, _form([_calc("day", {"today": []})]), testUser
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    tomorrow = (
        dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
    ).isoformat()
    far = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=9)).isoformat()

    async def stored_day(client_today):
        response = await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers={}),
            testUser,
            client_today=client_today,
        )
        stored = await container.form_response_repo().get_response(response.response_id)
        return (
            container.form_response_service()
            .decrypt_form_response(workspace_id=workspace.id, response=stored)
            .answers["day"]["text"]
        )

    assert await stored_day(tomorrow) == tomorrow
    assert await stored_day(far) == dt.datetime.now(dt.timezone.utc).date().isoformat()


async def test_date_rules_use_the_accepted_today(workspace):
    """A date rule "on or before today" is checked against the respondent's
    today when it was accepted, as their browser checked it."""
    start = {
        "id": "start",
        "type": "date",
        "title": "Start",
        "properties": {
            "dateRules": [{"comparison": "on_or_before", "target": "today"}]
        },
    }
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form([start]), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    utc = dt.datetime.now(dt.timezone.utc).date()
    yesterday = (utc - dt.timedelta(days=1)).isoformat()
    answer = {"start": {"type": "date", "date": utc.isoformat()}}
    # the respondent's today is yesterday: today's date is after it
    with pytest.raises(HTTPException):
        await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers=answer),
            testUser,
            client_today=yesterday,
        )
    # without one, the day either side of UTC is accepted as before
    assert await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=answer),
        testUser,
    )


# --- draft-only calculations and the event loop -------------------------------


def test_values_of_draft_only_calculations_are_dropped():
    published = _form([QTY, _calc("total", V("qty"))])
    draft = _form([QTY, _calc("total", V("qty")), _calc("new", 1)])
    answers = {"qty": _num(1), "total": _num(9), "new": _num(5)}
    assert drop_draft_calculations(answers, draft, published) == {
        "qty": _num(1),
        "total": _num(9),
    }
    assert drop_draft_calculations(answers, draft, None) == answers


async def test_submit_and_edit_evaluate_off_the_event_loop(workspace, monkeypatch):
    calls = []
    original = wfs.run_in_threadpool

    async def recording(fn, *args, **kwargs):
        calls.append(fn.__name__)
        return await original(fn, *args, **kwargs)

    monkeypatch.setattr(wfs, "run_in_threadpool", recording)
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id, _form([QTY, _calc("total", V("qty"))]), testUser
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers={"qty": _num(2)}),
        testUser,
    )
    assert "_calculated_checked_ending" in calls


# --- an ending chosen by a calculation ------------------------------------------


def _ending_form():
    jump = {
        "operator": "AND",
        "conditions": [
            {
                "fieldId": "total",
                "fieldType": "calculated",
                "comparison": "GREATER_THAN_EQUAL",
                "value": 100,
            }
        ],
        "target": "__SUBMIT__",
        "endingId": "large",
    }
    return StandardForm.model_validate(
        {
            "builder_version": "v2",
            "fields": [
                {
                    "id": "p0",
                    "type": "slide",
                    "index": 0,
                    "properties": {
                        "fields": [QTY, _calc("total", {"*": [V("qty"), 25]}, "Total")],
                        "jumps": [jump],
                    },
                },
                {"id": "p1", "type": "slide", "index": 1, "properties": {"fields": []}},
            ],
            "thankyou_page": [
                {"id": "thanks", "title": "Thank you"},
                {"id": "large", "name": "Large order", "title": "Large order"},
            ],
        }
    )


def test_the_reached_ending_uses_the_server_value():
    from backend.app.services.answer_validation import reached_ending_id

    form = _ending_form()
    large = apply_calculated_fields(form, {"qty": _num(4)})
    assert reached_ending_id(form, large) == "large"
    # the client claims a large total for a small order: replaced
    small = apply_calculated_fields(form, {"qty": _num(1), "total": _num(1000)})
    assert reached_ending_id(form, small) == "thanks"


async def test_a_submission_records_the_ending_its_calculation_chose(workspace):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _ending_form(), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)

    async def ending(answers):
        response = await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers=answers),
            testUser,
        )
        stored = await container.form_response_repo().get_response(response.response_id)
        return stored.ending_id

    assert await ending({"qty": _num(4)}) == "large"
    assert await ending({"qty": _num(1), "total": _num(1000)}) == "thanks"


# --- calculations kept from respondents -----------------------------------------


def _field_ids(form_json):
    ids = []
    for page in form_json.get("fields") or []:
        ids.append(page.get("id"))
        ids.extend(
            f.get("id") for f in (page.get("properties") or {}).get("fields") or []
        )
    return ids


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def test_hidden_calculations_never_reach_the_respondent(client, workspace):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        _form(
            [
                QTY,
                _calc("total", {"*": [V("qty"), 2]}, "Total"),
                _calc(
                    "risk",
                    {"*": [V("qty"), 1111]},
                    "Risk score",
                    hiddenFromRespondents=True,
                ),
            ]
        ),
        testUser,
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    response = await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers={"qty": _num(3)}, anonymize=False),
        testUser2,
    )

    mine = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
        cookies=_cookies(testUser2),
    )
    assert mine.status_code == 200
    answers = mine.json()["response"]["answers"]
    assert answers["total"]["number"] == 6
    assert "risk" not in answers and _places_holding(3333, mine.json()) == []
    # nor its definition (title, formula): the view shows answers only
    assert _field_ids(mine.json()["form"]) == ["p0", "qty", "total"]
    assert "Risk score" not in mine.text

    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/{response.submission_uuid}"
    )
    assert receipt.status_code == 200
    assert _places_holding(3333, receipt.json()) == []
    assert _field_ids(receipt.json()["form"]) == ["p0", "qty", "total"]
    assert "Risk score" not in receipt.text

    # the live form keeps it: its logic needs the formula
    live = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        params={"published": "true"},
        cookies=_cookies(testUser2),
    )
    assert live.status_code == 200
    assert "risk" in _field_ids(live.json())

    set_page(Page[StandardFormResponseCamelModel])
    set_params(Params(page=1, size=50))
    page = await container.form_response_service().get_user_submissions(
        workspace.id, testUser2
    )
    assert page.items
    for item in page.items:
        dumped = json.loads(
            json.dumps(
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item,
                default=str,
            )
        )
        assert _places_holding(3333, dumped) == []

    # staff see it
    staff = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
        cookies=_cookies(testUser),
    )
    assert staff.json()["response"]["answers"]["risk"]["number"] == 3333
    # the search above finds the value where it is present
    assert _places_holding(3333, staff.json()) == ["$.response.answers.risk.number"]
