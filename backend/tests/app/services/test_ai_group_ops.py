"""AI form ops for repeating groups (pure logic — no DB, no network)."""

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)

from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import project_form


@pytest.fixture()
def form() -> StandardForm:
    page = StandardFormField(
        id="page-1",
        index=0,
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(
            fields=[
                StandardFormField(
                    id="intro",
                    index=0,
                    type=StandardFormFieldType.SHORT_TEXT,
                    title="Household name",
                ),
            ]
        ),
    )
    return StandardForm(
        builder_version="v2", form_id="form-1", title="Household", fields=[page]
    )


def _apply(form, payload):
    new_form, results = apply_form_ops(form, parse_ops(payload))
    return new_form, results


def _group(form):
    return next(
        f
        for f in form.fields[0].properties.fields
        if f.type == StandardFormFieldType.GROUP
    )


def test_add_group_with_children(form):
    new_form, results = _apply(
        form,
        [
            {
                "op": "add_group",
                "pageId": "page-1",
                "title": "Family members",
                "itemLabel": "Member",
                "minItems": 1,
                "maxItems": 6,
                "fields": [
                    {"title": "Name", "type": "short_text", "required": True},
                    {"title": "Age", "type": "number"},
                ],
            }
        ],
    )
    assert results[0].ok, results[0].message
    group = _group(new_form)
    assert group.properties.repeat.item_label == "Member"
    assert group.properties.repeat.effective_export_layout == "rows"
    assert [c.title for c in group.properties.fields] == ["Name", "Age"]
    assert [c.index for c in group.properties.fields] == [0, 1]
    assert group.properties.fields[0].validations.required is True


def _with_group(form):
    new_form, _ = _apply(
        form,
        [
            {
                "op": "add_group",
                "pageId": "page-1",
                "title": "Employers",
                "itemLabel": "Employer",
                "fields": [{"title": "Employer name", "type": "short_text"}],
            }
        ],
    )
    return new_form, _group(new_form)


def test_add_field_into_group_and_update_group_settings(form):
    new_form, group = _with_group(form)
    new_form, results = _apply(
        new_form,
        [
            {
                "op": "add_field",
                "groupId": group.id,
                "field": {"title": "Salary", "type": "number"},
            },
            {
                "op": "update_field",
                "fieldId": group.id,
                "patch": {"maxItems": 4, "itemLabel": "Job"},
            },
        ],
    )
    assert all(r.ok for r in results), [r.message for r in results]
    group = _group(new_form)
    assert [c.title for c in group.properties.fields] == ["Employer name", "Salary"]
    assert group.properties.repeat.max_items == 4
    assert group.properties.repeat.item_label == "Job"


def test_group_rejects_nested_groups_and_uploads(form):
    new_form, group = _with_group(form)
    _, results = _apply(
        new_form,
        [
            {
                "op": "add_field",
                "groupId": group.id,
                "field": {"title": "CV", "type": "file_upload"},
            },
            {
                "op": "move_field",
                "fieldId": group.id,
                "toGroupId": group.id,
                "index": 0,
            },
            {
                "op": "update_field",
                "fieldId": group.id,
                "patch": {"minItems": 5, "maxItems": 2},
            },
            {"op": "update_field", "fieldId": "intro", "patch": {"maxItems": 2}},
        ],
    )
    assert [r.ok for r in results] == [False, False, False, False]


def test_move_field_into_and_out_of_group(form):
    new_form, group = _with_group(form)
    new_form, results = _apply(
        new_form,
        [{"op": "move_field", "fieldId": "intro", "toGroupId": group.id, "index": 0}],
    )
    assert results[0].ok
    assert [c.id for c in _group(new_form).properties.fields][0] == "intro"
    new_form, results = _apply(
        new_form,
        [{"op": "move_field", "fieldId": "intro", "toPageId": "page-1", "index": 0}],
    )
    assert results[0].ok
    assert new_form.fields[0].properties.fields[0].id == "intro"


def test_conditions_inside_and_outside_a_group(form):
    new_form, group = _with_group(form)
    new_form, _ = _apply(
        new_form,
        [
            {
                "op": "add_field",
                "groupId": group.id,
                "field": {"title": "Still employed?", "type": "yes_no"},
            }
        ],
    )
    group = _group(new_form)
    name_id, employed_id = [c.id for c in group.properties.fields]
    new_form, results = _apply(
        new_form,
        [
            # Sibling reference inside the group: this item's answer.
            {
                "op": "set_field_logic",
                "fieldId": name_id,
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {
                            "fieldId": employed_id,
                            "comparison": "IS_EQUAL",
                            "value": "Yes",
                        }
                    ],
                },
            },
            # Outside the group, children cannot be referenced by themselves...
            {
                "op": "set_field_logic",
                "fieldId": "intro",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {
                            "fieldId": employed_id,
                            "comparison": "IS_EQUAL",
                            "value": "Yes",
                        }
                    ],
                },
            },
            # ...only through the group as a whole.
            {
                "op": "set_field_logic",
                "fieldId": "intro",
                "logic": {
                    "action": "HIDE",
                    "conditions": [
                        {
                            "fieldId": group.id,
                            "groupMode": "ANY",
                            "childFieldId": employed_id,
                            "comparison": "IS_EQUAL",
                            "value": "Yes",
                        }
                    ],
                },
            },
            {
                "op": "set_page_jumps",
                "pageId": "page-1",
                "jumps": [
                    {
                        "conditions": [
                            {
                                "fieldId": group.id,
                                "groupMode": "COUNT",
                                "comparison": "GREATER_THAN_EQUAL",
                                "value": "2",
                            }
                        ],
                        "target": "__SUBMIT__",
                    }
                ],
            },
            {
                "op": "set_page_jumps",
                "pageId": "page-1",
                "jumps": [
                    {
                        "conditions": [
                            {"fieldId": group.id, "comparison": "IS_NOT_EMPTY"}
                        ],
                        "target": "__SUBMIT__",
                    }
                ],
            },
        ],
    )
    assert [r.ok for r in results] == [True, False, True, True, False], [
        r.message for r in results
    ]
    group = _group(new_form)
    condition = new_form.fields[0].properties.fields[0].properties.logic.conditions[0]
    assert (
        condition.group_mode,
        condition.child_field_id,
        condition.child_field_type,
    ) == ("ANY", employed_id, "yes_no")
    jump = new_form.fields[0].properties.jumps[0].conditions[0]
    assert (jump.group_mode, jump.value) == ("COUNT", 2)


def test_remove_child_and_duplicate_page_remaps_group(form):
    new_form, group = _with_group(form)
    child_id = group.properties.fields[0].id
    duplicated, results = _apply(
        new_form, [{"op": "duplicate_page", "pageId": "page-1"}]
    )
    assert results[0].ok
    clone_group = next(
        f
        for f in duplicated.fields[1].properties.fields
        if f.type == StandardFormFieldType.GROUP
    )
    assert clone_group.properties.fields[0].id != child_id
    removed, results = _apply(new_form, [{"op": "remove_field", "fieldId": child_id}])
    assert results[0].ok
    assert _group(removed).properties.fields == []


def test_snapshot_shows_group_children(form):
    new_form, group = _with_group(form)
    snapshot = project_form(new_form)
    assert '"repeatingGroup"' in snapshot
    assert "Employer name" in snapshot
