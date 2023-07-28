from dependency_injector import providers
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient
import asyncio

import pytest
from unittest.mock import patch

from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
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
)

from backend.app import get_application
from backend.app.container import container


@pytest.fixture
def client_test():
    container.database_client.override(providers.Singleton(AsyncMongoMockClient))
    app = get_application(is_test_mode=True)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def workspace():
    asyncio.run(workspace_service.create_workspace(testUser))
    workspace = (asyncio.run(WorkspaceDocument.find().to_list()))[0]
    yield workspace


@pytest.fixture()
def workspace_1():
    asyncio.run(workspace_service.create_workspace(testUser))
    asyncio.run(workspace_service.create_workspace(testUser1))
    workspace = (asyncio.run(WorkspaceDocument.find().to_list()))[1]
    yield workspace


@pytest.fixture()
def workspace_form(workspace):
    form = asyncio.run(
        container.workspace_form_service().create_form(
            workspace.id, StandardForm(**formData), testUser
        )
    )
    yield form


@pytest.fixture()
def workspace_form_1(workspace_1):
    form = asyncio.run(
        container.workspace_form_service().create_form(
            workspace_1.id, StandardForm(**formData), testUser1
        )
    )
    yield form


@pytest.fixture()
def workspace_form_response(workspace, workspace_form):
    response = dict(
        asyncio.run(
            container.workspace_form_service().submit_response(
                workspace.id,
                workspace_form.form_id,
                StandardFormResponse(**formResponse),
                testUser,
            )
        )
    )
    yield response


@pytest.fixture()
def workspace_form_response_1(workspace, workspace_form):
    response = dict(
        asyncio.run(
            container.workspace_form_service().submit_response(
                workspace.id,
                workspace_form.form_id,
                StandardFormResponse(**formResponse),
                testUser1,
            )
        )
    )
    yield response


@pytest.fixture()
def workspace_form_response_2(workspace, workspace_form):
    response = dict(
        asyncio.run(
            container.workspace_form_service().submit_response(
                workspace.id,
                workspace_form.form_id,
                StandardFormResponse(**formResponse),
                testUser2,
            )
        )
    )
    yield response


@pytest.fixture()
def workspace_group(workspace, workspace_form):
    group = asyncio.run(
        container.responder_groups_service().create_group(
            workspace.id,
            "Testing_Group",
            "testing_group@gmail.com",
            testUser,
            workspace_form.form_id,
            "testing_Description",
            "@gmail.com",
        )
    )
    yield group


@pytest.fixture()
def test_user_cookies():
    token = container.jwt_service().encode(testUser)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_user_cookies_1():
    token = container.jwt_service().encode(testUser1)
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
def mock_aiohttp_post_request(workspace_form, workspace_form_response):
    async def mock_post(*args, **kwargs):
        # class MockResponse:
        #     async def json(self):
        #         return StandardForm(**formData)
        responses = StandardFormResponse(**workspace_form_response)
        form = StandardForm(**dict(workspace_form))
        return FormImportResponse(form=form, responses=[responses])

    yield patch(
        "backend.app.services.workspace_form_service.WorkspaceFormService.convert_form",
        side_effect=mock_post,
    )
