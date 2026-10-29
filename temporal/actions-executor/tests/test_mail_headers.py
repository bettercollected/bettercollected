"""The respondent's copy of a response is sent as "<workspace> via <instance>"
(the instance's ORGANIZATION_NAME is the sender, the workspace the party it
is sent for), through the instance's SMTP server and through a workspace's own
alike; the form title is in the subject. Titles are free text, so both header
values are folded to one line and capped: no header injection."""

import asyncio
import json
from email import message_from_string
from email.utils import getaddresses, parseaddr

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from settings.application import settings

# configs.crypto refuses to load without a key; the shared settings object may
# have been created before any test set one
if not settings.aes_hex_key:
    settings.aes_hex_key = Fernet.generate_key().decode()

from configs.crypto import crypto  # noqa: E402
from fastapi_mail import FastMail  # noqa: E402
from utilities import actions  # noqa: E402
from utilities.mail_headers import (  # noqa: E402
    FROM_NAME_MAX,
    SUBJECT_MAX,
    one_line,
    respondent_from_name,
)

INJECTION = "Acme\r\nBcc: victim\r\nX-Evil: 1"


# ------------------------------------------------------------------ one_line


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, ""),
        ("", ""),
        ("  Acme   Corp  ", "Acme Corp"),
        ("Acme\r\nBcc: x@example.net", "Acme Bcc: x@example.net"),
        ("Acme\nCorp\rLtd", "Acme Corp Ltd"),
        ("Acme\tCorp\x00\x07\x1b[31m", "Acme Corp [31m"),
        ("Acme Corp Ltd\x85end", "Acme Corp Ltd end"),
        # bidi overrides and zero-width characters can't reorder or hide text
        ("Acme‮gnp.exe", "Acmegnp.exe"),
        ("Ac​me﻿", "Acme"),
        ("Stichting Zorg & Welzijn", "Stichting Zorg & Welzijn"),
        ("Café Ñandú 東京", "Café Ñandú 東京"),
    ],
)
def test_one_line_folds_and_strips(value, expected):
    assert one_line(value, 200) == expected


def test_one_line_caps_with_an_ellipsis():
    assert one_line("x" * 200, FROM_NAME_MAX) == "x" * (FROM_NAME_MAX - 1) + "…"
    assert len(one_line("y " * 200, SUBJECT_MAX)) <= SUBJECT_MAX
    assert one_line("short", FROM_NAME_MAX) == "short"
    assert one_line("z" * FROM_NAME_MAX, FROM_NAME_MAX) == "z" * FROM_NAME_MAX


# ------------------------------------------------------ the From name


@pytest.mark.parametrize(
    "workspace, instance, expected",
    [
        ("Acme Corp", "BetterCollected", "Acme Corp via BetterCollected"),
        ("  Acme   Corp ", "Better Collected", "Acme Corp via Better Collected"),
        ("Acme\r\nBcc: x\r\nX-Evil: 1", "BC", "Acme Bcc: x X-Evil: 1 via BC"),
        # no workspace, or the instance's own name: the instance alone
        (None, "BetterCollected", "BetterCollected"),
        ("", "BetterCollected", "BetterCollected"),
        ("Better Collected", "BetterCollected", "BetterCollected"),
        # no instance name configured: the product's name
        ("Acme", "", "Acme via BetterCollected"),
        ("Acme", None, "Acme via BetterCollected"),
        ("Acme", "\r\n", "Acme via BetterCollected"),
        # U+2028 / U+2029 are line breaks too
        ("Acme\u2028Bcc: x\u2029Corp", "BC", "Acme Bcc: x Corp via BC"),
        # an encoded-word start is removed, however it is nested
        ("=?utf-8?b?QWNtZQ==?=", "BC", "utf-8?b?QWNtZQ== via BC"),
        ("=?=?x?q?y?=", "BC", "x?q?y?= via BC"),
        ("=\u200b?Acme", "BC", "Acme via BC"),
        ("Acme ==??Corp", "BC", "Acme Corp via BC"),
        # looks like an address or a link: the instance alone
        ("billing@bank.example", "BC", "BC"),
        ("Acme <ceo@acme.example>", "BC", "BC"),
        ("https://bank.example/login", "BC", "BC"),
        ("go to bank.example://x", "BC", "BC"),
        ("Acme B.V.", "BC", "Acme B.V. via BC"),
    ],
)
def test_the_respondent_from_name(workspace, instance, expected):
    assert respondent_from_name(workspace, instance) == expected


@pytest.mark.parametrize("own", [True, False])
@pytest.mark.parametrize(
    "title", ["=?utf-8?b?QmFuaw==?= <x@y.example>", "support@bank.example", "https://a.example"]
)
def test_a_title_posing_as_an_address_or_encoded_name_is_not_in_from(
    monkeypatch, own, title
):
    _, raw = _send(
        monkeypatch, title, "Survey", workspace_values=OWN_FULL_SMTP if own else None
    )
    _, parsed = _headers(raw)
    (name, address), = getaddresses([str(parsed["From"])])
    assert name == "BetterCollected"
    assert "=?" not in raw.split("\n\n", 1)[0].split("Subject:")[0]


@pytest.mark.parametrize("workspace", ["W" * 300, "w " * 200, "東" * 90])
def test_a_long_workspace_title_is_cut_but_the_instance_stays(workspace):
    name = respondent_from_name(workspace, "BetterCollected")
    assert len(name) <= FROM_NAME_MAX
    assert name.endswith(" via BetterCollected")
    assert "…" in name


def test_a_long_instance_name_is_capped_too():
    name = respondent_from_name("Acme", "I" * 100)
    assert len(name) <= FROM_NAME_MAX and name.startswith("Acme via I")


ACTION_ID = "act-1"


def _param(name, value):
    return {"name": name, "value": value}


def _action(**defaults):
    return {
        "id": ACTION_ID,
        "name": "responder_copy_mail",
        "predefined": True,
        "parameters": [_param(k, v) for k, v in defaults.items()],
        "secrets": [_param("Password", crypto.encrypt("smtp-pw"))],
    }


INSTANCE_SMTP = {
    "Username": "mailer",
    "Sender": "noreply@instance.example",
    "Port": "587",
    "server": "smtp.instance.example",
}
OWN_SMTP = {"Sender": "forms@acme.example", "server": "smtp.acme.example"}
# what a workspace sends through its own server: the whole SMTP group is its
# own (the instance's login is never mixed in), Password being a secret
OWN_FULL_SMTP = {**OWN_SMTP, "Username": "acme-user", "Port": "2525"}


def _overrides(values):
    return {ACTION_ID: [_param(k, v) for k, v in values.items()]}


# ------------------------------------------------------- the sent message


class _CapturingFastMail:
    sent = []

    def __init__(self, config):
        self.config = config

    async def send_message(self, message, template_name=None):
        _CapturingFastMail.sent.append((self.config, message, template_name))


def _send(
    monkeypatch, workspace_title, form_title, workspace_values=None, form_values=None
):
    _CapturingFastMail.sent = []
    monkeypatch.setattr(actions, "FastMail", _CapturingFastMail)
    action = _action(**INSTANCE_SMTP)
    workspace = {
        "title": workspace_title,
        "parameters": _overrides(workspace_values or {}),
    }
    if workspace_values:
        workspace["secrets"] = {
            ACTION_ID: [_param("Password", crypto.encrypt("acme-pw"))]
        }
    form = {
        "builder_version": "v2",
        "title": form_title,
        "welcome_page": {"title": form_title, "description": ""},
        "fields": [],
        "parameters": _overrides(form_values or {}),
    }
    response = {"dataOwnerIdentifier": "respondent@example.org", "answers": {}}

    async def run():
        await actions.run_action(
            json.dumps(action),
            json.dumps(form),
            json.dumps(response),
            workspace=json.dumps(workspace),
        )
        await asyncio.sleep(0)  # the send is scheduled, not awaited
        assert len(_CapturingFastMail.sent) == 1
        config, message, template = _CapturingFastMail.sent[0]
        built = await FastMail(config).get_message(message, template_name=template)
        return config, built.as_string()

    return asyncio.run(run())


def _headers(raw):
    head = raw.split("\n\n", 1)[0]
    return head, message_from_string(raw)


@pytest.fixture(autouse=True)
def instance_name(monkeypatch):
    monkeypatch.setattr(settings, "organization_name", "BetterCollected")


def test_own_smtp_sends_as_workspace_via_instance_from_its_own_address(monkeypatch):
    config, raw = _send(
        monkeypatch, "Acme Corp", "Job application", workspace_values=OWN_FULL_SMTP
    )
    _, parsed = _headers(raw)
    assert config.MAIL_SERVER == "smtp.acme.example"
    assert parsed["From"] == "Acme Corp via BetterCollected <forms@acme.example>"
    assert parsed["Subject"] == "Copy of your response to Job application"
    assert parseaddr(parsed["To"])[1] == "respondent@example.org"


def test_the_instances_smtp_sends_as_workspace_via_instance_too(monkeypatch):
    config, raw = _send(monkeypatch, "Acme Corp", "Job application")
    _, parsed = _headers(raw)
    assert config.MAIL_SERVER == "smtp.instance.example"
    assert parsed["From"] == "Acme Corp via BetterCollected <noreply@instance.example>"
    assert parsed["Subject"] == "Copy of your response to Job application"


@pytest.mark.parametrize("own", [True, False])
def test_the_from_name_follows_the_configured_instance_name(monkeypatch, own):
    monkeypatch.setattr(settings, "organization_name", "Formulieren NL")
    _, raw = _send(
        monkeypatch,
        "Acme",
        "Survey",
        workspace_values=OWN_FULL_SMTP if own else None,
    )
    _, parsed = _headers(raw)
    assert parsed["From"].startswith("Acme via Formulieren NL <")


@pytest.mark.parametrize("own", [True, False])
def test_a_workspace_without_a_title_is_sent_in_the_instances_name(monkeypatch, own):
    _, raw = _send(
        monkeypatch, None, "Survey", workspace_values=OWN_FULL_SMTP if own else None
    )
    _, parsed = _headers(raw)
    assert parsed["From"].startswith("BetterCollected <")
    assert "via" not in parsed["From"]


@pytest.mark.parametrize("own", [True, False])
def test_titles_cannot_inject_headers(monkeypatch, own):
    _, raw = _send(
        monkeypatch,
        INJECTION,
        "Survey\r\nBcc: other@example.net\nX-Evil: 2",
        workspace_values=OWN_FULL_SMTP if own else None,
    )
    head, parsed = _headers(raw)
    lines = head.splitlines()
    # no header of its own, only folded continuation lines at most
    assert not any(line.lower().startswith(("bcc:", "x-evil:")) for line in lines)
    assert parsed["Bcc"] is None and parsed["X-Evil"] is None
    subject = " ".join(str(parsed["Subject"]).split())
    assert subject == "Copy of your response to Survey Bcc: other@example.net X-Evil: 2"
    # the From header is one address, the instance's tail intact
    (name, address), = getaddresses([str(parsed["From"])])
    assert " ".join(name.split()) == "Acme Bcc: victim X-Evil: 1 via BetterCollected"
    assert address == ("forms@acme.example" if own else "noreply@instance.example")
    assert parseaddr(parsed["To"])[1] == "respondent@example.org"


@pytest.mark.parametrize("own", [True, False])
def test_quotes_and_specials_in_a_title_stay_inside_the_display_name(monkeypatch, own):
    _, raw = _send(
        monkeypatch,
        'Acme "Best, Inc" <evil>',
        "Survey",
        workspace_values=OWN_FULL_SMTP if own else None,
    )
    _, parsed = _headers(raw)
    addresses = getaddresses([str(parsed["From"])])
    assert len(addresses) == 1
    name, address = addresses[0]
    assert address in ("forms@acme.example", "noreply@instance.example")
    assert name == 'Acme "Best, Inc" <evil> via BetterCollected'
    assert "evil" not in address
    assert parsed["Bcc"] is None


@pytest.mark.parametrize("own", [True, False])
def test_long_titles_are_capped(monkeypatch, own):
    config, raw = _send(
        monkeypatch,
        "W" * 300,
        "F" * 300,
        workspace_values=OWN_FULL_SMTP if own else None,
    )
    _, parsed = _headers(raw)
    assert len(config.MAIL_FROM_NAME) <= FROM_NAME_MAX
    assert config.MAIL_FROM_NAME.endswith("… via BetterCollected")
    subject = " ".join(str(parsed["Subject"]).split())
    assert len(subject) <= SUBJECT_MAX + 30  # the decoded value; encoded words wrap it


def test_a_sender_that_is_not_one_address_is_refused(monkeypatch):
    with pytest.raises(ValidationError):
        _send(
            monkeypatch,
            "Acme",
            "Survey",
            workspace_values={
                **OWN_FULL_SMTP,
                "Sender": "forms@acme.example\r\nBcc: victim@example.net",
            },
        )


# ------------------------------------------------------ the setting


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "Better Collected"),
        ("", "Better Collected"),
        ("   ", "Better Collected"),
        ("  Formulieren NL ", "Formulieren NL"),
    ],
)
def test_the_instance_name_setting_reads_the_environment(monkeypatch, value, expected):
    from settings.application import ApplicationSettings

    if value is None:
        monkeypatch.delenv("ORGANIZATION_NAME", raising=False)
    else:
        monkeypatch.setenv("ORGANIZATION_NAME", value)
    assert ApplicationSettings().organization_name == expected
