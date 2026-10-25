"""The dashboard forms list and form search: who imported each form comes
from the auth service in one call that names each importer once, and every
form shows its own importer. Drafts and importer details (members' names and
emails) are for members who may read the workspace's forms only. The list's
response counts treat a form linked to one workspace only as that
workspace's form."""

from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.form_service import FormService
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1

OTHER_FORM_ID = "importers-other-form"
outsider = User(id=str(PydanticObjectId()), sub="importers-outsider@example.com")
disabled_admin = User(id=str(PydanticObjectId()), sub="importers-disabled@example.com")
viewer = User(id=str(PydanticObjectId()), sub="importers-viewer@example.com")


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def _member(workspace, user, role, disabled=False):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=[role],
            disabled=disabled,
        )
    )


def _search(workspace, published=False):
    return (
        f"/api/v1/workspaces/{workspace.id}/forms/search"
        f"?query=importers&published={str(published).lower()}"
    )


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


async def test_a_re_saved_link_still_counts_the_workspaces_own_responses(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    """A form whose link to the workspace is saved again is still linked to
    that workspace only (one link per workspace and form): a response stored
    before responses carried their workspace is its own."""
    (form,) = await _own_forms(workspace, 1)
    await container.form_response_repo().save(
        FormResponseDocument(
            form_id=form.form_id, response_id="importers-unstamped", answers={}
        )
    )
    await container.workspace_form_repo().save_workspace_form(
        workspace.id, form.form_id, testUser.id, WorkspaceFormSettings()
    )
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


@pytest.mark.parametrize(
    "who", ["outsider", "disabled member"], ids=["non-member", "member-no-form-read"]
)
async def test_draft_search_is_refused_without_form_read(
    client: AsyncClient, workspace, auth_users, who
):
    """A signed-in account that may not read the workspace's forms (no
    membership, or a disabled one, which grants nothing) gets 403 before any
    query: no draft titles, no importer details."""
    await _own_forms(workspace, 1)
    await _form_imported_by_other(workspace)
    user = outsider
    if who == "disabled member":
        user = disabled_admin
        await _member(workspace, user, WorkspaceRoles.ADMIN, disabled=True)

    found = await client.post(_search(workspace), cookies=_cookies(user))

    assert found.status_code == 403, found.text
    assert "importers" not in found.text
    auth_users.assert_not_awaited()


async def test_draft_search_for_a_member_with_form_read(
    client: AsyncClient, workspace, auth_users
):
    """A Viewer reads the workspace's forms: drafts with their importers."""
    (form,) = await _own_forms(workspace, 1)
    await _form_imported_by_other(workspace)
    await _member(workspace, viewer, WorkspaceRoles.VIEWER)

    found = await client.post(_search(workspace), cookies=_cookies(viewer))

    assert found.status_code == 200, found.text
    importers = {item["formId"]: item["importerDetails"] for item in found.json()}
    assert set(importers) == {form.form_id, OTHER_FORM_ID}
    assert importers[form.form_id]["id"] == testUser.id
    assert importers[OTHER_FORM_ID]["id"] == testUser1.id
    assert sorted(_asked_for(auth_users)) == sorted([testUser.id, testUser1.id])


@pytest.mark.parametrize("signed_in", [True, False], ids=["non-member", "anonymous"])
async def test_published_search_is_open_and_never_names_importers(
    client: AsyncClient, workspace, auth_users, signed_in
):
    """Published forms stay searchable by anyone, with no importer details
    and no call to the auth service, whoever searches."""
    forms = await _own_forms(workspace, 2)
    await container.workspace_form_service().publish_form(
        workspace.id, forms[0].form_id, testUser
    )

    found = await client.post(
        _search(workspace, published=True),
        cookies=_cookies(outsider) if signed_in else None,
    )

    assert found.status_code == 200, found.text
    assert [item["formId"] for item in found.json()] == [forms[0].form_id]
    assert all(item.get("importerDetails") is None for item in found.json())
    auth_users.assert_not_awaited()


async def test_published_search_by_staff_names_no_importers(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    (form,) = await _own_forms(workspace, 1)
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )

    found = await client.post(
        _search(workspace, published=True), cookies=test_user_cookies
    )

    assert found.status_code == 200, found.text
    assert [item["formId"] for item in found.json()] == [form.form_id]
    assert found.json()[0].get("importerDetails") is None
    auth_users.assert_not_awaited()


async def test_a_draft_read_by_a_non_member_names_no_importer(
    client: AsyncClient, workspace, auth_users
):
    """Reading one form as a signed-in non-member never carries its
    importer's details either."""
    (form,) = await _own_forms(workspace, 1)

    read = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=_cookies(outsider),
    )

    if read.status_code == 200:
        assert read.json().get("importerDetails") is None, read.json()
    auth_users.assert_not_awaited()


async def test_a_draft_read_by_staff_names_its_own_importer(
    client: AsyncClient, workspace, test_user_cookies, auth_users
):
    """The auth service lists another member first: the form still shows
    the member who imported it."""
    (form,) = await _own_forms(workspace, 1)

    read = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=test_user_cookies,
    )

    assert read.status_code == 200, read.text
    assert read.json()["importerDetails"]["id"] == testUser.id
    assert read.json()["importerDetails"]["firstName"] == "Own"
    assert _asked_for(auth_users) == [testUser.id]
