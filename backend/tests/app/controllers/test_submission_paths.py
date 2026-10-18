"""The flow view's insights read each submission's path through the pages
(``.../submission-paths``, response.read) and never the answers; the
decrypted bulk (``.../all-submissions`` and ``.../all-submissions/export``)
is an export (response.export)."""

import json
from types import SimpleNamespace

import pytest
from beanie import PydanticObjectId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.answer_validation import submission_path
from backend.app.services.form_response_service import FormResponseService
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser2

viewer = User(id=str(PydanticObjectId()), sub="paths-viewer@example.com")
reviewer = User(id=str(PydanticObjectId()), sub="paths-reviewer@example.com")
editor = User(id=str(PydanticObjectId()), sub="paths-editor@example.com")
officer = User(id=str(PydanticObjectId()), sub="paths-officer@example.com")
SECRET = "the attic key is under the blue pot"


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _jump(target="__SUBMIT__", ending_id=None, value="No", field="member"):
    jump = {
        "operator": "AND",
        "conditions": [
            {
                "fieldId": field,
                "fieldType": "yes_no",
                "comparison": "IS_EQUAL",
                "value": value,
            }
        ],
        "target": target,
    }
    if ending_id is not None:
        jump["endingId"] = ending_id
    return jump


def _form(pages, endings=None):
    body = {"title": "Paths", "builderVersion": "v2", "fields": pages}
    body["thankyouPage"] = endings or [
        {"id": "thanks", "name": "Thanks", "title": "Thank you"},
        {"id": "not-eligible", "name": "Not eligible", "title": "Sorry"},
    ]
    return _parse_form_body(json.dumps(body))


def _page(page_id, fields=(), jumps=None):
    properties = {"fields": list(fields)}
    if jumps is not None:
        properties["jumps"] = jumps
    return {"id": page_id, "type": "slide", "properties": properties}


MEMBER = {"id": "member", "type": "yes_no"}
WHY = {"id": "why", "type": "short_text"}
NO = {"member": {"type": "boolean", "boolean": False}}
YES = {"member": {"type": "boolean", "boolean": True}}


def _answers(answers):
    return StandardFormResponseCamelModel(answers=answers).answers


def _path(form, answers):
    steps, ended, ending_id = submission_path(form, _answers(answers))
    return steps, ended, ending_id


# ---------------------------------------------------------------------------
# The walk (twin of the webapp's submissionPath)
# ---------------------------------------------------------------------------


def test_a_linear_submission_goes_through_every_page():
    form = _form([_page("p1", [MEMBER]), _page("p2"), _page("p3")])
    assert _path(form, YES) == ([("p1", None), ("p2", None), ("p3", None)], True, None)


def test_a_jump_to_an_ending_ends_the_path_there():
    form = _form(
        [_page("p1", [MEMBER], [_jump(ending_id="not-eligible")]), _page("p2")]
    )
    assert _path(form, NO) == ([("p1", 0)], True, "not-eligible")
    assert _path(form, YES) == ([("p1", None), ("p2", None)], True, None)


def test_a_jump_to_a_page_resumes_the_linear_flow_from_there():
    form = _form([_page("a", [MEMBER], [_jump(target="c")]), _page("b"), _page("c")])
    assert _path(form, NO) == ([("a", 0), ("c", None)], True, None)


def test_a_jump_to_a_missing_page_is_not_taken():
    form = _form(
        [
            _page("a", [MEMBER], [_jump(target="gone"), _jump(target="c")]),
            _page("b"),
            _page("c"),
        ]
    )
    # the first rule matches but its page is gone: the second one decides
    assert _path(form, NO) == ([("a", 1), ("c", None)], True, None)


def test_rules_that_loop_stop_after_the_hop_cap_without_ending():
    form = _form(
        [_page("a", [MEMBER], [_jump(target="b")]), _page("b", [], [_jump(target="a")])]
    )
    steps, ended, ending_id = _path(form, NO)
    assert len(steps) == 2 * 2 + 2
    assert steps[:2] == [("a", 0), ("b", 0)]
    assert (ended, ending_id) == (False, None)


def test_a_form_without_pages_has_an_empty_ended_path():
    assert submission_path(None, {}) == ([], True, None)


def test_deletion_only_stubs_are_not_submissions():
    form = _form([_page("p1", [MEMBER])])
    stub = SimpleNamespace(answers=None, form_id="f")
    answered = SimpleNamespace(answers=_answers(YES), form_id="f")
    paths = FormResponseService._submission_paths(
        PydanticObjectId(), form, [stub, answered]
    )
    assert len(paths) == 1
    assert paths[0].steps[0].page_id == "p1"


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------


@pytest.fixture()
async def paths_form(workspace):
    """A published form with an ending jump, two submissions (one with a
    secret answer), and a Viewer, a Reviewer, an Editor and a Privacy
    officer in the workspace."""
    for user, role in (
        (viewer, WorkspaceRoles.VIEWER),
        (reviewer, WorkspaceRoles.REVIEWER),
        (editor, WorkspaceRoles.EDITOR),
        (officer, WorkspaceRoles.PRIVACY_OFFICER),
    ):
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(
                workspace_id=workspace.id, user_id=user.id, roles=[role]
            )
        )
    service = container.workspace_form_service()
    created = await service.create_form(
        workspace.id,
        _form(
            [
                _page("p1", [MEMBER], [_jump(ending_id="not-eligible")]),
                _page("p2", [WHY]),
            ]
        ),
        testUser,
    )
    await service.publish_form(workspace.id, created.form_id, testUser)
    for answers in (NO, {**YES, "why": {"type": "text", "text": SECRET}}):
        await service.submit_response(
            workspace.id,
            created.form_id,
            StandardFormResponseCamelModel(answers=answers),
            testUser2,
        )
    return f"/api/v1/workspaces/{workspace.id}/forms/{created.form_id}"


async def test_a_read_only_role_gets_paths_without_answers(
    client: AsyncClient, paths_form
):
    for user in (viewer, reviewer, editor, testUser):
        response = await client.get(
            f"{paths_form}/submission-paths", cookies=_cookies(user)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert sorted(body, key=lambda p: len(p["steps"])) == [
            {
                "steps": [{"pageId": "p1", "jump": 0}],
                "ended": True,
                "endingId": "not-eligible",
            },
            # None is left out: no jump (the linear "next"), the default ending
            {"steps": [{"pageId": "p1"}, {"pageId": "p2"}], "ended": True},
        ]
        # page ids, jump indexes and endings only: no answer values, no
        # respondent, no response ids or dates
        for word in (SECRET, "boolean", "why", "member", testUser2.sub):
            assert word not in response.text, word
        for path in body:
            assert set(path) <= {"steps", "ended", "endingId"}
            for step in path["steps"]:
                assert set(step) <= {"pageId", "jump"}


async def test_the_bulk_needs_the_export_permission(client: AsyncClient, paths_form):
    for route in ("all-submissions", "all-submissions/export"):
        for user in (viewer, reviewer, officer):
            refused = await client.get(f"{paths_form}/{route}", cookies=_cookies(user))
            assert refused.status_code == 403, (route, user.sub)
            assert SECRET not in refused.text
        for user in (editor, testUser):
            allowed = await client.get(f"{paths_form}/{route}", cookies=_cookies(user))
            assert allowed.status_code == 200, allowed.text
            assert len(allowed.json()) == 2
            assert SECRET in allowed.text


async def test_paths_need_response_read(client: AsyncClient, paths_form):
    refused = await client.get(
        f"{paths_form}/submission-paths", cookies=_cookies(officer)
    )
    assert refused.status_code == 403
