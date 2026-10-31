"""POST /notifications/draft-link: the mail that carries a respondent's link to
a saved draft. Not a relay: only the backend (shared internal key, no user
token), fixed wording in English and Dutch, escaped values, no answer in it,
and a link only to a form page of this instance with a draft token in its
fragment."""

from unittest.mock import AsyncMock, patch

import pytest

from auth.app.services import notification_service
from auth.app.services.notification_service import (
    is_allowed_draft_link,
    render_draft_link,
)
from auth.config import settings
from tests.integration.conftest import INTERNAL_KEY, without_internal_key

URL = "notifications/draft-link"
CLIENT = "https://forms.example.com"
TOKEN = "6a0000000000000000000001." + "A" * 43
LINK = f"{CLIENT}/acme/forms/6a0000000000000000000002#resume={TOKEN}"


def notice(**overrides) -> dict:
    return {
        "recipient": "applicant@example.com",
        "form_title": "Job application",
        "workspace_title": "Acme Hiring",
        "link": LINK,
        "days": 7,
        **overrides,
    }


def key() -> dict:
    return {"X-Internal-Key": INTERNAL_KEY}


@pytest.fixture(autouse=True)
def client_host(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", INTERNAL_KEY)
    monkeypatch.setattr(settings, "CLIENT_URL", CLIENT)
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "http://localhost:3000")


@pytest.fixture
def sent():
    with patch.object(
        notification_service.MailService, "send_message", new_callable=AsyncMock
    ) as send, patch.object(
        notification_service.MailService, "__init__", return_value=None
    ):
        yield send


def test_only_the_backend_may_ask(app_runner, sent):
    without_internal_key(app_runner)
    for headers in ({}, {"X-Internal-Key": ""}, {"X-Internal-Key": "wrong"}):
        response = app_runner.post(URL, json=notice(), headers=headers)
        assert response.status_code in (401, 403, 503), headers
    sent.assert_not_called()


def test_a_users_token_is_not_what_it_takes(app_runner, sent):
    without_internal_key(app_runner)
    response = app_runner.post(
        URL, json=notice(), headers={"Authorization": "Bearer anything"}
    )
    assert response.status_code in (401, 403, 503)
    sent.assert_not_called()


def test_it_sends_the_link_with_fixed_wording_and_no_answer(app_runner, sent):
    response = app_runner.post(URL, json=notice(), headers=key())
    assert response.status_code == 200, response.text
    sent.assert_awaited_once()
    message = sent.await_args.args[0]
    assert message.subject == "Your link to continue a form"
    assert [r.email for r in message.recipients] == ["applicant@example.com"]
    assert f'href="{LINK}"' in message.body
    assert "Job application" in message.body and "Acme Hiring" in message.body
    assert "7 days" in message.body and "do not forward" in message.body


def test_the_mail_is_in_dutch_when_asked(app_runner, sent):
    response = app_runner.post(URL, json=notice(locale="nl-NL"), headers=key())
    assert response.status_code == 200
    message = sent.await_args.args[0]
    assert message.subject == "Je link om een formulier af te maken"
    body = " ".join(message.body.split())
    assert '<html lang="nl"' in message.body
    assert "Verder met het formulier" in body
    assert "Je hebt een concept bewaard van" in body
    assert "Stuur deze e-mail dus niet door" in body


def test_only_structured_fields(app_runner, sent):
    for extra in ({"subject": "x"}, {"body": "<b>x</b>"}, {"answers": {"a": 1}}):
        response = app_runner.post(URL, json=notice(**extra), headers=key())
        assert response.status_code == 422, extra
    for bad in ({"recipient": "nope"}, {"form_title": ""}, {"days": 0}, {"days": 500}):
        response = app_runner.post(URL, json=notice(**bad), headers=key())
        assert response.status_code == 422, bad
    sent.assert_not_called()


@pytest.mark.parametrize(
    "link",
    [
        f"https://evil.example.com/acme/forms/6a01#resume={TOKEN}",
        f"https://forms.example.com.evil.com/acme/forms/6a01#resume={TOKEN}",
        f"http://forms.example.com/acme/forms/6a01#resume={TOKEN}",
        f"https://user:pw@forms.example.com/acme/forms/6a01#resume={TOKEN}",
        f"https://forms.example.com/acme/forms/6a01?next=https://evil.com#resume={TOKEN}",
        f"https://forms.example.com/acme/submissions/6a01#resume={TOKEN}",
        f"https://forms.example.com/acme/forms/../../logout#resume={TOKEN}",
        f"//forms.example.com/acme/forms/6a01#resume={TOKEN}",
        "https://forms.example.com/acme/forms/6a01",
        "https://forms.example.com/acme/forms/6a01#resume=short",
        f"https://forms.example.com/acme/forms/6a01#resume={TOKEN}&x=1",
        f"https://forms.example.com/acme/forms/6a01#x=1;resume={TOKEN}",
        f"https://forms.example.com/acme/forms/6a01#resume={TOKEN}\r\nBcc: x@evil.com",
    ],
)
def test_it_mails_no_other_link(app_runner, sent, link):
    response = app_runner.post(URL, json=notice(link=link), headers=key())
    assert response.status_code == 422
    sent.assert_not_called()


def test_the_admin_host_is_a_link_host_too():
    assert is_allowed_draft_link(
        f"http://localhost:3000/acme/forms/6a0000000000000000000002#resume={TOKEN}"
    )


def test_values_are_escaped_and_single_line(app_runner, sent):
    response = app_runner.post(
        URL,
        json=notice(
            form_title="<script>alert(1)</script>\r\nBcc: x@evil.com",
            workspace_title='<a href="https://evil.com">Click</a>',
        ),
        headers=key(),
    )
    assert response.status_code == 200
    message = sent.await_args.args[0]
    assert "\n" not in message.subject and "<script>" not in message.body
    assert "&lt;script&gt;" in message.body
    assert 'href="https://evil.com"' not in message.body
    assert "<img" not in render_draft_link('"><img src=x>', "A & B", LINK, 7)


def test_a_mail_failure_is_swallowed_and_logs_no_link(app_runner):
    with patch.object(
        notification_service.MailService, "__init__", return_value=None
    ), patch.object(
        notification_service.MailService,
        "send_message",
        new_callable=AsyncMock,
        side_effect=RuntimeError(f"smtp down {LINK}"),
    ), patch.object(
        notification_service, "logger"
    ) as log:
        response = app_runner.post(URL, json=notice(), headers=key())
    assert response.status_code == 200
    logged = " ".join(str(call) for call in log.warning.call_args_list)
    assert "applicant@example.com" not in logged and "resume=" not in logged


def test_a_burst_guard_stops_a_flood(app_runner, sent, monkeypatch):
    from auth.app.container import container

    container.notification_service()._sent.clear()
    monkeypatch.setattr(notification_service, "NOTICES_PER_HOUR", 2)
    codes = [
        app_runner.post(URL, json=notice(), headers=key()).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429]
