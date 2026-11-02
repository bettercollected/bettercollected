import pytest

from backend.config import settings


@pytest.fixture()
def switch_on(monkeypatch):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)


@pytest.fixture()
def switch_off(monkeypatch):
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
