"""Integration test fixtures."""

import pytest
from fastapi.testclient import TestClient
from googleform.app import get_application
from googleform.config import settings


@pytest.fixture
def app_runner():
    """App runner fixture."""
    app = get_application()

    with TestClient(app) as client:
        yield client
