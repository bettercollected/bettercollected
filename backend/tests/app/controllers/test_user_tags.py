from typing import Coroutine, Any

import pytest
from aiohttp.test_utils import TestClient

from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from tests.app.controllers.data import (
    test_form_import_data,
    workspace_attribute,
    workspace_settings,
    user_tag_details,
    testUser,
)


@pytest.fixture()
def get_add_form_in_group_url(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    workspace_group: Coroutine,
):
    return f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/groups/add?group_id={workspace_group.id}"


user_tags_url = "/api/v1/user/tags/"


class TestUserTags:
    def test_get_user_tags_for_form_import_and_delete_request_received_and_delete_request_processed(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
        workspace_form_response_1: Coroutine[Any, Any, dict],
        workspace_form_response_2: Coroutine[Any, Any, dict],
        workspace_form: Coroutine[Any, Any, FormDocument],
        mock_aiohttp_post_request,
    ):
        import_form_url = f"/api/v1/workspaces/{workspace.id}/forms/import/google"
        request_delete_url_1 = f"/api/v1/workspaces/{workspace.id}/submissions/{workspace_form_response['response_id']}"
        request_delete_url_2 = f"/api/v1/workspaces/{workspace.id}/submissions/{workspace_form_response_1['response_id']}"
        client.delete(
            request_delete_url_1,
            cookies=test_user_cookies,
        )
        client.delete(
            request_delete_url_2,
            cookies=test_user_cookies,
        )
        with mock_aiohttp_post_request:
            client.post(
                import_form_url, cookies=test_user_cookies, json=test_form_import_data
            )

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = [
            "DELETION_REQUEST_RECEIVED",
            "DELETION_REQUEST_PROCESSED",
            "FORM_IMPORTED",
        ]
        actual_response = fetched_tags.json()[0].get("tags")
        assert actual_response == expected_response

    def test_get_user_tags_for_workspace_handle_change_and_custom_domain(
        self,
        client: TestClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict[str, str],
        test_user_cookies: dict[str, str],
    ):
        patch_custom_domain = f"/api/v1/workspaces/{workspace_pro.id}"
        client.patch(
            patch_custom_domain, cookies=test_pro_user_cookies, data=workspace_attribute
        )

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = ["WORKSPACE_HANDLE_CHANGE", "CUSTOM_DOMAIN_UPDATED"]
        actual_response = fetched_tags.json()[0].get("tags")
        assert actual_response == expected_response

    def test_get_user_tags_for_form_added_to_group_and_group_created(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        get_add_form_in_group_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
    ):
        # add form to group
        create_group_url = f"/api/v1/{workspace.id}/responder-groups?name=random_group"
        client.patch(get_add_form_in_group_url, cookies=test_user_cookies)
        client.post(create_group_url, cookies=test_user_cookies)

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = ["FORM_ADDED_TO_GROUP", "GROUP_CREATED"]
        actual_response = fetched_tags.json()[0].get("tags")
        assert actual_response == expected_response

    def test_get_user_tags_for_custom_slug_and_new_user(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        mock_validate_otp,
    ):
        patch_setting_url = (
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/settings"
        )
        validate_otp_url = "/api/v1/auth/otp/validate"
        client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )
        with mock_validate_otp:
            client.post(
                validate_otp_url,
                cookies=test_user_cookies,
                json={"email": "asad@gmial.com", "otp_code": "12"},
            )

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = ["CUSTOM_SLUG", "NEW_USER"]
        actual_response = fetched_tags.json()[0].get("tags")
        assert actual_response == expected_response

    def test_non_admin_get_user_tags_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        get_add_form_in_group_url: str,
    ):
        tag_details = client.get(user_tags_url, cookies=test_user_cookies_1)

        expected_response = "You are not authorized."
        actual_response = tag_details.json()
        assert tag_details.status_code == 403
        assert actual_response == expected_response

    def test_get_user_tag_details(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        get_add_form_in_group_url: str,
        mock_aiohttp_get_request,
    ):
        tag_details_url = "/api/v1/user/tags/details"
        create_group_url = f"/api/v1/{workspace.id}/responder-groups?name=random_group"
        client.patch(get_add_form_in_group_url, cookies=test_user_cookies)
        client.post(create_group_url, cookies=test_user_cookies)

        with mock_aiohttp_get_request:
            tag_details = client.get(tag_details_url, cookies=test_user_cookies)

            expected_response = [{**user_tag_details, "userId": testUser.id}]
            actual_response = tag_details.json()
            assert actual_response == expected_response

    def test_non_admin_get_user_tag_details_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        get_add_form_in_group_url: str,
    ):
        tag_details_url = "/api/v1/user/tags/details"

        tag_details = client.get(tag_details_url, cookies=test_user_cookies_1)

        expected_response = "You are not authorized."
        actual_response = tag_details.json()
        assert tag_details.status_code == 403
        assert actual_response == expected_response
