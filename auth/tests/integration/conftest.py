import pytest
from fastapi.testclient import TestClient

from auth.app import get_application
from auth.app.container import container
from mongomock_motor import AsyncMongoMockClient


@pytest.fixture
def app_runner():
    container.database_client.override(AsyncMongoMockClient())
    app = get_application()

    with TestClient(app) as client:
        yield client
