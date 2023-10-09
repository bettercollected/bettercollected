import json
from typing import Any, Coroutine, Generator

import pytest
from aiohttp.test_utils import TestClient

from backend.app.container import container
from backend.app.schemas.responder_group import ResponderGroupFormDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDocument,
    FormResponseDeletionRequest,
)
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.constants import MESSAGE_FORBIDDEN
from common.models.form_import import FormImportRequestBody
from common.models.standard_form import StandardForm, StandardFormResponse
from tests.app.controllers.data import (
    formData,
    formResponse,
    workspace_settings,
    formData_2,
    test_form_import_data,
    testUser,
    proUser,
)


@pytest.fixture()
def workspace_form_common_url(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    return f"/api/v1/workspaces/{workspace.id}/forms"


@pytest.fixture()
def workspace_form_url(
    workspace_form_common_url: str, workspace_form: Coroutine[Any, Any, FormDocument]
):
    return f"{workspace_form_common_url}/{workspace_form.form_id}"


@pytest.fixture()
def get_workspace_group_url(
    workspace_form_common_url: str,
    workspace_form: Coroutine[Any, Any, FormDocument],
    workspace_group: Coroutine,
):
    return f"{workspace_form_common_url}/{workspace_form.form_id}/groups/add"


async def create_form_request_body():
    form = (await FormDocument.find().to_list())[0]
    form_dict = {**form.dict(), "formId": form.dict().get("form_id")}
    unwanted_keys = ["id", "updated_at", "created_at", "fields"]
    for key in unwanted_keys:
        del form_dict[key]
    return {"form": form_dict, "response_data_owner": "string"}


class TestWorkspaceForm:
    def test_get_workspace_forms(
        self,
        client: TestClient,
        workspace_form_common_url: str,
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        mock_aiohttp_get_request,
    ):
        with mock_aiohttp_get_request:
            forms = client.get(workspace_form_common_url, cookies=test_user_cookies)

            expected_form_id = workspace_form.form_id
            actual_form_id = forms.json()["items"][0]["formId"]
            assert actual_form_id == expected_form_id

    async def test_create_form(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
    ):
        response = client.post(
            workspace_form_common_url,
            cookies=test_user_cookies,
            data={"form_body": json.dumps(formData)},
        )

        actual_form_id = dict(response.json())["formId"]
        expected_form_ids = (
            await container.workspace_form_service().get_form_ids_in_workspace(
                workspace.id
            )
        )
        assert response.status_code == 200
        assert actual_form_id in expected_form_ids

    def test_unauthorized_user_create_form_fails(
        self,
        client: TestClient,
        workspace_form_common_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = client.post(
            workspace_form_common_url,
            cookies=test_user_cookies_1,
            data={"form_body": json.dumps(formData)},
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    def test_get_workspace_form_by_id(
        self,
        client: TestClient,
        workspace_form_url: str,
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        mock_aiohttp_get_request,
    ):
        with mock_aiohttp_get_request:
            form = client.get(workspace_form_url, cookies=test_user_cookies)

            expected_form_id = workspace_form.form_id
            actual_form_id = form.json().get("formId")
            assert form.status_code == 200
            assert actual_form_id == expected_form_id

    async def test_delete_workspace_form(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
        workspace_form_url: str,
    ):
        delete_form = client.delete(workspace_form_url, cookies=test_user_cookies)

        expected_response_message = "Form deleted from workspace."
        actual_response_message = delete_form.json()
        actual_form = await WorkspaceFormDocument.find_one({"id": workspace.id})
        expected_form = None
        assert delete_form.status_code == 200
        assert actual_response_message == expected_response_message
        assert actual_form == expected_form

    async def test_delete_workspace_form_deletes_responses(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
    ):
        delete_form = client.delete(workspace_form_url, cookies=test_user_cookies)

        actual_response = await FormResponseDocument.find_one(
            {"form_id": workspace_form.form_id}
        )
        expected_response = None
        assert actual_response == expected_response

    async def test_delete_workspace_form_also_deletes_request_response_deletion(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        await container.form_response_service().request_for_response_deletion(
            workspace.id, workspace_form_response["response_id"], testUser
        )

        delete_form = client.delete(workspace_form_url, cookies=test_user_cookies)

        actual_request_response_deletion = await FormResponseDeletionRequest.find_one(
            {"response_id": workspace_form_response["response_id"]}
        )
        expected_request_response_deletion = None
        assert actual_request_response_deletion == expected_request_response_deletion

    async def test_unauthorized_user_delete_workspace_form_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
    ):
        unauthorized_client = client.delete(
            workspace_form_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    def test_update_workspace_form(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        update_form = client.patch(
            workspace_form_url,
            cookies=test_user_cookies,
            data={"form_body": json.dumps({"description": "updated_form"})},
        )

        expected_updated_form_description = "updated_form"
        actual_updated_form_description = update_form.json()["description"]
        assert actual_updated_form_description == expected_updated_form_description

    def test_unauthorized_user_update_workspace_form_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        unauthorized_client = client.patch(
            workspace_form_url,
            cookies=test_user_cookies_1,
            data={"form_body": json.dumps({"description": "updated_form"})},
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_submit_workspace_form_response(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        submit_response_url = f"{workspace_form_url}/response"

        response = client.post(
            submit_response_url,
            cookies=test_user_cookies,
            data={"response": json.dumps(formResponse)},
        )

        actual_user_id = response.json()
        expected_user_id = (
            await FormResponseDocument.find_one({"response_id": actual_user_id})
        ).response_id
        assert actual_user_id == expected_user_id

    async def test_submit_non_workspace_form_response(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
    ):
        form = await container.form_service().create_form(StandardForm(**formData))
        submit_response_url = f"{workspace_form_common_url}/{form.id}/response"

        response = client.post(
            submit_response_url,
            cookies=test_user_cookies,
            data={"response": json.dumps(formResponse)},
        )

        expected_response_message = "Form not found"
        actual_response_message = response.json()
        assert response.status_code == 404
        assert actual_response_message == expected_response_message

    async def test_delete_form_response(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        delete_response_url = (
            f"{workspace_form_url}/response/{workspace_form_response['response_id']}"
        )

        delete_response = client.delete(delete_response_url, cookies=test_user_cookies)

        expected_deleted_response_id = workspace_form_response["response_id"]
        actual_deleted_response_id = delete_response.json()
        assert delete_response.status_code == 200
        assert actual_deleted_response_id == expected_deleted_response_id

    async def test_delete_form_response_also_deletes_request_response_deletion(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        delete_response_url = (
            f"{workspace_form_url}/response/{workspace_form_response['response_id']}"
        )

        delete_response = client.delete(delete_response_url, cookies=test_user_cookies)

        actual_form_response_deletion_request = (
            await FormResponseDeletionRequest.find_one(
                {"response_id": workspace_form_response["response_id"]}
            )
        )
        expected_form_response_deletion_request = None
        assert (
            actual_form_response_deletion_request
            == expected_form_response_deletion_request
        )

    async def test_search_form_in_workspace(
        self,
        client: TestClient,
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        mock_aiohttp_get_request,
    ):
        with mock_aiohttp_get_request:
            search_form_url = f"{workspace_form_common_url}/search?query=search_form"
            form = await container.workspace_form_service().create_form(
                workspace.id, StandardForm(**formData_2), testUser
            )

            search_form = client.post(search_form_url, cookies=test_user_cookies)

            expected_title_and_form_id = ["search_form", form.form_id]
            actual_title_and_form_id = [
                search_form.json()[0]["title"],
                search_form.json()[0]["formId"],
            ]
            assert search_form.status_code == 200
            assert actual_title_and_form_id == expected_title_and_form_id

    def test_patch_setting_in_workspace(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        patch_setting_url = (
            f"{workspace_form_common_url}/{workspace_form.form_id}/settings"
        )

        patch_settings = client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        expected_response = {
            "settings": {**workspace_settings, "embedUrl": None, "provider": "self"}
        }
        actual_response = patch_settings.json()
        assert patch_settings.status_code == 200
        assert actual_response == expected_response

    def test_multiple_same_patch_setting_in_workspace_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        patch_setting_url = (
            f"{workspace_form_common_url}/{workspace_form.form_id}/settings"
        )
        patch_settings = client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        same_patch_settings = client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        expected_response = (
            "Form with given custom slug already exists in the workspace!!"
        )
        actual_response = same_patch_settings.json()
        assert same_patch_settings.status_code == 409
        assert actual_response == expected_response

    async def test_patch_setting_on_non_workspace_form_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        test_user_cookies: dict[str, str],
    ):
        form = await container.form_service().create_form(StandardForm(**formData))
        patch_setting_url = f"{workspace_form_common_url}/{form.form_id}/settings"

        non_workspace_form_setting = client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        expected_response_message = "Form not found in workspace"
        actual_response_message = non_workspace_form_setting.json()
        assert non_workspace_form_setting.status_code == 404
        assert actual_response_message == expected_response_message

    async def test_add_form_in_group(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        get_workspace_group_url: str,
        workspace_group: Coroutine,
        test_user_cookies: dict[str, str],
    ):
        group_form = client.patch(get_workspace_group_url, cookies=test_user_cookies,json={"group_ids": [str(workspace_group.id)]})

        expected_added_form = (await ResponderGroupFormDocument.find().to_list())[
            0
        ].form_id
        actual_added_form = group_form.json()[0]["form_id"]
        assert group_form.status_code == 200
        assert actual_added_form == expected_added_form

    def test_unauthorized_user_add_form_in_group_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_group: Coroutine,
        workspace_form: Coroutine[Any, Any, FormDocument],
        get_workspace_group_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = client.patch(
            get_workspace_group_url, cookies=test_user_cookies_1,json={"group_ids": [str(workspace_group.id)]}
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_delete_form_from_group(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
        workspace_group: Coroutine,
        test_user_cookies: dict[str, str],
    ):
        delete_form_from_group_url = (
            f"{workspace_form_url}/groups?group_id={workspace_group.id}"
        )

        group_form = client.delete(
            delete_form_from_group_url, cookies=test_user_cookies
        )

        actual_form = await ResponderGroupFormDocument.find_one(
            {"form_id": workspace_form.form_id, "group_id": workspace_group.id}
        )
        expected_form = None
        assert group_form.status_code == 200
        assert actual_form == expected_form

    def test_unauthorized_user_delete_form_from_group_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_group: Coroutine,
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        delete_form_from_group_url = (
            f"{workspace_form_url}/groups?group_id={workspace_group.id}"
        )

        unauthorized_client = client.delete(
            delete_form_from_group_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_import_form_to_workspace(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_common_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
        mock_aiohttp_post_request,
    ):
        with mock_aiohttp_post_request:
            form_body = await create_form_request_body()
            import_form_url = f"{workspace_form_common_url}/import/google"

            import_form = client.post(
                import_form_url, cookies=test_user_cookies, json=form_body
            )

            expected_response = {"message": "Import successful."}
            actual_response = import_form.json()
            assert import_form.status_code == 200
            assert actual_response == expected_response

    def test_unauthorized_user_import_form_to_workspace_fails(
        self,
        client: TestClient,
        test_user_cookies_1: dict[str, str],
        workspace_form_common_url: str,
    ):
        import_form_url = f"{workspace_form_common_url}/import/google"

        unauthorized_client = client.post(
            import_form_url, cookies=test_user_cookies_1, json=test_form_import_data
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_import_form_imported_in_other_workspace_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        workspace_form_1: Coroutine[Any, Any, FormDocument],
        workspace_form_common_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
        mock_aiohttp_post_request,
    ):
        with mock_aiohttp_post_request:
            form_body = await create_form_request_body()
            import_form_url = f"{workspace_form_common_url}/import/google"

            import_form = client.post(
                import_form_url, cookies=test_user_cookies, json=form_body
            )

            expected_response = "Form has already been imported to another workspace"
            actual_response = import_form.json()
            assert import_form.status_code == 409
            assert actual_response == expected_response

    async def test_pro_user_can_import_more_than_100_form(
        self,
        client: TestClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict[str, str],
        mock_aiohttp_post_request_for_pro,
    ):
        for i in range(101):
            await container.workspace_form_service().create_form(
                workspace_pro.id, StandardForm(**formData), proUser
            )
        form_body = await create_form_request_body()
        import_form_url = f"/api/v1/workspaces/{workspace_pro.id}/forms/import/google"

        with mock_aiohttp_post_request_for_pro:
            import_form = client.post(
                import_form_url, cookies=test_pro_user_cookies, json=form_body
            )

            expected_response = {"message": "Import successful."}
            actual_response = import_form.json()
            assert import_form.status_code == 200
            assert actual_response == expected_response

    async def test_normal_user_importing_more_than_100_form_fails(
        self,
        client: TestClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
        mock_aiohttp_post_request,
    ):
        for i in range(101):
            await container.workspace_form_service().create_form(
                workspace.id, StandardForm(**formData), testUser
            )
        form_body = await create_form_request_body()
        import_form_url = f"{workspace_form_common_url}/import/google"

        with mock_aiohttp_post_request:
            import_form = client.post(
                import_form_url, cookies=test_user_cookies, json=form_body
            )

            expected_response = "Upgrade plan to import more forms"
            actual_response = import_form.json()
            assert import_form.status_code == 403
            assert actual_response == expected_response
