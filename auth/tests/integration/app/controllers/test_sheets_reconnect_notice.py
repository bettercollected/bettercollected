"""POST /notifications/sheets-reconnect: a fixed notice to a workspace's
billing owner that a form's Google Sheets connection must be renewed (the
backend found a grant from before drive.file). Only the backend may ask
(internal key); this service finds the owner's address and builds the link
itself, so a caller can neither pick a recipient nor point the button
elsewhere."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from auth.app.container import container
from auth.app.services import notification_service
from auth.app.services.mail_text import TEXTS
from auth.app.services.notification_service import (
    NotificationService,
    render_sheets_reconnect,
    sheets_reconnect_link,
)
from auth.config import settings
from tests.integration.conftest import INTERNAL_KEY, without_internal_key

URL = "notifications/sheets-reconnect"
ADMIN = "https://admin.example.com"
OWNER_ID = "5f0000000000000000000001"
FORM_ID = "6a0000000000000000000001"
LINK = f"{ADMIN}/acme/dashboard/forms/{FORM_ID}/integrations"
HEADERS = {"X-Internal-Key": INTERNAL_KEY}


def notice(**overrides) -> dict:
    return {
        "user_id": OWNER_ID,
        "workspace_name": "acme",
        "workspace_title": "Acme",
        "form_id": FORM_ID,
        "form_title": "Job application",
        **overrides,
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", INTERNAL_KEY)
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", ADMIN)
    monkeypatch.setattr(settings, "ORGANIZATION_NAME", "BetterCollected")


@pytest.fixture
def owner():
    """The billing owner as the user repository finds them."""
    found = AsyncMock(return_value=SimpleNamespace(email="owner@example.com"))
    with patch.object(container.user_repository(), "get_user_by_id", found):
        yield found


@pytest.fixture
def sent():
    with patch.object(
        notification_service.MailService, "send_message", new_callable=AsyncMock
    ) as send, patch.object(
        notification_service.MailService, "__init__", return_value=None
    ):
        yield send


class TestSheetsReconnectNotice:
    def test_mails_the_owner_a_fixed_notice(self, app_runner, owner, sent):
        response = app_runner.post(URL, json=notice(), headers=HEADERS)

        assert response.status_code == 200, response.text
        owner.assert_awaited_once_with(OWNER_ID)
        message = sent.await_args.args[0]
        assert [r.email for r in message.recipients] == ["owner@example.com"]
        assert message.subject == "Reconnect Google Sheets for one of your forms"
        body = " ".join(message.body.split())
        assert "Job application" in body and "Acme" in body
        assert f'href="{LINK}"' in body
        assert "Until you reconnect, new submissions are not added" in body

    def test_in_dutch(self, app_runner, owner, sent):
        response = app_runner.post(URL, json=notice(locale="nl-NL"), headers=HEADERS)

        assert response.status_code == 200, response.text
        message = sent.await_args.args[0]
        assert message.subject == "Koppel Google Sheets opnieuw voor een van je formulieren"
        body = " ".join(message.body.split())
        assert '<html lang="nl"' in body
        assert "Google Sheets opnieuw koppelen" in body
        assert "in de werkruimte" in body

    def test_only_the_backend_may_ask(self, app_runner, owner, sent):
        client = without_internal_key(app_runner)
        for headers in ({}, {"X-Internal-Key": "wrong"}):
            assert client.post(URL, json=notice(), headers=headers).status_code == 403
        sent.assert_not_called()
        owner.assert_not_called()

    def test_only_structured_fields(self, app_runner, owner, sent):
        for extra in (
            {"recipient": "x@evil.com"},
            {"link": "https://evil.com"},
            {"subject": "x"},
        ):
            response = app_runner.post(URL, json=notice(**extra), headers=HEADERS)
            assert response.status_code == 422, extra
        sent.assert_not_called()

    @pytest.mark.parametrize(
        "bad",
        [
            {"workspace_name": "../logout"},
            {"workspace_name": "a/b"},
            {"workspace_name": "a?next=https://evil.com"},
            # dot segments: the browser would resolve them out of the path
            {"workspace_name": "."},
            {"workspace_name": ".."},
            {"form_id": "x/../../y"},
            {"form_id": "x#y"},
        ],
    )
    def test_the_link_is_built_here_from_plain_segments(
        self, app_runner, owner, sent, bad
    ):
        response = app_runner.post(URL, json=notice(**bad), headers=HEADERS)
        assert response.status_code == 422
        sent.assert_not_called()

    def test_no_owner_no_mail(self, app_runner, sent):
        missing = AsyncMock(side_effect=RuntimeError("not found"))
        with patch.object(container.user_repository(), "get_user_by_id", missing):
            response = app_runner.post(URL, json=notice(), headers=HEADERS)
        assert response.status_code == 200
        assert response.json() == {"message": "No recipient."}
        sent.assert_not_called()

    def test_values_are_escaped_and_single_line(self, app_runner, owner, sent):
        response = app_runner.post(
            URL,
            json=notice(
                form_title="<script>alert(1)</script>\r\nBcc: x@evil.com",
                workspace_title='<a href="https://evil.com">Click</a>',
            ),
            headers=HEADERS,
        )
        assert response.status_code == 200
        message = sent.await_args.args[0]
        assert "<script>" not in message.body
        assert "&lt;script&gt;" in message.body
        assert 'href="https://evil.com"' not in message.body
        assert "evil" not in message.subject

    def test_burst_guard(self, app_runner, owner, sent, monkeypatch):
        monkeypatch.setattr(notification_service, "NOTICES_PER_HOUR", 2)
        body = notice(user_id="5f00000000000000000000cc")
        codes = [
            app_runner.post(URL, json=body, headers=HEADERS).status_code
            for _ in range(3)
        ]
        assert codes == [200, 200, 429]


def test_the_link_follows_the_admin_host(monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "https://admin.example.com/app/")
    assert sheets_reconnect_link("acme", FORM_ID) == (
        f"https://admin.example.com/app/acme/dashboard/forms/{FORM_ID}/integrations"
    )
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "")
    assert sheets_reconnect_link("acme", FORM_ID) is None


@pytest.mark.parametrize("handle", [".", ".."])
def test_no_link_for_a_dot_handle(handle):
    assert sheets_reconnect_link(handle, FORM_ID) is None


@pytest.mark.parametrize("handle", ["a.b", "...", ".acme", "acme.", "~a_b-c"])
def test_handles_with_dots_inside_still_link(handle):
    assert sheets_reconnect_link(handle, FORM_ID) == (
        f"{ADMIN}/{handle}/dashboard/forms/{FORM_ID}/integrations"
    )


def test_both_languages_have_the_sheets_texts():
    keys = {k for k in TEXTS["en"] if k.startswith("sheets_")}
    assert len(keys) == 8
    assert keys <= set(TEXTS["nl"])


def test_render_without_a_workspace_title():
    body = " ".join(render_sheets_reconnect("Form", None, LINK).split())
    assert "in the workspace" not in body
    assert "Form" in body


@pytest.mark.asyncio
async def test_a_mail_failure_is_logged_without_the_address():
    with patch.object(notification_service, "MailService") as mail, patch.object(
        notification_service.logger, "warning"
    ) as warning:
        mail.return_value.send_message = AsyncMock(side_effect=RuntimeError("smtp"))
        await NotificationService().send_sheets_reconnect(
            "owner@example.com", "Form", "Acme", LINK
        )
    [call] = warning.call_args_list
    assert "owner@example.com" not in str(call)
