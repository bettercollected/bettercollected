"""The "send me a copy" action (creator_copy_mail) mails only a current member
of the form's workspace or the form's creator, checked right before sending
through the backend's in-network route. Anything else, or a check that cannot
be made, sends nothing and fails the job with a message that holds no address.
"""

import asyncio
import json
import logging

import httpx
import pytest
from cryptography.fernet import Fernet

from settings.application import settings

if not settings.aes_hex_key:
    settings.aes_hex_key = Fernet.generate_key().decode()

from configs.crypto import crypto  # noqa: E402
from utilities import actions, copy_recipient  # noqa: E402
from utilities.copy_recipient import (  # noqa: E402
    CopyRecipientRefused,
    CopyRecipientUnavailable,
    normalize_address,
)

ACTION_ID = "act-1"
WORKSPACE_ID = "65a000000000000000000001"
FORM_ID = "65a000000000000000000002"
MEMBER = "member@acme.example"
CREATOR = "creator@acme.example"
OUTSIDER = "someone@elsewhere.example"
ROUTE = f"/temporal/workspaces/{WORKSPACE_ID}/forms/{FORM_ID}/copy-recipient"


class _Capture:
    sent = []

    def __init__(self, config):
        self.config = config

    async def send_message(self, message, template_name=None):
        _Capture.sent.append([r.email for r in message.recipients])


class _Backend:
    """The backend's route: a fixed set of current addresses, a record of what
    was asked."""

    def __init__(self, allowed, status=200, body=None, error=None):
        self.allowed = {normalize_address(a) for a in allowed}
        self.status = status
        self.body = body
        self.error = error
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if self.error:
            raise self.error
        body = self.body
        if body is None:
            body = {"allowed": normalize_address(json["address"]) in self.allowed}
        return httpx.Response(self.status, json=body)


@pytest.fixture(autouse=True)
def _mail(monkeypatch):
    _Capture.sent = []
    monkeypatch.setattr(actions, "FastMail", _Capture)
    monkeypatch.setattr(settings, "server_url", "http://backend:8001/api/v1")
    monkeypatch.setattr(settings, "api_key", "test-job-key")


@pytest.fixture()
def backend(monkeypatch):
    def install(*allowed, **kwargs):
        fake = _Backend(allowed, **kwargs)
        monkeypatch.setattr(copy_recipient.httpx, "post", fake.post)
        return fake

    return install


def _run(recipient, workspace_id=WORKSPACE_ID, form_id=FORM_ID, **extra):
    action = {
        "id": ACTION_ID,
        "name": "creator_copy_mail",
        "predefined": True,
        "parameters": [
            {"name": "Username", "value": "instance-user"},
            {"name": "Sender", "value": "noreply@instance.example"},
            {"name": "Port", "value": "587"},
            {"name": "server", "value": "smtp.instance.example"},
            {"name": "Receiving Mail Address", "value": recipient},
        ],
        "secrets": [{"name": "Password", "value": crypto.encrypt("pw")}],
    }
    workspace = {"title": "Acme", **extra}
    if workspace_id:
        workspace["id"] = workspace_id
    form = {
        "builder_version": "v2",
        "title": "Survey",
        "welcome_page": {"title": "Survey", "description": ""},
        "fields": [],
    }
    if form_id:
        form["form_id"] = form_id

    async def go():
        await actions.run_action(
            json.dumps(action),
            json.dumps(form),
            json.dumps({"answers": {}}),
            workspace=json.dumps(workspace),
        )
        await asyncio.sleep(0)

    asyncio.run(go())
    return _Capture.sent


def test_a_member_is_mailed(backend):
    fake = backend(MEMBER)
    assert _run(MEMBER) == [[MEMBER]]
    (call,) = fake.calls
    assert call["url"] == f"http://backend:8001/api/v1{ROUTE}"
    assert call["headers"] == {"api-key": "test-job-key"}
    assert call["json"] == {"address": MEMBER}


def test_the_creator_is_mailed(backend):
    backend(CREATOR)
    assert _run(CREATOR) == [[CREATOR]]


def test_an_outsider_is_not_mailed(backend):
    backend(MEMBER, CREATOR)
    with pytest.raises(CopyRecipientRefused, match="copy_recipient_not_allowed"):
        _run(OUTSIDER)
    assert _Capture.sent == []


def test_a_member_removed_since_the_action_was_saved_is_not_mailed(backend):
    backend(CREATOR)  # the membership is gone: only the creator is left
    with pytest.raises(CopyRecipientRefused):
        _run(MEMBER)
    assert _Capture.sent == []


@pytest.mark.parametrize(
    "written",
    ["Member@Acme.Example", "  member@acme.example  ", " MEMBER@ACME.EXAMPLE\t"],
)
def test_case_and_surrounding_space_do_not_matter(backend, written):
    backend(MEMBER)
    assert _run(written) == [[MEMBER]]


@pytest.mark.parametrize(
    "written", ["member+news@acme.example", "mem.ber@acme.example"]
)
def test_plus_tags_and_dots_are_not_stripped(backend, written):
    backend(MEMBER)
    with pytest.raises(CopyRecipientRefused):
        _run(written)
    assert _Capture.sent == []


def test_a_members_own_plus_address_counts_when_it_matches_exactly(backend):
    backend("member+news@acme.example")
    assert _run("Member+News@acme.example") == [["member+news@acme.example"]]


@pytest.mark.parametrize(
    "written",
    [
        "member@acme.example\r\nBcc: someone@elsewhere.example",
        "member@acme.example\nBcc: x@y.example",
        "member@acme.example,someone@elsewhere.example",
        "member@acme.example; someone@elsewhere.example",
        "member@acme.example someone@elsewhere.example",
        "Member <member@acme.example>",
        '"member@acme.example"@elsewhere.example',
        "member@acme.example@elsewhere.example",
        "@acme.example",
        "member@",
        "member",
        "a" * 250 + "@acme.example",
    ],
)
def test_header_injection_and_lists_are_refused_without_asking(backend, written):
    fake = backend(MEMBER)
    with pytest.raises(CopyRecipientRefused):
        _run(written)
    assert fake.calls == []
    assert _Capture.sent == []


def test_an_unreachable_backend_sends_nothing(backend):
    backend(MEMBER, error=httpx.ConnectError("down"))
    with pytest.raises(CopyRecipientUnavailable):
        _run(MEMBER)
    assert _Capture.sent == []


@pytest.mark.parametrize(
    "status, body",
    [
        (403, {"detail": "no"}),
        (404, {"detail": "Not Found"}),
        (500, {}),
        (200, {"allowed": "yes"}),
        (200, {}),
        (200, ["allowed"]),
    ],
)
def test_an_answer_that_is_not_a_clear_yes_sends_nothing(backend, status, body):
    backend(MEMBER, status=status, body=body)
    with pytest.raises(CopyRecipientUnavailable):
        _run(MEMBER)
    assert _Capture.sent == []


def test_a_job_without_a_workspace_or_form_sends_nothing(backend):
    fake = backend(MEMBER)
    with pytest.raises(CopyRecipientUnavailable):
        _run(MEMBER, workspace_id=None)
    with pytest.raises(CopyRecipientUnavailable):
        _run(MEMBER, form_id=None)
    assert fake.calls == []
    assert _Capture.sent == []


def test_no_recipient_sends_nothing_and_asks_nothing(backend):
    fake = backend(MEMBER)
    assert _run("") == []
    assert fake.calls == []


def test_logs_and_errors_hold_no_address(backend, caplog):
    backend(MEMBER)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(CopyRecipientRefused) as refused:
        _run(OUTSIDER)
    backend(MEMBER, error=httpx.ConnectError("down"))
    with pytest.raises(CopyRecipientUnavailable) as unavailable:
        _run(MEMBER)
    texts = [caplog.text, str(refused.value), str(unavailable.value)]
    for text in texts:
        for address in (OUTSIDER, MEMBER, CREATOR):
            assert address not in text
    assert "creator_copy_mail not sent" in caplog.text


def test_the_instances_defaults_are_checked_like_any_other_recipient(backend):
    # the address can come from the action's own defaults: still checked
    backend(MEMBER)
    with pytest.raises(CopyRecipientRefused):
        _run(OUTSIDER, parameters={})
    assert _Capture.sent == []


@pytest.mark.parametrize(
    "value, expected",
    [
        ("A@B.C", "a@b.c"),
        ("  a@b.c ", "a@b.c"),
        ("a+t@b.c", "a+t@b.c"),
        ("a.b@b.c", "a.b@b.c"),
        (None, None),
        (5, None),
        ("", None),
        ("a@b.c\x00", None),
        ("a@b.c x", None),
    ],
)
def test_normalize_address(value, expected):
    assert normalize_address(value) == expected
