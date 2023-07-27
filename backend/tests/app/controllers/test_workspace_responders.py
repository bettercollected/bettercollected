import pytest


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
