"""Fetching an image from an address someone gave us (services/image_fetch.py):
never into our own network, whatever the address, its DNS answers or its
redirects say. No real network: DNS and the connections are faked."""

import httpcore
import pytest

from backend.app.services import image_fetch
from backend.app.services.image_fetch import (
    FetchRefused,
    PinnedBackend,
    fetch_image,
    is_public_address,
)

PUBLIC = "93.184.216.34"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def http_response(status=200, headers=None, body=b"") -> list:
    reason = {200: b"OK", 302: b"Found", 404: b"Not Found"}.get(status, b"X")
    head = [b"HTTP/1.1 %d %s\r\n" % (status, reason)]
    headers = dict(headers or {})
    headers.setdefault("Content-Length", str(len(body)))
    for name, value in headers.items():
        if value is not None:
            head.append(f"{name}: {value}\r\n".encode())
    head.append(b"\r\n")
    return head + ([body] if body else [])


def image(body=PNG, content_type="image/png", **headers) -> list:
    return http_response(200, {"Content-Type": content_type, **headers}, body)


def redirect(location: str) -> list:
    return http_response(302, {"Location": location})


class FakeNetwork:
    """DNS answers per host (a list, or a list of lists for successive
    lookups) and canned responses per host; records every lookup and every
    connection (the address actually dialled)."""

    def __init__(self):
        self.dns = {}
        self.responses = {}
        self.lookups = []
        self.connections = []

    async def resolve(self, host, port=443):
        self.lookups.append(host)
        if host not in self.dns:
            raise OSError("no such host")
        answers = self.dns[host]
        if answers and isinstance(answers[0], list):
            return answers.pop(0) if len(answers) > 1 else answers[0]
        return answers

    def backend(self, host, address):
        network = self

        class Recording(httpcore.AsyncMockBackend):
            async def connect_tcp(self, dialled, port, **kwargs):
                network.connections.append((dialled, port))
                return await super().connect_tcp(dialled, port, **kwargs)

        return PinnedBackend(host, address, inner=Recording(self.responses[host]))


@pytest.fixture()
def net(monkeypatch):
    fake = FakeNetwork()
    monkeypatch.setattr(image_fetch, "resolve", fake.resolve)
    monkeypatch.setattr(image_fetch, "network_backend", fake.backend)
    return fake


async def refused(url, **kwargs) -> str:
    with pytest.raises(FetchRefused) as raised:
        await fetch_image(url, **kwargs)
    return raised.value.code


async def test_a_public_image_is_fetched_from_the_address_we_checked(net):
    net.dns["images.example.org"] = [PUBLIC]
    net.responses["images.example.org"] = image(content_type="image/png; charset=x")
    fetched = await fetch_image("https://images.example.org/a.png#frag")
    assert fetched.data == PNG and fetched.content_type == "image/png"
    # dialled by address, not by name
    assert net.connections == [(PUBLIC, 443)]


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "0.0.0.0",
        "100.64.0.1",  # carrier-grade NAT
        "224.0.0.1",
        "240.0.0.1",
        "255.255.255.255",
        "198.18.0.1",
        "192.0.2.1",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "fec0::1",
        "ff02::1",
        "2001:db8::1",
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
        "2002:7f00:1::",  # 6to4 of 127.0.0.1
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
    ],
)
async def test_private_and_special_addresses_are_refused(net, address):
    assert not is_public_address(address)
    net.dns["inside.example.org"] = [address]
    assert await refused("https://inside.example.org/x.png") == "not_allowed"
    assert net.connections == []


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "::1"])
async def test_an_address_literal_is_checked_like_a_name(net, address):
    host = f"[{address}]" if ":" in address else address
    net.dns[address] = [address]
    assert await refused(f"https://{host}/x.png") == "not_allowed"
    assert net.connections == []


def test_public_addresses_are_public():
    for address in (PUBLIC, "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"):
        assert is_public_address(address)


async def test_a_name_that_also_points_inward_is_refused(net):
    net.dns["mixed.example.org"] = [PUBLIC, "10.0.0.7"]
    assert await refused("https://mixed.example.org/x.png") == "not_allowed"
    assert net.connections == []


async def test_dns_rebinding_cannot_move_the_connection(net):
    # first answer public, every later one private: we dial what we checked
    net.dns["rebind.example.org"] = [[PUBLIC], ["127.0.0.1"]]
    net.responses["rebind.example.org"] = image()
    await fetch_image("https://rebind.example.org/x.png")
    assert net.lookups == ["rebind.example.org"]
    assert net.connections == [(PUBLIC, 443)]


async def test_the_pinned_connection_refuses_another_host():
    backend = PinnedBackend(
        "a.example.org", PUBLIC, inner=httpcore.AsyncMockBackend([])
    )
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("b.example.org", 443)


async def test_a_redirect_to_a_private_address_is_refused(net):
    net.dns["outside.example.org"] = [PUBLIC]
    net.responses["outside.example.org"] = redirect("https://inside.example.org/x")
    net.dns["inside.example.org"] = ["10.0.0.1"]
    assert await refused("https://outside.example.org/x.png") == "not_allowed"
    assert net.connections == [(PUBLIC, 443)]


@pytest.mark.parametrize(
    "location",
    [
        "http://outside.example.org/x.png",
        "https://user:pw@outside.example.org/x.png",
        "https://outside.example.org:8443/x.png",
        "file:///etc/passwd",
    ],
)
async def test_a_redirect_is_checked_like_the_first_address(net, location):
    net.dns["outside.example.org"] = [PUBLIC]
    net.responses["outside.example.org"] = redirect(location)
    assert await refused("https://outside.example.org/a.png") == "invalid_url"


async def test_redirects_are_followed_at_most_three_times(net):
    for hop in range(5):
        host = f"h{hop}.example.org"
        net.dns[host] = [PUBLIC]
        net.responses[host] = redirect(f"https://h{hop + 1}.example.org/x.png")
    net.dns["h3.example.org"] = [PUBLIC]
    net.responses["h3.example.org"] = image()
    # three redirects: fine
    assert (await fetch_image("https://h0.example.org/x.png")).data == PNG
    # four: refused
    net.responses["h3.example.org"] = redirect("https://h4.example.org/x.png")
    net.responses["h4.example.org"] = image()
    assert await refused("https://h0.example.org/x.png") == "too_many_redirects"


async def test_a_relative_redirect_stays_on_the_host_and_is_checked(net):
    net.dns["outside.example.org"] = [PUBLIC]
    net.responses["outside.example.org"] = redirect("/real.png")
    # the mock answers the same way on the second request: the loop ends
    assert await refused("https://outside.example.org/a.png") == "too_many_redirects"
    assert len(net.connections) == 4


@pytest.mark.parametrize(
    "url",
    [
        "http://images.example.org/x.png",
        "ftp://images.example.org/x.png",
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "https://user:pw@images.example.org/x.png",
        "https://user@images.example.org/x.png",
        "https://images.example.org:8443/x.png",
        "https://images.example.org:0/x.png",
        "https://bücher.example/x.png",
        "https:///x.png",
        "https://images.example.org/x y.png",
        "",
        "https://images.example.org/" + "a" * 2100,
    ],
)
async def test_bad_addresses_are_refused_before_any_lookup(net, url):
    assert await refused(url) == "invalid_url"
    assert net.lookups == [] and net.connections == []


async def test_an_unknown_name_is_unreachable(net):
    assert await refused("https://nowhere.example.org/x.png") == "unreachable"


@pytest.mark.parametrize(
    "content_type",
    [
        "text/html",
        "image/svg+xml",
        "image/gif",
        "image/avif",
        "application/octet-stream",
        None,
    ],
)
async def test_only_jpeg_png_and_webp_are_taken(net, content_type):
    net.dns["images.example.org"] = [PUBLIC]
    net.responses["images.example.org"] = image(content_type=content_type)
    assert await refused("https://images.example.org/x") == "not_image"


async def test_a_declared_size_over_the_limit_is_refused_before_reading(net):
    net.dns["images.example.org"] = [PUBLIC]
    net.responses["images.example.org"] = http_response(
        200, {"Content-Type": "image/png", "Content-Length": str(11 * 1024 * 1024)}
    )
    assert await refused("https://images.example.org/x.png") == "too_large"


async def test_a_body_over_the_limit_is_refused_while_streaming(net):
    net.dns["images.example.org"] = [PUBLIC]
    body = PNG * 100
    # no length announced: read in chunks until over the cap
    net.responses["images.example.org"] = [
        b"HTTP/1.1 200 OK\r\n",
        b"Content-Type: image/png\r\n",
        b"Connection: close\r\n\r\n",
    ] + [body[i : i + 512] for i in range(0, len(body), 512)]
    assert (
        await refused("https://images.example.org/x.png", max_bytes=1000) == "too_large"
    )


@pytest.mark.parametrize("status", [404, 500, 403])
async def test_an_error_answer_is_unreachable(net, status):
    net.dns["images.example.org"] = [PUBLIC]
    net.responses["images.example.org"] = http_response(
        status, {"Content-Type": "image/png"}
    )
    assert await refused("https://images.example.org/x.png") == "unreachable"


async def test_a_fixed_host_and_no_redirects_for_the_unsplash_route(net):
    net.dns["images.unsplash.com"] = [PUBLIC]
    net.responses["images.unsplash.com"] = redirect("https://images.unsplash.com/b")
    kwargs = dict(allowed_hosts={"images.unsplash.com"}, max_redirects=0)
    assert (
        await refused("https://images.unsplash.com/a", **kwargs) == "too_many_redirects"
    )
    assert await refused("https://evil.example.org/a", **kwargs) == "not_allowed"
    assert net.lookups == ["images.unsplash.com"]
