"""A respondent who submitted without sharing their address (the default) can
ask for deletion, and their portal's deletion requests list shows that request
and its status: it is matched by the same one-way identity hash the response
carries. Nobody else sees it, the address is never stored, and the submissions
list still does not link anonymous responses to the account."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.utils.hash import hash_string
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.controllers.test_responses_per_workspace import (  # noqa: F401
    FORM_ID,
    RESPONDENT,
    _converted,
    _no_auth_service,
)
from tests.app.response_helpers import deletion_request_of


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


async def _submit(workspace, form, user, anonymize: bool):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=anonymize),
        user,
    )


async def _listed(client: AsyncClient, workspace, user, request_for_deletion=True):
    """The response ids on ``user``'s own portal list."""
    listed = await client.get(
        f"{_url(workspace)}/submissions",
        params={"request_for_deletion": request_for_deletion},
        cookies=_cookies(user),
    )
    assert listed.status_code == 200, listed.text
    return [item["responseId"] for item in listed.json()["items"]]


async def test_a_request_filed_without_sharing_the_address_is_listed_to_its_respondent(
    client: AsyncClient, workspace, published_form
):
    response = await _submit(workspace, published_form, testUser1, anonymize=True)
    response_id = str(response.response_id)

    filed = await client.delete(
        f"{_url(workspace)}/submissions/{response_id}", cookies=_cookies(testUser1)
    )
    assert filed.status_code == 200, filed.text

    # the respondent sees their request, with its status
    listed = await client.get(
        f"{_url(workspace)}/submissions",
        params={"request_for_deletion": True},
        cookies=_cookies(testUser1),
    )
    assert listed.status_code == 200, listed.text
    (item,) = listed.json()["items"]
    assert item["responseId"] == response_id
    assert item["status"] == "pending"

    # another respondent does not
    assert await _listed(client, workspace, testUser2) == []

    # the request holds no address, only the hash
    request = await deletion_request_of(
        workspace.id, published_form.form_id, response_id
    )
    assert request.dataOwnerIdentifier is None
    assert request.anonymous_identity == hash_string(testUser1.sub)
    assert testUser1.sub not in request.model_dump_json()

    # and the submissions list still keeps the anonymous response off the account
    assert response_id not in await _listed(
        client, workspace, testUser1, request_for_deletion=False
    )


async def test_requests_with_and_without_the_address_are_both_listed(
    client: AsyncClient, workspace, published_form
):
    shared = await _submit(workspace, published_form, testUser1, anonymize=False)
    unshared = await _submit(workspace, published_form, testUser1, anonymize=True)
    other = await _submit(workspace, published_form, testUser2, anonymize=True)
    for response, user in (
        (shared, testUser1),
        (unshared, testUser1),
        (other, testUser2),
    ):
        filed = await client.delete(
            f"{_url(workspace)}/submissions/{response.response_id}",
            cookies=_cookies(user),
        )
        assert filed.status_code == 200, filed.text

    assert sorted(await _listed(client, workspace, testUser1)) == sorted(
        [str(shared.response_id), str(unshared.response_id)]
    )
    assert await _listed(client, workspace, testUser2) == [str(other.response_id)]


# -- per workspace (#768) ------------------------------------------------------
# A provider form linked to workspaces A and B: each import holds its own copy
# of the respondent's response. A request filed in A shows in A's list only,
# whether the respondent is matched by address or by the identity hash.


async def _import_owned_by(workspace, user, slug, identity: str):
    converted = _converted(["r1"])
    if identity == "hash":
        converted["responses"][0]["dataOwnerIdentifier"] = None
        converted["responses"][0]["anonymous_identity"] = hash_string(RESPONDENT.sub)
    await container.form_import_service().save_converted_form_and_responses(
        converted, None, workspace_id=workspace.id
    )
    await container.workspace_form_repo().save_workspace_form(
        workspace_id=workspace.id,
        form_id=FORM_ID,
        user_id=user.id,
        workspace_form_settings=WorkspaceFormSettings(
            custom_url=slug, provider="google", private=False
        ),
    )


@pytest.mark.parametrize("identity", ["address", "hash"])
async def test_a_request_filed_in_one_workspace_is_listed_there_only(
    client: AsyncClient, workspace, workspace_1, identity
):
    a, b = workspace, workspace_1
    await _import_owned_by(a, testUser, "shared-a", identity)
    await _import_owned_by(b, testUser1, "shared-b", identity)

    filed = await client.delete(
        f"{_url(a)}/submissions/r1", cookies=_cookies(RESPONDENT)
    )
    assert filed.status_code == 200, filed.text

    listed_a = await client.get(
        f"{_url(a)}/submissions",
        params={"request_for_deletion": True},
        cookies=_cookies(RESPONDENT),
    )
    assert listed_a.status_code == 200, listed_a.text
    (item,) = listed_a.json()["items"]
    assert item["responseId"] == "r1"
    assert item["submissionUuid"] == "uuid-r1"

    assert await _listed(client, b, RESPONDENT) == []
