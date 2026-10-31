from unittest.mock import AsyncMock, patch

import pytest

from backend.app.container import container
from backend.app.services.email_actions.transport import MailFailed
from backend.config import settings
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.email_actions.helpers import ACCOUNTS
from tests.app.registration.conftest import memory_jobs  # noqa: F401

# who the (faked) auth service knows, by account id
EMAILS = {
    testUser.id: "owner@acme.example",
    invited_user.id: "Editor@Acme.example",
    testUser1.id: "outsider@elsewhere.example",
}


class FakeTransport:
    """Records what would be sent; ``fail`` raises one of our codes."""

    def __init__(self):
        self.sent = []
        self.fail = None

    async def send(self, *, recipients, subject, body):
        if self.fail is not None:
            raise self.fail
        self.sent.append({"recipients": list(recipients), "subject": subject, "body": body})


@pytest.fixture()
def emails_on(monkeypatch):
    monkeypatch.setattr(settings.email_actions, "ENABLED", True)
    monkeypatch.setattr(settings.mail_settings, "smtp_server", "smtp.example.test")
    monkeypatch.setattr(settings.mail_settings, "sender", "noreply@example.test")


@pytest.fixture()
def transport(monkeypatch):
    fake = FakeTransport()
    monkeypatch.setattr(container.email_action_service(), "_transport", fake)
    return fake


@pytest.fixture(autouse=True)
def auth_users():
    """User details come from the auth service, outside the test."""

    async def users(url, params=None, **kwargs):
        known = {**EMAILS, **ACCOUNTS}
        return {
            "users_info": [
                {"_id": user_id, "email": known[user_id]}
                for user_id in params["user_ids"]
                if user_id in known
            ]
        }

    with patch.object(
        container.copy_recipient_service()._http_client,
        "get",
        AsyncMock(side_effect=users),
    ) as get:
        yield get


@pytest.fixture()
def public_dns_on(monkeypatch):
    """Every name resolves to a public address (the webhook address check)."""
    from backend.app.services.registration import client
    from tests.app.registration.tls_server import PUBLIC_ADDRESS

    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(client, "resolve", resolve)
