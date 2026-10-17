"""Several endings chosen by page jumps: ending ids derived on read, the
ending ops (add / update / remove, refs, set_page_jumps), the respondent's
path (an ending jump ends it like "submit", and the reached ending is
recorded), the publish check and the spec checks."""

import json

import pytest

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import project_form
from backend.app.services.answer_validation import (
    reached_ending_id,
    validate_answers,
    visited_slides,
)
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.publish_checks import (
    MISSING_ENDING,
    ensure_publishable,
    publish_problems,
)
from tests.app.controllers.data import testUser


def _eligible_jump(ending_id=None, value="No"):
    jump = {
        "operator": "AND",
        "conditions": [
            {
                "fieldId": "member",
                "fieldType": "yes_no",
                "comparison": "IS_EQUAL",
                "value": value,
            }
        ],
        "target": "__SUBMIT__",
    }
    if ending_id is not None:
        jump["endingId"] = ending_id
    return jump


def _pages(jumps):
    return [
        {
            "id": "p1",
            "type": "slide",
            "properties": {
                "fields": [{"id": "member", "type": "yes_no"}],
                "jumps": jumps,
            },
        },
        {
            "id": "p2",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "why", "type": "short_text", "validations": {"required": True}}
                ]
            },
        },
    ]


def _form(jumps, endings=None):
    body = {"title": "Endings", "builderVersion": "v2", "fields": _pages(jumps)}
    body["thankyouPage"] = (
        endings
        if endings is not None
        else [
            {"id": "thanks", "name": "Thanks", "title": "Thank you"},
            {"id": "not-eligible", "name": "Not eligible", "title": "Sorry"},
        ]
    )
    return _parse_form_body(json.dumps(body))


def _answers(answers):
    return StandardFormResponseCamelModel(answers=answers).answers


NO = {"member": {"type": "boolean", "boolean": False}}
YES = {"member": {"type": "boolean", "boolean": True}}


# ---------------------------------------------------------------------------
# Stored model and builder body
# ---------------------------------------------------------------------------


def test_the_builder_body_keeps_ending_ids_names_and_jump_endings():
    form = _form([_eligible_jump("not-eligible")])
    assert [e.id for e in form.thankyou_page] == ["thanks", "not-eligible"]
    assert form.thankyou_page[1].name == "Not eligible"
    assert form.fields[0].properties.jumps[0].ending_id == "not-eligible"
    # and the builder reads them back in camelCase
    out = FormDtoCamelModel(**form.model_dump(mode="json")).model_dump(by_alias=True)
    assert out["fields"][0]["properties"]["jumps"][0]["endingId"] == "not-eligible"
    assert out["thankyouPage"][1]["id"] == "not-eligible"


def test_endings_stored_without_ids_get_derived_ones():
    form = _form([], endings=[{"title": "A"}, {"title": "B"}])
    assert [e.id for e in form.thankyou_page] == ["ending-1", "ending-2"]


# ---------------------------------------------------------------------------
# Respondent path
# ---------------------------------------------------------------------------


def test_an_ending_jump_ends_the_path_like_submit():
    form = _form([_eligible_jump("not-eligible")])
    assert [s.id for s in visited_slides(form.fields, _answers(NO))] == ["p1"]
    # the required question on the skipped page is not asked
    assert validate_answers(form, _answers(NO)) == []
    assert [s.id for s in visited_slides(form.fields, _answers(YES))] == ["p1", "p2"]
    assert [p.key for p in validate_answers(form, _answers(YES))] == ["why"]


def test_the_reached_ending_is_the_jump_s_else_the_default():
    form = _form([_eligible_jump("not-eligible")])
    assert reached_ending_id(form, _answers(NO)) == "not-eligible"
    answers = {**YES, "why": {"type": "text", "text": "x"}}
    assert reached_ending_id(form, _answers(answers)) == "thanks"
    # a plain submit jump shows the default ending; isDefault picks it
    form = _form(
        [_eligible_jump()],
        endings=[{"id": "a"}, {"id": "b", "isDefault": True}],
    )
    assert reached_ending_id(form, _answers(NO)) == "b"
    # a jump to an ending that is gone shows the default ending
    form = _form([_eligible_jump("gone")])
    assert reached_ending_id(form, _answers(NO)) == "thanks"
    # no endings at all
    assert reached_ending_id(_form([], endings=[]), _answers(NO)) is None


async def _published(workspace, form):
    service = container.workspace_form_service()
    created = await service.create_form(workspace.id, form, testUser)
    await service.publish_form(workspace.id, created.form_id, testUser)
    return created


@pytest.mark.asyncio
async def test_the_submission_records_the_ending_from_the_answers(workspace):
    created = await _published(workspace, _form([_eligible_jump("not-eligible")]))
    service = container.workspace_form_service()
    # what the request claims is ignored: the server replays the path
    stored = await service.submit_response(
        workspace.id,
        created.form_id,
        StandardFormResponseCamelModel(answers=NO, ending_id="thanks"),
        testUser,
    )
    assert stored.ending_id == "not-eligible"
    stored = await service.submit_response(
        workspace.id,
        created.form_id,
        StandardFormResponseCamelModel(
            answers={**YES, "why": {"type": "text", "text": "x"}}
        ),
        testUser,
    )
    assert stored.ending_id == "thanks"


# ---------------------------------------------------------------------------
# Publish check
# ---------------------------------------------------------------------------


def test_a_jump_to_a_missing_ending_blocks_publishing():
    assert publish_problems(_form([_eligible_jump("not-eligible")])) == []
    form = _form([_eligible_jump("gone")])
    problems = publish_problems(form)
    assert [(p["code"], p["fieldId"]) for p in problems] == [(MISSING_ENDING, "p1")]
    with pytest.raises(HTTPException) as error:
        ensure_publishable(form, 1)
    assert error.value.status_code == 422
    # dict forms (camelCase jumps, endings without ids) are checked the same way
    raw = {
        "fields": [{"id": "p1", "properties": {"jumps": [{"endingId": "ending-2"}]}}],
        "thankyou_page": [{}, {}],
    }
    assert publish_problems(raw) == []
    raw["thankyou_page"] = [{}]
    assert [p["code"] for p in publish_problems(raw)] == [MISSING_ENDING]


@pytest.mark.asyncio
async def test_publishing_a_form_with_a_missing_ending_is_refused(workspace):
    service = container.workspace_form_service()
    created = await service.create_form(
        workspace.id, _form([_eligible_jump("gone")]), testUser
    )
    with pytest.raises(HTTPException) as error:
        await service.publish_form(workspace.id, created.form_id, testUser)
    assert error.value.status_code == 422
    assert error.value.content["problems"][0]["code"] == MISSING_ENDING


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------


def _apply(form, ops, **kwargs):
    return apply_form_ops(form, parse_ops(ops), **kwargs)


def test_add_ending_with_a_ref_and_jump_to_it():
    form = _form([], endings=[{"title": "Thanks"}])
    new, results = _apply(
        form,
        [
            {"op": "add_ending", "ref": "no", "name": " Not eligible ", "title": "Sorry"},
            {
                "op": "set_page_jumps",
                "pageId": "p1",
                "jumps": [_eligible_jump("$ref:no")],
            },
        ],
        atomic=True,
    )
    assert all(r.ok for r in results), results
    created = results[0].created_id
    assert [e.id for e in new.thankyou_page] == ["ending-1", created]
    assert new.thankyou_page[1].name == "Not eligible"
    assert new.fields[0].properties.jumps[0].ending_id == created
    assert reached_ending_id(new, _answers(NO)) == created
    # the original is untouched
    assert len(form.thankyou_page) == 1


def test_update_ending_patches_and_moves_the_default():
    form = _form([])
    new, results = _apply(
        form,
        [
            {
                "op": "update_ending",
                "endingId": "not-eligible",
                "patch": {
                    "name": "Rejected",
                    "message": "We cannot help you.",
                    "buttonLink": "https://example.org/help",
                    "isDefault": True,
                },
            },
            {"op": "update_ending", "endingId": "thanks", "patch": {"title": ""}},
        ],
    )
    assert all(r.ok for r in results), results
    second = new.thankyou_page[1]
    assert (second.name, second.message, second.buttonLink) == (
        "Rejected",
        "We cannot help you.",
        "https://example.org/help",
    )
    assert second.isDefault is True and new.thankyou_page[0].isDefault is None
    assert new.thankyou_page[0].title is None
    # making another one the default unmarks this one
    new, _ = _apply(
        new,
        [{"op": "update_ending", "endingId": "thanks", "patch": {"isDefault": True}}],
    )
    assert [e.isDefault for e in new.thankyou_page] == [True, None]


def test_ending_ops_refuse_bad_values_alone():
    form = _form([])
    new, results = _apply(
        form,
        [
            {"op": "update_ending", "endingId": "nope", "patch": {"title": "x"}},
            {
                "op": "update_ending",
                "endingId": "thanks",
                "patch": {"buttonLink": "javascript:alert(1)"},
            },
            {"op": "update_ending", "endingId": "thanks", "patch": {"name": "x" * 61}},
            {"op": "add_ending", "title": "Fine"},
        ],
    )
    assert [r.ok for r in results] == [False, False, False, True]
    assert "not found" in results[0].message
    assert len(new.thankyou_page) == 3


def test_set_page_jumps_checks_the_ending():
    form = _form([])
    jump_to_page = {**_eligible_jump("thanks"), "target": "p2"}
    _, results = _apply(
        form,
        [
            {"op": "set_page_jumps", "pageId": "p1", "jumps": [_eligible_jump("nope")]},
            {"op": "set_page_jumps", "pageId": "p1", "jumps": [jump_to_page]},
        ],
    )
    assert [r.ok for r in results] == [False, False]
    assert "not found" in results[0].message
    assert "__SUBMIT__" in results[1].message


def test_remove_ending_falls_back_to_the_default_for_its_jumps():
    form = _form([_eligible_jump("not-eligible"), _eligible_jump("thanks", "Yes")])
    new, results = _apply(form, [{"op": "remove_ending", "endingId": "not-eligible"}])
    assert results[0].ok, results
    assert "1 jump(s)" in results[0].message
    assert [e.id for e in new.thankyou_page] == ["thanks"]
    jumps = new.fields[0].properties.jumps
    # the jump still submits; it now shows the default ending
    assert [(j.target, j.ending_id) for j in jumps] == [
        ("__SUBMIT__", None),
        ("__SUBMIT__", "thanks"),
    ]
    # the last ending stays
    _, results = _apply(new, [{"op": "remove_ending", "endingId": "thanks"}])
    assert not results[0].ok
    assert "at least one ending" in results[0].message


def test_the_ai_snapshot_lists_endings_and_jump_endings():
    snapshot = json.loads(project_form(_form([_eligible_jump("not-eligible")])))
    assert snapshot["endings"] == [
        {"endingId": "thanks", "name": "Thanks", "title": "Thank you", "isDefault": True},
        {"endingId": "not-eligible", "name": "Not eligible", "title": "Sorry"},
    ]
    assert snapshot["pages"][0]["jumps"][0]["endingId"] == "not-eligible"


# ---------------------------------------------------------------------------
# Spec documents
# ---------------------------------------------------------------------------


def _spec(jumps, endings):
    return {
        "specVersion": "1",
        "title": "Endings",
        "pages": [
            {
                "id": "p1",
                "jumps": jumps,
                "fields": [{"id": "member", "type": "yes_no", "title": "Member?"}],
            }
        ],
        "endings": endings,
    }


def _errors(document):
    return [(e["path"], e["message"]) for e in check_spec_document(document)["errors"]]


def test_a_spec_may_choose_an_ending_by_id_or_derived_id():
    assert _errors(_spec([_eligible_jump("no")], [{"title": "A"}, {"id": "no"}])) == []
    # an ending left without an id gets "ending-<n>", which jumps may name
    assert _errors(_spec([_eligible_jump("ending-1")], [{"title": "A"}])) == []


def test_spec_ending_problems_are_errors_with_paths():
    errors = _errors(
        _spec(
            [
                _eligible_jump("gone"),
                {**_eligible_jump("a"), "target": "p1"},
            ],
            [
                {"id": "a", "isDefault": True},
                {"id": "a", "isDefault": True},
            ],
        )
    )
    paths = [path for path, _ in errors]
    assert "/endings/1/id" in paths
    assert "/endings/1/isDefault" in paths
    assert "/pages/0/jumps/0/endingId" in paths
    assert "/pages/0/jumps/1/endingId" in paths
    # the missing ending is not also repeated as a publish warning
    result = check_spec_document(_spec([_eligible_jump("gone")], [{"id": "a"}]))
    assert not any("ending" in w["message"] for w in result["warnings"])
