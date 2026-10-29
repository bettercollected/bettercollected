"""Every mail this service sends renders in English and in Dutch with nothing
missing: each placeholder a template reads has a value (the template
environment is made strict here), no format field or template tag is left in
the output, and the language of one mail never leaks into the other. The
sender is the instance in both languages, whatever the caller supplies."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from jinja2 import Environment, FileSystemLoader, Undefined, select_autoescape

from auth.app.services import mail_service
from auth.app.services.auth_service import AuthService
from auth.app.services.mail_text import RESPONDENT_TEXTS, TEXTS, texts
from auth.app.services.notification_service import (
    NotificationService,
    render_sheets_reconnect,
    render_submission_update,
)
from auth.app.services.user_service import UserService
from auth.config import settings

LANGUAGES = ("en", "nl")
LINK = "https://admin.example.com/acme/submissions/r1"
FORM_LINK = "https://admin.example.com/acme/dashboard/forms/f1/integrations"
SPOOF = "PayPal Security\r\nBcc: victim@example.com"


class MissingValue(Undefined):
    """A template reading a value nobody supplied fails instead of printing
    nothing (only printing it fails: ``{% if x %}`` on an optional one is
    fine)."""

    def __str__(self):
        raise AssertionError(f"template prints a missing value: {self._undefined_name}")


@pytest.fixture(autouse=True)
def instance(monkeypatch):
    monkeypatch.setattr(settings, "ORGANIZATION_NAME", "BetterCollected")
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "https://admin.example.com")
    monkeypatch.setattr(
        mail_service,
        "_environment",
        Environment(
            loader=FileSystemLoader(str(mail_service.TEMPLATES)),
            autoescape=select_autoescape(default=True, default_for_string=True),
            undefined=MissingValue,
        ),
    )


async def code_mail(locale, title="Acme Zorg", creator=False):
    repo = SimpleNamespace(
        get_user_by_email=AsyncMock(return_value=None), save_otp_user=AsyncMock()
    )
    with patch("auth.app.services.auth_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await AuthService(None, repo, None).send_otp_to_mail(
            receiver_mail="someone@example.com",
            workspace_title=title,
            workspace_profile_image=None,
            creator=creator,
            locale=locale,
        )
    return mail.return_value.send_message.await_args.args[0]


async def invitation_mail(locale, title="Acme Zorg", first_name="Ann", role="Editor"):
    inviter = SimpleNamespace(
        first_name=first_name, email="owner@example.com", profile_image=None
    )
    repo = SimpleNamespace(get_user_by_id=AsyncMock(return_value=inviter))
    with patch("auth.app.services.user_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await UserService(repo, None).send_mail_to_user_for_invitation(
            workspace_title=title,
            workspace_name="acme",
            role=role,
            email="new@example.com",
            token="t",
            inviter_id="5f0000000000000000000000",
            locale=locale,
        )
    return mail.return_value.send_message.await_args.args[0]


async def update_mail(locale, workspace="Acme Zorg", form="Aanvraag"):
    with patch("auth.app.services.notification_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await NotificationService().send_submission_update(
            "r@example.com", form, workspace, LINK, locale=locale
        )
    mail.assert_called_once_with()
    return mail.return_value.send_message.await_args.args[0]


async def sheets_mail(locale, workspace="Acme Zorg", form="Aanvraag"):
    with patch("auth.app.services.notification_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await NotificationService().send_sheets_reconnect(
            "o@example.com", form, workspace, FORM_LINK, locale=locale
        )
    mail.assert_called_once_with()
    return mail.return_value.send_message.await_args.args[0]


MAILS = {
    "code": code_mail,
    "invitation": invitation_mail,
    "submission update": update_mail,
    "sheets reconnect": sheets_mail,
}

# words that are the same in both languages or are brand, link or legal text
SHARED = {"Sireto", "BetterCollected", "Google", "Sheets"}


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LANGUAGES)
@pytest.mark.parametrize("name", MAILS)
async def test_every_mail_renders_with_nothing_missing(name, locale):
    message = await MAILS[name](locale)
    body = message.body
    assert f'<html lang="{locale}"' in body
    # no unfilled format field ("{product}"), template tag or "None"
    for leftover in ("{product}", "{workspace}", "{{", "{%", "}}", "%}", ">None<"):
        assert leftover not in body, leftover
    assert "{" not in message.subject and "None" not in message.subject
    # the sender, never the workspace, is the product
    assert "BetterCollected" in body or name in ("submission update", "sheets reconnect")
    # every text of the mail is in this language: none of the other one's
    # distinctive sentences appears
    other = "nl" if locale == "en" else "en"
    # what the reader sees: template comments are not part of it
    squashed = " ".join(re.sub(r"<!--.*?-->", "", body, flags=re.S).split())
    for key, text in TEXTS[other].items():
        if text == TEXTS[locale][key] or text in SHARED or "{" in text:
            continue
        assert text not in squashed, key


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LANGUAGES)
async def test_every_text_a_mail_shows_is_in_the_table(locale):
    """The words come from one table: the footer and the legal lines are in
    the language of the mail."""
    for name, make in MAILS.items():
        body = " ".join((await make(locale)).body.split())
        assert TEXTS[locale]["footer_product_of"] in body or name == "code"
        assert TEXTS[locale]["footer_trademark"] in body, name


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LANGUAGES)
async def test_the_sender_is_the_instance_whatever_is_supplied(locale):
    """From display name and subject never carry a workspace, form or inviter
    name, and no header takes a line break from them."""
    for message in (
        await code_mail(locale, title=SPOOF),
        await invitation_mail(locale, title=SPOOF, first_name=SPOOF),
        await update_mail(locale, workspace=SPOOF, form=SPOOF),
        await sheets_mail(locale, workspace=SPOOF, form=SPOOF),
    ):
        assert "PayPal" not in message.subject
        assert "Bcc" not in message.subject
        assert "\r" not in message.subject and "\n" not in message.subject
        assert message.subject in {
            table[key].format(product="BetterCollected")
            for table in (texts(locale), texts(locale, respondent=True))
            for key in (
                "code_subject",
                "invite_subject",
                "update_subject",
                "sheets_subject",
            )
        }
        # recipients are the ones the caller named, nothing from the titles
        assert all("victim" not in str(recipient) for recipient in message.recipients)


def _from_name(monkeypatch, organization_name):
    monkeypatch.setattr(settings, "ORGANIZATION_NAME", organization_name)
    with patch("auth.app.services.mail_service.ConnectionConfig") as config, patch(
        "auth.app.services.mail_service.FastMail"
    ):
        mail_service.MailService()
    return config.call_args.kwargs["MAIL_FROM_NAME"]


def test_the_from_display_name_is_the_instance(monkeypatch):
    assert _from_name(monkeypatch, "BetterCollected") == "BetterCollected"


def test_a_hostile_organization_name_is_one_line_in_the_from_name(monkeypatch):
    name = _from_name(monkeypatch, "Better\r\nBcc: victim@example.com")
    assert "\r" not in name and "\n" not in name


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LANGUAGES)
async def test_the_invitation_names_the_inviter_only_as_information(locale):
    body = " ".join((await invitation_mail(locale, first_name="Ann")).body.split())
    t = TEXTS[locale]
    assert "Acme Zorg</span>" in body and f"{t['invite_heading_via']} BetterCollected" in body
    assert "Ann</span>" in body
    assert t["invite_name_note"].format(product="BetterCollected") in body
    # the inviter comes after the workspace line, never in its place
    assert body.index("Acme Zorg") < body.index("Ann</span>")


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["nl", "nl-NL", "NL_be"])
async def test_a_dutch_language_tag_selects_dutch_everywhere(language):
    # (code_mail is the respondent's; the creator's is formal)
    assert (await code_mail(language)).subject == texts(
        "nl", respondent=True
    )["code_subject"].format(product="BetterCollected")
    assert (await code_mail(language, creator=True)).subject == TEXTS["nl"][
        "code_subject"
    ].format(product="BetterCollected")
    assert (await invitation_mail(language)).subject == TEXTS["nl"][
        "invite_subject"
    ].format(product="BetterCollected")
    assert 'lang="nl"' in render_submission_update("F", None, LINK, language)
    assert 'lang="nl"' in render_sheets_reconnect("F", None, FORM_LINK, language)


@pytest.mark.asyncio
@pytest.mark.parametrize("language", [None, "", "en-GB", "de", "fr-FR", "x" * 100])
async def test_anything_else_selects_english(language):
    assert (await code_mail(language)).subject == TEXTS["en"]["code_subject"].format(
        product="BetterCollected"
    )
    assert 'lang="en"' in render_submission_update("F", None, LINK, language)
    assert 'lang="en"' in render_sheets_reconnect("F", None, FORM_LINK, language)


# ----------------------------------------------------------- Dutch register
# Creators and team members are addressed formally ("u", "uw"), like the
# dashboard; respondents informally ("je"), like the respondent pages.


async def creator_code_mail(locale):
    return await code_mail(locale, creator=True)


# the mails (and the recipient they are for) that use "u" in Dutch
FORMAL_MAILS = {
    "creator code": creator_code_mail,
    "invitation": invitation_mail,
    "sheets reconnect": sheets_mail,
}
# the mails respondents receive: "je"
INFORMAL_MAILS = {
    "respondent code": code_mail,
    "submission update": update_mail,
}

INFORMAL_WORDS = re.compile(r"\b(je|jij|jouw|jou|jouwe)\b", re.I)
FORMAL_PRONOUN = re.compile(r"(?<![\w-])(u|uw)(?![\w-])", re.I)


def _words(message):
    """What a reader reads: subject and body text without markup, comments,
    styles or the titles people chose."""
    body = re.sub(r"<!--.*?-->|<style.*?</style>", " ", message.body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return " ".join((message.subject + " " + body).split())


@pytest.mark.asyncio
@pytest.mark.parametrize("name", FORMAL_MAILS)
async def test_dutch_creator_and_team_mails_say_u(name):
    words = _words(await FORMAL_MAILS[name]("nl"))
    assert not INFORMAL_WORDS.search(words), INFORMAL_WORDS.search(words)
    assert FORMAL_PRONOUN.search(words), name


@pytest.mark.asyncio
@pytest.mark.parametrize("name", INFORMAL_MAILS)
async def test_dutch_respondent_mails_say_je(name):
    words = _words(await INFORMAL_MAILS[name]("nl"))
    assert INFORMAL_WORDS.search(words), name
    # no formal pronoun (the Dutch "u"/"uw"); English text is not Dutch
    assert not FORMAL_PRONOUN.search(words), FORMAL_PRONOUN.search(words)


def test_the_dutch_table_is_formal_except_for_respondent_texts():
    respondent_keys = {k for k in TEXTS["nl"] if k.startswith("update_")}
    for key, text in TEXTS["nl"].items():
        if key in respondent_keys:
            assert not FORMAL_PRONOUN.search(text), key
        else:
            assert not INFORMAL_WORDS.search(text), key
    # the code mail's informal variant is exactly the keys that differ
    for key, text in RESPONDENT_TEXTS["nl"].items():
        assert INFORMAL_WORDS.search(text) and not FORMAL_PRONOUN.search(text), key
        assert key in TEXTS["nl"] and TEXTS["nl"][key] != text


@pytest.mark.asyncio
async def test_the_dutch_creator_code_subject_is_formal_and_the_respondents_is_not():
    assert (await code_mail("nl", creator=True)).subject == (
        "Uw verificatiecode voor BetterCollected"
    )
    assert (await code_mail("nl", creator=False)).subject == (
        "Je verificatiecode voor BetterCollected"
    )
    # English has one text for both
    assert (await code_mail("en", creator=True)).subject == (
        (await code_mail("en", creator=False)).subject
    )
