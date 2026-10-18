"""resolve_client_ip: headers are believed only from trusted proxies, and
X-Forwarded-For is read from the right."""

import pytest

from common.utils.client_ip import (
    CLOUDFLARE_IPS,
    parse_address,
    parse_networks,
    rate_limit_key,
    resolve_client_ip,
)

CF_EDGE = "172.70.1.2"  # in 172.64.0.0/13
CF_EDGE_V6 = "2a06:98c0:3600::103"
PROXY = "172.18.0.3"
TRUST = "172.18.0.0/16, 2001:db8:ffff::/48"


def resolve(peer, forwarded=None, cf=None, trusted=TRUST, cloudflare=None):
    return resolve_client_ip(peer, forwarded or [], cf, trusted, cloudflare)


def test_default_trusts_nobody():
    # private peers included: a container on the overlay can't forge anything
    for peer in ("172.18.0.9", "10.0.0.5", "127.0.0.1", "fd00::1", "203.0.113.5"):
        assert resolve_client_ip(peer, ["198.51.100.1"], "198.51.100.2") == peer
        assert resolve(peer, ["198.51.100.1"], "198.51.100.2", trusted="") == peer


def test_spoofed_headers_from_an_untrusted_peer_are_ignored():
    assert resolve("203.0.113.5", ["198.51.100.1"]) == "203.0.113.5"
    assert (
        resolve("203.0.113.5", [CF_EDGE], cf="198.51.100.1", cloudflare=CLOUDFLARE_IPS)
        == "203.0.113.5"
    )
    # a private peer that isn't listed is just as untrusted
    assert resolve("10.0.0.2", ["198.51.100.1"]) == "10.0.0.2"


def test_headers_are_honoured_from_a_trusted_proxy():
    assert resolve(PROXY, ["198.51.100.1"]) == "198.51.100.1"
    assert resolve("2001:db8:ffff::5", ["198.51.100.1"]) == "198.51.100.1"
    assert resolve(PROXY, None) == PROXY


def test_walk_from_the_right_skipping_trusted_proxies():
    # the left-most entries are the client's own claims
    assert resolve(PROXY, ["1.1.1.1, 2.2.2.2, 198.51.100.1"]) == "198.51.100.1"
    # a trusted hop on the right is skipped, an untrusted one stops the walk
    chain = "6.6.6.6, 198.51.100.1, 203.0.113.7, 172.18.0.7, 172.18.0.8"
    assert resolve(PROXY, [chain]) == "203.0.113.7"
    # several headers count as one list, in order
    assert resolve(PROXY, ["6.6.6.6", "198.51.100.1, 172.18.0.7"]) == "198.51.100.1"
    # all trusted: the last readable hop
    assert resolve(PROXY, ["172.18.0.7, 172.18.0.8"]) == "172.18.0.7"


def test_ipv6():
    assert resolve("2001:db8:ffff::5", ["2001:db8:1::9"]) == "2001:db8:1::9"
    assert resolve(PROXY, ["2001:db8:1::9, 2001:db8:ffff::6"]) == "2001:db8:1::9"
    assert resolve("::ffff:172.18.0.3", ["198.51.100.1"]) == "198.51.100.1"
    assert resolve("::ffff:203.0.113.5") == "203.0.113.5"
    assert resolve("2001:DB8::A") == "2001:db8::a"


@pytest.mark.parametrize(
    "header, expected",
    [
        ("198.51.100.1:5555", "198.51.100.1"),
        ("  198.51.100.1  ", "198.51.100.1"),
        ("[2001:db8::7]", "2001:db8::7"),
        ("[2001:db8::7]:443", "2001:db8::7"),
        ("2001:db8::7", "2001:db8::7"),
        ("1.2.3.4, 198.51.100.1 , 172.18.0.2", "198.51.100.1"),
    ],
)
def test_spaces_ports_brackets(header, expected):
    assert resolve(PROXY, [header]) == expected


@pytest.mark.parametrize(
    "header",
    [
        "198.51.100.1, nonsense",
        "nonsense",
        "198.51.100.1, ",
        "198.51.100.1:port",
        "[2001:db8::7",
        "[2001:db8::7]x",
        "1.2.3",
        "1.2.3.4.5",
        "1.2.3.256",
        "fe80::1%eth0",
        "198.51.100.1 7",
        "0x7f.1",
        "999999999999999999999",
        "x" * 10000,
    ],
)
def test_garbage_falls_back_to_the_peer_never_raises(header):
    assert resolve(PROXY, [header]) == PROXY


def test_unreadable_peer():
    assert resolve(None, ["198.51.100.1"]) is None
    assert resolve("garbage", ["198.51.100.1"]) is None
    assert resolve("", ["198.51.100.1"]) is None


def test_cloudflare_only_through_a_trusted_proxy():
    both = ["203.0.113.5, " + CF_EDGE]
    assert resolve(PROXY, both, cf="203.0.113.5", cloudflare=CLOUDFLARE_IPS) == "203.0.113.5"
    # the client's own left-of-edge claims don't matter
    assert (
        resolve(PROXY, ["6.6.6.6, " + CF_EDGE], cf="203.0.113.5", cloudflare=CLOUDFLARE_IPS)
        == "203.0.113.5"
    )
    # Cloudflare off, or the edge isn't Cloudflare: the header is not read
    assert resolve(PROXY, both, cf="203.0.113.5", cloudflare=None) == CF_EDGE
    assert (
        resolve(PROXY, ["198.51.100.7"], cf="203.0.113.5", cloudflare=CLOUDFLARE_IPS)
        == "198.51.100.7"
    )
    # a Cloudflare peer that isn't a trusted proxy can't set it either
    assert (
        resolve(CF_EDGE, None, cf="203.0.113.5", cloudflare=CLOUDFLARE_IPS) == CF_EDGE
    )
    # ...unless it is listed
    assert (
        resolve(CF_EDGE, None, cf="203.0.113.5", cloudflare=CLOUDFLARE_IPS, trusted=CLOUDFLARE_IPS)
        == "203.0.113.5"
    )
    assert (
        resolve(PROXY, [CF_EDGE_V6], cf="2001:db8::42", cloudflare=CLOUDFLARE_IPS)
        == "2001:db8::42"
    )
    assert (
        resolve(PROXY, [CF_EDGE], cf="not-an-ip", cloudflare=CLOUDFLARE_IPS) == CF_EDGE
    )


def test_a_hop_limit_cuts_long_chains():
    chain = ", ".join(["6.6.6.6"] + ["172.18.0.7"] * 40)
    assert resolve(PROXY, [chain]) == "172.18.0.7"


def test_typos_in_the_trusted_list_only_narrow_trust():
    assert len(parse_networks("172.18.0.0/16, bogus, , fe80::1%eth0, 10.0.0.1")) == 2
    assert resolve(PROXY, ["198.51.100.1"], trusted="bogus") == PROXY
    assert parse_networks(None) == ()


def test_parse_address():
    assert str(parse_address("::ffff:1.2.3.4")) == "1.2.3.4"
    assert parse_address(None) is None


def test_rate_limit_key_buckets_ipv6_by_slash_64():
    assert rate_limit_key("203.0.113.9") == "203.0.113.9"
    assert rate_limit_key("2001:db8:1:2::1") == rate_limit_key("2001:db8:1:2:ab::7")
    assert rate_limit_key("2001:db8:1:2::1") == "2001:db8:1:2::/64"
    assert rate_limit_key("2001:db8:1:3::1") != rate_limit_key("2001:db8:1:2::1")
    assert rate_limit_key("::ffff:203.0.113.9") == "203.0.113.9"
    assert rate_limit_key(None) == rate_limit_key("garbage") == "unknown"
