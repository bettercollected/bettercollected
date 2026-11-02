"""Update from library: the diff of a copy against the latest version, which
question ids are kept, and the fragment that replaces the copy."""

import copy

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import EDITOR_CONTEXT, SpliceFieldsOp, apply_form_ops
from backend.app.services.reusable_sections import limits, refs
from backend.app.services.reusable_sections.service import (
    PlanRequestDto,
    SectionContentDto,
)
from tests.app.controllers.data import testUser
from tests.app.reusable_sections.helpers import (
    cond,
    form_with_page,
    make_section,
    q,
    show_if,
    validations,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(sections_on):
    pass


def service():
    return container.reusable_section_service()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def v1_fields():
    return [
        q("name", title="Name"),
        validations(q("age", "number", "Age", logic=show_if(cond("name"))), required=True),
        q("kind", "dropdown", "Kind", choices=[{"id": "k1", "value": "one"}]),
        q("notes", "long_text", "Notes"),
    ]


async def inserted(workspace, fields=None):
    """A section with a copy of it: (section, fragment, the copy's questions by title)."""
    section = await make_section(workspace, fields=fields or v1_fields(), containers=[])
    fragment = await service().instantiate(workspace.id, section.id, testUser)
    return section, fragment, {refs.plain_title(f): f for f in fragment.fields}


def by_key(plan):
    return {c.key: c for c in plan.changes}


async def next_version(workspace, section, fragment, edit):
    """Save a new version from the copy (what "Save a copy to the library" sends)."""
    fields = copy.deepcopy(fragment.fields)
    fields = edit(fields) or fields
    return await service().save_content(
        workspace.id, section.id, SectionContentDto(fields=fields, containers=[]), testUser
    )


def retitle(fields, title, new):
    for field in fields:
        if field["title"] == title:
            field["title"] = new


async def test_saving_a_copy_back_keeps_the_section_ids_of_the_questions_it_came_from(workspace):
    section, fragment, named = await inserted(workspace)
    v1 = await container.reusable_section_repo().get(workspace.id, section.id)
    v1_ids = {f["title"]: f["id"] for f in v1.fields}

    def edit(fields):
        retitle(fields, "Age", "Age in years")
        fields.append(q("brand-new", "email", "Email"))

    v2 = await next_version(workspace, section, fragment, edit)
    stored = await container.reusable_section_repo().get(workspace.id, section.id)
    ids = {f["title"]: f["id"] for f in stored.fields}
    assert ids["Name"] == v1_ids["Name"] and ids["Age in years"] == v1_ids["Age"]
    assert ids["Kind"] == v1_ids["Kind"] and ids["Notes"] == v1_ids["Notes"]
    assert ids["Email"] not in v1_ids.values()
    # the reference inside the copy still points at the same question
    age = next(f for f in stored.fields if f["id"] == v1_ids["Age"])
    assert age["logic"]["conditions"][0]["fieldId"] == v1_ids["Name"]
    # a marker never becomes content
    assert "library" not in str(stored.fields)
    assert v2.version == 2


async def test_a_marker_of_another_section_never_lends_its_key(workspace):
    one, fragment_one, _ = await inserted(workspace)
    other = await make_section(workspace, name="Other", fields=[q("x", title="X")], containers=[])
    fields = copy.deepcopy(fragment_one.fields)
    # these questions are copies of `one`; saved into `other` they are new questions
    await service().save_content(
        workspace.id, other.id, SectionContentDto(fields=fields, containers=[]), testUser
    )
    stored_other = await container.reusable_section_repo().get(workspace.id, other.id)
    stored_one = await container.reusable_section_repo().get(workspace.id, one.id)
    assert not {f["id"] for f in stored_other.fields} & {f["id"] for f in stored_one.fields}


async def test_the_diff_says_what_was_added_removed_and_changed_and_keeps_unchanged_ids(workspace):
    section, fragment, named = await inserted(workspace)

    def edit(fields):
        retitle(fields, "Age", "Age in years")
        fields[:] = [f for f in fields if f["title"] != "Name"]
        for field in fields:
            if field["title"] == "Kind":  # retyped
                field["type"] = "multiple_choice"
        fields.append(q("brand-new", "email", "Email"))

    await next_version(workspace, section, fragment, edit)
    plan = await service().update_plan(
        workspace.id,
        section.id,
        PlanRequestDto(instance=fragment.instance, fields=copy.deepcopy(fragment.fields)),
        testUser,
    )
    stored = await container.reusable_section_repo().get(workspace.id, section.id)
    key = {f["title"]: f["id"] for f in stored.fields}
    changes = by_key(plan)
    assert plan.version == 2 and plan.base_version == 1 and plan.base_known
    assert changes[key["Notes"]].status == "unchanged" and changes[key["Notes"]].what == []
    assert changes[key["Age in years"]].status == "changed" and "title" in changes[key["Age in years"]].what
    assert changes[key["Kind"]].status == "changed" and changes[key["Kind"]].what == ["type"]
    assert changes[key["Email"]].status == "added" and changes[key["Email"]].id is None
    removed = [c for c in plan.changes if c.status == "removed"]
    assert [c.title for c in removed] == ["Name"] and removed[0].id == named["Name"]["id"]
    # ids: unchanged and edited questions keep the form's id; a retyped one does not
    new = {f["title"]: f["id"] for f in plan.fields}
    assert new["Notes"] == named["Notes"]["id"]
    assert new["Age in years"] == named["Age"]["id"]
    assert new["Kind"] != named["Kind"]["id"]
    assert new["Email"] not in {f["id"] for f in fragment.fields}
    # the reference of Age to Name lost its target: it is dropped (Name is gone)
    age = next(f for f in plan.fields if f["title"] == "Age in years")
    assert age["properties"].get("logic") is None
    assert all(f["properties"]["library"]["version"] == 2 for f in plan.fields)
    assert all(f["properties"]["library"]["instance"] == fragment.instance for f in plan.fields)


async def test_the_plan_applied_keeps_unchanged_question_ids_in_the_form(workspace):
    section, fragment, named = await inserted(workspace)
    await next_version(workspace, section, fragment, lambda f: retitle(f, "Notes", "Remarks"))
    form_doc = await form_with_page(workspace)
    document = await container.form_service().get_form_document_by_id(form_doc.form_id)
    form = StandardForm(**document.model_dump())
    form, results = apply_form_ops(
        form,
        [
            SpliceFieldsOp.model_validate(
                {"op": "splice_fields", "pageId": "s1", "fields": fragment.fields},
                context={EDITOR_CONTEXT: True},
            )
        ],
        atomic=True,
    )
    assert all(r.ok for r in results)
    plan = await service().update_plan(
        workspace.id,
        section.id,
        PlanRequestDto(instance=fragment.instance, fields=copy.deepcopy(fragment.fields)),
        testUser,
    )
    page = form.fields[0].properties.fields
    replace = [f["id"] for f in fragment.fields]
    first = next(i for i, f in enumerate(page) if f.id == replace[0])
    form, results = apply_form_ops(
        form,
        [
            SpliceFieldsOp.model_validate(
                {
                    "op": "splice_fields",
                    "pageId": "s1",
                    "index": first,
                    "replaceIds": replace,
                    "fields": plan.fields,
                },
                context={EDITOR_CONTEXT: True},
            )
        ],
        atomic=True,
    )
    assert all(r.ok for r in results), [r.message for r in results]
    after = form.fields[0].properties.fields
    assert [f.id for f in after] == [f.id for f in page]  # same ids, same order
    assert next(f for f in after if f.id == named["Notes"]["id"]).title == "Remarks"
    assert all(f.properties.library.version == 2 for f in after if f.properties.library)


async def test_a_change_the_copys_creator_made_is_reported(workspace):
    section, fragment, named = await inserted(workspace)
    await next_version(workspace, section, fragment, lambda f: retitle(f, "Name", "Full name"))
    mine = copy.deepcopy(fragment.fields)
    retitle(mine, "Notes", "My own notes")  # edited in the form after the insert
    plan = await service().update_plan(
        workspace.id, section.id, PlanRequestDto(instance=fragment.instance, fields=mine), testUser
    )
    flags = {c.title: c.modified_in_copy for c in plan.changes if c.status != "removed"}
    assert flags["Full name"] is False
    notes = next(c for c in plan.changes if c.key and c.id == named["Notes"]["id"])
    assert notes.modified_in_copy is True


async def test_without_the_base_version_a_copys_own_changes_are_unknown(workspace):
    section, fragment, _ = await inserted(workspace)
    for n in range(limits.VERSIONS_KEPT + 1):
        await next_version(workspace, section, fragment, lambda f, n=n: retitle(f, "Notes", f"Notes {n}"))
        fragment_notes = [f for f in fragment.fields if f["title"].startswith("Notes")]
        for f in fragment_notes:
            f["title"] = f"Notes {n}"
    plan = await service().update_plan(
        workspace.id,
        section.id,
        PlanRequestDto(instance=fragment.instance, fields=copy.deepcopy(fragment.fields)),
        testUser,
    )
    assert plan.base_version == 1 and plan.base_known is False
    assert not any(c.modified_in_copy for c in plan.changes)


async def test_questions_that_are_not_one_copy_of_the_section_are_refused(workspace):
    section, fragment, _ = await inserted(workspace)
    other = await make_section(workspace, name="Other", fields=[q("x", title="X")], containers=[])
    foreign = await service().instantiate(workspace.id, other.id, testUser)
    plain = [q("p", title="Hand made")]
    for fields, code in (
        (plain, "not_a_copy"),
        (foreign.fields, "not_a_copy"),
        (fragment.fields + foreign.fields, "not_a_copy"),
    ):
        error = await refused(
            service().update_plan(
                workspace.id,
                section.id,
                PlanRequestDto(instance=fragment.instance, fields=copy.deepcopy(fields)),
                testUser,
            )
        )
        assert error.status_code == 422 and error.content["code"] == code
    twice = copy.deepcopy(fragment.fields)
    twin = copy.deepcopy(twice[0])
    twin["id"] = "another-form-id"
    twice.append(twin)
    error = await refused(
        service().update_plan(
            workspace.id, section.id, PlanRequestDto(instance=fragment.instance, fields=twice), testUser
        )
    )
    assert error.content["code"] == "copy_ambiguous"


async def test_a_duplicated_page_does_not_claim_the_copy_twice(workspace):
    section, fragment, _ = await inserted(workspace)
    form_doc = await form_with_page(workspace)
    document = await container.form_service().get_form_document_by_id(form_doc.form_id)
    form = StandardForm(**document.model_dump())
    form, _ = apply_form_ops(
        form,
        [
            SpliceFieldsOp.model_validate(
                {"op": "splice_fields", "pageId": "s1", "fields": fragment.fields},
                context={EDITOR_CONTEXT: True},
            )
        ],
        atomic=True,
    )
    from backend.app.services.ai.ops import parse_ops

    form, results = apply_form_ops(form, parse_ops([{"op": "duplicate_page", "pageId": "s1"}]))
    assert results[0].ok
    clone = form.fields[1].properties.fields
    assert all(f.properties is None or f.properties.library is None for f in clone)
    assert any(f.properties.library for f in form.fields[0].properties.fields)


# ------------------------------------------------ rules and the shape of an answer


async def _plan_of(workspace, section, fragment):
    return await service().update_plan(
        workspace.id,
        section.id,
        PlanRequestDto(instance=fragment.instance, fields=copy.deepcopy(fragment.fields)),
        testUser,
    )


async def test_a_section_with_rules_is_up_to_date_when_nothing_changed(workspace):
    from tests.app.reusable_sections.helpers import applicant_fields

    section, fragment, _ = await inserted(workspace, fields=applicant_fields())
    plan = await _plan_of(workspace, section, fragment)
    # the copy's rules have ids of their own; they are not a change
    assert [c.status for c in plan.changes] == ["unchanged"] * len(plan.changes)
    assert not any(c.modified_in_copy for c in plan.changes)
    assert plan.base_known


async def test_a_changed_rule_is_a_change_and_an_untouched_one_next_to_it_is_not(workspace):
    from tests.app.reusable_sections.helpers import applicant_fields

    section, fragment, named = await inserted(workspace, fields=applicant_fields())

    def edit(fields):
        for field in fields:
            if field["title"] == "Limit":
                field["properties"]["rules"][0]["then"]["title"] = "Another title"

    await next_version(workspace, section, fragment, edit)
    plan = await _plan_of(workspace, section, fragment)
    stored = await container.reusable_section_repo().get(workspace.id, section.id)
    key = {refs.plain_title(f): f["id"] for f in stored.fields}
    changes = by_key(plan)
    assert changes[key["Limit"]].status == "changed" and changes[key["Limit"]].what == ["rules"]
    assert changes[key["Age"]].status == "unchanged"
    assert changes[key["Limit"]].modified_in_copy is False


async def test_section_rules_have_ids_of_their_own_not_a_forms(workspace):
    from tests.app.reusable_sections.helpers import applicant_fields

    section, fragment, _ = await inserted(workspace, fields=applicant_fields())
    stored = await container.reusable_section_repo().get(workspace.id, section.id)
    saved = [r["id"] for f in stored.fields for r in f.get("rules") or []]
    assert saved and not {"r1", "r2"} & set(saved)


@pytest.mark.parametrize(
    "make_old,make_new",
    [
        (
            lambda: q("pick", "multiple_choice", "Pick", choices=[{"id": "c1", "value": "a"}], allowMultipleSelection=False),
            lambda: q("pick", "multiple_choice", "Pick", choices=[{"id": "c1", "value": "a"}], allowMultipleSelection=True),
        ),
        (
            lambda: q("pick", "dropdown", "Pick", choices=[{"id": "c1", "value": "a"}]),
            lambda: q("pick", "dropdown", "Pick", choices=[{"id": "c1", "value": "a"}], allowOtherChoice=True),
        ),
        (
            lambda: q("grp", "group", "People", fields=[q("who", title="Who")]),
            lambda: q("grp", "group", "People", fields=[q("who", title="Who")], repeat={"minItems": 1, "maxItems": 3}),
        ),
    ],
)
async def test_a_question_whose_answer_changes_shape_gets_a_new_id_though_its_type_is_the_same(workspace, make_old, make_new):
    section, fragment, named = await inserted(workspace, fields=[make_old(), q("keep", title="Keep")])

    def edit(fields):
        fields[0] = make_new() | {"properties": {**make_new()["properties"], "library": fragment.fields[0]["properties"]["library"]}}

    await next_version(workspace, section, fragment, edit)
    plan = await _plan_of(workspace, section, fragment)
    top = [c for c in plan.changes if c.title in ("Pick", "People")][0]
    assert top.status == "changed" and top.what == ["type"]
    new = {f["title"]: f["id"] for f in plan.fields}
    old_id = {f["title"]: f["id"] for f in fragment.fields}
    title = "Pick" if "Pick" in new else "People"
    assert new[title] != old_id[title]
    # the question that is the same keeps its id
    assert new["Keep"] == old_id["Keep"]
