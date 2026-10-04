"""Access decisions that pick a view rather than refuse (staff or public form,
the dashboard flag, the staff side of deletion requests and invitation
lookups), and the respondent paths, which never go through member
permissions."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.form_service import FormService
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser, testUser1, testUser2
from tests.app.services.test_internal_fields import NAME, REFERENCE, _form_payload

admin_user = User(id=str(PydanticObjectId()), sub="branches-admin@example.com")
disabled_admin = User(id=str(PydanticObjectId()), sub="branches-disabled@example.com")
invitee = User(id=str(PydanticObjectId()), sub="invitee@example.com")


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def user_details():
    """User details come from the auth service, outside the test."""
    with patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ):
        yield


@pytest.fixture()
async def form(workspace, user_details):
    for user, disabled in ((admin_user, False), (disabled_admin, True)):
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=user.id,
                roles=[WorkspaceRoles.ADMIN],
                disabled=disabled,
            )
        )
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**_form_payload()), testUser
    )
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    return form


async def _submit(workspace, form, user):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={NAME: {"field": {"id": NAME}, "type": "text", "text": "Ada"}}
        ),
        user,
    )


def _field_ids(form_json) -> list:
    ids = []
    for page in form_json.get("fields") or []:
        ids.append(page.get("id"))
        ids += [f.get("id") for f in (page.get("properties") or {}).get("fields") or []]
    return ids


async def _disable_workspace(workspace):
    workspace.disabled = True
    await container.workspace_repo().save(workspace)


@pytest.mark.parametrize("version", [False, True])
async def test_staff_see_the_staff_form_and_others_the_public_one(
    client: AsyncClient, workspace, form, version
):
    """get_form_by_id / get_form_by_version: has_permission(form.read)."""
    url = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}"
    url, params = (url + "/versions/1", {}) if version else (url, {"published": "true"})

    for user in (testUser, admin_user, invited_user):
        staff = await client.get(url, params=params, cookies=_cookies(user))
        assert staff.status_code == 200, staff.text
        assert REFERENCE in _field_ids(staff.json()), user.sub
    for user in (testUser1, testUser2, disabled_admin, None):
        cookies = _cookies(user) if user else None
        public = await client.get(url, params=params, cookies=cookies)
        assert public.status_code == 200, public.text
        assert REFERENCE not in _field_ids(public.json())


async def test_the_unpublished_listing_is_for_members(
    client: AsyncClient, workspace, form
):
    """get_forms_in_workspace: has_permission(form.read)."""
    url = f"/api/v1/workspaces/{workspace.id}/forms"
    for user in (testUser, admin_user, invited_user):
        listed = await client.get(url, cookies=_cookies(user))
        assert listed.status_code == 200, listed.text
        assert [f["formId"] for f in listed.json()["items"]] == [form.form_id]
    for user in (testUser1, disabled_admin):
        refused = await client.get(url, cookies=_cookies(user))
        assert refused.status_code == 403


async def test_a_disabled_workspace_keeps_its_owners_dashboard(
    client: AsyncClient, workspace, form
):
    """The owner of a downgraded workspace still reads its forms (staff view)
    and its responses; other members don't."""
    await _disable_workspace(workspace)
    base = f"/api/v1/workspaces/{workspace.id}/forms"

    listed = await client.get(base, cookies=_cookies(testUser))
    assert listed.status_code == 200, listed.text
    assert [f["formId"] for f in listed.json()["items"]] == [form.form_id]
    staff = await client.get(
        f"{base}/{form.form_id}",
        params={"published": "true"},
        cookies=_cookies(testUser),
    )
    assert REFERENCE in _field_ids(staff.json())

    for user in (admin_user, invited_user):
        assert (await client.get(base, cookies=_cookies(user))).status_code == 403
        public = await client.get(
            f"{base}/{form.form_id}",
            params={"published": "true"},
            cookies=_cookies(user),
        )
        assert REFERENCE not in _field_ids(public.json())


async def test_dashboard_access_is_for_members(client: AsyncClient, workspace):
    """get_workspace_by_query: dashboard_access = has_permission(form.read)."""
    for user, expected in (
        (testUser, True),
        (invited_user, True),
        (testUser1, None),
        (None, None),
    ):
        response = await client.get(
            "/api/v1/workspaces",
            params={"workspace_name": workspace.workspace_name},
            cookies=_cookies(user) if user else None,
        )
        assert response.status_code == 200, response.text
        assert response.json().get("dashboardAccess") is expected, user


async def test_staff_may_file_a_deletion_request_for_any_response(
    client: AsyncClient, workspace, form
):
    """The staff branch of request_for_response_deletion: privacy.manage
    (Owner, Admin, Privacy officer; an Editor no longer since step b)."""
    response = await _submit(workspace, form, testUser2)
    url = f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}"

    for user in (testUser1, disabled_admin, invited_user):
        refused = await client.delete(url, cookies=_cookies(user))
        assert refused.status_code == 403, user.sub
    filed = await client.delete(url, cookies=_cookies(admin_user))
    assert filed.status_code == 200, filed.text
    assert await container.form_response_repo().find_deletion_request_by_response_id(
        response.response_id
    )


async def test_an_invitation_is_read_by_who_manages_members_or_the_invitee(
    client: AsyncClient, workspace, form
):
    """get_workspace_invitation_by_token: has_permission(members.manage) or
    the invitee's own email."""
    invitation = (
        await container.workspace_invitation_repo().create_workspace_invitation(
            workspace_id=workspace.id,
            invitation=InvitationRequest(
                email=invitee.sub, role=WorkspaceRoles.COLLABORATOR
            ),
        )
    )
    url = (
        f"/api/v1/workspaces/{workspace.id}/members/invitations/"
        f"{invitation.invitation_token}"
    )
    for user in (testUser, admin_user, invitee):
        read = await client.get(url, cookies=_cookies(user))
        assert read.status_code == 200, (user.sub, read.text)
    for user in (invited_user, testUser1, disabled_admin):
        refused = await client.get(url, cookies=_cookies(user))
        assert refused.status_code == 403, user.sub


async def test_respondent_paths_need_no_membership(
    client: AsyncClient, workspace, form
):
    """A respondent who is not a member submits, lists their own submissions
    and asks for one to be deleted: by identity, never by permission."""
    cookies = _cookies(testUser2)
    submitted = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/response",
        data={
            "response": json.dumps(
                {
                    "answers": {
                        NAME: {"field": {"id": NAME}, "type": "text", "text": "Ada"}
                    }
                }
            )
        },
        cookies=cookies,
    )
    assert submitted.status_code == 200, submitted.text

    mine = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions", cookies=cookies
    )
    assert mine.status_code == 200, mine.text
    items = mine.json()["items"]
    assert len(items) == 1
    response_id = items[0]["responseId"]

    deletion = await client.delete(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response_id}",
        cookies=cookies,
    )
    assert deletion.status_code == 200, deletion.text
    # someone else's response stays out of reach
    other = await _submit(workspace, form, testUser1)
    refused = await client.delete(
        f"/api/v1/workspaces/{workspace.id}/submissions/{other.response_id}",
        cookies=cookies,
    )
    assert refused.status_code == 403
