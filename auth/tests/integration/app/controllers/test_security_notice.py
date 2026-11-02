"""POST /notifications/security: a fixed notice to an account about a change to
its own second factor. Only the backend may ask (internal key); this service
finds the address from the account id and owns every word of the mail, so a
caller can neither pick a recipient nor any text."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from auth.app.container import container
from auth.app.services import notification_service
from auth.app.services.mail_text import TEXTS
from auth.app.services.notification_service import (
    SECURITY_KINDS,
    render_security_notice,
)
from auth.config import settings
from tests.integration.conftest import INTERNAL_KEY, without_internal_key

URL = "notifications/security"
USER_ID = "5f0000000000000000000001"
HEADERS = {"X-Internal-Key": INTERNAL_KEY}


def notice(**overrides) -> dict:
    return {"user_id": USER_ID, "kind": "enrolled", **overrides}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", INTERNAL_KEY)
    monkeypatch.setattr(settings, "ORGANIZATION_NAME", "BetterCollected")


@pytest.fixture
def account():
    found = AsyncMock(return_value=SimpleNamespace(email="person@example.com"))
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


@pytest.mark.parametrize("kind", SECURITY_KINDS)
def test_every_kind_mails_the_account_in_both_languages(app_runner, account, sent, kind):
    extra = {"recovery_left": 3, "minutes": 15, "workspace_title": "Acme"}
    for locale in (None, "nl-NL"):
        response = app_runner.post(
            URL, json=notice(kind=kind, locale=locale, **extra), headers=HEADERS
        )
        assert response.status_code == 200, response.text
        message = sent.await_args.args[0]
        assert [r.email for r in message.recipients] == ["person@example.com"]
        language = "nl" if locale else "en"
        assert message.subject == TEXTS[language][f"sec_subject_{kind}"]
        assert f'<html lang="{language}"' in message.body
        for leftover in ("{product}", "{left}", "{minutes}", "{workspace}", "None"):
            assert leftover not in message.body


def test_the_words_carry_the_numbers_and_the_workspace():
    _, html = render_security_notice("recovery_used", "en", recovery_left=2)
    assert "Recovery codes left: 2" in html
    _, html = render_security_notice("locked", "nl", minutes=15)
    assert "15 minuten" in html
    _, html = render_security_notice("reset_owner", "en", workspace_title="Acme Zorg")
    assert "Acme Zorg" in html


def test_a_notice_never_carries_a_code_or_an_address(app_runner, account, sent):
    app_runner.post(
        URL, json=notice(kind="recovery_used", recovery_left=1), headers=HEADERS
    )
    body = sent.await_args.args[0].body
    assert "person@example.com" not in body and "@" not in body.replace("&reg;", "")


def test_only_the_backend_may_ask(app_runner, account, sent):
    client = without_internal_key(app_runner)
    for headers in ({}, {"X-Internal-Key": "wrong"}):
        assert client.post(URL, json=notice(), headers=headers).status_code == 403
    sent.assert_not_called()
    account.assert_not_called()


def test_only_structured_fields(app_runner, account, sent):
    for extra in (
        {"recipient": "x@evil.com"},
        {"subject": "x"},
        {"body": "x"},
        {"link": "https://evil.com"},
        {"kind": "something_else"},
        {"recovery_left": -1},
        {"minutes": 0},
    ):
        response = app_runner.post(URL, json=notice(**extra), headers=HEADERS)
        assert response.status_code == 422, extra
    sent.assert_not_called()


def test_no_account_no_mail(app_runner, sent):
    missing = AsyncMock(side_effect=RuntimeError("not found"))
    with patch.object(container.user_repository(), "get_user_by_id", missing):
        response = app_runner.post(URL, json=notice(), headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"message": "No recipient."}
    sent.assert_not_called()


def test_the_workspace_title_is_escaped_and_one_line(app_runner, account, sent):
    response = app_runner.post(
        URL,
        json=notice(
            kind="reset_owner",
            workspace_title='<script>alert(1)</script>\r\nBcc: x@evil.com',
        ),
        headers=HEADERS,
    )
    assert response.status_code == 200
    message = sent.await_args.args[0]
    assert "<script>" not in message.body and "&lt;script&gt;" in message.body
    assert "evil" not in message.subject


def test_a_burst_for_one_account_is_capped(app_runner, account, sent, monkeypatch):
    monkeypatch.setattr(notification_service, "SECURITY_NOTICES_PER_ACCOUNT_PER_HOUR", 2)
    body = notice(user_id="5f00000000000000000000dd")
    codes = [
        app_runner.post(URL, json=body, headers=HEADERS).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429]


def test_both_languages_have_the_same_security_texts():
    keys = {k for k in TEXTS["en"] if k.startswith("sec_")}
    assert keys == {k for k in TEXTS["nl"] if k.startswith("sec_")}
    for kind in SECURITY_KINDS:
        for part in ("subject", "heading", "body"):
            assert f"sec_{part}_{kind}" in keys


@pytest.mark.asyncio
async def test_a_mail_failure_is_logged_without_the_address():
    with patch.object(notification_service, "MailService") as mail, patch.object(
        notification_service.logger, "warning"
    ) as warning:
        mail.return_value.send_message = AsyncMock(side_effect=RuntimeError("smtp down person@example.com"))
        await notification_service.NotificationService().send_security_notice(
            "person@example.com", "enrolled"
        )
    logged = " ".join(str(c.args[0]) for c in warning.call_args_list)
    assert "person@example.com" not in logged
