"""The SSRF guard of webhooks, class by class: what is refused when an address
is saved (syntax, then every answer of the resolver) and, in test_delivery.py,
again at the call (DNS rebinding)."""

import pytest

from backend.app.services.registration import client
from backend.app.services.webhooks import guard

pytestmark = pytest.mark.asyncio

PUBLIC = "93.184.216.34"


@pytest.fixture()
def answers(monkeypatch):
    """Set what the resolver answers for the length of a test."""
    state = {"result": [PUBLIC]}

    async def resolve(host, port=443):
        result = state["result"]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(client, "resolve", resolve)
    return state


async def refused(url: str) -> str:
    with pytest.raises(guard.DestinationRefused) as raised:
        await guard.check_destination(url)
    return raised.value.code


# -------------------------------------------------------------------- syntax


@pytest.mark.parametrize(
    "url,code",
    [
        ("http://example.org/hook", "not_https"),
        ("ftp://example.org/hook", "not_https"),
        ("file:///etc/passwd", "not_https"),
        ("//example.org/hook", "not_https"),
        ("example.org/hook", "not_https"),
        ("javascript:alert(1)", "not_https"),
        ("", "invalid_url"),
        ("   ", "invalid_url"),
        ("https://", "invalid_url"),
        ("https:///hook", "invalid_url"),
        # credentials, in every place they can hide
        ("https://user:pw@example.org/hook", "invalid_url"),
        ("https://user@example.org/hook", "invalid_url"),
        ("https://example.org@evil.example/hook", "invalid_url"),
        ("https://example.org%40evil.example/hook", "invalid_url"),
        ("https://@example.org/hook", "invalid_url"),
        # ports: 443 only
        ("https://example.org:8443/hook", "invalid_url"),
        ("https://example.org:80/hook", "invalid_url"),
        ("https://example.org:22/hook", "invalid_url"),
        ("https://example.org:0/hook", "invalid_url"),
        ("https://example.org:99999/hook", "invalid_url"),
        ("https://example.org:abc/hook", "invalid_url"),
        # whitespace, control characters and backslashes
        ("https://example.org/ho ok", "invalid_url"),
        ("https://example.org/hook\r\nHost: evil", "invalid_url"),
        ("https://example.org/hook\x00", "invalid_url"),
        ("https://example.org\\@evil.example/", "invalid_url"),
        ("https://example.org\\hook", "invalid_url"),
        # dot segments and encoded slashes in the path
        ("https://example.org/a/../b", "invalid_url"),
        ("https://example.org/a/%2e%2e/b", "invalid_url"),
        ("https://example.org/a%2fb", "invalid_url"),
        ("https://example.org/a%5cb", "invalid_url"),
        # non-ASCII outside the host must be percent-encoded
        ("https://example.org/höök", "invalid_url"),
        # too long
        ("https://example.org/" + "a" * 3000, "invalid_url"),
    ],
)
async def test_bad_syntax_is_refused(url, code, answers):
    assert await refused(url) == code


@pytest.mark.parametrize(
    "url",
    [
        # IP addresses in every spelling
        "https://127.0.0.1/hook",
        "https://10.0.0.1/hook",
        "https://93.184.216.34/hook",
        "https://2130706433/hook",
        "https://0x7f000001/hook",
        "https://0x7f.0.0.1/hook",
        "https://0177.0.0.1/hook",
        "https://127.1/hook",
        "https://[::1]/hook",
        "https://[::ffff:127.0.0.1]/hook",
        "https://[2606:4700:4700::1111]/hook",
        "https://[fd00:ec2::254]/hook",
        "https://169.254.169.254/latest/meta-data/",
        # names that are not on the public internet
        "https://localhost/hook",
        "https://localhost./hook",
        "https://intranet/hook",
        "https://printer.local/hook",
        "https://api.internal/hook",
        "https://nas.home.arpa/hook",
        "https://x.localhost/hook",
        "https://example.1/hook",
        "https://example.123/hook",
        # labels that cannot be a host name
        "https://-bad.example.org/hook",
        "https://bad-.example.org/hook",
        "https://exa_mple.example.org/hook",
        "https://exa mple.org/hook",
        "https://example..org/hook",
        "https://.example.org/hook",
        "https://" + "a" * 64 + ".example.org/hook",
    ],
)
async def test_hosts_that_are_not_public_names_are_refused(url, answers):
    assert await refused(url) == "invalid_url"


# ------------------------------------------------------------- normalisation


async def test_an_address_is_normalised_to_one_ascii_form(answers):
    cases = {
        "https://Example.ORG/Hook": "https://example.org/Hook",
        "https://example.org": "https://example.org/",
        "https://example.org./hook": "https://example.org/hook",
        "https://example.org/hook#frag": "https://example.org/hook",
        "https://example.org:443/hook": "https://example.org/hook",
        "  https://example.org/hook  ": "https://example.org/hook",
        "https://example.org/hook?a=1&b=2": "https://example.org/hook?a=1&b=2",
        # internationalised names become punycode, then are checked like any other
        "https://bücher.example/hook": "https://xn--bcher-kva.example/hook",
        # fullwidth letters and the ideographic full stop fold to plain ASCII
        "https://ｅxample。org/hook": "https://example.org/hook",
        # a zero-width space inside a label is dropped by nameprep
        "https://ex​ample.org/hook": "https://example.org/hook",
    }
    for given, expected in cases.items():
        url, host = await guard.check_destination(given)
        assert url == expected, given
        assert host.isascii() and host == host.lower()
        assert host == expected.split("/")[2]


async def test_the_resolver_is_asked_for_the_ascii_host_only(monkeypatch):
    asked = []

    async def resolve(host, port=443):
        asked.append((host, port))
        return [PUBLIC]

    monkeypatch.setattr(client, "resolve", resolve)
    await guard.check_destination("https://bücher.example/hook")
    assert asked == [("xn--bcher-kva.example", 443)]


async def test_a_host_that_does_not_convert_is_refused(answers):
    assert await refused("https://" + "ü" * 70 + ".example/hook") == "invalid_url"
    assert await refused("https://exa\ud800mple.org/hook") == "invalid_url"


# ------------------------------------------------------- resolved addresses

REFUSED_ADDRESSES = [
    # RFC 1918
    "10.0.0.1",
    "10.255.255.255",
    "172.16.0.1",
    "172.31.255.254",
    "192.168.0.1",
    "192.168.255.1",
    # loopback
    "127.0.0.1",
    "127.1.2.3",
    "::1",
    # link-local, the cloud metadata addresses among them
    "169.254.169.254",
    "169.254.0.1",
    "fe80::1",
    "fe80::a9fe:a9fe",
    # carrier-grade NAT
    "100.64.0.1",
    "100.127.255.254",
    # unique local IPv6 (the IPv6 metadata address is in it)
    "fc00::1",
    "fd00::1",
    "fd00:ec2::254",
    # site-local IPv6 (deprecated, still routable inward)
    "fec0::1",
    # multicast
    "224.0.0.1",
    "239.255.255.250",
    "ff02::1",
    "ff05::2",
    # unspecified and "this network"
    "0.0.0.0",
    "0.1.2.3",
    "::",
    # reserved, broadcast, documentation, benchmarking, protocol assignments
    "240.0.0.1",
    "255.255.255.255",
    "192.0.0.8",
    "192.0.2.1",
    "198.51.100.1",
    "203.0.113.1",
    "198.18.0.1",
    "2001:db8::1",
    # IPv4-mapped IPv6 forms of the above
    "::ffff:127.0.0.1",
    "::ffff:10.0.0.1",
    "::ffff:192.168.1.1",
    "::ffff:169.254.169.254",
    "::ffff:100.64.0.1",
    "::ffff:7f00:1",
    "0:0:0:0:0:ffff:a9fe:a9fe",
    # 6to4 wrapping a private or loopback IPv4
    "2002:7f00:1::",
    "2002:0a00:0001::1",
    "2002:c0a8:0101::1",
    "2002:a9fe:a9fe::1",
    # Teredo (can embed any server and client address)
    "2001:0:4136:e378:8000:63bf:3fff:fdd2",
    "2001:0:5ef5:79fd:0:0:7f00:1",
    # NAT64 wrapping a private IPv4
    "64:ff9b::a00:1",
    "64:ff9b::7f00:1",
    "64:ff9b::a9fe:a9fe",
    # not an address at all
    "not-an-address",
    "",
]


@pytest.mark.parametrize("address", REFUSED_ADDRESSES)
async def test_a_name_that_resolves_inward_is_refused(address, answers):
    answers["result"] = [address]
    assert await refused("https://hooks.example.org/x") == "not_allowed"


@pytest.mark.parametrize("address", REFUSED_ADDRESSES)
async def test_one_bad_answer_among_good_ones_refuses_the_name(address, answers):
    answers["result"] = [PUBLIC, address, "2606:4700:4700::1111"]
    assert await refused("https://hooks.example.org/x") == "not_allowed"
    answers["result"] = [address, PUBLIC]
    assert await refused("https://hooks.example.org/x") == "not_allowed"


@pytest.mark.parametrize(
    "address", [PUBLIC, "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "2001:4860:4860::8888"]
)
async def test_public_addresses_pass(address, answers):
    answers["result"] = [address]
    url, host = await guard.check_destination("https://hooks.example.org/x")
    assert (url, host) == ("https://hooks.example.org/x", "hooks.example.org")


async def test_a_name_that_does_not_resolve_is_unreachable(answers):
    answers["result"] = []
    assert await refused("https://hooks.example.org/x") == "unreachable"
    answers["result"] = OSError("nxdomain")
    assert await refused("https://hooks.example.org/x") == "unreachable"
    answers["result"] = UnicodeError("bad")
    assert await refused("https://hooks.example.org/x") == "unreachable"


async def test_a_resolver_that_hangs_is_unreachable(monkeypatch):
    import asyncio

    async def resolve(host, port=443):
        await asyncio.sleep(60)

    monkeypatch.setattr(client, "resolve", resolve)
    monkeypatch.setattr(guard, "RESOLVE_TIMEOUT_S", 0.05)
    assert await refused("https://hooks.example.org/x") == "unreachable"


async def test_syntax_alone_needs_no_resolver():
    url, host = await guard.check_destination("https://hooks.example.org/x", resolves=False)
    assert host == "hooks.example.org"
