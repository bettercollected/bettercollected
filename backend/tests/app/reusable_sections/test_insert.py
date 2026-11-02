"""Inserting a section is a copy: fresh ids, every reference remapped to the
copy's own questions, a marker on each question; two inserts of one section in
one form do not collide; the inserted questions pass the same checks as any save;
the insert works through the edit operations too (AI, MCP, API)."""

import copy

import pytest
from common.models.standard_form import LayoutContainer, StandardForm, StandardFormField
from common.models.user import User

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.minified_form import StandardFormFieldCamelModel
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import (
    EDITOR_CONTEXT,
    SpliceFieldsOp,
    apply_form_ops,
    parse_ops,
)
from backend.app.services.reusable_sections import refs
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.reusable_sections.helpers import (
    cond,
    form_with_page,
    make_section,
    q,
    show_if,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(sections_on):
    pass


def service():
    return container.reusable_section_service()


def as_field(raw) -> StandardFormField:
    model = StandardFormFieldCamelModel.model_validate(raw)
    return StandardFormField(**model.model_dump(mode="json"))


def spec_ids(fragment) -> list:
    """Every question id of a builder-shaped fragment (group children too)."""
    found, pending = [], list(fragment.fields)
    while pending:
        field = pending.pop(0)
        found.append(field["id"])
        pending.extend(field["properties"].get("fields") or [])
    return found


def by_title(fragment) -> dict:
    found, pending = {}, list(fragment.fields)
    while pending:
        field = pending.pop(0)
        title = field["title"]
        found[title if isinstance(title, str) else "rich"] = field
        pending.extend(field["properties"].get("fields") or [])
    return found


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


async def test_an_insert_has_new_ids_a_marker_per_question_and_remapped_references(workspace):
    created = await make_section(workspace)
    fragment = await service().instantiate(workspace.id, created.id, testUser)
    stored = await container.reusable_section_repo().get(workspace.id, created.id)
    old_ids = set(refs.question_ids(stored.fields))
    new_ids = set(spec_ids(fragment))
    assert len(new_ids) == 10 and not new_ids & old_ids
    named = by_title(fragment)
    age = named["Age"]
    assert age["properties"]["logic"]["conditions"][0]["fieldId"] == [
        f["id"] for f in fragment.fields if f["properties"].get("fields") == []
    ][0]
    # the marker names the section, its version, the question's key and the insert
    markers = [
        f["properties"]["library"]
        for f in [*fragment.fields, *fragment.fields[5]["properties"]["fields"]]
    ]
    assert {m["sectionId"] for m in markers} == {created.id}
    assert {m["version"] for m in markers} == {1}
    assert {m["instance"] for m in markers} == {fragment.instance}
    assert {m["key"] for m in markers} <= old_ids
    # containers: new ids, members are the copy's
    box = fragment.containers[0]
    assert box["fields"] == [fragment.fields[0]["id"], fragment.fields[1]["id"]]
    assert box["id"] != "box"


async def test_two_inserts_of_the_same_section_do_not_collide(workspace):
    created = await make_section(workspace)
    one = await service().instantiate(workspace.id, created.id, testUser)
    two = await service().instantiate(workspace.id, created.id, testUser)
    assert not set(spec_ids(one)) & set(spec_ids(two))
    assert one.instance != two.instance
    assert one.containers[0]["id"] != two.containers[0]["id"]
    rule_ids = lambda fragment: {  # noqa: E731
        r["id"] for f in fragment.fields for r in (f["properties"].get("rules") or [])
    }
    assert rule_ids(one) and not rule_ids(one) & rule_ids(two)
    # both go into one form through the edit operations and the form stays valid
    form = StandardForm(**(await form_with_page(workspace)).model_dump())
    ops = [
        _splice("s1", one),
        _splice("s1", two),
    ]
    result, results = apply_form_ops(form, ops, atomic=True)
    assert all(r.ok for r in results), [r.message for r in results]
    inserted = [f.id for f in result.fields[0].properties.fields]
    assert len(inserted) == 1 + 2 * 8 and len(set(inserted)) == len(inserted)
    # a calculation of each copy reads its own copy's questions
    calcs = [f for f in result.fields[0].properties.fields if f.type.value == "calculated"]
    assert len(calcs) == 2
    for calc, fragment in zip(calcs, (one, two)):
        own = set(spec_ids(fragment))
        keys = {n["var"] for n in _vars(calc.properties.expression)}
        assert keys and keys <= own


def _vars(ast):
    stack, found = [ast], []
    while stack:
        node = stack.pop()
        if isinstance(node, dict) and len(node) == 1:
            op, value = next(iter(node.items()))
            if op == "var":
                found.append(node)
            elif isinstance(value, list):
                stack.extend(value)
    return found


def _splice(page_id, fragment, **extra):
    return SpliceFieldsOp.model_validate(
        {
            "op": "splice_fields",
            "pageId": page_id,
            "fields": copy.deepcopy(fragment.fields),
            "containers": copy.deepcopy(fragment.containers),
            **extra,
        },
        context={EDITOR_CONTEXT: True},
    )


async def test_the_inserted_questions_pass_a_builder_save(workspace):
    created = await make_section(workspace)
    fragment = await service().instantiate(workspace.id, created.id, testUser)
    form_doc = await form_with_page(workspace)
    stored = await container.form_service().get_form_document_by_id(form_doc.form_id)
    edited = StandardForm(**stored.model_dump())
    page = edited.fields[0]
    page.properties.fields.extend(as_field(f) for f in fragment.fields)
    page.properties.containers = [
        # the builder holds containers as the model
        LayoutContainer.model_validate(c) for c in fragment.containers
    ]
    await container.workspace_form_service().update_form(
        workspace.id, form_doc.form_id, edited, testUser
    )
    saved = await container.form_service().get_form_document_by_id(form_doc.form_id)
    markers = [
        f.properties.library for f in saved.fields[0].properties.fields if f.properties.library
    ]
    assert len(markers) == 8 and {m.instance for m in markers} == {fragment.instance}


async def test_a_section_refused_by_the_form_checks_cannot_be_inserted(workspace, monkeypatch):
    created = await make_section(workspace)
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    error = await refused(service().instantiate(workspace.id, created.id, testUser))
    assert error.status_code == 422


async def test_a_reference_that_would_escape_refuses_the_insert(workspace):
    created = await make_section(workspace, fields=[q("a", title="A"), q("b", title="B", logic=show_if(cond("a")))], containers=[])
    repo = container.reusable_section_repo()
    stored = await repo.get(workspace.id, created.id)
    # stored data that points at a question of some other form (an older bug, a
    # hand edit): the insert drops it rather than carry it over
    stored.fields[1]["logic"]["conditions"].append(cond("some-other-form-question"))
    await repo.replace(stored, None, bump=False)
    fragment = await service().instantiate(workspace.id, created.id, testUser)
    named = by_title(fragment)
    conditions = named["B"]["properties"]["logic"]["conditions"]
    assert [c["fieldId"] for c in conditions] == [named["A"]["id"]]
    assert "some-other-form-question" not in str(fragment.fields)


# ---------------------------------------------------------- the operations


async def _doc_and_form(workspace):
    form_doc = await form_with_page(workspace)
    document = await container.form_service().get_form_document_by_id(form_doc.form_id)
    return document, StandardForm(**document.model_dump())


async def test_an_ai_or_api_op_inserts_a_library_section(workspace):
    created = await make_section(workspace)
    document, form = await _doc_and_form(workspace)
    ops = parse_ops(
        [{"op": "insert_library_section", "pageId": "s1", "sectionId": created.id, "index": 0}]
    )
    new_form, results, _ = await persist_ops_to_form(
        document, form, ops, workspace_id=workspace.id, atomic=True
    )
    assert [(r.op, r.ok) for r in results] == [("insert_library_section", True)]
    assert results[0].created_id
    page = (await container.form_service().get_form_document_by_id(document.form_id)).fields[0]
    titles = [f.title if isinstance(f.title, str) else "rich" for f in page.properties.fields]
    assert titles[0] == "rich" and titles[-1] == "Intro" and len(titles) == 9
    assert page.properties.fields[0].properties.library.section_id == created.id
    assert page.properties.containers and page.properties.containers[0].title == "Applicant"


async def test_an_op_cannot_read_another_workspaces_section(workspace, workspace_1):
    theirs = await make_section(workspace_1, name="Theirs", fields=[q("a", title="Secret")], containers=[], user=testUser1)
    document, form = await _doc_and_form(workspace)
    ops = parse_ops(
        [{"op": "insert_library_section", "pageId": "s1", "sectionId": theirs.id}]
    )
    _, results, _ = await persist_ops_to_form(
        document, form, ops, workspace_id=workspace.id
    )
    assert results[0].ok is False and results[0].op == "insert_library_section"
    # the same answer for an id that does not exist: nothing says which
    unknown = parse_ops(
        [{"op": "insert_library_section", "pageId": "s1", "sectionId": "0" * 24}]
    )
    _, again, _ = await persist_ops_to_form(document, form, unknown, workspace_id=workspace.id)
    assert again[0].message == results[0].message
    stored = await container.form_service().get_form_document_by_id(document.form_id)
    assert "Secret" not in str(stored.model_dump())


async def test_an_op_fails_while_the_switch_is_off(workspace, monkeypatch):
    created = await make_section(workspace)
    document, form = await _doc_and_form(workspace)
    monkeypatch.setattr(settings, "REUSABLE_SECTIONS_ENABLED", False)
    ops = parse_ops(
        [{"op": "insert_library_section", "pageId": "s1", "sectionId": created.id}]
    )
    _, results, _ = await persist_ops_to_form(document, form, ops, workspace_id=workspace.id)
    assert results[0].ok is False


async def test_the_engine_alone_never_inserts_a_library_section(workspace):
    created = await make_section(workspace, fields=[q("a")], containers=[])
    _, form = await _doc_and_form(workspace)
    ops = parse_ops([{"op": "insert_library_section", "pageId": "s1", "sectionId": created.id}])
    _, results = apply_form_ops(form, ops)
    assert results[0].ok is False


async def test_the_dry_run_resolves_the_op_too(workspace):
    created = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    form_doc = await form_with_page(workspace)
    from backend.app.services.form_spec.service import DryRunRequest

    response = await container.form_spec_service().dry_run(
        workspace.id,
        form_doc.form_id,
        DryRunRequest(ops=[{"op": "insert_library_section", "pageId": "s1", "sectionId": created.id}], atomic=True),
        testUser,
    )
    assert response.applied and response.results[0].op == "insert_library_section"
    assert "Alpha" in str(response.form)


async def test_splice_fields_replaces_in_place_and_keeps_the_ids_it_is_given(workspace):
    _, form = await _doc_and_form(workspace)
    page = form.fields[0]
    page.properties.fields = [
        as_field(q("a", title="A")),
        as_field(q("b", title="B", logic=show_if(cond("a")))),
        as_field(q("c", title="C", logic=show_if(cond("b")))),
    ]
    op = SpliceFieldsOp.model_validate(
        {
            "op": "splice_fields",
            "pageId": "s1",
            "index": 1,
            "replaceIds": ["a", "b"],
            "fields": [q("a", title="A2"), q("n", title="New")],
        },
        context={EDITOR_CONTEXT: True},
    )
    result, results = apply_form_ops(form, [op], atomic=True)
    assert results[0].ok, results[0].message
    ids = [f.id for f in result.fields[0].properties.fields]
    # "a" came back where it was told to, "b" is gone and what read it lost the reference
    assert ids == ["c", "a", "n"]
    titles = [f.title for f in result.fields[0].properties.fields]
    assert "B" not in titles and "A2" in titles and "New" in titles
    c = next(f for f in result.fields[0].properties.fields if f.id == "c")
    assert c.properties.logic is None


async def test_splice_fields_refuses_a_used_id_and_leaves_the_form_alone(workspace):
    _, form = await _doc_and_form(workspace)
    before = form.model_dump()
    op = SpliceFieldsOp.model_validate(
        {"op": "splice_fields", "pageId": "s1", "fields": [q("intro", title="Dup")]},
        context={EDITOR_CONTEXT: True},
    )
    result, results = apply_form_ops(form, [op])
    assert not results[0].ok and "already used" in results[0].message
    assert [f.id for f in result.fields[0].properties.fields] == ["intro"]
    assert before["fields"][0]["properties"]["fields"][0]["id"] == "intro"
