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
DAY = {"id": "d", "type": "day", "title": "Born"}
TEXT = {"id": "s", "type": "short_text", "title": "Name"}


def test_the_list_is_the_three_types_for_now():
    assert GATED_TYPES == {"time", "day", "currency"}


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
    ],
)
def test_changed_settings_count(changed):
    stored = _form(TIME, MONEY, DAY)
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
