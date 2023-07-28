import pytest

from backend.app.container import container
from tests.app.controllers.data import testUser, workspace_tag, workspace_responder_tag


@pytest.fixture()
def client(client_test):
    yield client_test


@pytest.fixture()
def workspace_responders_api(workspace):
    yield "api/v1/workspaces/" + str(workspace.id) + "/responders"


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
        emails = [
            workspace_form_response_2["dataOwnerIdentifier"],
            workspace_form_response_1["dataOwnerIdentifier"],
            workspace_form_response["dataOwnerIdentifier"],
        ]
        emails.sort()
        assert workspace_responders.status_code == 200
        assert workspace_responders.json()["total"] == 3
        workspace_responders_emails = [
            item["email"] for item in workspace_responders.json()["items"]
        ]
        assert workspace_responders_emails == emails

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
        assert unauthorized_client.status_code == 403
        assert (
            unauthorized_client.json()
            == "403 - Forbidden: You don't have permission to access this resource."
        )

    async def test_get_workspace_tags(
        self,
        client,
        workspace_responders_api,
        workspace_group,
        test_user_cookies,
        workspace,
    ):
        tag1 = await container.workspace_responders_service().create_workspace_tag(
            workspace.id, "Admin", testUser
        )
        tag2 = await container.workspace_responders_service().create_workspace_tag(
            workspace.id, "Leader", testUser
        )
        workspace_tags = client.get(
            workspace_responders_api + str("/tags"), cookies=test_user_cookies
        )
        workspace_tags_title = [item.get("title") for item in workspace_tags.json()]
        tags = [tag1.title, tag2.title]
        assert workspace_tags_title == tags

    def test_unauthorized_get_workspace_tags(
        self, client, workspace_responders_api, test_user_cookies_1
    ):
        workspace_tags = client.get(
            workspace_responders_api + "/tags", cookies=test_user_cookies_1
        )
        assert workspace_tags.status_code == 403
        assert (
            workspace_tags.json()
            == "403 - Forbidden: You don't have permission to access this resource."
        )

    def test_create_workspace_tag(
        self, client, workspace_responders_api, test_user_cookies
    ):
        tag = client.post(
            workspace_responders_api + "/tags",
            cookies=test_user_cookies,
            json=workspace_tag,
        )
        assert tag.status_code == 200
        assert tag.json().get("title") == workspace_tag.get("title")

    def test_unauthorized_create_workspace_tag(
        self, client, workspace_responders_api, test_user_cookies_1
    ):
        workspace_tags = client.post(
            workspace_responders_api + "/tags",
            cookies=test_user_cookies_1,
            json=workspace_tag,
        )
        assert workspace_tags.status_code == 403
        assert (
            workspace_tags.json()
            == "403 - Forbidden: You don't have permission to access this resource."
        )

    async def test_patch_workspace_responder_with_email(
        self, client, test_user_cookies, workspace, workspace_responders_api
    ):
        tag = await container.workspace_responders_service().create_workspace_tag(
            workspace.id, "GrandMaster", testUser
        )
        workspace_responder = client.patch(
            workspace_responders_api + "?email=bettercollected@gmail.com",
            cookies=test_user_cookies,
            json={"tags": [str(tag.id)]},
        )
        assert workspace_responder.status_code == 200
        assert workspace_responder.json().get("tags")[0] == str(tag.id)

    async def test_unauthorized_patch_workspace_responder_with_email(
        self, client, test_user_cookies_1, workspace_responders_api, workspace
    ):
        tag = await container.workspace_responders_service().create_workspace_tag(
            workspace.id, "GrandMaster", testUser
        )
        workspace_responder = client.patch(
            workspace_responders_api + "?email=bettercollected@gmail.com",
            cookies=test_user_cookies_1,
            json={"tags": [str(tag.id)]},
        )
        assert workspace_responder.status_code == 403
        assert (
            workspace_responder.json()
            == "403 - Forbidden: You don't have permission to access this resource."
        )
