from typing import Any, Coroutine

from aiohttp.test_utils import TestClient
from common.constants import MESSAGE_FORBIDDEN

from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.config import settings
from tests.app.controllers.data import (
    testUser,
    proUser,
    workspace_attribute,
    workspace_attribute_1,
)

common_url = "/api/v1/workspaces"


class TestWorkspaces:
    def test_get_workspace_by_query(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            workspace_1: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
            mock_get_workspace_by_query,
    ):
        get_workspace_url = f"{common_url}?workspace_name={testUser.id}"
        with mock_get_workspace_by_query:
            fetched_workspace = client.get(get_workspace_url, cookies=test_user_cookies)

            expected_workspace_id = str(workspace.id)
            actual_workspace_id = fetched_workspace.json().get("id")
            assert actual_workspace_id == expected_workspace_id

    def test_create_workspace(
            self, client: TestClient, test_pro_user_cookies: dict[str, str]
    ):
        created_workspace = client.post(
            common_url, cookies=test_pro_user_cookies, data=workspace_attribute_1
        )

        expected_workspace_attribute = {**workspace_attribute_1, "owner_id": proUser.id}
        actual_workspace_attribute = {
            "title": created_workspace.json()["title"],
            "description": created_workspace.json()["description"],
            "owner_id": created_workspace.json()["ownerId"],
        }
        assert actual_workspace_attribute == expected_workspace_attribute

    def test_create_workspace_fails_for_normal_user(
            self, client: TestClient, test_user_cookies: dict[str, str]
    ):
        free_user_workspace = client.post(
            common_url, cookies=test_user_cookies, data=workspace_attribute
        )

        expected_response_message = "Upgrade to Pro to add more workspace."
        actual_response_message = free_user_workspace.json()
        assert free_user_workspace.status_code == 403
        assert actual_response_message == expected_response_message

    def test_pro_user_can_only_create_specified_workspace(
            self, client: TestClient, test_pro_user_cookies: dict[str, str]
    ):
        for i in range(settings.api_settings.ALLOWED_WORKSPACES):
            client.post(
                common_url, cookies=test_pro_user_cookies, data=workspace_attribute_1
            )

        max_limit_workspace = client.post(
            common_url, cookies=test_pro_user_cookies, data=workspace_attribute_1
        )

        expected_response_message = "Cannot add more workspaces"
        actual_response_message = max_limit_workspace.json()
        assert max_limit_workspace.status_code == 409
        assert actual_response_message == expected_response_message

    def test_get_mine_workspaces_for_normal_user(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        get_mine_workspace_url = f"{common_url}/mine"

        normal_user_workspaces = client.get(
            get_mine_workspace_url, cookies=test_user_cookies
        )

        expected_workspace_owner_id = testUser.id
        actual_workspace_owner_id = normal_user_workspaces.json()[0].get("ownerId")
        assert actual_workspace_owner_id == expected_workspace_owner_id

    def test_get_mine_workspaces_for_pro_user(
            self, client: TestClient, test_pro_user_cookies: dict[str, str]
    ):
        get_mine_workspace_url = f"{common_url}/mine"
        client.post(common_url, cookies=test_pro_user_cookies, data=workspace_attribute)
        client.post(
            common_url, cookies=test_pro_user_cookies, data=workspace_attribute_1
        )

        pro_user_workspaces = client.get(
            get_mine_workspace_url, cookies=test_pro_user_cookies
        )

        expected_workspace_owner_id = [proUser.id] * len(pro_user_workspaces.json())
        actual_workspace_owner_id = [
            workspace.get("ownerId") for workspace in pro_user_workspaces.json()
        ]
        assert actual_workspace_owner_id == expected_workspace_owner_id

    def test_get_workspace_by_id(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        get_workspace_by_id_url = f"{common_url}/{workspace.id}"

        fetched_workspace = client.get(
            get_workspace_by_id_url, cookies=test_user_cookies
        )

        expected_workspace_id = str(workspace.id)
        actual_workspace_id = fetched_workspace.json().get("id")
        assert fetched_workspace.status_code == 200
        assert actual_workspace_id == expected_workspace_id

    def test_patch_workspace_with_custom_domain_for_pro_user(
            self,
            client: TestClient,
            workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
            test_pro_user_cookies: dict[str, str],
    ):
        patch_workspace_url = f"{common_url}/{workspace_pro.id}"

        patched_workspace = client.patch(
            patch_workspace_url, cookies=test_pro_user_cookies, data=workspace_attribute
        )

        expected_updated_workspace_attribute = workspace_attribute
        actual_updated_workspace_attribute = {
            "title": patched_workspace.json().get("title"),
            "description": patched_workspace.json().get("description"),
            "custom_domain": patched_workspace.json().get("customDomain"),
            "workspace_name": patched_workspace.json().get("workspaceName"),
        }
        assert (
                actual_updated_workspace_attribute == expected_updated_workspace_attribute
        )

    def test_patch_workspace_with_custom_domain_for_normal_user_fails(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        patch_workspace_url = f"{common_url}/{workspace.id}"

        patched_workspace = client.patch(
            patch_workspace_url, cookies=test_user_cookies, data=workspace_attribute
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = patched_workspace.json()
        assert patched_workspace.status_code == 403
        assert actual_response_message == expected_response_message

    def test_unauthorized_client_patch_workspace_false(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies_1: dict[str, str],
    ):
        patch_workspace_url = f"{common_url}/{workspace.id}"

        patched_workspace = client.patch(
            patch_workspace_url, cookies=test_user_cookies_1, data=workspace_attribute
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = patched_workspace.json()
        assert patched_workspace.status_code == 403
        assert actual_response_message == expected_response_message

    def test_check_handle_availability_using_workspace_name(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        check_handle_url = (
            f"{common_url}/check-handle-availability/sireto"
        )

        check_handle_availability = client.get(
            check_handle_url, cookies=test_user_cookies
        )

        expected_response = "True"
        actual_response = check_handle_availability.json()
        assert actual_response == expected_response

    def test_check_handle_availability_using_workspace_name_and_workspace_id(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        check_handle_url = (
            f"{common_url}/check-handle-availability/sireto?workspace_id={workspace.id}"
        )

        check_handle_availability = client.get(
            check_handle_url, cookies=test_user_cookies
        )

        expected_response = "True"
        actual_response = check_handle_availability.json()
        assert actual_response == expected_response

    def test_check_handle_availability_fails_for_existing_handle(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            workspace_1: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        check_handle_url = f"{common_url}/check-handle-availability/{workspace_1.workspace_name}"

        check_handle_availability = client.get(
            check_handle_url, cookies=test_user_cookies
        )

        expected_response = "False"
        actual_response = check_handle_availability.json()
        assert actual_response == expected_response

    def test_suggest_handles(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        suggest_handles_url = f"{common_url}/suggest-handle/test"

        suggest_handle = client.get(suggest_handles_url, cookies=test_user_cookies)

        expected_response = ["test", "test1", "test2", "test3", "test4", "test5"]
        actual_response = suggest_handle.json()
        assert actual_response == expected_response

    def test_send_otp_for_workspace(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
            mock_send_otp_get_request,
    ):
        with mock_send_otp_get_request:
            send_otp_url = f"{common_url}/{workspace.id}/auth/otp/send?receiver_email=johndoe@gmail.com"

            send_otp_for_workspace = client.post(
                send_otp_url, cookies=test_user_cookies
            )

            expected_response_message = {"message": "Otp sent successfully"}
            actual_response_message = send_otp_for_workspace.json()
            assert send_otp_for_workspace.status_code == 200
            assert actual_response_message == expected_response_message

    async def test_delete_custom_domain(
            self,
            client: TestClient,
            workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
            test_pro_user_cookies: dict[str, str],
    ):
        patch_workspace_url = f"{common_url}/{workspace_pro.id}"
        patched_workspace_custom_domain = client.patch(
            patch_workspace_url, cookies=test_pro_user_cookies, data=workspace_attribute
        )
        delete_custom_domain_url = f"{common_url}/{workspace_pro.id}/custom-domain"

        deleted_custom_domain_workspace = client.delete(
            delete_custom_domain_url, cookies=test_pro_user_cookies
        )

        expected_custom_domain = ""
        actual_custom_domain = deleted_custom_domain_workspace.json().get(
            "customDomain"
        )
        assert actual_custom_domain == expected_custom_domain

    def test_delete_custom_domain_for_normal_user_fails(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            test_user_cookies: dict[str, str],
    ):
        delete_custom_domain_url = f"{common_url}/{workspace.id}/custom-domain"

        deleted_custom_domain_workspace = client.delete(
            delete_custom_domain_url, cookies=test_user_cookies
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = deleted_custom_domain_workspace.json()
        assert deleted_custom_domain_workspace.status_code == 403
        assert actual_response_message == expected_response_message

    def test_get_workspace_stats(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            workspace_form: Coroutine[Any, Any, FormDocument],
            workspace_form_response: Coroutine[Any, Any, dict],
            test_user_cookies: dict[str, str],
    ):
        workspace_stats_url = f"{common_url}/{workspace.id}/stats"

        workspace_stats = client.get(workspace_stats_url, cookies=test_user_cookies)

        expected_response = {
            "deletionRequests": {"pending": 0, "success": 0, "total": 0},
            "forms": 1,
            "responses": 1,
        }
        actual_response = workspace_stats.json()
        assert actual_response == expected_response

    def test_unauthorized_client_get_workspace_stats_fails(
            self,
            client: TestClient,
            workspace: Coroutine[Any, Any, WorkspaceDocument],
            workspace_form: Coroutine[Any, Any, FormDocument],
            workspace_form_response: Coroutine[Any, Any, dict],
            test_user_cookies_1: dict[str, str],
    ):
        workspace_stats_url = f"{common_url}/{workspace.id}/stats"

        workspace_stats = client.get(workspace_stats_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = workspace_stats.json()
        assert workspace_stats.status_code == 403
        assert actual_response_message == expected_response_message
