import pytest
from fastapi.testclient import TestClient
from bettercollected_backend_server.app import get_application
from bettercollected_backend_server.config import settings


@pytest.fixture
def app_runner():
    # Overriding to true in order to initialize redis client on FastAPI event
    # startup handler. It'll be needed for unit tests.
    settings.USE_REDIS = True
    app = get_application()

    with TestClient(app) as client:
        yield client
