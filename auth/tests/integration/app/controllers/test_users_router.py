"""GET /users/invite/send/mail: only this instance's backend (shared internal
key) may have invitation mails sent."""

from unittest.mock import AsyncMock, patch

import pytest

from auth.app.services.user_service import UserService
from auth.config import settings

URL = "users/invite/send/mail"
KEY = "internal-notify-key-for-tests"
PARAMS = {
    "workspace_title": "Acme",
    "workspace_name": "acme",
    "role": "Collaborator",
    "email": "new@example.com",
    "token": "invitation-token",
    "inviter_id": "5f0000000000000000000000",
}


@pytest.fixture(autouse=True)
def internal_key(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", KEY)


@pytest.fixture
def sent():
    with patch.object(
        UserService, "send_mail_to_user_for_invitation", new_callable=AsyncMock
    ) as send:
        yield send


class TestInvitationMail:
    def test_refused_without_the_internal_key(self, app_runner, sent):
        for headers in ({}, {"X-Internal-Key": ""}, {"X-Internal-Key": "wrong"}):
            response = app_runner.get(URL, params=PARAMS, headers=headers)
            assert response.status_code == 403, headers
        sent.assert_not_called()

    def test_refused_while_no_key_is_configured(self, app_runner, sent, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
        response = app_runner.get(URL, params=PARAMS, headers={"X-Internal-Key": ""})
        assert response.status_code == 503
        sent.assert_not_called()

    def test_backend_sends_the_mail(self, app_runner, sent):
        response = app_runner.get(URL, params=PARAMS, headers={"X-Internal-Key": KEY})
        assert response.status_code == 200
        sent.assert_awaited_once()
        assert sent.call_args.kwargs["email"] == "new@example.com"
