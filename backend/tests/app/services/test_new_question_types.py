"""What counts as a new or changed question of the newer types
(services/new_question_types.py), and the refusal the switch gives."""

import pytest

from backend.app.exceptions import HTTPException
from backend.app.services.new_question_types import (
    DISABLED_CODE,
    GATED_TYPES,
    ensure_question_types_allowed,
    gated_signatures,
    new_or_changed_questions,
    question_type_problem,
)
from backend.config import settings
from common.models.standard_form import StandardForm


def _form(*questions, group=None):
    page_fields = list(questions)
    if group:
        page_fields.append(
            {
                "id": "g",
                "type": "group",
                "title": "Group",
                "properties": {"repeat": {"minItems": 0, "maxItems": 3}, "fields": group},
            }
        )
    return StandardForm.model_validate(
        {
            "title": "T",
            "builderVersion": "v2",
            "fields": [
                {
                    "id": "p1",
                    "index": 0,
                    "type": "slide",
                    "properties": {"fields": page_fields},
                }
            ],
        }
    )


TIME = {"id": "t", "type": "time", "title": "At", "properties": {"min_time": "08:00"}}
MONEY = {
    "id": "m",
    "type": "currency",
    "title": "Pay",
    "properties": {"currencies": ["EUR"]},
    "validations": {"min_value": 1},
}
STAY = {
    "id": "r",
    "type": "date_range",
    "title": "Stay",
    "properties": {"date_rules": [{"comparison": "after", "target": "today"}]},
}
TAGS = {"id": "g", "type": "tags", "title": "Topics", "validations": {"max_choices": 3}}
DAY = {"id": "d", "type": "day", "title": "Born"}
TEXT = {"id": "s", "type": "short_text", "title": "Name"}


def test_the_list_is_the_five_types():
    assert GATED_TYPES == {"time", "day", "currency", "date_range", "tags"}


def test_only_gated_questions_have_signatures_nested_ones_included():
    form = _form(TEXT, TIME, group=[{**DAY, "id": "d2"}])
    assert set(gated_signatures(form)) == {"t", "d2"}


def test_a_question_that_is_the_same_is_not_new_or_changed():
    stored = _form(TEXT, TIME, MONEY, DAY)
    assert new_or_changed_questions(_form(DAY, MONEY, TIME, TEXT), stored) == []
    # a title, a label, a required flag and the place do not count
    renamed = {**TIME, "title": "Arrival", "properties": {"min_time": "08:00", "label": "x"}}
    assert new_or_changed_questions(_form(renamed), stored) == []


@pytest.mark.parametrize(
    "changed",
    [
        {**TIME, "properties": {"min_time": "09:00"}},
        {**TIME, "properties": {"min_time": "08:00", "max_time": "17:00"}},
        {**MONEY, "properties": {"currencies": ["EUR", "USD"]}},
        {**MONEY, "validations": {"min_value": 1, "max_value": 9}},
        {**DAY, "properties": {"date_rules": [{"comparison": "before", "target": "today"}]}},
        {**STAY, "properties": {"date_rules": [{"comparison": "before", "target": "today"}]}},
        {**TAGS, "validations": {"max_choices": 4}},
        {**TAGS, "validations": {"max_choices": 3, "max_length": 10}},
        {**TAGS, "validations": {"max_choices": 3, "min_choices": 1}},
    ],
)
def test_changed_settings_count(changed):
    stored = _form(TIME, MONEY, DAY, STAY, TAGS)
    result = new_or_changed_questions(_form(changed), stored)
    assert [r[0] for r in result] == [changed["id"]]


def test_a_new_question_or_a_changed_type_counts_and_going_away_does_not():
    stored = _form(TEXT, TIME)
    assert new_or_changed_questions(_form(TEXT, TIME, MONEY), stored) == [("m", "currency")]
    assert new_or_changed_questions(_form({**TEXT, "type": "time"}), stored) == [("s", "time")]
    assert new_or_changed_questions(_form({**TIME, "type": "short_text"}), stored) == []
    assert new_or_changed_questions(_form(TEXT), stored) == []
    # with nothing stored, every gated question is new
    assert len(new_or_changed_questions(_form(TIME, DAY), None)) == 2


def test_the_guard_follows_the_switch(monkeypatch):
    stored = _form(TEXT, TIME)
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    ensure_question_types_allowed(_form(TEXT, TIME), stored)
    with pytest.raises(HTTPException) as refused:
        ensure_question_types_allowed(_form(TEXT, TIME, DAY), stored)
    assert refused.value.status_code == 422
    assert refused.value.content["code"] == DISABLED_CODE
    assert refused.value.content["errors"][0]["fieldId"] == "d"
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)
    ensure_question_types_allowed(_form(TEXT, TIME, DAY), stored)


def test_the_operation_check_looks_only_at_the_listed_operations(monkeypatch):
    stored = gated_signatures(_form(TIME))
    changed = _form({**TIME, "properties": {"min_time": "09:00"}})
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    assert question_type_problem(changed, stored, "update_field")
    assert question_type_problem(changed, stored, "move_field") is None
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)
    assert question_type_problem(changed, stored, "update_field") is None


def test_only_an_op_that_can_gate_needs_a_look(monkeypatch):
    from backend.app.services.ai.ops import parse_ops
    from backend.app.services.new_question_types import op_may_gate

    started = gated_signatures(_form(TIME))

    def may(raw):
        return op_may_gate(parse_ops([raw], allow_editor_ops=True)[0], started)

    page = "p1"
    assert may({"op": "add_field", "pageId": page, "field": {"type": "time", "title": "x"}})
    assert not may({"op": "add_field", "pageId": page, "field": {"type": "short_text", "title": "x"}})
    assert may({"op": "update_field", "fieldId": "t", "patch": {"title": "x"}})
    assert not may({"op": "update_field", "fieldId": "s", "patch": {"title": "x"}})
    assert may({"op": "replace_field", "field": {"id": "t", "type": "time", "title": "x"}})
    assert may({"op": "duplicate_page", "pageId": page})
    assert not may({"op": "move_field", "fieldId": "t", "index": 0})
    assert not op_may_gate(
        parse_ops([{"op": "duplicate_page", "pageId": page}])[0], {}
    )


def test_a_type_that_is_not_text_in_a_payload_never_breaks_the_look(monkeypatch):
    """`type` may be anything in an op's payload (a list or an object inside an
    expression): that is no gated type, and no crash."""
    from backend.app.services.ai.ops import apply_form_ops, parse_ops
    from backend.app.services.new_question_types import op_may_gate

    started = gated_signatures(_form(TIME))
    for odd in (["x"], {"a": 1}, 3, None):
        ops = parse_ops(
            [
                {
                    "op": "add_field",
                    "pageId": "p1",
                    "field": {"title": "c", "type": "calculated", "expression": {"type": odd}},
                }
            ]
        )
        assert op_may_gate(ops[0], started) is False
        monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
        _, results = apply_form_ops(_form(TEXT), ops)
        assert results[0].ok is False and "NEW_QUESTION_TYPES" not in results[0].message
    patch = parse_ops(
        [{"op": "update_field", "fieldId": "s", "patch": {"expression": {"type": ["x"]}}}]
    )
    assert op_may_gate(patch[0], started) is False


def test_a_second_question_with_a_stored_id_reads_as_new():
    stored = _form(TIME)
    twice = _form(TIME, {**TIME, "title": "Again"})
    assert new_or_changed_questions(twice, stored) == [("t", "time")]
    # as many copies as the stored form has pass
    assert new_or_changed_questions(twice, _form(TIME, {**TIME, "title": "Again"})) == []
    # the stored copies are not used up by a check: it can run again
    signatures = gated_signatures(stored)
    assert new_or_changed_questions(twice, None, signatures) == [("t", "time")]
    assert new_or_changed_questions(twice, None, signatures) == [("t", "time")]
    once_more = _form(TIME)
    assert new_or_changed_questions(once_more, None, signatures) == []


async def test_a_provider_import_cannot_bring_the_newer_types_while_off(
    workspace, monkeypatch
):
    from backend.app.container import container

    form = _form(TEXT, TIME).model_dump(mode="json")
    data = {"form": {**form, "form_id": "provider-form-types"}, "responses": []}
    service = container.form_import_service()
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    with pytest.raises(HTTPException) as refused:
        await service.save_converted_form_and_responses(data, "owner", workspace.id)
    assert refused.value.content["code"] == DISABLED_CODE
    plain = {**form, "form_id": "provider-form-plain"}
    plain["fields"][0]["properties"]["fields"] = [TEXT]
    saved = await service.save_converted_form_and_responses(
        {"form": plain, "responses": []}, "owner", workspace.id
    )
    assert saved is not None
