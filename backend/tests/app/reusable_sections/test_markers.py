"""The library marker on a copied question stays inside the workspace and the
creator's view: a respondent's form never has it, a copy to another workspace
(a template, an import) drops it, a duplicate inside the workspace keeps it."""

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.services.internal_fields import strip_internal_fields
from backend.app.services.reusable_sections.markers import strip_library_markers
from tests.app.controllers.data import testUser

pytestmark = pytest.mark.asyncio

MARK = {"section_id": "s1", "version": 1, "key": "k", "instance": "i1"}


def marked_form() -> StandardForm:
    return StandardForm(
        builder_version="v2",
        title="Marked",
        fields=[
            {
                "id": "p1",
                "type": "slide",
                "index": 0,
                "properties": {
                    "fields": [
                        {"id": "a", "type": "short_text", "title": "A", "index": 0, "properties": {"library": MARK}},
                        {"id": "b", "type": "short_text", "title": "B", "index": 1},
                        {
                            "id": "g",
                            "type": "group",
                            "title": "G",
                            "index": 2,
                            "properties": {
                                "repeat": {"min_items": 1, "max_items": 2},
                                "fields": [{"id": "c", "type": "short_text", "title": "C", "index": 0, "properties": {"library": MARK}}],
                            },
                        },
                    ]
                },
            }
        ],
    )


def libraries(form) -> list:
    page = form.fields[0].properties.fields
    return [f.properties.library if f.properties else None for f in [*page, *page[2].properties.fields]]


def test_strip_library_markers_clears_every_question_including_a_groups_children():
    form = marked_form()
    assert [x is not None for x in libraries(form)] == [True, False, False, True]
    assert strip_library_markers(form) == 2
    assert libraries(form) == [None, None, None, None]
    assert strip_library_markers(form) == 0


def test_it_reads_plain_dicts_too_in_either_case():
    document = {"fields": [{"type": "slide", "properties": {"fields": [{"id": "a", "type": "short_text", "properties": {"library": {"sectionId": "s"}}}]}}]}
    assert strip_library_markers(document) == 1
    assert "library" not in document["fields"][0]["properties"]["fields"][0]["properties"]


def test_a_respondents_form_never_carries_the_marker():
    form = marked_form()
    assert strip_internal_fields(form) is not None
    assert libraries(form) == [None, None, None, None]
    document = {
        "fields": [
            {"type": "slide", "properties": {"fields": [{"id": "a", "type": "short_text", "properties": {"library": {"sectionId": "s1", "key": "k"}}}]}}
        ]
    }
    strip_internal_fields(document)
    assert document["fields"][0]["properties"]["fields"][0]["properties"].get("library") is None


async def _marked_form_in(workspace):
    form = await container.workspace_form_service().create_form(workspace.id, marked_form(), testUser)
    stored = await container.form_service().get_form_document_by_id(form.form_id)
    assert libraries(stored)[0] is not None
    return form


async def test_a_duplicate_inside_the_workspace_keeps_the_marker(workspace):
    form = await _marked_form_in(workspace)
    duplicate = await container.workspace_form_service().duplicate_form(workspace.id, form.form_id, testUser)
    stored = await container.form_service().get_form_document_by_id(duplicate.form_id)
    assert libraries(stored)[0].section_id == "s1" and libraries(stored)[3] is not None


async def test_a_template_made_from_a_form_has_no_marker(workspace):
    form = await _marked_form_in(workspace)
    template = await container.workspace_form_service().duplicate_form(workspace.id, form.form_id, testUser, is_template=True)
    assert [m is None for m in libraries(template)] == [True, True, True, True]
