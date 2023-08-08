from typing import Any, Coroutine

from dependency_injector import providers
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

import pytest
import httpx
from unittest.mock import patch

from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services import workspace_service
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponse
from tests.app.controllers.data import (
    formData,
    formResponse,
    user_info,
    testUser,
    testUser1,
    testUser2,
    proUser,
)

from backend.app import get_application
from backend.app.container import container


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
    return workspace


@pytest.fixture()
async def workspace_1():
    await workspace_service.create_workspace(testUser)
    await workspace_service.create_workspace(testUser1)
    workspace = (await WorkspaceDocument.find().to_list())[1]
    return workspace


@pytest.fixture()
async def workspace_pro():
    await workspace_service.create_workspace(proUser)
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
        responses = StandardFormResponse(**workspace_form_response)
        form = StandardForm(**dict(workspace_form))
        return FormImportResponse(form=form, responses=[responses])

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
