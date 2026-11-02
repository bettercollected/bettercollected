import pytest

from backend.app.container import container
from backend.config import settings


@pytest.fixture(autouse=True)
def revisions_switched_on(monkeypatch):
    """RESPONSE_REVISIONS_ENABLED is on for these tests; the switch tests turn it off."""
    monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", True)


@pytest.fixture(autouse=True)
def no_member_names(monkeypatch):
    """The auth service is not there: names are best effort and absent."""

    async def get(self, url, **kwargs):
        raise ConnectionError("no auth service in tests")

    monkeypatch.setattr(type(container.http_client()), "get", get)
