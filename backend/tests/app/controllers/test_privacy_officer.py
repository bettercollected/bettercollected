"""The Privacy officer (docs/enterprise-access-model.md §2): runs deletion
requests and sees the data subjects, never their answers."""

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.standard_form_response import DeletionRequestStatus
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.controllers.test_form_ai_insights import _seed_form_and_responses

officer = User(id=str(PydanticObjectId()), sub="officer@example.com")
SECRET = "my landlord's name is Mallory"


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
async def requested(workspace, workspace_form):
    """A form with answered responses, one of them (with a secret answer)
    under a pending deletion request; the officer is a member."""
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=officer.id,
            roles=[WorkspaceRoles.PRIVACY_OFFICER],
        )
    )
    form_id = workspace_form.form_id
    await _seed_form_and_responses(workspace.id, form_id, allow=False)
    await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        form_id,
        StandardFormResponse(
            answers={"q-feedback": {"type": "text", "text": SECRET}},
        ),
        testUser2,
    )
    responses = container.form_response_repo()
    await responses.add_deletion_request(
        await responses.get_response(response.response_id), response.response_id
    )
    return {"ws": str(workspace.id), "form": form_id, "response": response.response_id}


ANSWER_WORDS = (SECRET, "Mallory", "invoice", "Onboarding", "Loved it")


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workspaces/{ws}/forms/{form}/submissions?request_for_deletion=true",
        "/api/v1/workspaces/{ws}/all-submissions?request_for_deletion=true",
        "/api/v1/workspaces/{ws}/responders",
    ],
)
async def test_what_a_privacy_officer_receives_has_no_answers(
    client: AsyncClient, requested, path
):
    response = await client.get(path.format(**requested), cookies=_cookies(officer))

    assert response.status_code == 200, response.text
    for word in ANSWER_WORDS:
        assert word not in response.text, (path, word)
    items = response.json()["items"]
    assert items, path
    for item in items:
        # identifiers, status and dates; never answers (decrypted or not)
        assert not item.get("answers"), (path, item)
        assert not item.get("internalAnswers"), (path, item)
    # the respondent's email is allowed (the doc's resolved question 2)
    assert testUser2.sub in response.text


async def test_a_privacy_officer_is_refused_the_answers(client: AsyncClient, requested):
    for path in (
        "/api/v1/workspaces/{ws}/forms/{form}/submissions",
        "/api/v1/workspaces/{ws}/forms/{form}/all-submissions",
        "/api/v1/workspaces/{ws}/submissions/{response}",
    ):
        refused = await client.get(path.format(**requested), cookies=_cookies(officer))
        assert refused.status_code == 403, path
        assert SECRET not in refused.text


async def test_a_privacy_officer_completes_a_deletion_request(
    client: AsyncClient, requested
):
    deleted = await client.delete(
        "/api/v1/workspaces/{ws}/forms/{form}/response/{response}".format(**requested),
        cookies=_cookies(officer),
    )

    assert deleted.status_code == 200, deleted.text
    responses = container.form_response_repo()
    assert await responses.get_response(requested["response"]) is None
    request = await responses.find_deletion_request_by_response_id(
        requested["response"]
    )
    assert request.status == DeletionRequestStatus.SUCCESS
    # done: a second delete of the same response is no longer a pending request
    again = await client.delete(
        "/api/v1/workspaces/{ws}/forms/{form}/response/{response}".format(**requested),
        cookies=_cookies(officer),
    )
    assert again.status_code == 403


async def test_a_privacy_officer_deletes_nothing_else(client: AsyncClient, requested):
    # a response nobody asked to delete
    other = await container.workspace_form_service().submit_response(
        PydanticObjectId(requested["ws"]),
        requested["form"],
        StandardFormResponse(answers={"q-feedback": {"type": "text", "text": "x"}}),
        testUser1,
    )

    refused = await client.delete(
        "/api/v1/workspaces/{ws}/forms/{form}/response/{response}".format(
            **{**requested, "response": other.response_id}
        ),
        cookies=_cookies(officer),
    )

    assert refused.status_code == 403
    assert await container.form_response_repo().get_response(other.response_id)
