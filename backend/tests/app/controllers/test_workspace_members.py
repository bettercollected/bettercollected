from typing import Coroutine, Any

import pytest
from aiohttp.test_utils import TestClient
from fastapi_camelcase import CamelModel

from backend.app.models.dtos.workspace_member_dto import WorkspaceMemberDto
from backend.app.schemas.workspace import WorkspaceDocument
from common.constants import MESSAGE_FORBIDDEN
from tests.app.controllers.data import user_info, testUser


@pytest.fixture
def workspace_member_url(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    return f"/api/v1/workspaces/{workspace.id}/members"


@pytest.fixture
def workspace_invitation_url(workspace_member_url: str):
    return f"{workspace_member_url}/invitations"


class TestWorkspaceMember:
    def test_get_workspace_members(self, client: TestClient, workspace_member_url: str,
                                   test_user_cookies: dict[str, str], mock_get_user_info):
        expected_members_info = {"user_id": testUser.id, "email": user_info.get("users_info")[0].get("email")}

        with mock_get_user_info:
            members = client.get(workspace_member_url, cookies=test_user_cookies)

        members_info = members.json()[0]
        expected_response = expected_members_info
        actual_response = {"user_id": members_info.get("id"), "email": members_info.get("email")}
        assert actual_response == expected_response

    def test_unauthorized_client_get_workspace_members(self, client, workspace_member_url, test_user_cookies_1):
        workspace_members = client.get(workspace_member_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = workspace_members.json()
        assert workspace_members.status_code == 403
        assert actual_response_message == expected_response_message

