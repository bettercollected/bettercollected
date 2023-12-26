from typing import Any, Coroutine
from unittest.mock import patch

import httpx
import pytest
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponse
from dependency_injector import providers
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.app import get_application
from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import workspace_service
from tests.app.controllers.data import (
    formData,
    formResponse,
    user_info,
    testUser,
    testUser1,
    testUser2,
    proUser,
    invited_user,
)


@pytest.fixture
def client():
    container.database_client.override(providers.Singleton(AsyncMongoMockClient))
    app = get_application(is_test_mode=True)
    with TestClient(app) as test_client:
        return test_client


@pytest.fixture()
async def workspace():
    await workspace_service.create_workspace(testUser)
    workspace = (await WorkspaceDocument.find().to_list())[0]
    await WorkspaceUserDocument(
        workspace_id=workspace.id,
        user_id=invited_user.id,
        roles=[WorkspaceRoles.COLLABORATOR],
    ).save()
    return workspace


@pytest.fixture()
async def workspace_1():
    await workspace_service.create_workspace(testUser)
    await workspace_service.create_workspace(testUser1)
    workspace = (await WorkspaceDocument.find().to_list())[1]
    return workspace


@pytest.fixture()
async def workspace_pro():
    await container.workspace_service().create_non_default_workspace(title="Title", description="description",
                                                                     workspace_name="name",
                                                                     user=proUser)
    workspace = (await WorkspaceDocument.find().to_list())[0]
    return workspace


@pytest.fixture()
async def workspace_form(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**formData), testUser
    )
    return form


@pytest.fixture()
async def workspace_form_1(workspace_1: Coroutine[Any, Any, WorkspaceDocument]):
    form = await container.workspace_form_service().create_form(
        workspace_1.id, StandardForm(**formData), testUser1
    )
    return form


@pytest.fixture()
async def workspace_form_response(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    form_response = await container.workspace_form_service().submit_response(
        workspace.id,
        workspace_form.form_id,
        StandardFormResponse(**formResponse),
        testUser,
    )
    return dict(form_response)


@pytest.fixture()
async def workspace_form_response_1(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        workspace_form.form_id,
        StandardFormResponse(**formResponse),
        testUser1,
    )
    return dict(response)


@pytest.fixture()
async def workspace_form_response_2(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        workspace_form.form_id,
        StandardFormResponse(**formResponse),
        testUser2,
    )
    return dict(response)


@pytest.fixture()
async def workspace_group(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    group = await container.responder_groups_service().create_group(
        workspace.id,
        "Testing_Group",
        "testing_group@gmail.com",
        testUser,
        workspace_form.form_id,
        "testing_Description",
        "@gmail.com",
    )
    return group


@pytest.fixture()
def test_user_cookies():
    token = container.jwt_service().encode(testUser)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_user_cookies_1():
    token = container.jwt_service().encode(testUser1)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_pro_user_cookies():
    token = container.jwt_service().encode(proUser)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_invited_user_cookies():
    token = container.jwt_service().encode(invited_user)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def mock_aiohttp_get_request():
    async def mock_get(*args, **kwargs):
        class MockResponse:
            async def json(self):
                return user_info

        return MockResponse()

    yield patch("aiohttp.ClientSession.get", side_effect=mock_get)


@pytest.fixture()
def mock_aiohttp_post_request(
    workspace_form: Coroutine[Any, Any, FormDocument],
    workspace_form_response: Coroutine[Any, Any, dict],
):
    async def mock_post(*args, **kwargs):
        responses = StandardFormResponse(**formResponse)
        form = StandardForm(**dict(workspace_form))
        return FormImportResponse(form=form, responses=[responses])

    yield patch(
        "backend.app.services.workspace_form_service.WorkspaceFormService.convert_form",
        side_effect=mock_post,
    )


@pytest.fixture()
def mock_aiohttp_post_request_for_pro(
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
):
    async def mock_post(*args, **kwargs):
        form = await container.workspace_form_service().create_form(
            workspace_pro.id, StandardForm(**formData), proUser
        )
        return FormImportResponse(
            form=StandardForm(**form.dict()),
            responses=[StandardFormResponse(**formResponse)],
        )

    yield patch(
        "backend.app.services.workspace_form_service.WorkspaceFormService.convert_form",
        side_effect=mock_post,
    )


@pytest.fixture()
def mock_send_otp_get_request():
    yield patch(
        "backend.app.services.workspace_service.WorkspaceService.send_otp_for_workspace",
        return_value={"message": "Otp sent successfully"},
    )


@pytest.fixture()
def mock_validate_otp():
    async def get_user_after_validation_of_otp(*args, **kwargs):
        return httpx.Response(200, json={"user": testUser.dict()})

    yield patch(
        "httpx.AsyncClient.get",
        side_effect=get_user_after_validation_of_otp,
    )


@pytest.fixture()
def mock_get_user_info():
    async def get_user_info_from_ids(*args, **kwargs):
        return httpx.Response(200, json=user_info)

    return patch(
        "httpx.AsyncClient.get",
        side_effect=get_user_info_from_ids,
    )


@pytest.fixture()
def mock_create_invitation_request():
    def send_email_for_invitation(*args, **kwargs):
        return httpx.Response(200, json={"data": "Mail sent successfully!!"})

    return patch("httpx.AsyncClient.get", side_effect=send_email_for_invitation)


@pytest.fixture()
def mock_get_workspace_by_query():
    def get_workspace_by_query(*args, **kwargs):
        return httpx.Response(200, json={"workspace_owner": proUser.dict()})

    return patch("httpx.AsyncClient.get", side_effect=get_workspace_by_query)
