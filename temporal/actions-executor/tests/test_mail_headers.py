"""The respondent's copy of a response: through the workspace's own SMTP
server it is sent in the workspace's name (its title as the From name, the
form title in the subject, its own address); through the action's defaults
(the instance's server) never in a workspace's name. Titles are free text, so
both header values are folded to one line and capped: no header injection."""

import asyncio
import json
from email import message_from_string
from email.utils import parseaddr

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
    uses_own_smtp,
)

INJECTION = "Acme\r\nBcc: victim@example.net\r\nX-Evil: 1"


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


# ------------------------------------------------------------- whose SMTP


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


def _overrides(values):
    return {ACTION_ID: [_param(k, v) for k, v in values.items()]}


@pytest.mark.parametrize(
    "workspace_values, form_values, own",
    [
        ({}, {}, False),
        (OWN_SMTP, {}, True),
        ({}, OWN_SMTP, True),
        ({"server": "smtp.acme.example"}, {"Sender": "forms@acme.example"}, True),
        # only one of the two: not the workspace's own server and address
        ({"server": "smtp.acme.example"}, {}, False),
        ({"Sender": "forms@acme.example"}, {}, False),
        # an empty override is no override
        ({"server": "", "Sender": ""}, {}, False),
    ],
)
def test_own_smtp_means_the_workspace_set_server_and_sender(
    workspace_values, form_values, own
):
    action = _action(**INSTANCE_SMTP)
    workspace = {"parameters": _overrides(workspace_values)}
    form = {"parameters": _overrides(form_values)}
    assert uses_own_smtp(action, workspace, form) is own


def test_another_actions_overrides_do_not_count():
    workspace = {
        "parameters": {"other-action": [_param(k, v) for k, v in OWN_SMTP.items()]}
    }
    assert not uses_own_smtp(_action(**INSTANCE_SMTP), workspace, {})


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


def test_own_smtp_sends_in_the_workspaces_name_from_its_own_address(monkeypatch):
    config, raw = _send(
        monkeypatch, "Acme Corp", "Job application", workspace_values=OWN_SMTP
    )
    _, parsed = _headers(raw)
    assert config.MAIL_SERVER == "smtp.acme.example"
    assert parsed["From"] == "Acme Corp <forms@acme.example>"
    assert parsed["Subject"] == "Copy of your response to Job application"
    assert parseaddr(parsed["To"])[1] == "respondent@example.org"


def test_the_instances_smtp_never_sends_in_a_workspaces_name(monkeypatch):
    config, raw = _send(monkeypatch, "Acme Corp", "Job application")
    _, parsed = _headers(raw)
    assert config.MAIL_SERVER == "smtp.instance.example"
    assert parsed["From"] == "noreply@instance.example"
    assert "Acme" not in parsed["From"]
    assert parsed["Subject"] == "Copy of your response to Job application"


@pytest.mark.parametrize("own", [True, False])
def test_titles_cannot_inject_headers(monkeypatch, own):
    _, raw = _send(
        monkeypatch,
        INJECTION,
        "Survey\r\nBcc: other@example.net\nX-Evil: 2",
        workspace_values=OWN_SMTP if own else None,
    )
    head, parsed = _headers(raw)
    lines = head.splitlines()
    # no header of its own, only folded continuation lines at most
    assert not any(line.lower().startswith(("bcc:", "x-evil:")) for line in lines)
    assert parsed["Bcc"] is None and parsed["X-Evil"] is None
    subject = " ".join(str(parsed["Subject"]).split())
    assert subject == "Copy of your response to Survey Bcc: other@example.net X-Evil: 2"
    if own:
        assert parsed["From"].endswith("<forms@acme.example>")
        assert "\n" not in parsed["From"].replace("\n ", "").replace("\n\t", "")


def test_long_titles_are_capped(monkeypatch):
    config, raw = _send(monkeypatch, "W" * 300, "F" * 300, workspace_values=OWN_SMTP)
    _, parsed = _headers(raw)
    assert config.MAIL_FROM_NAME == "W" * (FROM_NAME_MAX - 1) + "…"
    subject = " ".join(str(parsed["Subject"]).split())
    assert len(subject) <= SUBJECT_MAX + 30  # the decoded value; encoded words wrap it


def test_a_sender_that_is_not_one_address_is_refused(monkeypatch):
    with pytest.raises(ValidationError):
        _send(
            monkeypatch,
            "Acme",
            "Survey",
            workspace_values={
                "server": "smtp.acme.example",
                "Sender": "forms@acme.example\r\nBcc: victim@example.net",
            },
        )
