import pytest
from procrastinate.testing import InMemoryConnector

from backend.app.services.registration import client
from backend.config import settings
from backend.jobs.app import app
from backend.app.services.safe_http import PinnedBackend
from tests.app.registration.tls_server import (
    PUBLIC_ADDRESS,
    DialToServer,
    TlsServer,
)


@pytest.fixture()
def registration_on(monkeypatch):
    monkeypatch.setattr(settings.registration, "REGISTRATION", "on")


@pytest.fixture()
def memory_jobs():
    """procrastinate's in-memory connector: no queue database needed."""
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


@pytest.fixture()
async def tls(monkeypatch):
    """A local https server (test CA) the client reaches as ``case.example.org``
    at a public-looking address."""
    async with TlsServer() as server:

        async def resolve(host, port=443):
            return [PUBLIC_ADDRESS]

        monkeypatch.setattr(client, "resolve", resolve)
        monkeypatch.setattr(
            client,
            "network_backend",
            lambda host, address: PinnedBackend(
                host, address, inner=DialToServer(server)
            ),
        )
        monkeypatch.setattr(client, "ssl_context", server.client_context)
        yield server
