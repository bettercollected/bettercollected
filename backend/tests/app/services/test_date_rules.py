"""Date rules: the model checks, the pure evaluation and the service checks
(form save, submission, response edit)."""

import datetime as dt
import json

import pytest
from common.models.standard_form import (
    DateRule,
    StandardForm,
    StandardFormField,
    date_rule_problems,
    prune_date_rules,
)
from pydantic import ValidationError

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import (
    StandardFormCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.services.date_rules import (
    is_violated,
    today_range,
    validate_date_rule_answers,
)
from tests.app.controllers.data import testUser


def _date(field_id, title, rules=None, properties=None):
    field = {"id": field_id, "type": "date", "title": title}
    properties = dict(properties or {})
    if rules is not None:
        properties["dateRules"] = rules
    if properties:
        field["properties"] = properties
    return field


def _after(field_id, comparison="after"):
    return {"comparison": comparison, "target": "field", "fieldId": field_id}


START = _date("start", "Start date")
END = _date("end", "End date", [_after("start")])


def _form(fields):
    return StandardForm(
        builder_version="v2",
        title="Trip",
        fields=[
            {"id": "s1", "type": "slide", "index": 0, "properties": {"fields": fields}}
        ],
    )


def _group(children, group_id="stays"):
    return {
        "id": group_id,
        "type": "group",
        "title": "Stays",
        "properties": {
            "repeat": {"minItems": 1, "maxItems": 3, "itemLabel": "Stay"},
            "fields": children,
        },
    }


def _day(value):
    return {"type": "date", "date": value}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule",
    [
        {"comparison": "after", "target": "date"},
        {"comparison": "after", "target": "date", "date": "12/03/2026"},
        {"comparison": "after", "target": "date", "date": "2026-W11-4"},
        {"comparison": "after", "target": "date", "date": "2026-02-30"},
        {"comparison": "after", "target": "field"},
        {"comparison": "later", "target": "today"},
        {"comparison": "after", "target": "tomorrow"},
    ],
)
def test_malformed_rules_are_rejected(rule):
    with pytest.raises(ValidationError):
        DateRule.model_validate(rule)


def test_rule_keeps_only_what_its_target_needs():
    rule = DateRule.model_validate(
        {
            "comparison": "before",
            "target": "today",
            "date": "2026-01-01",
            "fieldId": "x",
        }
    )
    assert rule.date is None and rule.field_id is None
    rule = DateRule.model_validate(
        {"comparison": "before", "target": "date", "date": "2026-01-01", "fieldId": "x"}
    )
    assert rule.date == "2026-01-01" and rule.field_id is None


def test_only_date_questions_have_rules():
    with pytest.raises(ValidationError, match="Only date questions"):
        StandardFormField.model_validate(
            {
                "id": "n",
                "type": "number",
                "properties": {"dateRules": [_after("start")]},
            }
        )


def test_a_rule_never_compares_a_question_with_itself():
    with pytest.raises(ValidationError, match="itself"):
        StandardFormField.model_validate(_date("end", "End", [_after("end")]))


def test_at_most_five_rules():
    rules = [{"comparison": "after", "target": "today"}] * 6
    with pytest.raises(ValidationError):
        StandardFormField.model_validate(_date("end", "End", rules))


def test_valid_reference_has_no_problems():
    assert date_rule_problems(_form([START, END]).fields) == []


@pytest.mark.parametrize(
    "fields, expected",
    [
        ([END], "does not exist"),
        ([{"id": "start", "type": "number", "title": "Start"}, END], "not a date"),
        ([{**START, "internal": True}, END], "internal"),
        ([_group([START]), END], "repeating group"),
        ([START, _group([_date("x", "Check-out", [_after("start")])])], "another part"),
        (
            [
                _date("a", "A", [_after("b")]),
                _date("b", "B", [_after("c")]),
                _date("c", "C", [_after("a")]),
            ],
            "circle",
        ),
    ],
)
def test_bad_references_are_problems(fields, expected):
    problems = date_rule_problems(_form(fields).fields)
    assert problems and expected in " ".join(problems)


def _chain(length, closed):
    """Date questions each ruled after the next; closed loops the last back."""
    ids = [f"d{i}" for i in range(length)]
    targets = ids[1:] + ([ids[0]] if closed else [])
    return [
        _date(field_id, field_id, [_after(target)] if target else None)
        for field_id, target in zip(ids, targets + [None])
    ]


def test_a_long_chain_of_rules_is_checked_without_recursion():
    assert date_rule_problems(_form(_chain(3000, closed=False)).fields) == []
    problems = date_rule_problems(_form(_chain(3000, closed=True)).fields)
    assert problems and "circle" in " ".join(problems)


def test_sibling_in_the_same_group_is_fine():
    group = _group([_date("in", "Check-in"), _date("out", "Check-out", [_after("in")])])
    assert date_rule_problems(_form([group]).fields) == []


def test_prune_drops_dangling_rules_only():
    end = _date(
        "end",
        "End",
        [_after("start"), _after("gone"), {"comparison": "after", "target": "today"}],
    )
    form = _form([START, end])
    assert prune_date_rules(form.fields) == 1
    rules = form.fields[0].properties.fields[1].properties.date_rules
    assert [r.target for r in rules] == ["field", "today"]


def test_builder_payload_keeps_label_and_rules():
    body = {
        "title": "Trip",
        "fields": [
            {
                "id": "s1",
                "type": "slide",
                "index": 0,
                "properties": {
                    "fields": [
                        _date("start", "Start", properties={"label": "Start date"}),
                        _date("end", "End", [_after("start", "on_or_after")]),
                    ]
                },
            }
        ],
    }

    form = _parse_form_body(json.dumps(body))
    start, end = form.fields[0].properties.fields
    assert start.properties.label == "Start date"
    assert end.properties.date_rules[0].field_id == "start"
    assert end.properties.date_rules[0].comparison == "on_or_after"
    out = StandardFormCamelModel(**form.model_dump(mode="json")).model_dump(
        by_alias=True
    )
    end_out = out["fields"][0]["properties"]["fields"][1]["properties"]
    assert end_out["dateRules"][0]["fieldId"] == "start"


def test_builder_payload_with_a_self_rule_is_422():
    body = {"title": "T", "fields": [_date("end", "End", [_after("end")])]}

    with pytest.raises(HTTPException) as error:
        _parse_form_body(json.dumps(body))
    assert error.value.status_code == 422


# ---------------------------------------------------------------------------
# Evaluation (pure)
# ---------------------------------------------------------------------------

TODAY = today_range(dt.date(2026, 3, 12))


def _problems(fields, answers, **kwargs):
    return validate_date_rule_answers(_form(fields), answers, today=TODAY, **kwargs)


@pytest.mark.parametrize(
    "comparison, value, bound, violated",
    [
        ("after", "2026-03-13", "2026-03-12", False),
        ("after", "2026-03-12", "2026-03-12", True),
        ("on_or_after", "2026-03-12", "2026-03-12", False),
        ("on_or_after", "2026-03-11", "2026-03-12", True),
        ("before", "2026-03-12", "2026-03-12", True),
        ("on_or_before", "2026-03-12", "2026-03-12", False),
        ("on_or_before", "2026-12-31", "2027-01-01", False),
    ],
)
def test_comparisons(comparison, value, bound, violated):
    assert is_violated(value, comparison, bound) is violated


def test_end_before_start_is_a_problem():
    problems = _problems(
        [START, END], {"start": _day("2026-03-12"), "end": _day("2026-03-12")}
    )
    assert problems == ["'End date' must be after 'Start date' (12 Mar 2026)."]


def test_end_after_start_is_fine():
    answers = {"start": _day("2026-03-12"), "end": _day("2026-03-13")}
    assert _problems([START, END], answers) == []


def test_unanswered_reference_does_not_apply():
    assert _problems([START, END], {"end": _day("2000-01-01")}) == []


def test_reference_hidden_by_logic_does_not_apply():
    start = {
        **START,
        "properties": {
            "logic": {
                "action": "SHOW",
                "operator": "AND",
                "conditions": [
                    {
                        "fieldId": "trip",
                        "fieldType": "yes_no",
                        "comparison": "IS_EQUAL",
                        "value": "Yes",
                    }
                ],
            }
        },
    }
    trip = {"id": "trip", "type": "yes_no", "title": "Trip?"}
    answers = {
        "trip": {"type": "boolean", "boolean": False},
        "start": _day("2026-03-12"),
        "end": _day("2026-03-01"),
    }
    assert _problems([trip, start, END], answers) == []
    answers["trip"] = {"type": "boolean", "boolean": True}
    assert _problems([trip, start, END], answers)


def test_fixed_date_and_today():
    field = _date(
        "d",
        "Date",
        [
            {"comparison": "on_or_after", "target": "date", "date": "2026-01-01"},
            {"comparison": "on_or_before", "target": "today"},
        ],
    )
    assert _problems([field], {"d": _day("2025-12-31")}) == [
        "'Date' must be on or after 1 Jan 2026."
    ]
    # "today" is anywhere in UTC-12..UTC+14: tomorrow (UTC) is still accepted
    assert _problems([field], {"d": _day("2026-03-13")}) == []
    assert _problems([field], {"d": _day("2026-03-14")}) == [
        "'Date' must be on or before today."
    ]


def test_not_a_date_is_a_problem():
    field = _date("d", "Date", [{"comparison": "after", "target": "today"}])
    assert "not a valid date" in _problems([field], {"d": _day("tomorrow")})[0]


def test_group_rules_apply_per_item():
    group = _group([_date("in", "Check-in"), _date("out", "Check-out", [_after("in")])])
    answers = {
        "stays": {
            "type": "group",
            "items": [
                {"in": _day("2026-03-01"), "out": _day("2026-03-05")},
                {"in": _day("2026-03-10"), "out": _day("2026-03-02")},
                {"out": _day("2026-01-01")},
            ],
        }
    }
    assert _problems([group], answers) == [
        "Stay 2: 'Check-out' must be after 'Check-in' (10 Mar 2026)."
    ]


def test_edit_only_checks_what_changed():
    answers = {
        "start": _day("2026-03-12"),
        "end": _day("2026-03-01"),
        "other": {"type": "text", "text": "x"},
    }
    assert _problems([START, END], answers, changed=["other"]) == []
    assert _problems([START, END], answers, changed=["start"])


# ---------------------------------------------------------------------------
# Services: save, submit, edit
# ---------------------------------------------------------------------------


async def _published(workspace, fields):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(fields), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


async def _submit(workspace, form, answers):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=answers),
        testUser,
    )


@pytest.mark.asyncio
async def test_saving_a_form_with_a_dangling_rule_is_422(workspace):
    with pytest.raises(HTTPException) as error:
        await container.workspace_form_service().create_form(
            workspace.id, _form([END]), testUser
        )
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_saving_a_form_with_a_cycle_is_422(workspace):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form([START, END]), testUser)
    cyclic = _form([_date("start", "Start date", [_after("end")]), END])
    with pytest.raises(HTTPException) as error:
        await service.update_form(workspace.id, form.form_id, cyclic, testUser)
    assert error.value.status_code == 422
    assert "circle" in error.value.content


@pytest.mark.asyncio
async def test_saved_form_keeps_label_and_rules(workspace):
    start = _date("start", "Start", properties={"label": "Start date"})
    form = await _published(workspace, [start, END])
    loaded = await container.form_service().get_form_document_by_id(form.form_id)
    start, end = loaded.fields[0].properties.fields
    assert start.properties.label == "Start date"
    assert end.properties.date_rules[0].field_id == "start"


@pytest.mark.asyncio
async def test_submission_breaking_a_rule_is_422(workspace):
    form = await _published(workspace, [START, END])
    with pytest.raises(HTTPException) as error:
        await _submit(
            workspace, form, {"start": _day("2026-03-12"), "end": _day("2026-03-10")}
        )
    assert error.value.status_code == 422
    assert "must be after 'Start date' (12 Mar 2026)" in error.value.content


@pytest.mark.asyncio
async def test_submission_with_the_reference_unanswered_is_accepted(workspace):
    form = await _published(workspace, [START, END])
    response = await _submit(workspace, form, {"end": _day("2026-03-10")})
    assert response.response_id


@pytest.mark.asyncio
async def test_submission_with_the_reference_hidden_is_accepted(workspace):
    trip = {"id": "trip", "type": "yes_no", "title": "Trip?"}
    start = {
        **START,
        "properties": {
            "logic": {
                "action": "SHOW",
                "operator": "AND",
                "conditions": [
                    {
                        "fieldId": "trip",
                        "fieldType": "yes_no",
                        "comparison": "IS_EQUAL",
                        "value": "Yes",
                    }
                ],
            }
        },
    }
    form = await _published(workspace, [trip, start, END])
    response = await _submit(
        workspace,
        form,
        {
            "trip": {"type": "boolean", "boolean": False},
            "start": _day("2026-03-12"),
            "end": _day("2026-03-10"),
        },
    )
    assert response.response_id


@pytest.mark.asyncio
async def test_response_edit_breaking_a_rule_is_422(workspace):
    form = await _published(workspace, [START, END])
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form.form_id)
        )
    )
    workspace_form.settings.require_verified_identity = True
    workspace_form.settings.allow_editing_response = True
    await container.workspace_form_repo().save(workspace_form)
    submitted = await _submit(
        workspace, form, {"start": _day("2026-03-12"), "end": _day("2026-03-20")}
    )
    service = container.workspace_form_service()

    with pytest.raises(HTTPException) as error:
        await service.patch_response(
            workspace.id,
            form.form_id,
            submitted.response_id,
            None,
            StandardFormResponseCamelModel(answers={"start": _day("2026-03-25")}),
            testUser,
        )
    assert error.value.status_code == 422
    assert "Start date" in error.value.content

    await service.patch_response(
        workspace.id,
        form.form_id,
        submitted.response_id,
        None,
        StandardFormResponseCamelModel(answers={"start": _day("2026-03-15")}),
        testUser,
    )


def test_messages_name_the_other_date_from_label_rich_title_or_a_phrase():
    from types import SimpleNamespace

    from backend.app.services.date_rules import _title

    rich = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Start", "marks": [{"type": "bold"}]},
                    {"type": "text", "text": " date"},
                ],
            }
        ],
    }
    assert _title(SimpleNamespace(title=rich, properties=None)) == "Start date"
    labelled = SimpleNamespace(title=rich, properties=SimpleNamespace(label="Arrival"))
    assert _title(labelled) == "Arrival"
    assert _title(SimpleNamespace(title=None, properties=None)) == "the other date"
