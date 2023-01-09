import pytest

from settings import settings


@pytest.fixture
def mock_settings() -> settings:
    settings.environment = "test"
    return settings
