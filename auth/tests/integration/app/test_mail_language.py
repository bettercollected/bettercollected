"""The mails in Dutch and English (``locale``), and honest attribution: the
sender is always this instance, a workspace appears as "<workspace> via
<product>", and an invitation says the inviter's name is self-chosen."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from auth.app.services.auth_service import AuthService
from auth.app.services.mail_text import TEXTS, mail_locale, role_name
from auth.app.services.notification_service import (
    NotificationService,
    render_submission_update,
)
from auth.app.services.user_service import UserService
from auth.config import settings

LINK = "https://admin.example.com/acme/submissions/r1"


@pytest.fixture(autouse=True)
def instance(monkeypatch):
    monkeypatch.setattr(settings, "ORGANIZATION_NAME", "BetterCollected")
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "https://admin.example.com")


async def code_mail(locale, title="Acme Zorg"):
    repo = SimpleNamespace(
        get_user_by_email=AsyncMock(return_value=None), save_otp_user=AsyncMock()
    )
    with patch("auth.app.services.auth_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await AuthService(None, repo, None).send_otp_to_mail(
            receiver_mail="someone@example.com",
            workspace_title=title,
            workspace_profile_image=None,
            creator=False,
            locale=locale,
        )
    return mail.return_value.send_message.await_args.args[0]


async def invitation(locale, role="Editor", first_name="Ann"):
    inviter = SimpleNamespace(
        first_name=first_name, email="owner@example.com", profile_image=None
    )
    repo = SimpleNamespace(get_user_by_id=AsyncMock(return_value=inviter))
    with patch("auth.app.services.user_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await UserService(repo, None).send_mail_to_user_for_invitation(
            workspace_title="Acme Hiring",
            workspace_name="acme",
            role=role,
            email="new@example.com",
            token="t",
            inviter_id="5f0000000000000000000000",
            locale=locale,
        )
    return mail.return_value.send_message.await_args.args[0]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("nl", "nl"),
        ("NL-be", "nl"),
        ("nl_NL", "nl"),
        ("en", "en"),
        ("de", "en"),
        ("nlx", "en"),
        (None, "en"),
        ("", "en"),
    ],
)
def test_the_language_is_dutch_or_english(value, expected):
    assert mail_locale(value) == expected


def test_both_languages_have_every_text():
    assert set(TEXTS["nl"]) == set(TEXTS["en"])
    assert all(TEXTS["nl"].values())


def test_role_names():
    assert role_name("Editor", "nl") == "Bewerker"
    assert role_name("Privacy officer", "nl") == "Privacyfunctionaris"
    assert role_name("Editor", "en") == "Editor"
    assert role_name("Something new", "nl") == "Something new"
    assert role_name(None, "nl") is None


@pytest.mark.asyncio
async def test_the_code_mail_in_dutch():
    message = await code_mail("nl")
    assert message.subject == "Je verificatiecode voor BetterCollected"
    assert '<html lang="nl"' in message.body
    assert "Acme Zorg via BetterCollected" in message.body
    assert "verificatiecode" in message.body
    assert "Deze code is 5 minuten geldig" in message.body
    assert "This code will expire" not in message.body


@pytest.mark.asyncio
async def test_the_code_mail_defaults_to_english():
    message = await code_mail(None)
    assert message.subject == "Your BetterCollected verification code"
    assert '<html lang="en"' in message.body
    assert "This code will expire in 5 minutes" in message.body


@pytest.mark.asyncio
async def test_the_invitation_names_the_workspace_via_the_product():
    message = await invitation("en")
    body = " ".join(message.body.split())
    assert "Acme Hiring</span>" in body
    assert "via BetterCollected" in body
    # the inviter is named, with the role, and their name is said to be theirs
    assert "Ann</span> invited you to join this workspace as" in body
    assert "Editor</span>" in body
    assert "The name is the one they gave themselves on BetterCollected." in body
    assert "has invited you to" not in body
    assert message.subject == "You have been invited to a workspace on BetterCollected"


@pytest.mark.asyncio
async def test_the_invitation_in_dutch():
    message = await invitation("nl-NL", role="Viewer")
    body = " ".join(message.body.split())
    assert (
        message.subject == "U bent uitgenodigd voor een werkruimte op BetterCollected"
    )
    assert "nodigt u uit voor deze werkruimte als" in body
    assert "Kijker</span>" in body
    assert "Naar de werkruimte" in body
    assert "Join workspace" not in body


@pytest.mark.asyncio
async def test_an_invitation_without_a_role_still_reads_well():
    message = await invitation("en", role="")
    body = " ".join(message.body.split())
    assert "invited you to join this workspace." in body


def test_the_submission_notice_in_dutch():
    body = " ".join(render_submission_update("Aanvraag", "Acme", LINK, "nl").split())
    assert '<html lang="nl"' in body
    assert "Acme heeft gereageerd op je inzending voor" in body
    assert "Bekijk je inzending" in body
    body = " ".join(render_submission_update("Aanvraag", None, LINK, "nl").split())
    assert "Er is een reactie op je inzending voor" in body


def test_the_workspace_title_stays_escaped_in_a_sentence():
    body = render_submission_update("Form", "<b>Acme</b>", LINK, "nl")
    assert "<b>Acme</b>" not in body
    assert "&lt;b&gt;Acme&lt;/b&gt; heeft gereageerd" in body


@pytest.mark.asyncio
async def test_the_submission_notice_subject_follows_the_language():
    with patch("auth.app.services.notification_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await NotificationService().send_submission_update(
            "r@example.com", "Form", "Acme", LINK, locale="nl"
        )
    message = mail.return_value.send_message.await_args.args[0]
    assert message.subject == "Nieuws over je inzending"
