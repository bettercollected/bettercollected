import pytest

from backend.app.services.registration import client
from backend.config import settings
from tests.app.registration.conftest import memory_jobs, tls  # noqa: F401
from tests.app.registration.tls_server import PUBLIC_ADDRESS


@pytest.fixture()
def webhooks_on(monkeypatch):
    monkeypatch.setattr(settings.webhooks, "ENABLED", True)


@pytest.fixture()
def public_dns(monkeypatch):
    """Every name resolves to a public address (tests of the guard replace it)."""

    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(client, "resolve", resolve)
