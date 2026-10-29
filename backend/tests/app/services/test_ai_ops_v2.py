"""Ops v2: client refs, atomic batches, move_page, set_field_validation,
set_question_numbering and cross-page move_field (pure logic)."""

import pytest
from common.models.standard_form import (
    StandardChoice,
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)
from pydantic import ValidationError

from backend.app.services.ai.ops import (
    VALIDATION_PRESETS,
    applied,
    apply_form_ops,
    parse_ops,
)

T = StandardFormFieldType


def _q(fid, ftype, title, **props):
    return StandardFormField(
        id=fid,
        type=ftype,
        title=title,
        properties=StandardFieldProperty(fields=[], **props),
    )


def _page(pid, *fields):
    return StandardFormField(
        id=pid, type=T.SLIDE, properties=StandardFieldProperty(fields=list(fields))
    )


@pytest.fixture()
def form() -> StandardForm:
    return StandardForm(
        builder_version="v2",
        title="Form",
        fields=[
            _page(
                "p1",
                _q("name", T.SHORT_TEXT, "Name"),
                _q(
                    "pets",
                    T.YES_NO,
                    "Pets?",
                    choices=[
                        StandardChoice(id="y", value="Yes"),
                        StandardChoice(id="n", value="No"),
                    ],
                ),
                _q("age", T.NUMBER, "Age"),
                _q(
                    "topics",
                    T.MULTIPLE_CHOICE,
                    "Topics",
                    allow_multiple_selection=True,
                    choices=[StandardChoice(id=c, value=c) for c in ("A", "B", "C")],
                ),
                _q(
                    "colour",
                    T.DROPDOWN,
                    "Colour",
                    choices=[
                        StandardChoice(id="r", value="Red"),
                        StandardChoice(id="b", value="Blue"),
                    ],
                ),
            ),
            _page("p2", _q("notes", T.LONG_TEXT, "Notes")),
            _page("p3"),
        ],
    )


def run(form, payload, atomic=False):
    return apply_form_ops(form, parse_ops(payload), atomic=atomic)


def page_ids(form):
    return [p.id for p in form.fields]


def questions(form, page_id):
    page = next(p for p in form.fields if p.id == page_id)
    return page.properties.fields


def by_title(form, title):
    for page in form.fields:
        for field in page.properties.fields or []:
            if field.title == title:
                return field
            for child in (field.properties.fields if field.properties else None) or []:
                if child.title == title:
                    return child
    raise AssertionError(title)


# ---------------------------------------------------------------------------
# refs
# ---------------------------------------------------------------------------


def test_refs_build_a_page_with_logic_and_jumps_in_one_batch(form):
    new, results = run(
        form,
        [
            {
                "op": "add_page",
                "ref": "pg",
                "fields": [{"title": "Has car?", "type": "yes_no", "ref": "car"}],
            },
            {
                "op": "add_field",
                "pageId": "$ref:pg",
                "ref": "plate",
                "field": {"title": "Plate", "type": "short_text"},
            },
            {
                "op": "set_field_logic",
                "fieldId": "$ref:plate",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {
                            "fieldId": "$ref:car",
                            "comparison": "IS_EQUAL",
                            "value": "Yes",
                        }
                    ],
                },
            },
            {
                "op": "set_page_jumps",
                "pageId": "p1",
                "jumps": [
                    {
                        "conditions": [
                            {
                                "fieldId": "pets",
                                "comparison": "IS_EQUAL",
                                "value": "Yes",
                            }
                        ],
                        "target": "$ref:pg",
                    }
                ],
            },
            {
                "op": "move_field",
                "fieldId": "$ref:plate",
                "toPageId": "$ref:pg",
                "index": 0,
            },
        ],
    )
    assert all(r.ok for r in results), results
    page_id = results[0].created_id
    plate_id = results[1].created_id
    assert page_id in page_ids(new) and page_id != "pg"
    car = by_title(new, "Has car?")
    plate = by_title(new, "Plate")
    assert plate.id == plate_id
    assert [c.field_id for c in plate.properties.logic.conditions] == [car.id]
    assert plate.properties.logic.conditions[0].field_type == "yes_no"
    assert new.fields[0].properties.jumps[0].target == page_id
    assert [f.id for f in questions(new, page_id)] == [plate_id, car.id]


def test_refs_for_groups_and_their_questions(form):
    new, results = run(
        form,
        [
            {
                "op": "add_group",
                "pageId": "p2",
                "ref": "kids",
                "title": "Children",
                "itemLabel": "Child",
                "fields": [
                    {"title": "Child name", "type": "short_text", "ref": "kid-name"}
                ],
            },
            {
                "op": "add_field",
                "groupId": "$ref:kids",
                "field": {"title": "Allergies", "type": "yes_no", "ref": "allergy"},
            },
            {
                "op": "set_field_logic",
                "fieldId": "notes",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {
                            "fieldId": "$ref:kids",
                            "groupMode": "ANY",
                            "childFieldId": "$ref:allergy",
                            "comparison": "IS_EQUAL",
                            "value": "Yes",
                        }
                    ],
                },
            },
            {
                "op": "update_field",
                "fieldId": "$ref:kid-name",
                "patch": {"required": True},
            },
        ],
    )
    assert all(r.ok for r in results), results
    group = by_title(new, "Children")
    allergy = by_title(new, "Allergies")
    condition = by_title(new, "Notes").properties.logic.conditions[0]
    assert (condition.field_id, condition.child_field_id) == (group.id, allergy.id)
    assert by_title(new, "Child name").validations.required is True


def test_duplicate_page_ref(form):
    new, results = run(
        form,
        [
            {"op": "duplicate_page", "pageId": "p2", "ref": "copy"},
            {"op": "move_page", "pageId": "$ref:copy", "index": 0},
            {"op": "set_section_title", "pageId": "$ref:copy", "title": "Copied"},
        ],
    )
    assert all(r.ok for r in results), results
    assert new.fields[0].id == results[0].created_id
    assert new.fields[0].properties.section_title == "Copied"


def test_unknown_duplicate_and_failed_refs_are_plain_errors(form):
    _, results = run(
        form,
        [
            {
                "op": "add_field",
                "pageId": "$ref:nowhere",
                "field": {"title": "X", "type": "short_text"},
            },
            {"op": "add_page", "ref": "a"},
            {"op": "add_page", "ref": "a"},
            {
                "op": "add_field",
                "pageId": "missing-page",
                "ref": "lost",
                "field": {"title": "Y", "type": "short_text"},
            },
            {"op": "remove_field", "fieldId": "$ref:lost"},
            {
                "op": "add_page",
                "ref": "b",
                "fields": [
                    {"title": "1", "type": "text", "ref": "same"},
                    {"title": "2", "type": "text", "ref": "same"},
                ],
            },
        ],
    )
    assert [r.ok for r in results] == [False, True, False, False, False, False]
    assert "Unknown reference '$ref:nowhere'" in results[0].message
    assert "already defined by operation #1" in results[2].message
    assert "operation #3" in results[4].message and "failed" in results[4].message
    assert "defined twice" in results[5].message


def test_ref_text_outside_id_keys_is_left_alone(form):
    new, results = run(
        form,
        [
            {
                "op": "add_field",
                "pageId": "p3",
                "field": {"title": "$ref:literal", "type": "short_text"},
            }
        ],
    )
    assert results[0].ok
    assert questions(new, "p3")[0].title == "$ref:literal"


def test_add_field_refuses_two_different_refs(form):
    _, results = run(
        form,
        [
            {
                "op": "add_field",
                "pageId": "p3",
                "ref": "a",
                "field": {"title": "Q", "type": "short_text", "ref": "b"},
            }
        ],
    )
    assert not results[0].ok and "two different refs" in results[0].message


def test_ref_names_are_checked_when_parsing():
    with pytest.raises(ValidationError):
        parse_ops([{"op": "add_page", "ref": "$ref:x"}])
    with pytest.raises(ValidationError):
        parse_ops([{"op": "add_page", "ref": "has space"}])


def test_created_id_is_reported(form):
    _, results = run(
        form, [{"op": "add_page"}, {"op": "update_form_info", "title": "T"}]
    )
    assert results[0].created_id and results[1].created_id is None
    dumped = results[0].model_dump(by_alias=True)
    assert dumped["createdId"] == results[0].created_id


# ---------------------------------------------------------------------------
# atomic vs partial
# ---------------------------------------------------------------------------

MIXED = [
    {"op": "update_form_info", "title": "Renamed"},
    {"op": "remove_field", "fieldId": "does-not-exist"},
    {
        "op": "add_field",
        "pageId": "p3",
        "field": {"title": "New", "type": "short_text"},
    },
    {"op": "move_page", "pageId": "nope", "index": 0},
]


def test_atomic_leaves_the_form_unchanged_and_reports_every_error(form):
    before = form.model_dump()
    new, results = run(form, MIXED, atomic=True)
    assert new.model_dump() == before
    assert new is not form
    assert [(r.index, r.ok) for r in results] == [
        (0, True),
        (1, False),
        (2, True),
        (3, False),
    ]
    assert (
        "was not found" in results[1].message and "was not found" in results[3].message
    )
    assert applied(results, atomic=True) is False


def test_partial_applies_what_it_can(form):
    new, results = run(form, MIXED)
    assert new.title == "Renamed"
    assert [f.title for f in questions(new, "p3")] == ["New"]
    assert applied(results, atomic=False) is True


def test_atomic_applies_a_clean_batch(form):
    new, results = run(form, MIXED[:1] + MIXED[2:3], atomic=True)
    assert all(r.ok for r in results)
    assert new.title == "Renamed" and len(questions(new, "p3")) == 1
    assert applied(results, atomic=True) is True
    assert applied([], atomic=True) is False


def test_atomic_failed_ref_rolls_back_the_whole_batch(form):
    before = form.model_dump()
    new, results = run(
        form,
        [
            {"op": "add_page", "ref": "pg"},
            {
                "op": "add_field",
                "pageId": "$ref:typo",
                "field": {"title": "Q", "type": "short_text"},
            },
        ],
        atomic=True,
    )
    assert new.model_dump() == before
    assert [r.ok for r in results] == [True, False]


# ---------------------------------------------------------------------------
# move_page / move_field
# ---------------------------------------------------------------------------


def test_move_page(form):
    new, results = run(form, [{"op": "move_page", "pageId": "p3", "index": 0}])
    assert results[0].ok and page_ids(new) == ["p3", "p1", "p2"]
    assert [p.index for p in new.fields] == [0, 1, 2]
    new, results = run(form, [{"op": "move_page", "pageId": "p1", "index": 99}])
    assert results[0].ok and page_ids(new) == ["p2", "p3", "p1"]
    assert "position 3" in results[0].message
    new, results = run(form, [{"op": "move_page", "pageId": "p2", "index": 1}])
    assert results[0].ok and page_ids(new) == ["p1", "p2", "p3"]


def test_move_page_errors(form):
    _, results = run(
        form,
        [
            {"op": "move_page", "pageId": "p1", "index": -1},
            {"op": "move_page", "pageId": "name", "index": 0},
        ],
    )
    assert not results[0].ok and "0 or more" in results[0].message
    assert not results[1].ok and "was not found" in results[1].message


def test_move_field_across_pages_appends_without_an_index(form):
    new, results = run(
        form, [{"op": "move_field", "fieldId": "name", "toPageId": "p2"}]
    )
    assert results[0].ok
    assert [f.id for f in questions(new, "p2")] == ["notes", "name"]
    assert "name" not in [f.id for f in questions(new, "p1")]
    new, results = run(
        form, [{"op": "move_field", "fieldId": "notes", "toPageId": "p1", "index": 0}]
    )
    assert results[0].ok and questions(new, "p1")[0].id == "notes"


# ---------------------------------------------------------------------------
# set_field_validation
# ---------------------------------------------------------------------------


def _rules(form, fid):
    return by_title(
        form,
        next(f.title for p in form.fields for f in p.properties.fields if f.id == fid),
    ).validations


def test_text_lengths_and_patterns(form):
    new, results = run(
        form,
        [
            {
                "op": "set_field_validation",
                "fieldId": "name",
                "validation": {"minLength": 2, "maxLength": 40, "preset": "letters"},
            },
            {
                "op": "set_field_validation",
                "fieldId": "notes",
                "validation": {"maxLength": 500, "required": True},
            },
        ],
    )
    assert all(r.ok for r in results), results
    rules = _rules(new, "name")
    assert (rules.min_length, rules.max_length, rules.regex) == (
        2,
        40,
        VALIDATION_PRESETS["letters"],
    )
    assert (
        _rules(new, "notes").max_length == 500 and _rules(new, "notes").required is True
    )

    new, results = run(
        new,
        [
            {
                "op": "set_field_validation",
                "fieldId": "name",
                "validation": {"pattern": "^[A-Z]{2}\\d{4}$", "minLength": None},
            }
        ],
    )
    assert results[0].ok
    assert _rules(new, "name").regex == "^[A-Z]{2}\\d{4}$"
    assert (
        _rules(new, "name").min_length is None and _rules(new, "name").max_length == 40
    )

    new, results = run(
        new,
        [
            {
                "op": "set_field_validation",
                "fieldId": "name",
                "validation": {"pattern": None},
            }
        ],
    )
    assert results[0].ok and _rules(new, "name").regex is None


def test_values_and_choices(form):
    new, results = run(
        form,
        [
            {
                "op": "set_field_validation",
                "fieldId": "age",
                "validation": {"minValue": 18, "maxValue": 120},
            },
            {
                "op": "set_field_validation",
                "fieldId": "topics",
                "validation": {"minChoices": 1, "maxChoices": 2},
            },
        ],
    )
    assert all(r.ok for r in results), results
    assert (_rules(new, "age").min_value, _rules(new, "age").max_value) == (18, 120)
    assert (_rules(new, "topics").min_choices, _rules(new, "topics").max_choices) == (
        1,
        2,
    )


@pytest.mark.parametrize(
    "field_id, validation, expected",
    [
        ("age", {"minLength": 2}, "only apply to short or long text questions"),
        ("name", {"minValue": 1}, "only apply to number questions"),
        ("notes", {"preset": "digits"}, "only apply to short text questions"),
        ("colour", {"maxChoices": 1}, "allows several answers"),
        ("topics", {"maxChoices": 4}, "has 3 choice(s)"),
        ("name", {"minLength": 10, "maxLength": 5}, "cannot be more than the maximum"),
        ("age", {"minValue": 10, "maxValue": 5}, "cannot be more than the maximum"),
        ("name", {"minLength": -1}, "cannot be negative"),
        ("name", {"pattern": "(unclosed"}, "is not a valid pattern"),
        ("name", {"pattern": "a" * 201}, "at most 200 characters"),
        ("name", {"pattern": "^(?=a)b$"}, "no lookarounds and no backreferences"),
        (
            "name",
            {"pattern": "^a$", "preset": "digits"},
            "either a pattern or a preset",
        ),
        ("name", {}, "Nothing to change"),
        ("p1", {"required": True}, "was not found"),
    ],
)
def test_validation_errors_are_plain_and_change_nothing(
    form, field_id, validation, expected
):
    def rules(f):
        return [q.validations for p in f.fields for q in p.properties.fields]

    new, results = run(
        form,
        [{"op": "set_field_validation", "fieldId": field_id, "validation": validation}],
    )
    assert not results[0].ok
    assert expected in results[0].message, results[0].message
    assert rules(new) == rules(form)


# ---------------------------------------------------------------------------
# set_question_numbering
# ---------------------------------------------------------------------------


def test_question_numbering_for_one_page_or_all(form):
    new, results = run(
        form, [{"op": "set_question_numbering", "pageId": "p2", "show": True}]
    )
    assert results[0].ok and "page 2" in results[0].message
    assert [p.properties.show_question_numbers for p in new.fields] == [
        None,
        True,
        None,
    ]
    new, results = run(new, [{"op": "set_question_numbering", "show": False}])
    assert results[0].ok and "every page" in results[0].message
    assert [p.properties.show_question_numbers for p in new.fields] == [
        False,
        False,
        False,
    ]
    _, results = run(
        form, [{"op": "set_question_numbering", "pageId": "zzz", "show": True}]
    )
    assert not results[0].ok
