"""GET /users/invite/send/mail: only this instance's backend (shared internal
key) may have invitation mails sent."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from auth.app.services.user_service import UserService
from auth.config import settings
from tests.integration.conftest import INTERNAL_KEY, without_internal_key

URL = "users/invite/send/mail"
KEY = INTERNAL_KEY
PARAMS = {
    "workspace_title": "Acme",
    "workspace_name": "acme",
    "role": "Collaborator",
    "email": "new@example.com",
    "token": "invitation-token",
    "inviter_id": "5f0000000000000000000000",
}


@pytest.fixture
def sent():
    with patch.object(
        UserService, "send_mail_to_user_for_invitation", new_callable=AsyncMock
    ) as send:
        yield send


class TestInvitationMail:
    def test_refused_without_the_internal_key(self, app_runner, sent):
        without_internal_key(app_runner)
        for headers in ({}, {"X-Internal-Key": ""}, {"X-Internal-Key": "wrong"}):
            response = app_runner.get(URL, params=PARAMS, headers=headers)
            assert response.status_code == 403, headers
        sent.assert_not_called()

    def test_refused_while_no_key_is_configured(self, app_runner, sent, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
        response = without_internal_key(app_runner).get(URL, params=PARAMS)
        assert response.status_code == 503
        sent.assert_not_called()

    def test_backend_sends_the_mail(self, app_runner, sent):
        response = app_runner.get(URL, params=PARAMS, headers={"X-Internal-Key": KEY})
        assert response.status_code == 200
        sent.assert_awaited_once()
        assert sent.call_args.kwargs["email"] == "new@example.com"


class TestInvitationMailContent:
    @pytest.mark.asyncio
    async def test_an_inviter_without_a_first_name_is_named_by_email(self):
        inviter = SimpleNamespace(
            first_name=None, email="owner@example.com", profile_image=None
        )
        repo = SimpleNamespace(get_user_by_id=AsyncMock(return_value=inviter))
        with patch("auth.app.services.user_service.MailService") as mail_service:
            mail_service.return_value.send_message = AsyncMock()
            await UserService(repo, None).send_mail_to_user_for_invitation(**PARAMS)
        message = mail_service.return_value.send_message.await_args.args[0]
        assert "owner@example.com" in message.body
        assert re.search(r">\s*O\s*</div>", message.body)  # the initial


class TestDeleteUser:
    """A retried deletion job sees 404 for an account that is already gone."""

    def test_deletes_an_existing_user_then_404s(self, app_runner):
        from auth.app.container import container

        user = app_runner.portal.call(
            container.user_repository().save_user, "to-delete@example.com"
        )
        first = app_runner.delete(f"users/{user.id}")
        assert first.status_code == 200, first.text
        again = app_runner.delete(f"users/{user.id}")
        assert again.status_code == 404, again.text

    def test_a_missing_user_is_404_not_a_crash(self, app_runner):
        response = app_runner.delete("users/5f00000000000000000000ff")
        assert response.status_code == 404, response.text
