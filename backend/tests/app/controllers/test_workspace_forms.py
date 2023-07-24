import asyncio

import pytest
from beanie import PydanticObjectId
from unittest.mock import patch

from backend.app.container import container
from backend.app.schemas.responder_group import ResponderGroupFormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument, FormResponseDeletionRequest
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services import workspace_service
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponse
from common.models.user import User
from tests.app.controllers.data import formData, formResponse, workspace_settings, user_info, formData_2, \
    test_form_import_data

testUser = User(id=str(PydanticObjectId()), sub="test@email.com")
testUser1 = User(id=str(PydanticObjectId()), sub="test1@email.com")


@pytest.fixture()
def client(client_test):
    yield client_test
    # TODO might have to delete database


@pytest.fixture()
def workspace():
    asyncio.run(workspace_service.create_workspace(testUser))
    workspace = (asyncio.run(WorkspaceDocument.find().to_list()))[0]
    yield workspace


@pytest.fixture()
def workspace_api(workspace):
    yield '/api/v1/workspaces/' + str(workspace.id) + '/forms'


@pytest.fixture()
def workspace_form(workspace):
    form = asyncio.run(container.workspace_form_service().create_form
                       (workspace.id, StandardForm(**formData), testUser))
    yield form


@pytest.fixture()
def workspace_form_response(workspace, workspace_form):
    response = dict(asyncio.run(container.workspace_form_service().submit_response(workspace.id,
                                                                                   workspace_form.form_id,
                                                                                   StandardFormResponse(**formResponse),
                                                                                   testUser)))
    yield response


@pytest.fixture()
def workspace_group(workspace, workspace_form):
    group = asyncio.run(container.responder_groups_service().create_group(workspace.id, "Testing_Group",
                                                                          "testing_group@gmail.com", testUser,
                                                                          workspace_form.form_id, "testing_Description",
                                                                          "@gmail.com"))
    yield group


@pytest.fixture()
def test_user_cookies():
    token = container.jwt_service().encode(testUser)
    return {
        "Authorization": token,
        "RefreshToken": token
    }


@pytest.fixture()
def test_user_cookies_1():
    token = container.jwt_service().encode(testUser1)
    return {
        "Authorization": token,
        "RefreshToken": token
    }


@pytest.fixture()
def mock_aiohttp_get_request():
    async def mock_get(*args, **kwargs):
        class MockResponse:
            async def json(self):
                return user_info

        return MockResponse()

    yield patch('aiohttp.ClientSession.get', side_effect=mock_get)


@pytest.fixture()
def mock_aiohttp_post_request(workspace_form, workspace_form_response):
    async def mock_post(*args, **kwargs):
        # class MockResponse:
        #     async def json(self):
        #         return StandardForm(**formData)
        responses = StandardFormResponse(**workspace_form_response)
        form = StandardForm(**dict(workspace_form))
        return FormImportResponse(form=form, responses=[responses])

    yield patch('backend.app.services.workspace_form_service.WorkspaceFormService.convert_form', side_effect=mock_post)


@pytest.mark.asyncio
class TestWorkspaceForm:
    def test_get_workspace_forms(self, client, workspace_api, test_user_cookies, workspace_form,
                                 mock_aiohttp_get_request):
        with mock_aiohttp_get_request:
            form = workspace_form
            forms = client.get(workspace_api, cookies=test_user_cookies)
            assert forms.json()["items"][0]["formId"] == workspace_form.form_id

    async def test_create_form(self, client, test_user_cookies, workspace_api, workspace):
        response = client.post(
            workspace_api,
            cookies=test_user_cookies,
            json=formData)
        assert response.status_code == 200
        # db_form = (await FormDocument.find().to_list())
        form_ids = await container.workspace_form_service().get_form_ids_in_workspace(workspace.id)
        response_form = dict(response.json())
        assert response_form['formId'] in form_ids

    def test_unauthorized_user_create_form_fails(self, client, workspace_api, test_user_cookies_1):
        response = client.post(
            workspace_api,
            cookies=test_user_cookies_1,
            json=formData
        )
        assert response.status_code == 403

    def test_get_workspace_form_by_id(self, client, workspace_api, test_user_cookies, workspace_form,
                                      mock_aiohttp_get_request):
        with mock_aiohttp_get_request:
            form = client.get(workspace_api + '/' + str(workspace_form.form_id),
                              cookies=test_user_cookies)
            assert form.status_code == 200
            assert form.json()["formId"] == workspace_form.form_id

    async def test_delete_workspace_form(self, client, test_user_cookies, workspace, workspace_form, workspace_api):
        form_response = dict(await container.workspace_form_service().submit_response(workspace.id,
                                                                                      workspace_form.form_id,
                                                                                      StandardFormResponse(
                                                                                          **formResponse), testUser))
        await container.form_response_service().request_for_response_deletion(
            workspace.id, form_response["response_id"], testUser
        )
        delete_form = client.delete(workspace_api + '/' + str(workspace_form.form_id),
                                    cookies=test_user_cookies)
        assert delete_form.status_code == 200
        assert delete_form.json() == "Form deleted from workspace."
        form = await WorkspaceFormDocument.find_one({
            "id": workspace.id
        })
        assert form is None
        response = (await FormResponseDocument.find_one(
            {"form_id": workspace_form.form_id}
        ))
        assert response is None
        request_response_deletion = await FormResponseDeletionRequest.find_one(
            {"response_id": form_response["response_id"]}
        )
        assert request_response_deletion is None

    async def test_unauthorized_user_delete_workspace_form(self, client, test_user_cookies_1,
                                                           workspace_form, workspace_api):
        delete_form = client.delete(workspace_api + '/' + str(workspace_form.form_id),
                                    cookies=test_user_cookies_1)
        assert delete_form.status_code == 403

    def test_update_workspace_form(self, client, test_user_cookies, workspace_api, workspace_form):
        update_form = client.patch(workspace_api + '/' + str(workspace_form.form_id),
                                   cookies=test_user_cookies,
                                   json={"description": "updated_form"})
        assert update_form.json()["description"] == "updated_form"

    def test_unauthorized_user_update_workspace_form(self, client, test_user_cookies_1, workspace_api
                                                     , workspace_form):
        update_form = client.patch(workspace_api + '/' + str(workspace_form.form_id),
                                   cookies=test_user_cookies_1,
                                   json={"description": "updated_form"})
        assert update_form.status_code == 403

    async def test_submit_workspace_form_response(self, client, test_user_cookies, workspace_api, workspace_form):
        response = client.post(
            workspace_api + '/' + str(workspace_form.form_id) + '/response',
            cookies=test_user_cookies
            , json=formResponse)
        assert response.json()['dataOwnerIdentifier'] == testUser.sub
        form_response = (await FormResponseDocument.find().to_list())[0]
        assert response.json()['response_id'] in form_response.response_id

    async def test_submit_non_workspace_form_response(self, client, test_user_cookies, workspace_api):
        form = await container.form_service().create_form(StandardForm(**formData))
        response = client.post(
            workspace_api + '/' + str(form.id) + '/response',
            cookies=test_user_cookies
            , json=formResponse)
        assert response.status_code == 404
        assert response.json() == "Form not found"

    async def test_delete_form_response(self, client, test_user_cookies, workspace_api,
                                        workspace_form, workspace_form_response):
        deleted_response = client.delete(workspace_api + '/' +
                                         str(workspace_form.form_id) + '/response/' +
                                         str(workspace_form_response['response_id']),
                                         cookies=test_user_cookies)
        assert deleted_response.status_code == 200
        assert deleted_response.json() == workspace_form_response['response_id']
        form_response_deletion_request = await FormResponseDeletionRequest.find_one({
            "response_id": workspace_form_response['response_id']
        })
        assert form_response_deletion_request is None

    async def test_search_form_in_workspace(self, client, test_user_cookies,
                                            workspace_api, workspace, mock_aiohttp_get_request):
        with mock_aiohttp_get_request:
            form = await container.workspace_form_service().create_form(workspace.id,
                                                                        StandardForm(**formData_2), testUser)
            search_form = client.post(workspace_api + '/search?query=search_form', cookies=test_user_cookies)
            assert search_form.status_code == 200
            assert search_form.json()[0]["title"] == "search_form"
            assert search_form.json()[0]['formId'] == form.form_id

    def test_patch_setting_in_workspace(self, client, workspace, workspace_api, workspace_form, test_user_cookies):
        patch_settings = client.patch(workspace_api + '/' + str(workspace_form.form_id) + '/settings',
                                      cookies=test_user_cookies,
                                      json=workspace_settings)
        assert patch_settings.status_code == 200
        assert patch_settings.json() == {'settings': {**workspace_settings, 'embedUrl': None, 'provider': 'self'}}

    async def test_failure_case_for_patch_setting_in_workspace(self, client, workspace, workspace_api,
                                                               workspace_form, test_user_cookies):
        patch_settings = client.patch(workspace_api + '/' + str(workspace_form.form_id) + '/settings',
                                      cookies=test_user_cookies,
                                      json=workspace_settings)
        same_patch_settings = client.patch(workspace_api + '/' + str(workspace_form.form_id) + '/settings',
                                           cookies=test_user_cookies,
                                           json=workspace_settings)
        assert same_patch_settings.status_code == 409
        assert same_patch_settings.json() == "Form with given custom slug already exists in the workspace!!"
        form = await container.form_service().create_form(StandardForm(**formData))
        non_workspace_form_setting = client.patch(workspace_api + '/' + str(form.form_id) + '/settings',
                                                  cookies=test_user_cookies,
                                                  json=workspace_settings)
        assert non_workspace_form_setting.status_code == 404

    async def test_add_form_in_group(self, client, workspace, workspace_form,
                                     workspace_api, workspace_group, test_user_cookies):
        group_form = client.patch(workspace_api + '/' + str(workspace_form.form_id) +
                                  '/groups/add?group_id=' + str(workspace_group.id),
                                  cookies=test_user_cookies)
        added_form = (await ResponderGroupFormDocument.find().to_list())[0]
        assert group_form.status_code == 200
        assert group_form.json()["form_id"] == added_form.form_id == workspace_form.form_id

    def test_unauthorized_user_add_form_in_group(self, client, workspace, workspace_group,
                                                 workspace_form, workspace_api,
                                                 test_user_cookies_1):
        group_form = client.patch(workspace_api + '/' + str(workspace_form.form_id) +
                                  '/groups/add?group_id=' + str(workspace_group.id),
                                  cookies=test_user_cookies_1)
        assert group_form.status_code == 403

    async def test_delete_form_from_group(self, client, workspace, workspace_form,
                                          workspace_api, workspace_group, test_user_cookies):
        group_form = client.delete(workspace_api + '/' + str(workspace_form.form_id) +
                                   '/groups?group_id=' + str(workspace_group.id),
                                   cookies=test_user_cookies)
        assert group_form.status_code == 200
        form = await ResponderGroupFormDocument.find_one({"form_id": workspace_form.form_id,
                                                          "group_id": workspace_group.id})
        f = (await WorkspaceFormDocument.find_one({
            "form_id": workspace_form.form_id
        }))
        assert f.form_id == workspace_form.form_id
        assert form is None

    def test_unauthorized_user_delete_form_from_group(self, client, workspace, workspace_group,
                                                      workspace_form, workspace_api,
                                                      test_user_cookies_1):
        group_form = client.delete(workspace_api + '/' + str(workspace_form.form_id) +
                                   '/groups?group_id=' + str(workspace_group.id),
                                   cookies=test_user_cookies_1)
        assert group_form.status_code == 403

    async def test_request_for_delete_form_response(self, client, test_user_cookies, workspace,
                                                    workspace_form, workspace_form_response):
        request_response_deletion = client.delete('/api/v1/workspaces/' + str(workspace.id) + '/submissions/' +
                                                  str(workspace_form_response['response_id']),
                                                  cookies=test_user_cookies)
        assert request_response_deletion.status_code == 200
        assert request_response_deletion.json() == {'message': 'Request for deletion created successfully.'}
        form_response_deletion_request = await FormResponseDeletionRequest.find().to_list()
        assert form_response_deletion_request[0].response_id == workspace_form_response['response_id']
        request_response_deletion_2 = client.delete('/api/v1/workspaces/' + str(workspace.id) + '/submissions/' +
                                                    str(workspace_form_response['response_id']),
                                                    cookies=test_user_cookies)
        assert request_response_deletion_2.json() == 'Error: Deletion request already exists for the response : ' \
               + str(workspace_form_response['response_id'])
        deleted_requested_form = client.delete('/api/v1/workspaces/' + str(workspace.id) + '/forms/'
                                               + str(workspace_form.form_id) + '/response/' +
                                               str(workspace_form_response['response_id']),
                                               cookies=test_user_cookies)
        assert deleted_requested_form.status_code == 200
        assert deleted_requested_form.json() == workspace_form_response['response_id']

    def test_unauthorized_user_request_for_delete_form_response(self, client, test_user_cookies_1,
                                                                workspace, workspace_form_response):
        request_response_deletion = client.delete('/api/v1/workspaces/' + str(workspace.id) + '/submissions/' +
                                                  str(workspace_form_response['response_id']),
                                                  cookies=test_user_cookies_1)
        assert request_response_deletion.status_code == 403
        assert request_response_deletion.json() == "You are not authorized to perform this action."

    def test_import_form_to_workspace(self, client, workspace, test_user_cookies, workspace_form,
                                      workspace_api, mock_aiohttp_post_request, workspace_form_response):
        with mock_aiohttp_post_request:
            import_form = client.post(workspace_api + '/import/google', cookies=test_user_cookies,
                                      json=test_form_import_data)
            assert import_form.status_code == 200
            assert import_form.json() == {'message': 'Import successful.'}
