from typing import Coroutine, Any

import pytest
from aiohttp.test_utils import TestClient
from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel

from backend.app.container import container
from backend.app.models.dtos.workspace_member_dto import WorkspaceMemberDto
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import StandardForm
from tests.app.controllers.data import (
    user_info,
    testUser,
    formData,
    formData_2,
    invitation_request,
)


@pytest.fixture
def workspace_member_url(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    return f"/api/v1/workspaces/{workspace.id}/members"


@pytest.fixture
def workspace_invitation_url(workspace_member_url: str):
    return f"{workspace_member_url}/invitations"


async def create_invitation(
    workspace_id: PydanticObjectId, invitation: InvitationRequest
):
    return await container.workspace_invitation_repo().create_workspace_invitation(
        workspace_id, invitation
    )


class TestWorkspaceMember:
    def test_get_workspace_members(
        self,
        client: TestClient,
        workspace_member_url: str,
        test_user_cookies: dict[str, str],
        mock_get_user_info,
    ):
        expected_members_info = {
            "user_id": testUser.id,
            "email": user_info.get("users_info")[0].get("email"),
        }

        with mock_get_user_info:
            members = client.get(workspace_member_url, cookies=test_user_cookies)

        members_info = members.json()[0]
        expected_response = expected_members_info
        actual_response = {
            "user_id": members_info.get("id"),
            "email": members_info.get("email"),
        }
        assert actual_response == expected_response

    def test_unauthorized_client_get_workspace_members(
        self,
        client: TestClient,
        workspace_member_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        workspace_members = client.get(
            workspace_member_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = workspace_members.json()
        assert workspace_members.status_code == 403
        assert actual_response_message == expected_response_message

    def test_delete_workspace_member(
        self,
        client: TestClient,
        workspace_member_url: str,
        test_user_cookies: dict[str, str],
        mock_get_user_info,
    ):
        delete_url = f"{workspace_member_url}/{testUser.id}"

        with mock_get_user_info:
            delete_workspace_member = client.delete(
                delete_url, cookies=test_user_cookies
            )

        expected_response = {"message": "Deleted Successfully"}
        actual_response = delete_workspace_member.json()
        assert actual_response == expected_response

    async def test_delete_member_deletes_form_and_user(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, WorkspaceFormDocument],
        workspace_member_url: str,
        test_user_cookies: dict[str, str],
        mock_get_user_info,
    ):
        delete_url = f"{workspace_member_url}/{testUser.id}"
        await container.workspace_form_service().create_form(
            workspace.id, StandardForm(**formData_2), testUser
        )

        with mock_get_user_info:
            client.delete(delete_url, cookies=test_user_cookies)

        expected_form = await WorkspaceFormDocument.find_one(
            {"form_id": workspace_form.form_id, "workspace_id": workspace.id}
        )
        expected_user = await WorkspaceUserDocument.find_one(
            {"workspace_id": workspace.id, "user_id": PydanticObjectId(testUser.id)}
        )
        actual_user_and_form = None
        assert actual_user_and_form == expected_user == expected_form

    def test_unauthorized_client_delete_workspace_members(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_member_url: str,
    ):
        delete_url = f"{workspace_member_url}/{testUser.id}"

        delete_members = client.delete(delete_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = delete_members.json()
        assert delete_members.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_get_workspaces_invitations(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_invitation_url: str,
    ):
        await create_invitation(workspace.id, InvitationRequest(**invitation_request))

        invitations = client.get(workspace_invitation_url, cookies=test_user_cookies)

        expected_invitations_number = 1
        actual_invitations_number = invitations.json().get("total")
        expected_invited_email = invitation_request.get("email")
        actual_invited_email = invitations.json().get("items")[0].get("email")
        assert actual_invited_email == expected_invited_email
        assert actual_invitations_number == expected_invitations_number

    async def test_unauthorized_client_get_workspace_invitations(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_invitation_url: str,
    ):
        invitations = client.get(workspace_invitation_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = invitations.json()
        assert invitations.status_code == 403
        assert actual_response_message == expected_response_message
