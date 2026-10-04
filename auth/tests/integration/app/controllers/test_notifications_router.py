"""POST /notifications/submission-update: a fixed notice to a respondent that
staff responded to their submission. Not a relay: only the backend (shared
internal key) on behalf of a signed-in caller, fixed wording and sender name,
escaped values and links to this instance's submission pages only."""

from unittest.mock import AsyncMock, patch

import pytest

from auth.app.container import container
from auth.app.services import notification_service
from auth.app.services.notification_service import (
    is_allowed_submission_link,
    render_submission_update,
)
from auth.config import settings
from common.models.user import User
from tests.integration.conftest import INTERNAL_KEY, without_internal_key

URL = "notifications/submission-update"
CLIENT = "https://forms.example.com"
LINK = f"{CLIENT}/acme/submissions/6a0000000000000000000001"
KEY = INTERNAL_KEY


def bearer(user_id="5f0000000000000000000000", key=KEY) -> dict:
    """A signed-in user's token, plus the backend's internal key unless
    ``key`` is None."""
    user = User(id=user_id, sub="staff@example.com", roles=["FORM_CREATOR"])
    headers = {"Authorization": f"Bearer {container.jwt_service().encode(user)}"}
    if key is not None:
        headers["X-Internal-Key"] = key
    return headers


def notice(**overrides) -> dict:
    return {
        "recipient": "applicant@example.com",
        "form_title": "Job application",
        "workspace_title": "Acme Hiring",
        "link": LINK,
        **overrides,
    }


@pytest.fixture(autouse=True)
def client_host(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", KEY)
    monkeypatch.setattr(settings, "CLIENT_URL", CLIENT)
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "http://localhost:3000")


@pytest.fixture
def sent():
    """Messages handed to SMTP."""
    with patch.object(
        notification_service.MailService, "send_message", new_callable=AsyncMock
    ) as send, patch.object(
        notification_service.MailService, "__init__", return_value=None
    ):
        yield send


class TestSubmissionUpdateNotice:
    def test_requires_a_token(self, app_runner, sent):
        key_only = {"X-Internal-Key": KEY}
        assert app_runner.post(URL, json=notice(), headers=key_only).status_code == 401
        response = app_runner.post(
            URL,
            json=notice(),
            headers={**key_only, "Authorization": "Bearer not-a-jwt"},
        )
        assert response.status_code == 401
        sent.assert_not_called()

    def test_a_users_token_alone_is_refused(self, app_runner, sent):
        """Any signed-in user could otherwise mail any address from this
        instance's domain: only the backend holds the internal key."""
        without_internal_key(app_runner)
        for key in (None, "", "wrong-key", KEY + "x"):
            response = app_runner.post(URL, json=notice(), headers=bearer(key=key))
            assert response.status_code == 403, key
        sent.assert_not_called()

    def test_refused_while_no_key_is_configured(self, app_runner, sent, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
        response = app_runner.post(URL, json=notice(), headers=bearer(key=""))
        assert response.status_code == 503
        sent.assert_not_called()

    def test_the_sender_name_is_always_this_instances(self, app_runner):
        with patch.object(
            notification_service.MailService, "send_message", new_callable=AsyncMock
        ), patch.object(
            notification_service.MailService, "__init__", return_value=None
        ) as init:
            response = app_runner.post(
                URL,
                json=notice(workspace_title="PayPal Security"),
                headers=bearer(),
            )
        assert response.status_code == 200, response.text
        assert init.call_args.kwargs["organization_name"] == settings.ORGANIZATION_NAME

    def test_sends_a_fixed_notice(self, app_runner, sent):
        response = app_runner.post(URL, json=notice(), headers=bearer())
        assert response.status_code == 200, response.text
        sent.assert_awaited_once()
        message = sent.await_args.args[0]
        assert message.subject == "Update on your submission to Job application"
        assert [r.email for r in message.recipients] == ["applicant@example.com"]
        assert f'href="{LINK}"' in message.body
        assert "Acme Hiring" in message.body

    def test_only_structured_fields(self, app_runner, sent):
        for extra in ({"subject": "x"}, {"body": "<b>x</b>"}, {"message": "Selected"}):
            response = app_runner.post(URL, json=notice(**extra), headers=bearer())
            assert response.status_code == 422, extra
        for bad in ({"recipient": "not-an-email"}, {"form_title": ""}):
            response = app_runner.post(URL, json=notice(**bad), headers=bearer())
            assert response.status_code == 422, bad
        sent.assert_not_called()

    @pytest.mark.parametrize(
        "link",
        [
            "https://evil.example.com/acme/submissions/6a01",
            "https://forms.example.com.evil.com/acme/submissions/6a01",
            "http://forms.example.com/acme/submissions/6a01",  # other scheme
            "https://user:pw@forms.example.com/acme/submissions/6a01",
            "https://forms.example.com/acme/submissions/6a01?next=https://evil.com",
            "https://forms.example.com/acme/submissions/6a01#x",
            "https://forms.example.com/acme/forms/job",
            "https://forms.example.com/acme/submissions/../../logout",
            "javascript:alert(1)//forms.example.com/acme/submissions/1",
            "//forms.example.com/acme/submissions/6a01",
        ],
    )
    def test_refuses_links_off_this_instance(self, app_runner, sent, link):
        response = app_runner.post(URL, json=notice(link=link), headers=bearer())
        assert response.status_code == 422
        sent.assert_not_called()

    def test_admin_host_links_are_accepted(self):
        assert is_allowed_submission_link(
            "http://localhost:3000/acme/submissions/6a0000000000000000000001"
        )

    def test_values_are_escaped_and_single_line(self, app_runner, sent):
        response = app_runner.post(
            URL,
            json=notice(
                form_title="<script>alert(1)</script>\r\nBcc: x@evil.com",
                workspace_title='<a href="https://evil.com">Click</a>',
            ),
            headers=bearer(),
        )
        assert response.status_code == 200
        message = sent.await_args.args[0]
        assert "\n" not in message.subject and "\r" not in message.subject
        assert "<script>" not in message.body
        assert "&lt;script&gt;" in message.body
        assert 'href="https://evil.com"' not in message.body

    def test_render_escapes(self):
        html = render_submission_update('"><img src=x>', "A & B", LINK)
        assert "<img" not in html
        assert "A &amp; B" in html

    def test_burst_guard(self, app_runner, sent, monkeypatch):
        monkeypatch.setattr(notification_service, "NOTICES_PER_HOUR", 2)
        headers = bearer("5f00000000000000000000aa")
        codes = [
            app_runner.post(URL, json=notice(), headers=headers).status_code
            for _ in range(3)
        ]
        assert codes == [200, 200, 429]

    def test_mail_failure_is_swallowed(self, app_runner):
        with patch.object(
            notification_service.MailService, "__init__", return_value=None
        ), patch.object(
            notification_service.MailService,
            "send_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("smtp down"),
        ):
            response = app_runner.post(
                URL, json=notice(), headers=bearer("5f00000000000000000000bb")
            )
        assert response.status_code == 200
