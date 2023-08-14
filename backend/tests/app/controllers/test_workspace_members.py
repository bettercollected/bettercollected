import secrets
from typing import Coroutine, Any

import pytest
from aiohttp.test_utils import TestClient
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND
from common.models.standard_form import StandardForm
from tests.app.controllers.data import (
    user_info,
    testUser,
    formData_2,
    invitation_request,
)


@pytest.fixture
def workspace_member_url(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    return f"/api/v1/workspaces/{workspace.id}/members"


@pytest.fixture
def workspace_invitation_url(workspace_member_url: str):
    return f"{workspace_member_url}/invitations"


@pytest.fixture()
async def invitation_by_token_url(
    workspace_invitation_url: str, workspace: Coroutine[Any, Any, WorkspaceDocument]
):
    invitation = await create_invitation(
        workspace.id, InvitationRequest(**invitation_request)
    )
    return f"{workspace_invitation_url}/{invitation.invitation_token}"


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

    def test_unauthorized_client_get_workspace_members_fails(
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

    def test_unauthorized_client_delete_workspace_members_fails(
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

    async def test_unauthorized_client_get_workspace_invitations_fails(
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

    def test_create_workspace_invitation_by_admin(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_invitation_url: str,
        mock_create_invitation_request,
    ):
        invitation = {
            "email": invitation_request.get("email"),
            "workspace_id": f"{workspace.id}",
        }

        with mock_create_invitation_request:
            created_invitation = client.post(
                workspace_invitation_url,
                cookies=test_user_cookies,
                json=invitation_request,
            )

        response = created_invitation.json()
        expected_invitation = invitation
        actual_invitation = {
            "email": response.get("email"),
            "workspace_id": response.get("workspace_id"),
        }
        assert actual_invitation == expected_invitation

    async def test_create_workspace_invitation_by_collaborator_fails(
        self,
        client: TestClient,
        test_invited_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_invitation_url: str,
        mock_create_invitation_request,
    ):
        invitation = {
            "email": invitation_request.get("email"),
            "workspace_id": f"{workspace.id}",
        }

        with mock_create_invitation_request:
            created_invitation = client.post(
                workspace_invitation_url,
                cookies=test_invited_user_cookies,
                json=invitation_request,
            )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = created_invitation.json()
        assert created_invitation.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_unauthorized_client_create_workspace_invitation_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_invitation_url: str,
    ):
        created_invitation = client.get(
            workspace_invitation_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = created_invitation.json()
        assert created_invitation.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_get_invitation_by_token_for_admin(
        self,
        client: TestClient,
        invitation_by_token_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        invitation_by_token = client.get(
            invitation_by_token_url, cookies=test_user_cookies
        )

        response = invitation_by_token.json()
        expected_response = {
            "email": invitation_request.get("email"),
            "workspaceId": f"{workspace.id}",
        }
        actual_response = {
            "email": response.get("email"),
            "workspaceId": response.get("workspaceId"),
        }
        assert actual_response == expected_response

    async def test_get_invitation_by_token_for_invited_user(
        self,
        client: TestClient,
        invitation_by_token_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_invited_user_cookies: dict[str, str],
    ):
        invitation_by_token = client.get(
            invitation_by_token_url, cookies=test_invited_user_cookies
        )

        response = invitation_by_token.json()
        expected_response = {
            "email": invitation_request.get("email"),
            "workspaceId": f"{workspace.id}",
        }
        actual_response = {
            "email": response.get("email"),
            "workspaceId": response.get("workspaceId"),
        }
        assert actual_response == expected_response

    async def test_get_invitation_by_token_for_invited_user_without_pending_status_fails(
        self,
        client: TestClient,
        workspace_invitation_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_invited_user_cookies: dict[str, str],
    ):
        invitation = await WorkspaceUserInvitesDocument(
            workspace_id=workspace.id,
            email="invited_daemon@gmail.com",
            invitation_status="REMOVED",
            invitation_token=secrets.token_hex(16),
        ).save()
        invitation_by_token_url = (
            f"{workspace_invitation_url}/{invitation.invitation_token}"
        )

        invitation_by_token = client.get(
            invitation_by_token_url, cookies=test_invited_user_cookies
        )

        expected_response = "This operation is no longer valid"
        actual_response = invitation_by_token.json()
        assert actual_response == expected_response
        assert invitation_by_token.status_code == 410

    async def test_get_invitation_by_expired_token_for_invited_user_fails(
        self,
        client: TestClient,
        workspace_invitation_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_invited_user_cookies: dict[str, str],
    ):
        invitation = await WorkspaceUserInvitesDocument(
            workspace_id=workspace.id,
            email="invited_daemon@gmail.com",
            expiry=0,
            invitation_token=secrets.token_hex(16),
        ).save()
        invitation_by_token_url = (
            f"{workspace_invitation_url}/{invitation.invitation_token}"
        )

        invitation_by_token = client.get(
            invitation_by_token_url, cookies=test_invited_user_cookies
        )

        expected_response = "This operation is no longer valid"
        actual_response = invitation_by_token.json()
        assert actual_response == expected_response
        assert invitation_by_token.status_code == 410

    async def test_unauthorized_client_get_workspace_invitation_by_token_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies_1: dict[str, str],
        workspace_invitation_url: str,
    ):
        invitation = await create_invitation(
            workspace.id, InvitationRequest(**invitation_request)
        )
        invitation_by_token_url = (
            f"{workspace_invitation_url}/{invitation.invitation_token}"
        )

        invitation_by_token = client.get(
            invitation_by_token_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = invitation_by_token.json()
        assert invitation_by_token.status_code == 403
        assert actual_response_message == expected_response_message

    def test_respond_to_invitation_token_by_invited_user(
        self,
        client: TestClient,
        invitation_by_token_url: str,
        test_invited_user_cookies: dict[str, str],
    ):
        url = f"{invitation_by_token_url}?response_status=ACCEPTED"

        responded_invitation = client.post(url, cookies=test_invited_user_cookies)

        expected_response = "Request Processed Successfully."
        actual_response = responded_invitation.json()
        assert actual_response == expected_response

    def test_respond_to_invalid_invitation_token_fails(
        self,
        client: TestClient,
        workspace_invitation_url: str,
        test_invited_user_cookies: dict[str, str],
    ):
        url = f"{workspace_invitation_url}/{secrets.token_hex(16)}?response_status=ACCEPTED"

        responded_invitation = client.post(url, cookies=test_invited_user_cookies)

        expected_response_message = MESSAGE_NOT_FOUND
        actual_response_message = responded_invitation.json()
        assert responded_invitation.status_code == 404
        assert actual_response_message == expected_response_message

    async def test_respond_to_non_pending_invitation_token_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_invitation_url: str,
        test_invited_user_cookies: dict[str, str],
    ):
        accepted_invitation = await WorkspaceUserInvitesDocument(
            workspace_id=workspace.id,
            email="invited_daemon@gmail.com",
            invitation_status="ACCEPTED",
            invitation_token=secrets.token_hex(16),
        ).save()
        url = f"{workspace_invitation_url}/{accepted_invitation.invitation_token}?response_status=REJECTED"

        responded_invitation = client.post(url, cookies=test_invited_user_cookies)

        expected_response_message = "Invalid Invitation Token"
        actual_response_message = responded_invitation.json()
        assert responded_invitation.status_code == 410
        assert actual_response_message == expected_response_message

    async def test_respond_to_expired_invitation_token_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_invitation_url: str,
        test_invited_user_cookies: dict[str, str],
    ):
        accepted_invitation = await WorkspaceUserInvitesDocument(
            workspace_id=workspace.id,
            email="invited_daemon@gmail.com",
            expiry=0,
            invitation_token=secrets.token_hex(16),
        ).save()
        url = f"{workspace_invitation_url}/{accepted_invitation.invitation_token}?response_status=REJECTED"

        responded_invitation = client.post(url, cookies=test_invited_user_cookies)

        expected_response_message = "Token has expired"
        actual_response_message = responded_invitation.json()
        assert responded_invitation.status_code == 410
        assert actual_response_message == expected_response_message

    def test_respond_to_invitation_token_by_non_invited_user_fails(
        self,
        client: TestClient,
        invitation_by_token_url: str,
        test_user_cookies: dict[str, str],
    ):
        url = f"{invitation_by_token_url}?response_status=ACCEPTED"

        responded_invitation = client.post(url, cookies=test_user_cookies)

        expected_response = "Invalid User"
        actual_response = responded_invitation.json()
        assert actual_response == expected_response

    def test_delete_invitation_by_token_for_admin(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        invitation_by_token_url: str,
    ):
        deleted_invitation = client.delete(
            invitation_by_token_url, cookies=test_user_cookies
        )

        expected_response = {"message": "Invitation deleted successfully."}
        actual_response = deleted_invitation.json()
        assert actual_response == expected_response

    def test_delete_non_existing_token_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_invitation_url: str,
        test_user_cookies: dict[str, str],
    ):
        url = f"{workspace_invitation_url}/{secrets.token_hex(16)}"

        responded_invitation = client.delete(url, cookies=test_user_cookies)

        expected_response_message = "Invitation not found"
        actual_response_message = responded_invitation.json()
        assert responded_invitation.status_code == 404
        assert actual_response_message == expected_response_message

    def test_delete_invitation_by_token_for_non_admin_fails(
        self,
        client: TestClient,
        test_invited_user_cookies: dict[str, str],
        invitation_by_token_url: str,
    ):
        deleted_invitation = client.delete(
            invitation_by_token_url, cookies=test_invited_user_cookies
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = deleted_invitation.json()
        assert deleted_invitation.status_code == 403
        assert actual_response_message == expected_response_message
