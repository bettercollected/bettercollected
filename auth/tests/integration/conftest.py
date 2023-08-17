from auth.app import get_application
from auth.app.container import container
from auth.config import settings

from dependency_injector import providers

from fastapi.testclient import TestClient

from mongomock_motor import AsyncMongoMockClient

import pytest


@pytest.fixture
def app_runner():
    container.database_client.override(providers.Singleton(AsyncMongoMockClient))
    app = get_application()

    with TestClient(
        app,
        base_url=f"http://testserver{settings.API_ROOT_PATH}",
    ) as client:
        yield client
