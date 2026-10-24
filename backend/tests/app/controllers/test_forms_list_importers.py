"""The dashboard forms list and form search: who imported each form comes
from the auth service in one call that names each importer once, and every
form shows its own importer. The list's response counts treat a form linked
twice to the same workspace as that workspace's only form, in every store."""

from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.form_service import FormService
from tests.app.controllers.data import testUser, testUser1

OTHER_FORM_ID = "importers-other-form"


def _user_info(user, first_name):
    return {"_id": user.id, "first_name": first_name, "email": user.sub}


@pytest.fixture()
def auth_users():
    """The auth service's answer, the other importer listed first."""
    mock = AsyncMock(
        return_value={
            "users_info": [_user_info(testUser1, "Other"), _user_info(testUser, "Own")]
        }
    )
    with patch.object(FormService, "fetch_user_details", mock):
        yield mock


async def _own_forms(workspace, count):
    return [
        await container.workspace_form_service().create_form(
            workspace.id,
            StandardForm(title=f"importers own {n}", fields=[]),
            testUser,
        )
        for n in range(count)
    ]


async def _form_imported_by_other(workspace):
    """A form in ``workspace`` imported by another member (testUser1)."""
    await container.form_service().save_form(
        StandardForm(form_id=OTHER_FORM_ID, title="importers other", fields=[])
    )
    await container.workspace_form_repo().save_workspace_form(
        workspace_id=workspace.id,
        form_id=OTHER_FORM_ID,
        user_id=testUser1.id,
        workspace_form_settings=WorkspaceFormSettings(
            custom_url="importers-other", private=False
        ),
    )


def _asked_for(mock) -> list:
    (call,) = mock.await_args_list
    return list(call.kwargs["user_ids"])


async def test_the_list_asks_auth_for_each_importer_once(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    forms = await _own_forms(workspace, 3)
    await _form_imported_by_other(workspace)

    listed = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms", cookies=test_user_cookies
    )

    assert listed.status_code == 200, listed.text
    assert sorted(_asked_for(auth_users)) == sorted([testUser.id, testUser1.id])
    importers = {
        item["formId"]: item["importerDetails"] for item in listed.json()["items"]
    }
    for form in forms:
        assert importers[form.form_id]["id"] == testUser.id
        assert importers[form.form_id]["firstName"] == "Own"
    assert importers[OTHER_FORM_ID]["id"] == testUser1.id
    assert importers[OTHER_FORM_ID]["firstName"] == "Other"


async def test_search_shows_each_form_its_own_importer(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    forms = await _own_forms(workspace, 2)
    await _form_imported_by_other(workspace)

    found = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/search?query=importers",
        cookies=test_user_cookies,
    )

    assert found.status_code == 200, found.text
    assert sorted(_asked_for(auth_users)) == sorted([testUser.id, testUser1.id])
    importers = {item["formId"]: item["importerDetails"] for item in found.json()}
    assert set(importers) == {forms[0].form_id, forms[1].form_id, OTHER_FORM_ID}
    for form in forms:
        assert importers[form.form_id]["id"] == testUser.id
        assert importers[form.form_id]["firstName"] == "Own"
    assert importers[OTHER_FORM_ID]["id"] == testUser1.id
    assert importers[OTHER_FORM_ID]["firstName"] == "Other"


async def test_no_importer_no_auth_call(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    listed = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms", cookies=test_user_cookies
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    auth_users.assert_not_awaited()


async def test_a_duplicated_link_still_counts_the_workspaces_own_responses(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    """A form linked twice to one workspace is linked to that workspace only:
    a response stored before responses carried their workspace is its own.
    Postgres counts distinct workspaces; Mongo must too. The duplicate is
    written where it can exist, the Mongo store (Postgres keeps one link per
    workspace and form)."""
    (form,) = await _own_forms(workspace, 1)
    await container.form_response_repo().save(
        FormResponseDocument(
            form_id=form.form_id, response_id="importers-unstamped", answers={}
        )
    )
    if container.flags().writes_mongo("forms"):
        await WorkspaceFormDocument(
            id=PydanticObjectId(),
            workspace_id=workspace.id,
            form_id=form.form_id,
            user_id=testUser.id,
        ).insert()

    listed = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms", cookies=test_user_cookies
    )

    assert listed.status_code == 200, listed.text
    counts = [
        item["responses"]
        for item in listed.json()["items"]
        if item["formId"] == form.form_id
    ]
    assert counts and set(counts) == {1}
