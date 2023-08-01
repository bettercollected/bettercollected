import pytest

from backend.app.container import container
from common.constants import MESSAGE_FORBIDDEN
from tests.app.controllers.data import testUser, workspace_tag


@pytest.fixture()
def workspace_responders_api(workspace):
    return "api/v1/workspaces/" + str(workspace.id) + "/responders"


@pytest.fixture()
def workspace_tag_url(workspace_responders_api):
    return f"{workspace_responders_api}/tags"


async def create_tag_for_responder(workspace, tag_title):
    return await container.workspace_responders_service().create_workspace_tag(
        workspace.id, tag_title, testUser
    )


@pytest.mark.asyncio
class TestWorkspaceResponders:
    async def test_get_workspace_responders(
        self,
        client,
        workspace,
        workspace_responders_api,
        test_user_cookies,
        workspace_form_response,
        workspace_form_response_1,
        workspace_form_response_2,
    ):
        workspace_responders = client.get(
            workspace_responders_api, cookies=test_user_cookies
        )

        expected_responders_emails = [
            workspace_form_response_2["dataOwnerIdentifier"],
            workspace_form_response_1["dataOwnerIdentifier"],
            workspace_form_response["dataOwnerIdentifier"],
        ]
        expected_responders_emails.sort()
        actual_responders_emails = [
            item["email"] for item in workspace_responders.json()["items"]
        ]
        expected_responders_number = 3
        actual_responders_number = workspace_responders.json()["total"]
        assert workspace_responders.status_code == 200
        assert actual_responders_number == expected_responders_number
        assert actual_responders_emails == expected_responders_emails

    def test_unauthorized_get_workspace_responders(
        self,
        client,
        workspace_responders_api,
        workspace_form_response,
        test_user_cookies_1,
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
        client,
        workspace_tag_url,
        workspace_group,
        test_user_cookies,
        workspace,
    ):
        tag1 = await create_tag_for_responder(workspace, "Admin")
        tag2 = await create_tag_for_responder(workspace, "Leader")

        workspace_tags = client.get(workspace_tag_url, cookies=test_user_cookies)

        actual_tags = [item.get("title") for item in workspace_tags.json()]
        expected_tags = [tag1.title, tag2.title]
        assert actual_tags == expected_tags

    def test_unauthorized_get_workspace_tags(
        self, client, workspace_tag_url, test_user_cookies_1
    ):
        unauthorized_client = client.get(workspace_tag_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    def test_create_workspace_tag(self, client, workspace_tag_url, test_user_cookies):
        tag = client.post(
            workspace_tag_url, cookies=test_user_cookies, json=workspace_tag
        )

        expected_tag = workspace_tag.get("title")
        actual_tag = tag.json().get("title")
        assert tag.status_code == 200
        assert actual_tag == expected_tag

    def test_unauthorized_create_workspace_tag(
        self, client, workspace_tag_url, test_user_cookies_1
    ):
        unauthorized_client = client.post(
            workspace_tag_url, cookies=test_user_cookies_1, json=workspace_tag
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_patch_workspace_responder_with_email(
        self, client, test_user_cookies, workspace, workspace_responders_api
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

    async def test_unauthorized_patch_workspace_responder_with_email(
        self, client, test_user_cookies_1, workspace_responders_api, workspace
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
