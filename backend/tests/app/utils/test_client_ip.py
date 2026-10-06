"""Which address a request is counted under (#767): X-Forwarded-For only
from trusted proxies, read from the right; Cloudflare's CF-Connecting-IP only
when the request came through a Cloudflare edge."""

import pytest
from starlette.requests import Request

from backend.app.utils.client_ip import CLOUDFLARE_IPS, client_ip, request_client_ip
from backend.config import settings

CF_EDGE = "172.70.1.2"  # in 172.64.0.0/13
CF_EDGE_V6 = "2a06:98c0:3600::103"
NGINX = "172.18.0.3"


def _request(peer, forwarded=None, cf=None):
    headers = []
    for value in forwarded or []:
        headers.append((b"x-forwarded-for", value.encode()))
    if cf is not None:
        headers.append((b"cf-connecting-ip", cf.encode()))
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
        (NGINX, ["198.51.100.1"], "198.51.100.1"),
        # the client's own entries in front are ignored
        (NGINX, ["1.2.3.4, 198.51.100.1"], "198.51.100.1"),
        # two proxies (load balancer, then nginx)
        ("127.0.0.1", ["198.51.100.1, 10.0.0.9"], "198.51.100.1"),
        # several headers count as one list
        ("10.0.0.2", ["1.2.3.4", "198.51.100.1"], "198.51.100.1"),
        # garbage in the chain: stop at the last proxy we can read
        ("10.0.0.2", ["198.51.100.1, nonsense"], "10.0.0.2"),
        # a proxy that forwards nothing
        ("10.0.0.2", None, "10.0.0.2"),
        # ports and IPv6
        (NGINX, ["198.51.100.1:5555"], "198.51.100.1"),
        ("::1", ["2001:db8::7"], "2001:db8::7"),
        ("::ffff:203.0.113.5", None, "203.0.113.5"),
    ],
)
def test_client_ip(peer, forwarded, expected):
    assert client_ip(_request(peer, forwarded), "", CLOUDFLARE_IPS) == expected


def test_extra_trusted_proxies():
    request = _request("198.51.100.200", ["203.0.113.5"])
    assert client_ip(request) == "198.51.100.200"
    assert client_ip(request, "198.51.100.0/24") == "203.0.113.5"


def test_cloudflare_then_nginx_appending():
    request = _request(NGINX, ["203.0.113.5, " + CF_EDGE], cf="203.0.113.5")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "203.0.113.5"
    # CF-Connecting-IP decides, not the client's own XFF entries
    request = _request(NGINX, ["6.6.6.6, " + CF_EDGE], cf="203.0.113.5")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "203.0.113.5"


def test_cloudflare_with_nginx_replacing_the_chain():
    # nginx set XFF to its own peer: only the Cloudflare edge is visible
    request = _request(NGINX, [CF_EDGE], cf="203.0.113.5")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "203.0.113.5"
    # or Cloudflare connects to the backend directly
    request = _request(CF_EDGE, None, cf="203.0.113.5")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "203.0.113.5"


def test_cloudflare_ipv6():
    request = _request(NGINX, [CF_EDGE_V6], cf="2001:db8::42")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "2001:db8::42"
    request = _request("::1", ["2001:db8::9, " + CF_EDGE_V6], cf="2001:db8::9")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "2001:db8::9"


@pytest.mark.parametrize(
    "peer, forwarded",
    [
        # straight from the internet
        ("198.51.100.7", None),
        # through our proxy, but not through Cloudflare
        (NGINX, ["198.51.100.7"]),
        # a Cloudflare address named by the client itself, left of its own
        (NGINX, [CF_EDGE + ", 198.51.100.7"]),
    ],
)
def test_a_spoofed_cf_connecting_ip_is_ignored(peer, forwarded):
    request = _request(peer, forwarded, cf="203.0.113.5")
    assert client_ip(request, "", CLOUDFLARE_IPS) == "198.51.100.7"


def test_an_invalid_cf_connecting_ip_falls_back_to_the_edge():
    request = _request(NGINX, [CF_EDGE], cf="not-an-ip")
    assert client_ip(request, "", CLOUDFLARE_IPS) == CF_EDGE


def test_cloudflare_not_trusted():
    request = _request(NGINX, ["203.0.113.5, " + CF_EDGE], cf="203.0.113.5")
    assert client_ip(request, "", None) == CF_EDGE


def test_settings(monkeypatch):
    request = _request(NGINX, [CF_EDGE], cf="203.0.113.5")
    monkeypatch.setattr(settings.api_settings, "TRUST_CLOUDFLARE", True)
    monkeypatch.setattr(settings.api_settings, "CLOUDFLARE_IPS", "")
    assert request_client_ip(request) == "203.0.113.5"
    monkeypatch.setattr(settings.api_settings, "CLOUDFLARE_IPS", "192.0.2.0/24")
    assert request_client_ip(request) == CF_EDGE
    monkeypatch.setattr(settings.api_settings, "CLOUDFLARE_IPS", "")
    monkeypatch.setattr(settings.api_settings, "TRUST_CLOUDFLARE", False)
    assert request_client_ip(request) == CF_EDGE


def test_no_peer():
    assert client_ip(_request(None, ["198.51.100.1"]), "", CLOUDFLARE_IPS) is None
