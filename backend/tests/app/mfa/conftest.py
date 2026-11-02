import pytest

from backend.config import settings


@pytest.fixture()
def totp_on(monkeypatch):
    monkeypatch.setattr(settings.totp, "ENABLED", True)
