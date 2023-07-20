import loguru
import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.app import get_application
from backend.app.container import container


@pytest.fixture(scope="module")
def client_test():
    container.database_client.override(providers.Singleton(AsyncMongoMockClient))
    app = get_application(is_test_mode=True)
    with TestClient(app) as test_client:
        yield test_client
