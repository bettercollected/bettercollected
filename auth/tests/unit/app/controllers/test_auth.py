import pytest
from fastapi.testclient import TestClient
from auth.app import get_application


class TestAuthController:

    @pytest.fixture
    def client(self):
        # This is an example fixture for generated test sake.
        # By default there should be a 'app_runner' fixture just like this under:
        # tests/unit/app/conftest.py
        app = get_application()
        with TestClient(app) as client:
            yield client

    def test_shouldstatus_return_ok(self, client):
        # given / when
        response = client.get("/api/auth/status")

        # then
        assert response.status_code == 200
        assert response.json() == {"hello": "world"}
