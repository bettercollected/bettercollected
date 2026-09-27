"""Repeating groups: model, form DTO and answer validation (pure, no DB)."""

import json

import pytest
from common.models.standard_form import (
    RepeatSettings,
    StandardForm,
    StandardFormField,
    StandardFormResponse,
    StandardFormResponseAnswer,
    StandardResponseType,
)
from pydantic import ValidationError

from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.services.repeating_groups import (
    evaluate_conditions,
    validate_group_answers,
)


def group_field(children=None, **repeat):
    return {
        "id": "g",
        "type": "group",
        "title": "Applicants",
        "properties": {
            "repeat": {
                "minItems": 1,
                "maxItems": 3,
                "itemLabel": "Applicant",
                **repeat,
            },
            "fields": (
                children
                if children is not None
                else [
                    {
                        "id": "name",
                        "type": "short_text",
                        "title": "Name",
                        "validations": {"required": True},
                    },
                    {"id": "age", "type": "number", "title": "Age"},
                ]
            ),
        },
    }


def form_with(*fields):
    return StandardForm(
        builder_version="v2",
        fields=[
            {
                "id": "s1",
                "type": "slide",
                "index": 0,
                "properties": {"fields": list(fields)},
            }
        ],
    )


def test_repeat_settings_accept_camel_case_and_default_layout():
    field = StandardFormField(**group_field())
    repeat = field.properties.repeat
    assert (repeat.min_items, repeat.max_items, repeat.item_label) == (
        1,
        3,
        "Applicant",
    )
    assert repeat.effective_export_layout == "columns"
    assert RepeatSettings(max_items=6).effective_export_layout == "rows"
    assert (
        RepeatSettings(max_items=6, export_layout="columns").effective_export_layout
        == "columns"
    )


def test_min_above_max_is_rejected():
    with pytest.raises(ValidationError, match="minimum"):
        RepeatSettings(min_items=4, max_items=2)


def test_nested_groups_are_rejected():
    with pytest.raises(ValidationError, match="cannot contain another group"):
        StandardFormField(**group_field(children=[group_field()]))


@pytest.mark.parametrize(
    "child_type", ["hidden", "calculated", "file_upload", "matrix"]
)
def test_internal_and_unsupported_children_are_rejected(child_type):
    with pytest.raises(
        ValidationError, match="cannot be placed inside a repeating group"
    ):
        StandardFormField(**group_field(children=[{"id": "x", "type": child_type}]))


def test_legacy_groups_without_repeat_settings_still_load():
    # Imported (e.g. Typeform) groups carry no repeat settings and may nest.
    field = StandardFormField(
        id="legacy",
        type="group",
        properties={"fields": [{"id": "inner", "type": "group"}]},
    )
    assert field.properties.repeat is None


def test_group_answer_round_trips_items_verbatim():
    answer = StandardFormResponseAnswer(
        type="group", items=[{"name": {"type": "text", "text": "Sita"}}, {}]
    )
    assert answer.type == StandardResponseType.GROUP
    response = StandardFormResponse(answers={"g": answer.model_dump()})
    stored = json.loads(json.dumps(response.model_dump(mode="json")))
    assert stored["answers"]["g"]["items"][0]["name"]["text"] == "Sita"


def test_existing_answers_are_unchanged():
    response = StandardFormResponse(answers={"a": {"type": "text", "text": "hi"}})
    assert response.model_dump(mode="json")["answers"]["a"] == {
        "type": "text",
        "text": "hi",
    }


def test_builder_payload_keeps_repeat_settings_and_col_span():
    payload = {
        "builderVersion": "v2",
        "fields": [
            {
                "id": "s1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            **group_field(exportLayout="rows"),
                            "properties": {**group_field()["properties"], "colSpan": 6},
                        },
                    ]
                },
            }
        ],
    }
    form = _parse_form_body(json.dumps(payload))
    group = form.fields[0].properties.fields[0]
    assert group.properties.col_span == 6
    assert group.properties.repeat.item_label == "Applicant"
    assert [c.id for c in group.properties.fields] == ["name", "age"]
    # ...and goes back to the webapp in camelCase.
    out = FormDtoCamelModel(**form.model_dump(mode="json")).model_dump(
        by_alias=True, mode="json"
    )
    props = out["fields"][0]["properties"]["fields"][0]["properties"]
    assert props["repeat"]["itemLabel"] == "Applicant"
    assert props["colSpan"] == 6


def test_builder_payload_with_nested_group_is_a_client_error():
    payload = {
        "fields": [
            {
                "id": "s1",
                "type": "slide",
                "properties": {"fields": [group_field(children=[group_field()])]},
            }
        ]
    }
    with pytest.raises(HTTPException) as error:
        _parse_form_body(json.dumps(payload))
    assert error.value.status_code == 422
    assert "another group" in str(error.value.content)


def item(name=None, age=None):
    result = {}
    if name is not None:
        result["name"] = {"type": "text", "text": name}
    if age is not None:
        result["age"] = {"type": "number", "number": age}
    return result


def test_valid_group_answer_passes():
    form = form_with(group_field())
    answers = {"g": {"type": "group", "items": [item("Sita", 30), item("Ram")]}}
    assert validate_group_answers(form, answers) == []


def test_item_count_limits_are_enforced():
    form = form_with(group_field(minItems=2, maxItems=3))
    too_few = {"g": {"type": "group", "items": [item("A")]}}
    too_many = {
        "g": {"type": "group", "items": [item("A"), item("B"), item("C"), item("D")]}
    }
    assert "at least 2" in validate_group_answers(form, too_few)[0]
    assert "at most 3" in validate_group_answers(form, too_many)[0]


def test_required_applies_per_item():
    form = form_with(group_field())
    answers = {"g": {"type": "group", "items": [item("A"), item(age=4)]}}
    problems = validate_group_answers(form, answers)
    assert problems == ["Applicant 2: 'Name' is required."]


def test_child_hidden_by_item_logic_is_not_required():
    children = [
        {"id": "age", "type": "number", "title": "Age"},
        {
            "id": "guardian",
            "type": "short_text",
            "title": "Guardian",
            "validations": {"required": True},
            "properties": {
                "logic": {
                    "action": "SHOW",
                    "operator": "AND",
                    "conditions": [
                        {
                            "fieldId": "age",
                            "fieldType": "number",
                            "comparison": "LESS_THAN",
                            "value": 18,
                        }
                    ],
                }
            },
        },
    ]
    form = form_with(group_field(children=children))
    adult = {"age": {"type": "number", "number": 40}}
    minor = {"age": {"type": "number", "number": 9}}
    assert (
        validate_group_answers(form, {"g": {"type": "group", "items": [adult]}}) == []
    )
    problems = validate_group_answers(
        form, {"g": {"type": "group", "items": [adult, minor]}}
    )
    assert problems == ["Applicant 2: 'Guardian' is required."]


def test_unknown_keys_and_malformed_answers_are_rejected():
    form = form_with(group_field())
    assert validate_group_answers(
        form, {"g": {"type": "group", "items": [{"other": {}}]}}
    )
    assert validate_group_answers(form, {"g": {"type": "group", "items": "nope"}})


def test_missing_group_answer_is_accepted():
    # Hidden by logic or on a skipped page: nothing submitted.
    assert validate_group_answers(form_with(group_field()), {}) == []


def test_group_level_conditions():
    answers = {"g": {"type": "group", "items": [item("Sita", 30), item("Ram", 12)]}}
    count = [
        {
            "fieldId": "g",
            "fieldType": "group",
            "groupMode": "COUNT",
            "comparison": "GREATER_THAN_EQUAL",
            "value": 2,
        }
    ]
    anyone_minor = [
        {
            "fieldId": "g",
            "groupMode": "ANY",
            "childFieldId": "age",
            "childFieldType": "number",
            "comparison": "LESS_THAN",
            "value": 18,
        }
    ]
    all_minor = [{**anyone_minor[0], "groupMode": "ALL"}]
    assert evaluate_conditions("AND", count, answers)
    assert evaluate_conditions("AND", anyone_minor, answers)
    assert not evaluate_conditions("AND", all_minor, answers)
    # ALL over no items never matches.
    assert not evaluate_conditions(
        "AND", all_minor, {"g": {"type": "group", "items": []}}
    )


def test_group_hidden_by_its_own_rule_is_not_validated():
    hidden_group = group_field()
    hidden_group["properties"]["logic"] = {
        "action": "SHOW",
        "operator": "AND",
        "conditions": [
            {
                "fieldId": "has_applicants",
                "fieldType": "yes_no",
                "comparison": "IS_EQUAL",
                "value": "Yes",
            }
        ],
    }
    form = form_with({"id": "has_applicants", "type": "yes_no"}, hidden_group)
    stale = {"g": {"type": "group", "items": [{}]}}
    no = {"has_applicants": {"type": "boolean", "boolean": False}, **stale}
    yes = {"has_applicants": {"type": "boolean", "boolean": True}, **stale}
    assert validate_group_answers(form, no) == []
    assert validate_group_answers(form, yes) == ["Applicant 1: 'Name' is required."]


def test_items_are_typed_and_bounded():
    with pytest.raises(ValidationError):
        StandardFormResponseAnswer(type="group", items=[{"age": {"number": {"x": 1}}}])
    with pytest.raises(ValidationError):
        StandardFormResponseAnswer(type="group", items=[{}] * 51)
    form = form_with(group_field(maxItems=50))
    crafted = {"g": {"type": "group", "items": [{"age": {"number": {"x": 1}}}]}}
    assert "malformed" in validate_group_answers(form, crafted)[0]


def test_items_on_other_keys_are_rejected():
    form = form_with(
        {"id": "plain", "type": "short_text"},
        {"id": "legacy", "type": "group", "properties": {"fields": []}},
        group_field(),
    )
    for key in ("plain", "legacy", "unknown"):
        answers = {key: {"type": "group", "items": [{}]}}
        assert validate_group_answers(form, answers) == [
            "Only repeating groups can have items."
        ]
    nested = {
        "g": {"type": "group", "items": [{"name": {"type": "group", "items": [{}]}}]}
    }
    assert validate_group_answers(form, nested)


@pytest.mark.parametrize(
    "empty", [{}, {"type": "text"}, {"type": "text", "text": ""}, {"choice": {}}]
)
def test_empty_child_answers_count_as_missing(empty):
    form = form_with(group_field())
    answers = {"g": {"type": "group", "items": [{"name": empty}]}}
    assert validate_group_answers(form, answers) == ["Applicant 1: 'Name' is required."]


def test_repeat_settings_null_limits_use_defaults():
    repeat = RepeatSettings(min_items=None, max_items=None)
    assert (repeat.effective_min, repeat.effective_max) == (1, 3)
