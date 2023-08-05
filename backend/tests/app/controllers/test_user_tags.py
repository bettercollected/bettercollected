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


@pytest.fixture()
def get_request_delete_response_url(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form_response: Coroutine[Any, Any, dict],
):
    return f"/api/v1/workspaces/{workspace.id}/submissions/{workspace_form_response['response_id']}"


user_tags_url = "/api/v1/user/tags/"


class TestUserTags:
    def test_get_user_tags_for_form_import_and_group_create(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
        workspace_form: Coroutine[Any, Any, FormDocument],
        get_request_delete_response_url: str,
        mock_aiohttp_post_request,
    ):
        import_form_url = f"/api/v1/workspaces/{workspace.id}/forms/import/google"
        create_group_url = f"/api/v1/{workspace.id}/responder-groups?name=random_group"
        with mock_aiohttp_post_request:
            client.post(
                import_form_url, cookies=test_user_cookies, json=test_form_import_data
            )
        client.post(create_group_url, cookies=test_user_cookies)

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = ["FORM_IMPORTED", "GROUP_CREATED"]
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

    def test_get_user_tags_for_form_added_to_group_and_deletion_request_received(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        get_add_form_in_group_url: str,
        get_request_delete_response_url: str,
    ):
        # add form to group
        client.patch(get_add_form_in_group_url, cookies=test_user_cookies)
        client.delete(get_request_delete_response_url, cookies=test_user_cookies)

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = ["FORM_ADDED_TO_GROUP", "DELETION_REQUEST_RECEIVED"]
        actual_response = fetched_tags.json()[0].get("tags")
        assert actual_response == expected_response

    def test_get_user_tags_for_custom_slug(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        patch_setting_url = (
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/settings"
        )
        client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        fetched_tags = client.get(user_tags_url, cookies=test_user_cookies)

        expected_response = ["CUSTOM_SLUG"]
        actual_response = fetched_tags.json()[0].get("tags")
        assert actual_response == expected_response

    def test_non_admin_get_user_tags(
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
        test_user_cookies: dict[str, str],
        get_add_form_in_group_url: str,
        get_request_delete_response_url: str,
        mock_aiohttp_get_request,
    ):
        tag_details_url = "/api/v1/user/tags/details"
        client.patch(get_add_form_in_group_url, cookies=test_user_cookies)
        client.delete(get_request_delete_response_url, cookies=test_user_cookies)

        with mock_aiohttp_get_request:
            tag_details = client.get(tag_details_url, cookies=test_user_cookies)

            expected_response = [{**user_tag_details, "userId": testUser.id}]
            actual_response = tag_details.json()
            assert actual_response == expected_response

    def test_non_admin_get_user_tag_details(
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
