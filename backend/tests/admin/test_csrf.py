import pytest

from backend.admin.security import csrf
from backend.admin.security.clock import FakeClock

KEY = b"k" * 32
HOSTS = ["admin.example.org", "localhost:8100"]


def test_session_token_is_stable_per_session_and_key():
    a = csrf.session_token(KEY, "session-1")
    assert a == csrf.session_token(KEY, "session-1")
    assert a != csrf.session_token(KEY, "session-2")
    assert a != csrf.session_token(b"z" * 32, "session-1")
    assert "=" not in a and "+" not in a and "/" not in a


def test_session_token_verification():
    token = csrf.session_token(KEY, "s1")
    assert csrf.verify_session_token(KEY, "s1", token)
    assert not csrf.verify_session_token(KEY, "s2", token)
    assert not csrf.verify_session_token(
        KEY, "s1", token[:-1] + "A" * (token[-1] != "A")
    )
    for bad in (None, "", "ü", " ", 5, "x" * 10_000):
        assert not csrf.verify_session_token(KEY, "s1", bad)


def test_form_token_round_trip_and_expiry():
    clock = FakeClock(10_000)
    token = csrf.issue_form_token(KEY, clock)
    assert csrf.verify_form_token(KEY, token, token, clock)
    clock.advance(csrf.FORM_TOKEN_MAX_AGE - 1)
    assert csrf.verify_form_token(KEY, token, token, clock)
    clock.advance(2)
    assert not csrf.verify_form_token(KEY, token, token, clock)


def test_form_tokens_are_unique_and_must_match_each_other():
    clock = FakeClock(10_000)
    a, b = csrf.issue_form_token(KEY, clock), csrf.issue_form_token(KEY, clock)
    assert a != b
    assert not csrf.verify_form_token(KEY, a, b, clock)
    assert not csrf.verify_form_token(KEY, a, None, clock)
    assert not csrf.verify_form_token(KEY, None, a, clock)
    assert not csrf.verify_form_token(KEY, "", "", clock)


def test_form_token_must_be_signed_by_us():
    clock = FakeClock(10_000)
    token = csrf.issue_form_token(b"other-key" * 4, clock)
    assert not csrf.verify_form_token(KEY, token, token, clock)
    forged = "10000.AAAA.AAAA"
    assert not csrf.verify_form_token(KEY, forged, forged, clock)
    for bad in ("a.b", "a.b.c.d", "x.y.z", "..", "٣.a.b"):
        assert not csrf.verify_form_token(KEY, bad, bad, clock)


def test_form_token_from_the_future_is_rejected():
    clock = FakeClock(10_000)
    token = csrf.issue_form_token(KEY, clock)
    clock.set(10_000 - 3600)
    assert not csrf.verify_form_token(KEY, token, token, clock)


@pytest.mark.parametrize(
    "headers,allowed",
    [
        ({"Origin": "https://admin.example.org"}, True),
        ({"Origin": "https://ADMIN.example.org"}, True),
        ({"origin": "http://localhost:8100"}, True),
        (
            {"Origin": "https://admin.example.org", "Sec-Fetch-Site": "same-origin"},
            True,
        ),
        ({"Origin": "https://admin.example.org", "Sec-Fetch-Site": "none"}, True),
        ({"Referer": "https://admin.example.org/login?x=1"}, True),
        ({"Referer": "http://localhost:8100/"}, True),
        ({"Origin": "https://evil.example"}, False),
        ({"Origin": "https://admin.example.org.evil.example"}, False),
        ({"Origin": "https://evil.example/admin.example.org"}, False),
        ({"Origin": "https://admin.example.org@evil.example"}, False),
        ({"Origin": "https://admin.example.org:evil@x.example"}, False),
        ({"Origin": "http://localhost:9999"}, False),
        ({"Origin": "http://localhost"}, False),
        ({"Origin": "null"}, False),
        ({"Origin": ""}, False),
        ({"Origin": "ftp://admin.example.org"}, False),
        ({"Origin": "//admin.example.org"}, False),
        ({"Origin": "admin.example.org"}, False),
        (
            {"Origin": "https://admin.example.org", "Sec-Fetch-Site": "cross-site"},
            False,
        ),
        ({"Origin": "https://admin.example.org", "Sec-Fetch-Site": "same-site"}, False),
        ({"Origin": "https://admin.example.org", "Sec-Fetch-Site": ""}, False),
        ({"Sec-Fetch-Site": "same-origin"}, False),
        ({}, False),
        (
            {"Origin": "https://evil.example", "Referer": "https://admin.example.org/"},
            False,
        ),
        ({"Referer": "garbage"}, False),
    ],
)
def test_origin_allowed(headers, allowed):
    assert csrf.origin_allowed(headers, HOSTS) is allowed


def test_origin_allowed_never_raises_on_garbage():
    nasty = [
        "\x00",
        "http://[::1",
        "http://[bad]/",
        "https://a:99999999/",
        "http://:80",
        "ü" * 500,
        "%%%",
    ]
    for value in nasty:
        assert csrf.origin_allowed({"Origin": value}, HOSTS) is False
        assert csrf.origin_allowed({"Referer": value}, HOSTS) is False
    assert csrf.origin_allowed({"Origin": b"https://admin.example.org"}, HOSTS) is True
    assert csrf.origin_allowed({1: 2, None: None}, HOSTS) is False
    assert csrf.origin_allowed({"Origin": "https://admin.example.org"}, []) is False
    assert csrf.origin_allowed({"Origin": "https://x.example"}, ["", "  "]) is False


def test_ipv6_origin_matches_a_bracketed_allow_list_entry():
    assert csrf.origin_allowed({"Origin": "http://[::1]:8100"}, ["[::1]:8100"])
    assert not csrf.origin_allowed({"Origin": "http://[::1]:8101"}, ["[::1]:8100"])
