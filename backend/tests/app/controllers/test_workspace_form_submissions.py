import pytest

from backend.app.container import container
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from common.models.standard_form import StandardFormResponse, StandardForm
from tests.app.controllers.data import testUser1, formResponse, testUser, formData_2


@pytest.fixture()
def client(client_test):
    yield client_test


@pytest.fixture()
def form_response_api(workspace):
    yield "/api/v1/workspaces/" + str(workspace.id)


@pytest.mark.asyncio
class TestWorkspaceFormSubmission:
    async def test_request_for_delete_form_response(
        self,
        client,
        test_user_cookies,
        workspace,
        workspace_form,
        workspace_form_response,
        form_response_api,
    ):
        request_response_deletion = client.delete(
            form_response_api
            + "/submissions/"
            + str(workspace_form_response["response_id"]),
            cookies=test_user_cookies,
        )
        assert request_response_deletion.status_code == 200
        assert request_response_deletion.json() == {
            "message": "Request for deletion created successfully."
        }
        form_response_deletion_request = (
            await FormResponseDeletionRequest.find().to_list()
        )
        assert (
            form_response_deletion_request[0].response_id
            == workspace_form_response["response_id"]
        )
        request_response_deletion_2 = client.delete(
            form_response_api
            + "/submissions/"
            + str(workspace_form_response["response_id"]),
            cookies=test_user_cookies,
        )
        assert (
            request_response_deletion_2.json()
            == "Error: Deletion request already exists for the response : "
            + str(workspace_form_response["response_id"])
        )
        deleted_requested_form = client.delete(
            form_response_api
            + "/forms/"
            + str(workspace_form.form_id)
            + "/response/"
            + str(workspace_form_response["response_id"]),
            cookies=test_user_cookies,
        )
        assert deleted_requested_form.status_code == 200
        assert deleted_requested_form.json() == workspace_form_response["response_id"]

    def test_unauthorized_user_request_for_delete_form_response(
        self,
        client,
        test_user_cookies_1,
        workspace,
        workspace_form_response,
        form_response_api,
    ):
        request_response_deletion = client.delete(
            form_response_api
            + "/submissions/"
            + str(workspace_form_response["response_id"]),
            cookies=test_user_cookies_1,
        )
        assert request_response_deletion.status_code == 403
        assert (
            request_response_deletion.json()
            == "You are not authorized to perform this action."
        )

    async def test_get_workspace_form_responses(
        self,
        client,
        form_response_api,
        test_user_cookies,
        workspace_form,
        workspace_form_response_1,
        workspace_form_response,
        workspace_form_1,
        workspace_1,
    ):
        response_id_1 = workspace_form_response["response_id"]
        response_id_2 = workspace_form_response_1["response_id"]
        response_ids = [response_id_1, response_id_2]
        new_form_response = dict(
            await container.workspace_form_service().submit_response(
                workspace_1.id,
                workspace_form_1.form_id,
                StandardFormResponse(**formResponse),
                testUser1,
            )
        )
        form_responses = client.get(
            form_response_api
            + "/forms/"
            + str(workspace_form.form_id)
            + "/submissions",
            cookies=test_user_cookies,
        )
        assert form_responses.status_code == 200
        assert form_responses.json()["total"] == 2
        form_responses_response_id = [
            item["responseId"] for item in form_responses.json()["items"]
        ]
        assert form_responses_response_id == response_ids
        assert new_form_response["response_id"] not in form_responses_response_id

    def test_unauthorized_get_workspace_form_responses(
        self,
        client,
        form_response_api,
        test_user_cookies_1,
        workspace_form,
    ):
        form_responses = client.get(
            form_response_api
            + "/forms/"
            + str(workspace_form.form_id)
            + "/submissions",
            cookies=test_user_cookies_1,
        )
        assert form_responses.status_code == 403
        assert (
            form_responses.json()
            == "403 - Forbidden: You don't have permission to access this resource."
        )

    async def test_non_workspace_form_get_form_responses_fails(
        self, client, form_response_api, test_user_cookies, workspace_form_1
    ):
        form_responses = client.get(
            form_response_api
            + "/forms/"
            + str(workspace_form_1.form_id)
            + "/submissions",
            cookies=test_user_cookies,
        )
        assert form_responses.json() == "Form not found in the workspace."

    async def test_get_all_workspaces_response(
        self,
        client,
        workspace,
        form_response_api,
        test_user_cookies,
        workspace_form_response,
    ):
        new_form = await container.workspace_form_service().create_form(
            workspace.id, StandardForm(**formData_2), testUser
        )
        user_1_response = dict(
            await container.workspace_form_service().submit_response(
                workspace.id,
                new_form.form_id,
                StandardFormResponse(**formResponse),
                testUser,
            )
        )
        user_2_response = dict(
            await container.workspace_form_service().submit_response(
                workspace.id,
                new_form.form_id,
                StandardFormResponse(**formResponse),
                testUser1,
            )
        )
        response_ids = [
            user_2_response["response_id"],
            user_1_response["response_id"],
            workspace_form_response["response_id"],
        ]
        all_responses = client.get(
            form_response_api + "/all-submissions", cookies=test_user_cookies
        )
        assert all_responses.status_code == 200
        assert all_responses.json()["total"] == 3
        all_responses_response_ids = [
            item["responseId"] for item in all_responses.json()["items"]
        ]
        assert all_responses_response_ids == response_ids

    def test_unauthorized_get_all_workspace_responses(
        self, client, form_response_api, workspace_form_response, test_user_cookies_1
    ):
        all_responses = client.get(
            form_response_api + "/all-submissions", cookies=test_user_cookies_1
        )
        assert all_responses.status_code == 403
        assert (
            all_responses.json()
            == "403 - Forbidden: You don't have permission to access this resource."
        )

    async def test_get_single_user_submissions_in_workspace(
        self,
        client,
        workspace,
        form_response_api,
        test_user_cookies,
        workspace_form,
        workspace_form_response,
    ):
        new_form_response = dict(
            await container.workspace_form_service().submit_response(
                workspace.id,
                workspace_form.form_id,
                StandardFormResponse(**formResponse),
                testUser,
            )
        )
        new_user_response = dict(
            await container.workspace_form_service().submit_response(
                workspace.id,
                workspace_form.form_id,
                StandardFormResponse(**formResponse),
                testUser1,
            )
        )
        response_ids = [
            workspace_form_response["response_id"],
            new_form_response["response_id"],
        ]
        user_submission = client.get(
            form_response_api + "/submissions", cookies=test_user_cookies
        )
        assert user_submission.status_code == 200
        assert user_submission.json()["total"] == 2
        user_submission_response_ids = [
            item["responseId"] for item in user_submission.json()["items"]
        ]
        assert user_submission_response_ids == response_ids
        assert new_user_response not in user_submission_response_ids

    def test_get_workspace_form_response_by_response_id(
        self, client, form_response_api, test_user_cookies, workspace_form_response
    ):
        single_form_response = client.get(
            form_response_api
            + "/submissions/"
            + str(workspace_form_response["response_id"]),
            cookies=test_user_cookies,
        )
        assert single_form_response.status_code == 200
        assert (
            single_form_response.json()["response"]["responseId"]
            == workspace_form_response["response_id"]
        )

    def test_unauthorized_get_workspace_form_response_by_response_id(
        self, client, form_response_api, test_user_cookies_1, workspace_form_response
    ):
        single_form_response = client.get(
            form_response_api
            + "/submissions/"
            + str(workspace_form_response["response_id"]),
            cookies=test_user_cookies_1,
        )
        assert single_form_response.status_code == 403
        assert (
            single_form_response.json()
            == "You are not authorized to perform this action."
        )

    async def test_get_workspace_form_response_by_response_id_fails(
        self,
        client,
        workspace_form_1,
        form_response_api,
        workspace_1,
        test_user_cookies,
    ):
        new_form_response = dict(
            await container.workspace_form_service().submit_response(
                workspace_1.id,
                workspace_form_1.form_id,
                StandardFormResponse(**formResponse),
                testUser,
            )
        )
        single_form_response = client.get(
            form_response_api + "/submissions/" + str(new_form_response["response_id"]),
            cookies=test_user_cookies,
        )
        assert single_form_response.json() == "Form not found in this workspace"
