"""A respondent who submitted without sharing their address (the default) can
ask for deletion, and their portal's deletion requests list shows that request
and its status: it is matched by the same one-way identity hash the response
carries. Nobody else sees it, the address is never stored, and the submissions
list still does not link anonymous responses to the account."""

from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.utils.hash import hash_string
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser1, testUser2
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
