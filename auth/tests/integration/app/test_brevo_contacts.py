"""The one-off Brevo contact erasure (``python -m auth.brevo_contacts``):
contacts without an account are counted (by marker and list), and deleted
only with --apply and a marker, and only when on no Brevo list. Brevo is a
mock transport: no test reaches it."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from auth import brevo_contacts
from auth.brevo_contacts import BrevoContacts, BrevoError, erase, parse_marker


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
    {"email": "kept@acme.org", "listIds": [], "attributes": {"SOURCE": "bc"}},
    # an account stored as Mixed@Acme.org
    {"email": "mixed@acme.org", "listIds": [], "attributes": {}},
    {"email": "gone@acme.org", "listIds": [], "attributes": {"SOURCE": "bc"}},
    {"email": "gone-listed@acme.org", "listIds": [3], "attributes": {"SOURCE": "BC"}},
    {"email": "crm@elsewhere.org", "listIds": [], "attributes": {"SOURCE": "crm"}},
    {"email": "subscriber@elsewhere.org", "listIds": [3], "attributes": {}},
    {"email": "bare@elsewhere.org", "listIds": [], "attributes": {"FIRSTNAME": ""}},
]
ACCOUNTS = ["kept@acme.org", "Mixed@Acme.org"]
MARKER = ("SOURCE", "bc")


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


def test_a_dry_run_shows_the_breakdown_and_deletes_nothing(brevo):
    fake, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), False, MARKER))

    assert counts["contacts"] == 7
    assert counts["with_account"] == 2
    assert counts["without_account"] == 5
    assert counts["without_account_by_marker_and_list"] == {
        "marked_unlisted": 1,
        "marked_listed": 1,
        "unmarked_unlisted": 2,
        "unmarked_listed": 1,
    }
    assert counts["without_account_with_no_attributes"] == 2
    assert counts["without_account_attribute_names"] == {"SOURCE": 3}
    assert counts["marker"] == "SOURCE=bc"
    assert counts["to_delete"] == 1 and counts["deleted"] == 0
    assert fake.deleted == []
    assert {r.method for r in fake.requests} == {"GET"}
    # counts and attribute names only: no address, no value
    printed = json.dumps(counts)
    assert "@" not in printed and "crm" not in printed


def test_without_a_marker_nothing_is_a_target(brevo):
    _, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), False, None))
    assert counts["to_delete"] == 0
    assert counts["without_account_by_marker_and_list"]["unmarked_unlisted"] == 3


def test_apply_needs_a_marker(brevo):
    _, client = brevo
    with pytest.raises(ValueError):
        asyncio.run(erase(client, FakeUsers(ACCOUNTS), True, None))


def test_apply_deletes_only_marked_contacts_on_no_list(brevo):
    fake, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), True, MARKER))

    assert counts["deleted"] == 1
    assert fake.deleted == ["gone%40acme.org"]


def test_a_name_only_marker_matches_any_value(brevo):
    fake, client = brevo
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), True, ("source", None)))
    # gone@ and crm@ carry SOURCE and are on no list
    assert counts["deleted"] == 2
    assert sorted(fake.deleted) == ["crm%40elsewhere.org", "gone%40acme.org"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("SOURCE", ("SOURCE", None)),
        (" SOURCE = bc ", ("SOURCE", "bc")),
        ("", None),
        (None, None),
    ],
)
def test_parse_marker(value, expected):
    assert parse_marker(value) == expected


def test_a_marker_needs_a_name():
    with pytest.raises(ValueError):
        parse_marker("=bc")


@pytest.mark.parametrize(
    "email,path",
    [
        ("a/b@acme.org", "a%2Fb%40acme.org"),
        ("a?b=1@acme.org", "a%3Fb%3D1%40acme.org"),
        ("a#b@acme.org", "a%23b%40acme.org"),
        ("A+B@Acme.org", "a%2Bb%40acme.org"),
    ],
)
def test_addresses_are_one_encoded_path_segment(email, path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(204)

    client = BrevoContacts("k", transport=httpx.MockTransport(handler))
    assert asyncio.run(client.remove_contact(email)) == "deleted"
    (request,) = seen
    assert request.url.raw_path.decode() == (
        f"/v3/contacts/{path}?identifierType=email_id"
    )


def test_rate_limits_are_waited_out(brevo):
    fake, client = brevo
    fake.rate_limited = 2
    counts = asyncio.run(erase(client, FakeUsers(ACCOUNTS), False, MARKER))
    assert counts["contacts"] == 7


def test_a_refused_listing_stops_before_any_deletion():
    def refuse(request):
        return httpx.Response(401)

    client = BrevoContacts("bad-key", transport=httpx.MockTransport(refuse))
    with pytest.raises(BrevoError):
        asyncio.run(erase(client, FakeUsers([]), True, MARKER))


def test_the_key_never_comes_from_the_command_line(monkeypatch, capsys):
    monkeypatch.delenv("BREVO_CONTACTS_API_KEY", raising=False)
    monkeypatch.setattr(brevo_contacts.sys.stdin, "isatty", lambda: False)
    assert brevo_contacts.main([]) == 2
    assert "BREVO_CONTACTS_API_KEY" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        brevo_contacts.main(["--api-key", "x"])


def test_the_key_is_asked_for_without_echo(monkeypatch):
    monkeypatch.delenv("BREVO_CONTACTS_API_KEY", raising=False)
    monkeypatch.setattr(brevo_contacts.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(brevo_contacts, "getpass", lambda prompt: " typed-key ")
    assert brevo_contacts.api_key() == "typed-key"
    monkeypatch.setenv("BREVO_CONTACTS_API_KEY", "env-key")
    assert brevo_contacts.api_key() == "env-key"


def test_apply_without_a_marker_stops_before_brevo(monkeypatch, capsys):
    monkeypatch.setenv("BREVO_CONTACTS_API_KEY", "contacts-key")

    async def never(*args):
        raise AssertionError("must not run")

    monkeypatch.setattr(brevo_contacts, "_main", never)
    assert brevo_contacts.main(["--apply"]) == 2
    assert "--marker" in capsys.readouterr().out


def test_the_command_prints_counts_only(monkeypatch, capsys):
    monkeypatch.setenv("BREVO_CONTACTS_API_KEY", "contacts-key")

    async def fake_main(args, key, marker):
        assert key == "contacts-key" and marker == ("SOURCE", "bc")
        return {"contacts": 1, "failed": 0}

    monkeypatch.setattr(brevo_contacts, "_main", fake_main)
    assert brevo_contacts.main(["--marker", "SOURCE=bc"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"applied": False, "contacts": 1, "failed": 0}
