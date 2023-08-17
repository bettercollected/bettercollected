from typing import Any, Coroutine

import pytest
from aiohttp.test_utils import TestClient

from backend.app.container import container
from backend.app.schemas.workspace import WorkspaceDocument
from common.constants import MESSAGE_FORBIDDEN
from tests.app.controllers.data import testUser, workspace_tag


@pytest.fixture()
def workspace_responders_api(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    return "api/v1/workspaces/" + str(workspace.id) + "/responders"


@pytest.fixture()
def workspace_tag_url(workspace_responders_api: Coroutine[Any, Any, str]):
    return f"{workspace_responders_api}/tags"


async def create_tag_for_responder(
    workspace: Coroutine[Any, Any, WorkspaceDocument], tag_title: str
):
    return await container.workspace_responders_service().create_workspace_tag(
        workspace.id, tag_title, testUser
    )


class TestWorkspaceResponders:
    async def test_get_workspace_responders(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_responders_api: str,
        test_user_cookies: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
        workspace_form_response_1: Coroutine[Any, Any, dict],
        workspace_form_response_2: Coroutine[Any, Any, dict],
    ):
        responders_emails = [
            workspace_form_response_2["dataOwnerIdentifier"],
            workspace_form_response_1["dataOwnerIdentifier"],
            workspace_form_response["dataOwnerIdentifier"],
        ]

        workspace_responders = client.get(
            workspace_responders_api, cookies=test_user_cookies
        )

        expected_responders_emails = responders_emails
        expected_responders_emails.sort()
        actual_responders_emails = [
            item["email"] for item in workspace_responders.json()["items"]
        ]
        expected_responders_number = 3
        actual_responders_number = workspace_responders.json()["total"]
        assert workspace_responders.status_code == 200
        assert actual_responders_number == expected_responders_number
        assert actual_responders_emails == expected_responders_emails

    def test_unauthorized_get_workspace_responders_fails(
        self,
        client: TestClient,
        workspace_responders_api: str,
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = client.get(
            workspace_responders_api, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_get_workspace_tags(
        self,
        client: TestClient,
        workspace_tag_url: str,
        workspace_group: Coroutine,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
    ):
        tag1 = await create_tag_for_responder(workspace, "Admin")
        tag2 = await create_tag_for_responder(workspace, "Leader")

        workspace_tags = client.get(workspace_tag_url, cookies=test_user_cookies)

        actual_tags = [item.get("title") for item in workspace_tags.json()]
        expected_tags = [tag1.title, tag2.title]
        assert actual_tags == expected_tags

    def test_unauthorized_get_workspace_tags_fails(
        self,
        client: TestClient,
        workspace_tag_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = client.get(workspace_tag_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    def test_create_workspace_tag(
        self,
        client: TestClient,
        workspace_tag_url: str,
        test_user_cookies: dict[str, str],
    ):
        tag = client.post(
            workspace_tag_url, cookies=test_user_cookies, json=workspace_tag
        )

        expected_tag = workspace_tag.get("title")
        actual_tag = tag.json().get("title")
        assert tag.status_code == 200
        assert actual_tag == expected_tag

    def test_unauthorized_create_workspace_tag_fails(
        self,
        client: TestClient,
        workspace_tag_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = client.post(
            workspace_tag_url, cookies=test_user_cookies_1, json=workspace_tag
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_patch_workspace_responder_with_email(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_responders_api: str,
    ):
        tag = await container.workspace_responders_service().create_workspace_tag(
            workspace.id, "GrandMaster", testUser
        )
        patch_workspace_responder_url = (
            f"{workspace_responders_api}?email=bettercollected@gmail.com"
        )

        workspace_responder = client.patch(
            patch_workspace_responder_url,
            cookies=test_user_cookies,
            json={"tags": [str(tag.id)]},
        )

        expected_tag_id = str(tag.id)
        actual_tag_id = workspace_responder.json().get("tags")[0]
        assert workspace_responder.status_code == 200
        assert actual_tag_id == expected_tag_id

    async def test_unauthorized_patch_workspace_responder_with_email_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_responders_api: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
    ):
        tag = await container.workspace_responders_service().create_workspace_tag(
            workspace.id, "GrandMaster", testUser
        )
        patch_workspace_responder_url = (
            f"{workspace_responders_api}?email=bettercollected@gmail.com"
        )

        unauthorized_client = client.patch(
            patch_workspace_responder_url,
            cookies=test_user_cookies_1,
            json={"tags": [str(tag.id)]},
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message
