"""Unit tests for the AI form-ops engine (pure logic — no DB, no network)."""

import uuid

import pytest
from common.models.standard_form import (
    StandardChoice,
    StandardFieldProperty,
    StandardFieldValidations,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
    Theme,
)

from backend.app.services.ai.ops import (
    AddFieldOp,
    AddPageOp,
    FieldPatch,
    MoveFieldOp,
    NewFieldSpec,
    RemoveFieldOp,
    RemovePageOp,
    UpdateFieldOp,
    UpdateFormInfoOp,
    UpdateThemeOp,
    apply_form_ops,
    parse_ops,
)


def _field(ftype: StandardFormFieldType, title: str, index: int, choices=None) -> StandardFormField:
    props = StandardFieldProperty(fields=[])
    if choices:
        props.choices = [StandardChoice(id=str(uuid.uuid4()), value=v) for v in choices]
    return StandardFormField(id=str(uuid.uuid4()), index=index, type=ftype, title=title, properties=props)


@pytest.fixture()
def form() -> StandardForm:
    page1 = StandardFormField(
        id="page-1",
        index=0,
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(
            fields=[
                _field(StandardFormFieldType.SHORT_TEXT, "Your name", 0),
                _field(StandardFormFieldType.YES_NO, "Do you enjoy forms?", 1, choices=["Yes", "No"]),
            ]
        ),
    )
    page2 = StandardFormField(
        id="page-2",
        index=1,
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(
            fields=[_field(StandardFormFieldType.MULTIPLE_CHOICE, "Favourite colour?", 0, choices=["Red", "Blue"])]
        ),
    )
    return StandardForm(builder_version="v2", form_id="form-1", title="Test form", fields=[page1, page2])


def _page_fields(form: StandardForm, page_id: str):
    page = next(f for f in form.fields if f.id == page_id)
    return page.properties.fields


class TestAddField:
    def test_append_by_default(self, form):
        op = AddFieldOp(page_id="page-1", field=NewFieldSpec(title="Email", type=StandardFormFieldType.EMAIL, required=True))
        new_form, results = apply_form_ops(form, [op])
        assert results[0].ok, results[0].message
        fields = _page_fields(new_form, "page-1")
        assert [f.title for f in fields] == ["Your name", "Do you enjoy forms?", "Email"]
        assert fields[2].validations.required is True
        assert fields[2].id  # got a generated id
        assert [f.index for f in fields] == [0, 1, 2]  # renumbered

    def test_insert_after_sibling(self, form):
        anchor = _page_fields(form, "page-1")[0].id
        op = AddFieldOp(page_id="page-1", field=NewFieldSpec(title="Phone", type=StandardFormFieldType.PHONE_NUMBER), after_field_id=anchor)
        new_form, results = apply_form_ops(form, [op])
        assert results[0].ok
        assert [f.title for f in _page_fields(new_form, "page-1")] == ["Your name", "Phone", "Do you enjoy forms?"]

    def test_yes_no_gets_fixed_choices(self, form):
        op = AddFieldOp(page_id="page-2", field=NewFieldSpec(title="Agree?", type=StandardFormFieldType.YES_NO))
        new_form, results = apply_form_ops(form, [op])
        added = _page_fields(new_form, "page-2")[-1]
        assert [c.value for c in added.properties.choices] == ["Yes", "No"]

    def test_choice_field_requires_two_choices(self, form):
        op = AddFieldOp(page_id="page-1", field=NewFieldSpec(title="Pick", type=StandardFormFieldType.DROPDOWN, choices=["Only one"]))
        new_form, results = apply_form_ops(form, [op])
        assert not results[0].ok
        assert "at least 2 choices" in results[0].message
        assert len(_page_fields(new_form, "page-1")) == 2  # unchanged

    def test_rating_defaults_steps(self, form):
        op = AddFieldOp(page_id="page-1", field=NewFieldSpec(title="Rate us", type=StandardFormFieldType.RATING))
        new_form, _ = apply_form_ops(form, [op])
        assert _page_fields(new_form, "page-1")[-1].properties.steps == 5

    def test_disallowed_type_fails_gracefully(self, form):
        op = AddFieldOp(page_id="page-1", field=NewFieldSpec(title="Grid", type=StandardFormFieldType.MATRIX))
        _, results = apply_form_ops(form, [op])
        assert not results[0].ok
        assert "cannot be created" in results[0].message

    def test_unknown_page_fails_gracefully(self, form):
        op = AddFieldOp(page_id="nope", field=NewFieldSpec(title="X", type=StandardFormFieldType.SHORT_TEXT))
        _, results = apply_form_ops(form, [op])
        assert not results[0].ok
        assert "not found" in results[0].message


class TestUpdateField:
    def test_title_and_required(self, form):
        fid = _page_fields(form, "page-1")[0].id
        op = UpdateFieldOp(field_id=fid, patch=FieldPatch(title="Full name", required=True))
        new_form, results = apply_form_ops(form, [op])
        assert results[0].ok
        field = _page_fields(new_form, "page-1")[0]
        assert field.title == "Full name"
        assert field.validations.required is True

    def test_choices_replacement_preserves_ids_of_kept_values(self, form):
        original = _page_fields(form, "page-2")[0]
        red_id = next(c.id for c in original.properties.choices if c.value == "Red")
        op = UpdateFieldOp(field_id=original.id, patch=FieldPatch(choices=["Red", "Green"]))
        new_form, results = apply_form_ops(form, [op])
        assert results[0].ok
        updated = _page_fields(new_form, "page-2")[0]
        values = {c.value: c.id for c in updated.properties.choices}
        assert set(values) == {"Red", "Green"}
        assert values["Red"] == red_id  # logic rules referencing Red survive

    def test_choices_on_non_choice_field_fails(self, form):
        fid = _page_fields(form, "page-1")[0].id  # short_text
        op = UpdateFieldOp(field_id=fid, patch=FieldPatch(choices=["A", "B"]))
        _, results = apply_form_ops(form, [op])
        assert not results[0].ok

    def test_yes_no_choices_are_fixed(self, form):
        fid = _page_fields(form, "page-1")[1].id
        op = UpdateFieldOp(field_id=fid, patch=FieldPatch(choices=["Ja", "Nein"]))
        _, results = apply_form_ops(form, [op])
        assert not results[0].ok
        assert "fixed" in results[0].message

    def test_empty_patch_fails(self, form):
        fid = _page_fields(form, "page-1")[0].id
        _, results = apply_form_ops(form, [UpdateFieldOp(field_id=fid, patch=FieldPatch())])
        assert not results[0].ok


class TestRemoveAndMove:
    def test_remove(self, form):
        fid = _page_fields(form, "page-1")[0].id
        new_form, results = apply_form_ops(form, [RemoveFieldOp(field_id=fid)])
        assert results[0].ok
        fields = _page_fields(new_form, "page-1")
        assert [f.title for f in fields] == ["Do you enjoy forms?"]
        assert fields[0].index == 0  # renumbered

    def test_move_within_page(self, form):
        fid = _page_fields(form, "page-1")[1].id
        new_form, results = apply_form_ops(form, [MoveFieldOp(field_id=fid, index=0)])
        assert results[0].ok
        assert [f.title for f in _page_fields(new_form, "page-1")] == ["Do you enjoy forms?", "Your name"]

    def test_move_between_pages(self, form):
        fid = _page_fields(form, "page-1")[0].id
        new_form, results = apply_form_ops(form, [MoveFieldOp(field_id=fid, to_page_id="page-2", index=0)])
        assert results[0].ok
        assert [f.title for f in _page_fields(new_form, "page-1")] == ["Do you enjoy forms?"]
        assert [f.title for f in _page_fields(new_form, "page-2")] == ["Your name", "Favourite colour?"]
        # indexes renumbered on both pages
        assert [f.index for f in _page_fields(new_form, "page-2")] == [0, 1]


class TestPages:
    def test_add_page_with_fields(self, form):
        op = AddPageOp(fields=[NewFieldSpec(title="Feedback", type=StandardFormFieldType.LONG_TEXT)])
        new_form, results = apply_form_ops(form, [op])
        assert results[0].ok
        pages = [f for f in new_form.fields if f.type == StandardFormFieldType.SLIDE]
        assert len(pages) == 3
        assert pages[2].index == 2
        assert pages[2].properties.fields[0].title == "Feedback"

    def test_add_page_at_index(self, form):
        new_form, results = apply_form_ops(form, [AddPageOp(index=0)])
        assert results[0].ok
        pages = [f for f in new_form.fields if f.type == StandardFormFieldType.SLIDE]
        assert pages[0].properties.fields == []
        assert pages[1].id == "page-1"

    def test_remove_page(self, form):
        new_form, results = apply_form_ops(form, [RemovePageOp(page_id="page-1")])
        assert results[0].ok
        pages = [f for f in new_form.fields if f.type == StandardFormFieldType.SLIDE]
        assert [p.id for p in pages] == ["page-2"]
        assert pages[0].index == 0


class TestFormLevel:
    def test_update_form_info(self, form):
        new_form, results = apply_form_ops(form, [UpdateFormInfoOp(title="Renamed", description="New desc")])
        assert results[0].ok
        assert new_form.title == "Renamed"
        assert new_form.description == "New desc"

    def test_update_theme(self, form):
        theme = Theme(title="Ocean", primary="#111827", secondary="#1D4ED8", tertiary="#2563EB", accent="#DBEAFE")
        new_form, results = apply_form_ops(form, [UpdateThemeOp(theme=theme)])
        assert results[0].ok
        assert new_form.theme.title == "Ocean"


class TestEngineSemantics:
    def test_original_form_is_untouched(self, form):
        before = form.model_dump()
        apply_form_ops(form, [UpdateFormInfoOp(title="Changed")])
        assert form.model_dump() == before

    def test_failed_op_does_not_stop_later_ops(self, form):
        ops = [
            RemoveFieldOp(field_id="does-not-exist"),
            UpdateFormInfoOp(title="Still applied"),
        ]
        new_form, results = apply_form_ops(form, ops)
        assert not results[0].ok
        assert results[1].ok
        assert new_form.title == "Still applied"

    def test_parse_ops_from_camel_case_json(self):
        payload = [
            {"op": "add_field", "pageId": "page-1", "field": {"title": "Email", "type": "email", "required": True}},
            {"op": "update_field", "fieldId": "f1", "patch": {"colSpan": 6}},
            {"op": "move_field", "fieldId": "f1", "toPageId": "page-2", "index": 0},
        ]
        ops = parse_ops(payload)
        assert isinstance(ops[0], AddFieldOp) and ops[0].field.required is True
        assert isinstance(ops[1], UpdateFieldOp) and ops[1].patch.col_span == 6
        assert isinstance(ops[2], MoveFieldOp) and ops[2].to_page_id == "page-2"

    def test_parse_rejects_unknown_op(self):
        with pytest.raises(Exception):
            parse_ops([{"op": "drop_database"}])

    def test_result_messages_are_human_readable(self, form):
        fid = _page_fields(form, "page-1")[0].id
        _, results = apply_form_ops(form, [UpdateFieldOp(field_id=fid, patch=FieldPatch(required=True))])
        assert "Your name" in results[0].message
