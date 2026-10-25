from auth.app import get_application
from auth.app.controllers.internal_key import INTERNAL_KEY_HEADER
from auth.config import settings

from fastapi.testclient import TestClient

import pytest

# The auth API is internal (controllers/internal_key.py): ``app_runner`` calls
# it the way the backend does, with the shared key. A test of the refusal
# drops the header with ``without_internal_key(app_runner)``.
INTERNAL_KEY = "internal-notify-key-for-tests"


def without_internal_key(client: TestClient) -> TestClient:
    client.headers.pop(INTERNAL_KEY_HEADER, None)
    return client


@pytest.fixture
def app_runner(monkeypatch, _postgres_schema):
    """The app on the test database (it refuses to start without one)."""
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", INTERNAL_KEY)
    app = get_application()

    with TestClient(
        app,
        base_url=f"http://testserver{settings.API_ROOT_PATH}",
        headers={INTERNAL_KEY_HEADER: INTERNAL_KEY},
    ) as client:
        yield client
