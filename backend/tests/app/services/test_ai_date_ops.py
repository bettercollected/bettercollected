"""AI form ops for date labels and date rules (pure logic — no DB)."""

import pytest
from common.models.standard_form import StandardForm

from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import project_form


@pytest.fixture()
def form() -> StandardForm:
    return StandardForm.model_validate(
        {
            "builder_version": "v2",
            "title": "Trip",
            "fields": [
                {
                    "id": "page-1",
                    "type": "slide",
                    "index": 0,
                    "properties": {
                        "fields": [
                            {"id": "start", "type": "date", "title": "Start date"},
                            {"id": "end", "type": "date", "title": "End date"},
                            {"id": "name", "type": "short_text", "title": "Name"},
                            {
                                "id": "stays",
                                "type": "group",
                                "title": "Stays",
                                "properties": {
                                    "repeat": {"minItems": 1, "maxItems": 3},
                                    "fields": [
                                        {"id": "in", "type": "date", "title": "In"},
                                        {"id": "out", "type": "date", "title": "Out"},
                                    ],
                                },
                            },
                        ]
                    },
                }
            ],
        }
    )


def _apply(form, payload):
    return apply_form_ops(form, parse_ops(payload))


def _field(form, field_id):
    for field in form.fields[0].properties.fields:
        if field.id == field_id:
            return field
        for child in (field.properties.fields if field.properties else None) or []:
            if child.id == field_id:
                return child
    raise KeyError(field_id)


def _rules(field_id, rules):
    return {"op": "update_field", "fieldId": field_id, "patch": {"dateRules": rules}}


AFTER_START = {"comparison": "after", "target": "field", "fieldId": "start"}


def test_update_field_sets_label_and_rules(form):
    new_form, results = _apply(
        form,
        [
            {"op": "update_field", "fieldId": "end", "patch": {"label": "End date"}},
            _rules(
                "end", [AFTER_START, {"comparison": "on_or_after", "target": "today"}]
            ),
        ],
    )
    assert all(r.ok for r in results), [r.message for r in results]
    end = _field(new_form, "end")
    assert end.properties.label == "End date"
    assert [r.target for r in end.properties.date_rules] == ["field", "today"]
    snapshot = project_form(new_form)
    assert '"dateRules"' in snapshot and '"label": "End date"' in snapshot


@pytest.mark.parametrize(
    "field_id, rules, expected",
    [
        ("end", [{**AFTER_START, "fieldId": "end"}], "itself"),
        ("end", [{**AFTER_START, "fieldId": "name"}], "not a date"),
        ("end", [{**AFTER_START, "fieldId": "nope"}], "does not exist"),
        ("end", [{**AFTER_START, "fieldId": "in"}], "repeating group"),
        ("out", [AFTER_START], "another part"),
        ("name", [AFTER_START], "only apply to date"),
        (
            "end",
            [{"comparison": "after", "target": "date", "date": "soon"}],
            "YYYY-MM-DD",
        ),
        ("end", [{"comparison": "after", "target": "today"}] * 6, "at most 5"),
    ],
)
def test_bad_rules_are_refused(form, field_id, rules, expected):
    new_form, results = _apply(form, [_rules(field_id, rules)])
    assert not results[0].ok
    assert expected in results[0].message
    assert _field(new_form, field_id).properties.date_rules is None


def test_cycle_is_refused(form):
    new_form, results = _apply(
        form,
        [
            _rules("end", [AFTER_START]),
            _rules("start", [{**AFTER_START, "fieldId": "end"}]),
        ],
    )
    assert results[0].ok and not results[1].ok
    assert "circle" in results[1].message
    assert _field(new_form, "start").properties.date_rules is None


def test_sibling_rule_in_a_group(form):
    new_form, results = _apply(
        form, [_rules("out", [{**AFTER_START, "fieldId": "in"}])]
    )
    assert results[0].ok, results[0].message
    assert _field(new_form, "out").properties.date_rules[0].field_id == "in"


def test_empty_list_clears(form):
    new_form, _ = _apply(form, [_rules("end", [AFTER_START])])
    cleared, results = _apply(new_form, [_rules("end", [])])
    assert results[0].ok
    assert _field(cleared, "end").properties.date_rules is None


def test_removing_the_referenced_date_drops_the_rule(form):
    new_form, _ = _apply(form, [_rules("end", [AFTER_START])])
    after, results = _apply(new_form, [{"op": "remove_field", "fieldId": "start"}])
    assert results[0].ok and "1 date rule" in results[0].message
    assert _field(after, "end").properties.date_rules is None


def test_referenced_date_cannot_become_internal(form):
    new_form, _ = _apply(form, [_rules("end", [AFTER_START])])
    _, results = _apply(
        new_form,
        [{"op": "update_field", "fieldId": "start", "patch": {"internal": True}}],
    )
    assert not results[0].ok and "date rule" in results[0].message


def test_duplicate_page_remaps_rule_references(form):
    new_form, _ = _apply(
        form,
        [
            _rules("end", [AFTER_START]),
            _rules("out", [{**AFTER_START, "fieldId": "in"}]),
        ],
    )
    copied, results = _apply(new_form, [{"op": "duplicate_page", "pageId": "page-1"}])
    assert results[0].ok
    clone = copied.fields[1].properties.fields
    start, end, _, group = clone
    assert end.properties.date_rules[0].field_id == start.id != "start"
    check_in, check_out = group.properties.fields
    assert check_out.properties.date_rules[0].field_id == check_in.id != "in"


def test_label_only_on_date_questions(form):
    _, results = _apply(
        form, [{"op": "update_field", "fieldId": "name", "patch": {"label": "x"}}]
    )
    assert not results[0].ok
