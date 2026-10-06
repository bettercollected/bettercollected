"""Which address a request is counted under (#767): X-Forwarded-For only
from trusted proxies, read from the right."""

import pytest
from starlette.requests import Request

from backend.app.utils.client_ip import client_ip

TRUSTED = "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7"


def _request(peer, forwarded=None):
    headers = []
    for value in forwarded or []:
        headers.append((b"x-forwarded-for", value.encode()))
    scope = {
        "type": "http",
        "headers": headers,
        "client": (peer, 1234) if peer else None,
    }
    return Request(scope)


@pytest.mark.parametrize(
    "peer, forwarded, expected",
    [
        # straight from the internet: headers are the client's own words
        ("203.0.113.5", ["198.51.100.1"], "203.0.113.5"),
        # behind a proxy: the address it appended
        ("172.18.0.3", ["198.51.100.1"], "198.51.100.1"),
        # the client's own entries in front are ignored
        ("172.18.0.3", ["1.2.3.4, 198.51.100.1"], "198.51.100.1"),
        # two proxies (load balancer, then nginx)
        ("127.0.0.1", ["198.51.100.1, 10.0.0.9"], "198.51.100.1"),
        # several headers count as one list
        ("10.0.0.2", ["1.2.3.4", "198.51.100.1"], "198.51.100.1"),
        # garbage in the chain: stop at the last proxy we can read
        ("10.0.0.2", ["198.51.100.1, nonsense"], "10.0.0.2"),
        # a proxy that forwards nothing
        ("10.0.0.2", None, "10.0.0.2"),
        # ports and IPv6
        ("172.18.0.3", ["198.51.100.1:5555"], "198.51.100.1"),
        ("::1", ["2001:db8::7"], "2001:db8::7"),
        ("::ffff:203.0.113.5", None, "203.0.113.5"),
    ],
)
def test_client_ip(peer, forwarded, expected):
    assert client_ip(_request(peer, forwarded), TRUSTED) == expected


def test_nothing_trusted_means_the_peer():
    assert client_ip(_request("127.0.0.1", ["198.51.100.1"]), "") == "127.0.0.1"


def test_no_peer():
    assert client_ip(_request(None, ["198.51.100.1"]), TRUSTED) is None
