import datetime
import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormCamelModel
from backend.app.schemas.responder_group import ResponderGroupFormDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDocument,
    FormResponseDeletionRequest,
)
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
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


async def create_form_request_body(form_id: str):
    form = await container.form_repo().get_form_document_by_id(form_id)
    form_dict = {**form.model_dump(), "formId": form.model_dump().get("form_id")}
    unwanted_keys = ["id", "updated_at", "created_at", "fields"]
    for key in unwanted_keys:
        del form_dict[key]
    return {"form": form_dict, "response_data_owner": "string"}


class TestWorkspaceForm:
    async def test_publishing_form(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        publish_form_url = (
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/publish"
        )

        published_form = await client.post(publish_form_url, cookies=test_user_cookies)
        actual_response = StandardFormCamelModel(**published_form.json())
        assert workspace_form.form_id == actual_response.form_id
        assert actual_response.version is not None

    async def test_publish_upgrades_placeholder_slug_from_title(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        # A blank form (placeholder title) keeps the form id as its slug...
        blank_form = await container.workspace_form_service().create_form(
            workspace.id,
            StandardForm(**{**formData, "title": "Untitled form"}),
            testUser,
        )
        repo = container.workspace_form_service().workspace_form_repository
        wf = await repo.get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(blank_form.form_id)
        )
        assert wf.settings.custom_url == str(blank_form.form_id)

        # ...until it's titled and published, when it gets a title-based slug.
        form_doc = await container.form_repo().get_form_document_by_id(
            blank_form.form_id
        )
        form_doc.title = "Customer Feedback"
        await container.form_repo().save_form(form_doc)

        publish_url = (
            f"/api/v1/workspaces/{workspace.id}/forms/{blank_form.form_id}/publish"
        )
        response = await client.post(publish_url, cookies=test_user_cookies)
        assert response.status_code == 200

        wf_after = await repo.get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(blank_form.form_id)
        )
        assert wf_after.settings.custom_url == "customer-feedback"

    async def test_duplicate_form(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        duplicate_form_api = f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/duplicate"

        duplicate_form_response = await client.post(
            duplicate_form_api, cookies=test_user_cookies
        )

        actual_response = StandardForm(**duplicate_form_response.json())
        assert duplicate_form_response.status_code == 200
        assert actual_response.form_id != workspace_form.form_id
        assert workspace_form.fields == actual_response.fields
        assert workspace_form.description == actual_response.description
        assert workspace_form.button_text == actual_response.button_text
        assert workspace_form.logo == actual_response.logo
        assert workspace_form.cover_image == actual_response.cover_image

    async def test_unauthorized_user_form_duplication_fails(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies_1: dict[str, str],
    ):
        duplicate_form_api = f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/duplicate"

        duplicate_form_response = await client.post(
            duplicate_form_api, cookies=test_user_cookies_1
        )

        assert duplicate_form_response.status_code == 403

    async def test_unauthorized_user_form_duplication_fails(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form_1: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        duplicate_form_api = f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form_1.form_id}/duplicate"

        duplicate_form_response = await client.post(
            duplicate_form_api, cookies=test_user_cookies
        )

        assert duplicate_form_response.status_code == 404

    async def test_get_workspace_forms(
        self,
        client: AsyncClient,
        workspace_form_common_url: str,
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        mock_aiohttp_get_request,
    ):
        with mock_aiohttp_get_request:
            forms = await client.get(
                workspace_form_common_url, cookies=test_user_cookies
            )

            expected_form_id = workspace_form.form_id
            actual_form_id = forms.json()["items"][0]["formId"]
            assert actual_form_id == expected_form_id

    async def test_create_form(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
    ):
        response = await client.post(
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

    async def test_unauthorized_user_create_form_fails(
        self,
        client: AsyncClient,
        workspace_form_common_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = await client.post(
            workspace_form_common_url,
            cookies=test_user_cookies_1,
            data={"form_body": json.dumps(formData)},
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_get_workspace_form_by_id(
        self,
        client: AsyncClient,
        workspace_form_url: str,
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        mock_aiohttp_get_request,
    ):
        with mock_aiohttp_get_request:
            form = await client.get(workspace_form_url, cookies=test_user_cookies)

            expected_form_id = workspace_form.form_id
            actual_form_id = form.json().get("formId")
            assert form.status_code == 200
            assert actual_form_id == expected_form_id

    async def test_delete_workspace_form(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
        workspace_form_url: str,
    ):
        delete_form = await client.delete(workspace_form_url, cookies=test_user_cookies)

        expected_response_message = "Form deleted from workspace."
        actual_response_message = delete_form.json()
        actual_form = await container.workspace_form_repo().find_workspace_form(
            workspace.id, published_form.form_id
        )
        expected_form = None
        assert delete_form.status_code == 200
        assert actual_response_message == expected_response_message
        assert actual_form == expected_form

    async def test_delete_workspace_form_deletes_responses(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
    ):
        delete_form = await client.delete(workspace_form_url, cookies=test_user_cookies)

        actual_response = await container.form_response_repo().list_by_form_id(
            workspace_form.form_id
        )
        expected_response = []
        assert actual_response == expected_response

    async def test_delete_workspace_form_also_deletes_request_response_deletion(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        await container.form_response_service().request_for_response_deletion(
            workspace.id, workspace_form_response["response_id"], testUser
        )

        delete_form = await client.delete(workspace_form_url, cookies=test_user_cookies)

        actual_request_response_deletion = (
            await container.form_response_repo().find_deletion_request_by_response_id(
                workspace_form_response["response_id"]
            )
        )
        expected_request_response_deletion = None
        assert actual_request_response_deletion == expected_request_response_deletion

    async def test_unauthorized_user_delete_workspace_form_fails(
        self,
        client: AsyncClient,
        test_user_cookies_1: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
    ):
        unauthorized_client = await client.delete(
            workspace_form_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_update_workspace_form(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        update_form = await client.patch(
            workspace_form_url,
            cookies=test_user_cookies,
            data={"form_body": json.dumps({"description": "updated_form"})},
        )

        expected_updated_form_description = "updated_form"
        actual_updated_form_description = update_form.json()["description"]
        assert actual_updated_form_description == expected_updated_form_description

    async def test_unauthorized_user_update_workspace_form_fails(
        self,
        client: AsyncClient,
        test_user_cookies_1: dict[str, str],
        workspace_form_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        unauthorized_client = await client.patch(
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
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        submit_response_url = f"{workspace_form_url}/response"

        response = await client.post(
            submit_response_url,
            cookies=test_user_cookies,
            data={"response": json.dumps(formResponse)},
        )

        submission_uuid = response.json()
        expected_user_id = (
            await container.form_response_repo().get_by_submission_uuid(submission_uuid)
        ).submission_uuid
        assert submission_uuid == expected_user_id

    async def test_submit_non_workspace_form_response(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
    ):
        form = await container.form_service().create_form(StandardForm(**formData))
        submit_response_url = f"{workspace_form_common_url}/{form.id}/response"

        response = await client.post(
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
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        delete_response_url = (
            f"{workspace_form_url}/response/{workspace_form_response['response_id']}"
        )

        delete_response = await client.delete(
            delete_response_url, cookies=test_user_cookies
        )

        expected_deleted_response_id = workspace_form_response["response_id"]
        actual_deleted_response_id = delete_response.json()
        assert delete_response.status_code == 200
        assert actual_deleted_response_id == expected_deleted_response_id

    async def test_delete_form_response_also_deletes_request_response_deletion(
        self,
        client: AsyncClient,
        test_user_cookies: dict[str, str],
        workspace_form_url: str,
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
    ):
        delete_response_url = (
            f"{workspace_form_url}/response/{workspace_form_response['response_id']}"
        )

        delete_response = await client.delete(
            delete_response_url, cookies=test_user_cookies
        )

        actual_form_response_deletion_request = (
            await container.form_response_repo().find_deletion_request_by_response_id(
                workspace_form_response["response_id"]
            )
        )
        expected_form_response_deletion_request = None
        assert (
            actual_form_response_deletion_request
            == expected_form_response_deletion_request
        )

    async def test_search_form_in_workspace(
        self,
        client: AsyncClient,
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

            search_form = await client.post(search_form_url, cookies=test_user_cookies)

            expected_title_and_form_id = ["search_form", form.form_id]
            actual_title_and_form_id = [
                search_form.json()[0]["title"],
                search_form.json()[0]["formId"],
            ]
            assert search_form.status_code == 200
            assert actual_title_and_form_id == expected_title_and_form_id

    async def test_patch_setting_in_workspace(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        patch_setting_url = (
            f"{workspace_form_common_url}/{workspace_form.form_id}/settings"
        )

        patch_settings = await client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        expected_response = {
            "settings": {**workspace_settings, "embedUrl": None, "provider": "self"}
        }
        actual_response = patch_settings.json()
        assert patch_settings.status_code == 200
        assert actual_response == expected_response

    async def test_patch_form_close_date_in_workspace_form(
        self,
        client: AsyncClient,
        workspace: WorkspaceDocument,
        workspace_form_common_url: str,
        workspace_form: FormDocument,
        test_user_cookies: dict[str, str],
    ):
        patch_url = f"{workspace_form_common_url}/{workspace_form.form_id}/settings"
        close_date = datetime.datetime.now(datetime.timezone.utc).isoformat()

        patch_settings = await client.patch(
            patch_url, cookies=test_user_cookies, json={"formCloseDate": close_date}
        )

        actual_response = patch_settings.json()
        assert patch_settings.status_code == 200
        assert close_date == actual_response.get("settings").get("formCloseDate")

    async def test_multiple_same_patch_setting_in_workspace_fails(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        patch_setting_url = (
            f"{workspace_form_common_url}/{workspace_form.form_id}/settings"
        )
        patch_settings = await client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        same_patch_settings = await client.patch(
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
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form_common_url: str,
        test_user_cookies: dict[str, str],
    ):
        form = await container.form_service().create_form(StandardForm(**formData))
        patch_setting_url = f"{workspace_form_common_url}/{form.form_id}/settings"

        non_workspace_form_setting = await client.patch(
            patch_setting_url, cookies=test_user_cookies, json=workspace_settings
        )

        expected_response_message = "Form not found in workspace"
        actual_response_message = non_workspace_form_setting.json()
        assert non_workspace_form_setting.status_code == 404
        assert actual_response_message == expected_response_message

    async def test_add_form_in_group(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        get_workspace_group_url: str,
        workspace_group: Coroutine,
        test_user_cookies: dict[str, str],
    ):
        group_form = await client.patch(
            get_workspace_group_url,
            cookies=test_user_cookies,
            json={"group_ids": [str(workspace_group.id)]},
        )

        expected_added_form = (
            await container.responder_groups_repository().get_emails_in_group(
                workspace_group.id
            )
        )["forms"][0]
        actual_added_form = group_form.json()[0]["form_id"]
        assert group_form.status_code == 200
        assert actual_added_form == expected_added_form

    async def test_unauthorized_user_add_form_in_group_fails(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_group: Coroutine,
        workspace_form: Coroutine[Any, Any, FormDocument],
        get_workspace_group_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        unauthorized_client = await client.patch(
            get_workspace_group_url,
            cookies=test_user_cookies_1,
            json={"group_ids": [str(workspace_group.id)]},
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_delete_form_from_group(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
        workspace_group: Coroutine,
        test_user_cookies: dict[str, str],
    ):
        delete_form_from_group_url = (
            f"{workspace_form_url}/groups?group_id={workspace_group.id}"
        )

        group_form = await client.delete(
            delete_form_from_group_url, cookies=test_user_cookies
        )

        actual_form = (
            await container.responder_groups_repository().get_emails_in_group(
                workspace_group.id
            )
        )["forms"]
        expected_form = []
        assert group_form.status_code == 200
        assert actual_form == expected_form

    async def test_unauthorized_user_delete_form_from_group_fails(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_group: Coroutine,
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_url: str,
        test_user_cookies_1: dict[str, str],
    ):
        delete_form_from_group_url = (
            f"{workspace_form_url}/groups?group_id={workspace_group.id}"
        )

        unauthorized_client = await client.delete(
            delete_form_from_group_url, cookies=test_user_cookies_1
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_import_form_to_workspace(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        workspace_form: Coroutine[Any, Any, FormDocument],
        workspace_form_common_url: str,
        workspace_form_response_for_test: Coroutine[Any, Any, dict],
        mock_aiohttp_post_request,
    ):
        with mock_aiohttp_post_request:
            form_body = await create_form_request_body(workspace_form.form_id)
            import_form_url = f"{workspace_form_common_url}/import/google"

            import_form = await client.post(
                import_form_url, cookies=test_user_cookies, json=form_body
            )

            actual_response = import_form.json()
            assert import_form.status_code == 200
            assert actual_response.get("title") == form_body.get("form").get("title")

    async def test_unauthorized_user_import_form_to_workspace_fails(
        self,
        client: AsyncClient,
        test_user_cookies_1: dict[str, str],
        workspace_form_common_url: str,
    ):
        import_form_url = f"{workspace_form_common_url}/import/google"

        unauthorized_client = await client.post(
            import_form_url, cookies=test_user_cookies_1, json=test_form_import_data
        )

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = unauthorized_client.json()
        assert unauthorized_client.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_import_form_imported_in_other_workspace_fails(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        # published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        workspace_form_1: Coroutine[Any, Any, FormDocument],
        workspace_form_common_url: str,
        workspace_form_response: Coroutine[Any, Any, dict],
        mock_aiohttp_post_request,
    ):
        with mock_aiohttp_post_request:
            form_body = await create_form_request_body(workspace_form_1.form_id)
            import_form_url = f"{workspace_form_common_url}/import/google"

            import_form = await client.post(
                import_form_url, cookies=test_user_cookies, json=form_body
            )

            expected_response = "Form has already been imported to another workspace"
            actual_response = import_form.json()
            assert import_form.status_code == 409
            assert actual_response == expected_response

    async def test_pro_user_can_import_more_than_100_form(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict[str, str],
        mock_aiohttp_post_request_for_pro,
    ):
        first_form = None
        for i in range(101):
            created = await container.workspace_form_service().create_form(
                workspace_pro.id, StandardForm(**formData), proUser
            )
            first_form = first_form or created
        form_body = await create_form_request_body(first_form.form_id)
        import_form_url = f"/api/v1/workspaces/{workspace_pro.id}/forms/import/google"

        with mock_aiohttp_post_request_for_pro:
            import_form = await client.post(
                import_form_url, cookies=test_pro_user_cookies, json=form_body
            )

            actual_response = import_form.json()
            assert import_form.status_code == 200
            assert actual_response.get("title") == form_body.get("form").get("title")

    async def test_normal_user_can_import_beyond_100_forms(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        workspace_form_common_url: str,
        mock_aiohttp_post_request,
    ):
        # Forms are unlimited on every plan — importing past the old 100-form
        # cap must succeed, not return the "Upgrade plan" 403.
        for i in range(101):
            await container.workspace_form_service().create_form(
                workspace.id, StandardForm(**formData), testUser
            )
        form_body = await create_form_request_body(published_form.form_id)
        import_form_url = f"{workspace_form_common_url}/import/google"

        with mock_aiohttp_post_request:
            import_form = await client.post(
                import_form_url, cookies=test_user_cookies, json=form_body
            )
            assert import_form.status_code == 200
            assert import_form.json() != "Upgrade plan to import more forms"
