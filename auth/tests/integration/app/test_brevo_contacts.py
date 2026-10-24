"""The one-off Brevo contact erasure (``python -m auth.brevo_contacts``):
contacts whose address has no account are counted, and deleted only with
--apply; contacts on a Brevo list only with --include-listed. Brevo is a
mock transport: no test reaches it."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from auth import brevo_contacts
from auth.brevo_contacts import BrevoContacts, BrevoError, erase


class FakeUsers:
    """The two lookups the command makes, over a fixed set of accounts."""

    def __init__(self, emails):
        self.emails = list(emails)

    async def get_users_by_emails(self, emails):
        return [SimpleNamespace(email=e) for e in self.emails if e in set(emails)]

    async def find_users_by_email_ci(self, email):
        return [SimpleNamespace(email=e) for e in self.emails if e.lower() == email]


class FakeBrevo:
    def __init__(self, contacts, page_size=2):
        self.contacts = contacts
        self.page_size = page_size
        self.deleted = []
        self.requests = []
        self.rate_limited = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.headers["api-key"] == "contacts-key"
        if self.rate_limited:
            self.rate_limited -= 1
            return httpx.Response(429)
        if request.method == "GET":
            offset = int(request.url.params["offset"])
            limit = int(request.url.params["limit"])
            page = self.contacts[offset : offset + min(limit, self.page_size)]
            return httpx.Response(200, json={"contacts": page, "count": len(page)})
        assert request.url.params["identifierType"] == "email_id"
        self.deleted.append(
            request.url.raw_path.decode().split("?")[0].rsplit("/", 1)[1]
        )
        return httpx.Response(204)


CONTACTS = [
    {"email": "kept@acme.org", "listIds": []},
    {"email": "mixed@acme.org", "listIds": []},  # account stored as Mixed@Acme.org
    {"email": "gone@acme.org", "listIds": []},
    {"email": "subscriber@elsewhere.org", "listIds": [3]},
    {"email": "gone2@acme.org", "listIds": []},
]
ACCOUNTS = ["kept@acme.org", "Mixed@Acme.org"]


@pytest.fixture
def brevo(monkeypatch):
    fake = FakeBrevo(CONTACTS)
    monkeypatch.setattr(brevo_contacts, "PAGE_SIZE", 2)

    async def no_wait(seconds):
        return None

    client = BrevoContacts(
        "contacts-key", transport=httpx.MockTransport(fake.handler), sleep=no_wait
    )
    return fake, client


def test_a_dry_run_counts_and_deletes_nothing(brevo):
    fake, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), False, False))

    assert counts == {
        "contacts": 5,
        "with_account": 2,
        "without_account": 3,
        "without_account_on_no_list": 2,
        "without_account_on_a_list": 1,
        "to_delete": 2,
        "deleted": 0,
        "absent": 0,
        "failed": 0,
    }
    assert fake.deleted == []
    assert {r.method for r in fake.requests} == {"GET"}


def test_apply_deletes_contacts_without_an_account_on_no_list(brevo):
    fake, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), True, False))

    assert counts["deleted"] == 2
    assert sorted(fake.deleted) == ["gone%40acme.org", "gone2%40acme.org"]


def test_include_listed_also_deletes_list_members(brevo):
    fake, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), True, True))

    assert counts["to_delete"] == counts["deleted"] == 3
    assert "subscriber%40elsewhere.org" in fake.deleted


def test_rate_limits_are_waited_out(brevo):
    fake, client = brevo
    fake.rate_limited = 2
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), False, False))
    assert counts["contacts"] == 5


def test_a_refused_listing_stops_before_any_deletion():
    def refuse(request):
        return httpx.Response(401)

    client = BrevoContacts("bad-key", transport=httpx.MockTransport(refuse))
    with pytest.raises(BrevoError):
        asyncio.run(erase(client, FakeUsers([]), True, True))


def test_the_command_needs_the_key(monkeypatch, capsys):
    monkeypatch.delenv("BREVO_CONTACTS_API_KEY", raising=False)
    assert brevo_contacts.main([]) == 2
    assert "BREVO_CONTACTS_API_KEY" in capsys.readouterr().out


def test_the_command_prints_counts_only(monkeypatch, capsys):
    monkeypatch.setenv("BREVO_CONTACTS_API_KEY", "contacts-key")

    async def fake_main(args):
        return {"contacts": 1, "failed": 0}

    monkeypatch.setattr(brevo_contacts, "_main", fake_main)
    assert brevo_contacts.main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"applied": False, "contacts": 1, "failed": 0}
