import pytest
from fastapi.testclient import TestClient

from backend.app import get_application


@pytest.fixture
def app_runner():
    app = get_application(is_test_mode=True)

    with TestClient(app) as client:
        yield client
