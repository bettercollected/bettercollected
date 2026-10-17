"""Size limits while ops apply: a batch can't grow a form past MAX_PAGES /
MAX_FIELDS, and the expensive op is refused before it copies anything
(limits patched low to reproduce the large-form shape at small scale)."""

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)
from pydantic import ValidationError

from backend.app.services.ai import ops as ops_module
from backend.app.services.ai.ops import (
    SIZE_LIMIT_SKIPPED,
    apply_form_ops,
    parse_ops,
)

T = StandardFormFieldType


def _form(fields_on_page: int = 5) -> StandardForm:
    return StandardForm(
        builder_version="v2",
        title="Big",
        fields=[
            StandardFormField(
                id="p1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[
                        StandardFormField(
                            id=f"q{i}",
                            type=T.SHORT_TEXT,
                            title=f"Q{i}",
                            properties=StandardFieldProperty(fields=[]),
                        )
                        for i in range(fields_on_page)
                    ]
                ),
            )
        ],
    )


@pytest.fixture()
def small_limits(monkeypatch):
    monkeypatch.setattr(ops_module, "MAX_PAGES", 4)
    monkeypatch.setattr(ops_module, "MAX_FIELDS", 12)


@pytest.fixture()
def duplicate_calls(monkeypatch):
    calls = []
    original = ops_module._HANDLERS["duplicate_page"]

    def counting(form, op):
        calls.append(op.page_id)
        return original(form, op)

    monkeypatch.setitem(ops_module._HANDLERS, "duplicate_page", counting)
    return calls


def test_repeated_duplicate_page_stops_before_copying(small_limits, duplicate_calls):
    form = _form()
    batch = parse_ops([{"op": "duplicate_page", "pageId": "p1"}] * 50)
    new, results = apply_form_ops(form, batch)
    # 5 + 5 fields fit, a third copy (15 > 12) is refused before it runs
    assert duplicate_calls == ["p1"]
    assert [r.ok for r in results[:2]] == [True, False]
    assert "at most 12 fields" in results[1].message
    assert all(r.message == SIZE_LIMIT_SKIPPED for r in results[2:])
    assert len(results) == 50
    assert len(new.fields) == 2


def test_atomic_attack_changes_nothing(small_limits, duplicate_calls):
    form = _form()
    before = form.model_dump()
    new, results = apply_form_ops(
        form, parse_ops([{"op": "duplicate_page", "pageId": "p1"}] * 50), atomic=True
    )
    assert new.model_dump() == before
    assert not results[1].ok and len(duplicate_calls) == 1


def test_add_page_with_too_many_fields_is_refused(small_limits):
    form = _form()
    spec = {"title": "x", "type": "short_text"}
    _, results = apply_form_ops(
        form, parse_ops([{"op": "add_page", "fields": [spec] * 8}])
    )
    assert not results[0].ok and "would make 13" in results[0].message


def test_the_page_limit(small_limits):
    new, results = apply_form_ops(_form(1), parse_ops([{"op": "add_page"}] * 6))
    assert [r.ok for r in results] == [True, True, True, False, False, False]
    assert "at most 4 pages" in results[3].message
    assert len(new.fields) == 4


def test_groups_count_with_their_questions(small_limits):
    spec = {"title": "c", "type": "short_text"}
    _, results = apply_form_ops(
        _form(),
        parse_ops(
            [{"op": "add_group", "pageId": "p1", "title": "G", "fields": [spec] * 7}]
        ),
    )
    assert not results[0].ok and "would make 13" in results[0].message


def test_a_form_already_over_the_limit_can_still_be_edited(monkeypatch):
    monkeypatch.setattr(ops_module, "MAX_FIELDS", 3)
    _, results = apply_form_ops(
        _form(),
        parse_ops(
            [
                {"op": "update_field", "fieldId": "q0", "patch": {"title": "New"}},
                {"op": "remove_field", "fieldId": "q1"},
                {
                    "op": "add_field",
                    "pageId": "p1",
                    "field": {"title": "x", "type": "email"},
                },
            ]
        ),
    )
    assert [r.ok for r in results] == [True, True, False]


def test_an_unforeseen_growth_drops_the_whole_batch(small_limits, monkeypatch):
    monkeypatch.setattr(ops_module, "_growth", lambda form, op: (0, 0))
    form = _form()
    new, results = apply_form_ops(
        form,
        parse_ops(
            [{"op": "update_form_info", "title": "Renamed"}]
            + [{"op": "duplicate_page", "pageId": "p1"}] * 3
        ),
    )
    assert new.title == "Big" and len(new.fields) == 1
    assert [r.ok for r in results] == [True, True, False, False]
    assert results[3].message == SIZE_LIMIT_SKIPPED


def test_creating_ops_are_capped_when_parsing():
    spec = {"title": "x", "type": "short_text"}
    with pytest.raises(ValidationError):
        parse_ops([{"op": "add_page", "fields": [spec] * 201}])
    with pytest.raises(ValidationError):
        parse_ops(
            [{"op": "add_group", "pageId": "p", "title": "G", "fields": [spec] * 101}]
        )
    parse_ops([{"op": "add_page", "fields": [spec] * 200}])
