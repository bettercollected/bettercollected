import pytest

from settings import settings


@pytest.fixture
def mock_app():
    settings.environment = "test"

    from app import create_app

    return create_app()


def test_mock_app(mock_app):
    assert mock_app.title == "[BetterCollected] Google Forms Integrations API"
