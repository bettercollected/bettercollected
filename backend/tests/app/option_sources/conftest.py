import pytest

from backend.config import settings


@pytest.fixture()
def sources_on(monkeypatch):
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)
