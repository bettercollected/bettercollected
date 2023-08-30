from typing import Any, Coroutine

import pytest
from aiohttp.test_utils import TestClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.schemas.workspace import WorkspaceDocument
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import StandardFormResponse, StandardForm
from tests.app.controllers.data import testUser1, formResponse, testUser, formData_2


@pytest.fixture()
def common_url(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    return f"/api/v1/workspaces/{workspace.id}"


@pytest.fixture()
def get_request_delete_response_url(
    common_url: str, workspace_form_response: Coroutine[Any, Any, dict]
):
    return f"{common_url}/submissions/{workspace_form_response['response_id']}"


@pytest.fixture()
def get_delete_form_response_url(
    common_url: str,
    workspace_form: Coroutine[Any, Any, FormDocument],
    workspace_form_response: Coroutine[Any, Any, dict],
):
    return f"{common_url}/forms/{workspace_form.form_id}/response/{workspace_form_response['response_id']}"


@pytest.fixture()
def get_get_form_responses_url(
    common_url: str, workspace_form: Coroutine[Any, Any, FormDocument]
):
    return f"{common_url}/forms/{workspace_form.form_id}/submissions"


@pytest.fixture()
def get_all_workspace_responses_url(common_url: str):
    return f"{common_url}/all-submissions"


@pytest.fixture()
def get_user_submission_url(common_url: str):
    return f"{common_url}/submissions"


@pytest.fixture()
def get_form_response_by_id_url(
    common_url: str, workspace_form_response: Coroutine[Any, Any, dict]
):
    return f"{common_url}/submissions/{workspace_form_response['response_id']}"


async def create_responses(
    form: FormDocument, workspace: Coroutine[Any, Any, WorkspaceDocument]
):
    user_1_response = await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponse(**formResponse),
        testUser,
    )
    user_2_response = await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponse(**formResponse),
        testUser1,
    )
    return [
        (dict(user_2_response))["response_id"],
        (dict(user_1_response))["response_id"],
    ]


class TestWorkspaceFormSubmission:
    async def test_request_for_delete_form_response(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
        get_request_delete_response_url: str,
    ):
        request_response_deletion = client.delete(
            get_request_delete_response_url,
            cookies=test_user_cookies,
        )

        form_response_deletion_request = (
            await FormResponseDeletionRequest.find().to_list()
        )
        actual_response = request_response_deletion.json()
        expected_response = {"message": "Request for deletion created successfully."}
        assert actual_response == expected_response
        actual_response_id = form_response_deletion_request[0].response_id
        expected_response_id = workspace_form_response["response_id"]
        assert actual_response_id == expected_response_id

    def test_throws_error_on_multiple_request_for_delete_form_response(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        get_request_delete_response_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        # Arrange
        request_response_deletion = client.delete(
            get_request_delete_response_url, cookies=test_user_cookies
        )

        # Act
        request_response_deletion_2 = client.delete(
            get_request_delete_response_url, cookies=test_user_cookies
        )

        # Assert
        actual_response = request_response_deletion_2.json()
        expected_response = (
            f"Error: Deletion request already exists for the response : "
            f"{workspace_form_response['response_id']}"
        )
        assert actual_response == expected_response

    def test_delete_deletion_requested_form_response(
        self,
        client: TestClient,
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies: dict[str, str],
        get_request_delete_response_url: str,
        get_delete_form_response_url: str,
    ):
        # Arrange
        request_response_deletion = client.delete(
            get_request_delete_response_url, cookies=test_user_cookies
        )

        # Act
        deleted_requested_form = client.delete(
            get_delete_form_response_url, cookies=test_user_cookies
        )

        # Assert
        actual_response = deleted_requested_form.json()
        expected_response = workspace_form_response["response_id"]
        assert deleted_requested_form.status_code == 200
        assert actual_response == expected_response

    def test_unauthorized_user_request_for_delete_form_response_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        get_request_delete_response_url: str,
    ):
        request_response_deletion = client.delete(
            get_request_delete_response_url,
            cookies=test_user_cookies_1,
        )

        actual_response = request_response_deletion.json()
        expected_response = "You are not authorized to perform this action."
        assert request_response_deletion.status_code == 403
        assert actual_response == expected_response

    async def test_get_workspace_form_responses(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response_1: Coroutine[Any, Any, dict],
        workspace_form_response: Coroutine[Any, Any, dict],
        get_get_form_responses_url: str,

    ):
        response_ids = [
            workspace_form_response["response_id"],
            workspace_form_response_1["response_id"],
        ]

        form_responses = client.get(
            get_get_form_responses_url,
            cookies=test_user_cookies,
        )

        actual_total_responses = form_responses.json()["total"]
        expected_total_responses = 2
        expected_response_ids = response_ids
        actual_response_ids = [
            item["responseId"] for item in form_responses.json()["items"]
        ]
        assert form_responses.status_code == 200
        assert actual_total_responses == expected_total_responses
        assert actual_response_ids == expected_response_ids

    async def test_get_workspace_form_responses_returns_only_its_workspace_responses(
        self,
        client: TestClient,
        workspace_form_1: Coroutine[Any, Any, FormDocument],
        get_get_form_responses_url: str,
        workspace_1: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_response_1: Coroutine[Any, Any, dict],
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies: dict[str, str],
    ):
        new_workspace_form_response = dict(
            await container.workspace_form_service().submit_response(
                workspace_1.id,
                workspace_form_1.form_id,
                StandardFormResponse(**formResponse),
                testUser1,
            )
        )

        form_responses = client.get(
            get_get_form_responses_url,
            cookies=test_user_cookies,
        )

        actual_response_ids = [
            item["responseId"] for item in form_responses.json()["items"]
        ]
        expected_response_id = new_workspace_form_response["response_id"]
        assert expected_response_id not in actual_response_ids

    def test_unauthorized_get_workspace_form_responses_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        get_get_form_responses_url: str,
    ):
        form_responses = client.get(
            get_get_form_responses_url,
            cookies=test_user_cookies_1,
        )

        expected_response = MESSAGE_FORBIDDEN
        actual_response = form_responses.json()
        assert form_responses.status_code == 403
        assert actual_response == expected_response

    async def test_non_workspace_form_fails_on_get_form_responses(
        self,
        client: TestClient,
        common_url: str,
        test_user_cookies: dict[str, str],
        workspace_form_1: Coroutine[Any, Any, FormDocument],
    ):
        get_non_workspace_form_url = (
            f"{common_url}/forms/{workspace_form_1.form_id}/submissions"
        )

        form_responses = client.get(
            get_non_workspace_form_url,
            cookies=test_user_cookies,
        )

        expected_response = "Form not found in the workspace."
        actual_response = form_responses.json()
        assert actual_response == expected_response

    async def test_get_all_workspaces_response(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        get_all_workspace_responses_url: str,
        test_user_cookies: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        # Arrange
        new_form = await container.workspace_form_service().create_form(
            workspace.id, StandardForm(**formData_2), testUser
        )
        user_responses = await create_responses(new_form, workspace)

        # Act
        all_responses = client.get(
            get_all_workspace_responses_url, cookies=test_user_cookies
        )

        # Assert
        expected_response_ids = [
            *user_responses,
            workspace_form_response["response_id"],
        ]
        actual_response_ids = [
            item["responseId"] for item in all_responses.json()["items"]
        ]
        actual_responses = all_responses.json()["total"]
        expected_responses = 3
        assert actual_responses == expected_responses
        assert actual_response_ids == expected_response_ids

    def test_unauthorized_get_all_workspace_responses_fails(
        self,
        client: TestClient,
        get_all_workspace_responses_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies_1: dict[str, str],
    ):
        all_responses = client.get(
            get_all_workspace_responses_url, cookies=test_user_cookies_1
        )

        expected_response = MESSAGE_FORBIDDEN
        actual_response = all_responses.json()
        assert all_responses.status_code == 403
        assert actual_response == expected_response

    async def test_get_single_user_submissions_in_workspace(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        get_user_submission_url: str,
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        [new_user_form_response, current_user_form_response] = await create_responses(
            workspace_form, workspace
        )

        user_submissions = client.get(
            get_user_submission_url, cookies=test_user_cookies
        )

        expected_response_ids = [
            workspace_form_response["response_id"],
            current_user_form_response,
        ]
        actual_response_ids = [
            item["responseId"] for item in user_submissions.json()["items"]
        ]
        expected_number_of_responses = 2
        actual_number_of_responses = user_submissions.json()["total"]
        assert user_submissions.status_code == 200
        assert actual_number_of_responses == expected_number_of_responses
        assert actual_response_ids == expected_response_ids
        assert new_user_form_response not in expected_response_ids

    def test_get_workspace_form_response_by_response_id(
        self,
        client: TestClient,
        get_form_response_by_id_url: str,
        test_user_cookies: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        single_form_response = client.get(
            get_form_response_by_id_url, cookies=test_user_cookies
        )

        expected_response_id = workspace_form_response["response_id"]
        actual_response_id = single_form_response.json()["response"]["responseId"]
        assert single_form_response.status_code == 200
        assert actual_response_id == expected_response_id

    def test_unauthorized_get_workspace_form_response_by_response_id_fails(
        self,
        client: TestClient,
        get_form_response_by_id_url: str,
        test_user_cookies_1: dict[str, str],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        single_form_response = client.get(
            get_form_response_by_id_url, cookies=test_user_cookies_1
        )

        expected_response_message = "You are not authorized to perform this action."
        actual_response_message = single_form_response.json()
        assert single_form_response.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_get_workspace_form_response_by_response_id_of_other_workspace_form_fails(
        self,
        client: TestClient,
        workspace_form_1: Coroutine[Any, Any, FormDocument],
        common_url: str,
        workspace_1: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        new_form_response = dict(
            await container.workspace_form_service().submit_response(
                workspace_1.id,
                workspace_form_1.form_id,
                StandardFormResponse(**formResponse),
                testUser,
            )
        )
        get_workspace_response_by_id_url = (
            f"{common_url}/submissions/{new_form_response['response_id']}"
        )

        single_form_response = client.get(
            get_workspace_response_by_id_url, cookies=test_user_cookies
        )

        expected_response_message = "Form not found in this workspace"
        actual_response_message = single_form_response.json()
        assert actual_response_message == expected_response_message
