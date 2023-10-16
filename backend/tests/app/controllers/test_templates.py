import json
from typing import Any, Coroutine

import pytest
from aiohttp.test_utils import TestClient
from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN

from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.config import settings

template = {
    "title": "Test_template",
    "description": "Description of template",
    "buttonText": "Template_button"
}

public_template = {
    "title": "public_template",
    "settings": {
        "is_public": "true"
    }
}
private_template = {
    "title": "private_template",
    "settings": {
        "is_public": "false"
    }
}


@pytest.fixture()
async def predefined_workspace_template():
    template = FormTemplateDocument(**private_template)
    template.workspace_id = settings.template_settings.PREDEFINED_WORKSPACE_ID
    await template.save()
    return template


@pytest.fixture()
async def workspace_template(workspace: WorkspaceDocument):
    template = FormTemplateDocument(**public_template)
    template.workspace_id = workspace.id
    template = await template.save()
    return template


@pytest.fixture()
async def workspace_1_public_template(workspace_1: WorkspaceDocument):
    template = FormTemplateDocument(**public_template)
    template.workspace_id = workspace_1.id
    template = await template.save()
    return template


@pytest.fixture()
async def workspace_1_private_template(workspace_1: WorkspaceDocument):
    template = FormTemplateDocument(**private_template)
    template.workspace_id = workspace_1.id
    template = await template.save()
    return template


class TestFormTemplates:

    async def test_create_template_from_form(self, client: TestClient,
                                             workspace: WorkspaceDocument,
                                             workspace_form: WorkspaceFormDocument,
                                             test_user_cookies: dict[str, str]):
        create_template_url = f"/api/v1/workspaces/{workspace.id}/form/{workspace_form.form_id}/template"

        template = client.post(create_template_url, cookies=test_user_cookies)

        expected_template_id = ((await FormTemplateDocument.find().to_list())[0]).dict().get("id")
        actual_template_id = template.json().get("id")
        assert actual_template_id == str(expected_template_id)

    def test_unauthorized_user_create_template_from_form_fails(self, client: TestClient,
                                                               workspace: WorkspaceDocument,
                                                               workspace_form: WorkspaceFormDocument,
                                                               test_user_cookies_1: dict[str, str]):
        create_template_url = f"/api/v1/workspaces/{workspace.id}/form/{workspace_form.form_id}/template"

        template = client.post(create_template_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = template.json()
        assert template.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_import_public_template_in_workspace(self, client: TestClient,
                                                       workspace: WorkspaceDocument,
                                                       test_user_cookies: dict[str, str],
                                                       workspace_1_public_template: FormTemplateDocument):
        import_url = f"/api/v1/workspaces/{workspace.id}/template/import?template_id={workspace_1_public_template.id}"

        imported_template = client.post(import_url, cookies=test_user_cookies)

        expected_template_id = str((await FormTemplateDocument.find({"workspace_id": workspace.id}).to_list())[0].id)
        actual_template_id = imported_template.json().get("id")
        assert actual_template_id == expected_template_id

    def test_import_private_template_in_workspace(self, client: TestClient,
                                                  workspace: WorkspaceDocument,
                                                  test_user_cookies: dict[str, str],
                                                  workspace_1_private_template: FormTemplateDocument):
        import_url = f"/api/v1/workspaces/{workspace.id}/template/import?template_id={workspace_1_private_template.id}"

        imported_template = client.post(import_url, cookies=test_user_cookies)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = imported_template.json()
        assert imported_template.status_code == 403
        assert actual_response_message == expected_response_message

    def test_unauthorized_user_import_template_in_workspace(self, client: TestClient,
                                                            workspace: WorkspaceDocument,
                                                            test_user_cookies_1: dict[str, str],
                                                            workspace_1_public_template: FormTemplateDocument):
        import_url = f"/api/v1/workspaces/{workspace.id}/template/import?template_id={workspace_1_public_template.id}"

        imported_template = client.post(import_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = imported_template.json()
        assert imported_template.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_create_new_template(self, client: TestClient, workspace: WorkspaceDocument,
                                       test_user_cookies: dict[str, str]):
        create_url = f"/api/v1/workspaces/{workspace.id}/template"

        created_template = client.post(create_url, cookies=test_user_cookies,
                                       data={"template_body": json.dumps(template)})

        expected_response = await FormTemplateDocument.find({"workspace_id": workspace.id}).to_list()
        assert expected_response is not None

    def test_unauthorized_user_create_new_template(self, client: TestClient,
                                                   workspace: WorkspaceDocument,
                                                   test_user_cookies_1: dict[str, str]):
        create_url = f"/api/v1/workspaces/{workspace.id}/template"

        created_template = client.post(create_url, cookies=test_user_cookies_1,
                                       data={"template_body": json.dumps(template)})

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = created_template.json()
        assert created_template.status_code == 403
        assert actual_response_message == expected_response_message

    def test_update_template(self, client: TestClient, workspace: WorkspaceDocument, test_user_cookies: dict[str, str],
                             workspace_template: FormTemplateDocument):
        update_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_template.id}"

        updated_template = client.patch(update_url, cookies=test_user_cookies,
                                        data={"template_body": json.dumps({"title": "updated_template"})})

        expected_updated_title = "updated_template"
        actual_updated_title = updated_template.json().get("title")
        assert actual_updated_title == expected_updated_title

    def test_update_other_workspace_template_fails(self, client: TestClient, workspace: WorkspaceDocument,
                                                   test_user_cookies: dict[str, str],
                                                   workspace_1_public_template: FormTemplateDocument):
        update_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_1_public_template.id}"

        updated_template = client.patch(update_url, cookies=test_user_cookies,
                                        data={"template_body": json.dumps({"title": "updated_template"})})

        expected_response_message = "You are not allowed to update this template."
        actual_response_message = updated_template.json()
        assert updated_template.status_code == 403
        assert actual_response_message == expected_response_message

    def test_unauthorized_user_update_template_fails(self, client: TestClient, workspace: WorkspaceDocument,
                                                     test_user_cookies_1: dict[str, str],
                                                     workspace_template: FormTemplateDocument):
        update_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_template.id}"

        updated_template = client.patch(update_url, cookies=test_user_cookies_1,
                                        data={"template_body": json.dumps({"title": "updated_template"})})

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = updated_template.json()
        assert updated_template.status_code == 403
        assert actual_response_message == expected_response_message

    def test_delete_template(self, client: TestClient, workspace: WorkspaceDocument,
                             workspace_template: FormTemplateDocument, test_user_cookies: dict[str, str]):
        delete_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_template.id}"

        deleted_template = client.delete(delete_url, cookies=test_user_cookies)

        expected_deleted_template_id = str(workspace_template.id)
        actual_deleted_template_id = deleted_template.json()
        assert actual_deleted_template_id == expected_deleted_template_id

    def test_delete_other_workspace_template_fails(self, client: TestClient, workspace: WorkspaceDocument,
                                                   workspace_1_public_template: FormTemplateDocument,
                                                   test_user_cookies: dict[str, str]):
        delete_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_1_public_template.id}"

        deleted_template = client.delete(delete_url, cookies=test_user_cookies)

        expected_response_message = "You are not allowed to perform this action."
        actual_response_message = deleted_template.json()
        assert deleted_template.status_code == 403
        assert actual_response_message == expected_response_message

    def test_unauthorized_user_delete_template_fails(self, client: TestClient, workspace: WorkspaceDocument,
                                                     workspace_template: FormTemplateDocument,
                                                     test_user_cookies_1: dict[str, str]):
        delete_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_template.id}"

        deleted_template = client.delete(delete_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = deleted_template.json()
        assert deleted_template.status_code == 403
        assert actual_response_message == expected_response_message

    async def test_create_form_from_template(self, client: TestClient, workspace: WorkspaceDocument,
                                             workspace_template: FormTemplateDocument,
                                             test_user_cookies: dict[str, str]):
        create_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_template.id}"

        created_form = client.post(create_url, cookies=test_user_cookies)

        expected_form_title = workspace_template.title
        actual_form_title = created_form.json().get("title")
        assert actual_form_title == expected_form_title

    def test_unauthorized_user_create_form_from_template_fails(self, client: TestClient, workspace: WorkspaceDocument,
                                                               workspace_template: FormTemplateDocument,
                                                               test_user_cookies_1: dict[str, str]):
        create_url = f"/api/v1/workspaces/{workspace.id}/template/{workspace_template.id}"

        created_form = client.post(create_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = created_form.json()
        assert created_form.status_code == 403
        assert actual_response_message == expected_response_message

    def test_get_templates_of_predefined_workspaces(self, client: TestClient, test_user_cookies: dict[str, str],
                                                    workspace: WorkspaceDocument,
                                                    predefined_workspace_template: FormTemplateDocument,
                                                    workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates"

        templates = client.get(get_url, cookies=test_user_cookies)

        expected_template_id = str(predefined_workspace_template.id)
        actual_template_id = templates.json()[0].get("id")
        assert actual_template_id == expected_template_id

    def test_get_templates(self, client: TestClient, test_user_cookies: dict[str, str],
                           workspace: WorkspaceDocument,
                           predefined_workspace_template: FormTemplateDocument,
                           workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates?workspace_id={workspace.id}"

        templates = client.get(get_url, cookies=test_user_cookies)

        expected_template_id = str(workspace_template.id)
        actual_template_id = templates.json()[0].get("id")
        assert actual_template_id == expected_template_id

    def test_unauthorized_user_get_templates_fails(self, client: TestClient, test_user_cookies_1: dict[str, str],
                                                   workspace: WorkspaceDocument,
                                                   predefined_workspace_template: FormTemplateDocument,
                                                   workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates?workspace_id={workspace.id}"

        templates = client.get(get_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = templates.json()
        assert templates.status_code == 403
        assert actual_response_message == expected_response_message

    def test_get_template_of_predefined_workspace_by_id(self, client: TestClient, test_user_cookies: dict[str, str],
                                                        workspace: WorkspaceDocument,
                                                        predefined_workspace_template: FormTemplateDocument,
                                                        workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates/{predefined_workspace_template.id}"

        template_by_id = client.get(get_url, cookies=test_user_cookies)

        expected_template_id = str(predefined_workspace_template.id)
        actual_template_id = template_by_id.json().get("id")
        assert actual_template_id == expected_template_id

    def test_get_template_by_id(self, client: TestClient, test_user_cookies: dict[str, str],
                                workspace: WorkspaceDocument,
                                predefined_workspace_template: FormTemplateDocument,
                                workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates/{workspace_template.id}?workspace_id={workspace.id}"

        template_by_id = client.get(get_url, cookies=test_user_cookies)

        expected_template_id = str(workspace_template.id)
        actual_template_id = template_by_id.json().get("id")
        assert actual_template_id == expected_template_id

    def test_unauthorized_user_get_template_by_id(self, client: TestClient, test_user_cookies_1: dict[str, str],
                                                  workspace: WorkspaceDocument,
                                                  predefined_workspace_template: FormTemplateDocument,
                                                  workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates/{workspace_template.id}?workspace_id={workspace.id}"

        template_by_id = client.get(get_url, cookies=test_user_cookies_1)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = template_by_id.json()
        assert template_by_id.status_code == 403
        assert actual_response_message == expected_response_message

    def test_get_non_existent_template_by_id(self, client: TestClient, test_user_cookies: dict[str, str],
                                             workspace: WorkspaceDocument,
                                             predefined_workspace_template: FormTemplateDocument,
                                             workspace_template: FormTemplateDocument):
        get_url = f"/api/v1/templates/{PydanticObjectId()}?workspace_id={workspace.id}"

        template_by_id = client.get(get_url, cookies=test_user_cookies)

        expected_response = "Template not found"
        actual_response = template_by_id.json()
        assert template_by_id.status_code == 404
        assert actual_response == expected_response

    def test_get_other_workspace_private_template_by_id(self, client: TestClient, test_user_cookies: dict[str, str],
                                                        workspace: WorkspaceDocument,
                                                        workspace_1_private_template: FormTemplateDocument):
        get_url = f"/api/v1/templates/{workspace_1_private_template.id}?workspace_id={workspace.id}"

        template_by_id = client.get(get_url, cookies=test_user_cookies)

        expected_response_message = MESSAGE_FORBIDDEN
        actual_response_message = template_by_id.json()
        assert template_by_id.status_code == 403
        assert actual_response_message == expected_response_message

    def test_get_other_workspace_public_template_by_id(self, client: TestClient, test_user_cookies: dict[str, str],
                                                       workspace: WorkspaceDocument,
                                                       workspace_1_public_template: FormTemplateDocument):
        get_url = f"/api/v1/templates/{workspace_1_public_template.id}?workspace_id={workspace.id}"

        template_by_id = client.get(get_url, cookies=test_user_cookies)

        expected_template_id = str(workspace_1_public_template.id)
        actual_template_id = template_by_id.json().get("id")
        assert actual_template_id == expected_template_id
