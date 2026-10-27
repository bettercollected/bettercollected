"""The registration client: https only, public addresses only (checked at every
connection), no redirects, size and time limits, headers that cannot be
smuggled. A local https server with a test CA stands in for the destination;
no setting allows http or private addresses."""

import asyncio
from urllib.parse import parse_qsl, urlsplit

import httpcore
import pytest

from backend.app.services.registration import client
from backend.app.services.registration.client import (
    SendFailed,
    Target,
    post_json,
    request,
)
from backend.app.services.safe_http import PinnedBackend
from tests.app.registration.tls_server import HOST, PUBLIC_ADDRESS

pytestmark = pytest.mark.asyncio

BODY = b'{"values":{}}'


def target(**kwargs) -> Target:
    return Target(base_url=f"https://{HOST}/api/", **kwargs)


async def failure(**kwargs) -> SendFailed:
    with pytest.raises(SendFailed) as raised:
        await post_json(kwargs.pop("target", target()), BODY, idempotency_key="d1")
    return raised.value


async def test_posts_json_with_credentials_and_the_checked_address(tls):
    status = await post_json(
        target(
            path="intake/1",
            auth="header",
            auth_name="Authorization",
            secret="Token abc",
        ),
        BODY,
        idempotency_key="delivery-1",
    )
    assert status == 200
    (request,) = tls.requests
    assert request.method == "POST" and request.target == "/api/intake/1"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["authorization"] == "Token abc"
    assert request.headers["idempotency-key"] == "delivery-1"
    assert request.headers["host"] == HOST
    assert request.body == BODY
    # the connection went to the address that was checked
    assert tls.dialled == [(PUBLIC_ADDRESS, 443)]


async def test_basic_auth(tls):
    await post_json(
        target(auth="basic", auth_name="u", secret="p"), BODY, idempotency_key="d"
    )
    assert tls.requests[0].headers["authorization"] == "Basic dTpw"


@pytest.mark.parametrize(
    "url",
    [
        "http://case.example.org/",
        "https://case.example.org:8443/",
        "https://user:pw@case.example.org/",
        "https://case.example.org/?x=1",
        "ftp://case.example.org/",
        "https:///nohost",
        "https://case.example.org/a b",
    ],
)
async def test_only_plain_https_addresses(tls, url):
    failed = await failure(target=Target(base_url=url))
    assert failed.code == "invalid_url" and failed.permanent
    assert tls.requests == []


@pytest.mark.parametrize(
    "path",
    [
        "../x",
        "a/../../b",
        "%2e%2e/x",
        "%252e%252e/x",
        "//evil.example.org/x",
        "a?b=1",
        "a#f",
        "https://evil.example.org/",
        "a\\b",
    ],
)
async def test_path_cannot_leave_the_service(tls, path):
    failed = await failure(target=target(path=path))
    assert failed.code == "invalid_url" and failed.permanent
    assert tls.requests == []


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # carrier-grade NAT
        "0.0.0.0",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",  # IPv4-mapped
        "::ffff:169.254.169.254",
        "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
        "2002:7f00:1::",  # 6to4 of 127.0.0.1
        "224.0.0.1",
    ],
)
async def test_non_public_addresses_are_refused_at_connect_time(
    tls, monkeypatch, address
):
    async def resolve(host, port=443):
        return [address]

    monkeypatch.setattr(client, "resolve", resolve)
    failed = await failure()
    assert failed.code == "not_allowed" and failed.permanent
    assert tls.requests == [] and tls.dialled == []


async def test_a_name_that_also_points_inward_is_refused(tls, monkeypatch):
    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS, "10.0.0.8"]

    monkeypatch.setattr(client, "resolve", resolve)
    assert (await failure()).code == "not_allowed"


async def test_dns_rebinding_second_answer_private_is_refused(tls, monkeypatch):
    """The first lookup (when the service was saved) was public; the next one,
    at connect time, is not. Every attempt resolves again."""
    answers = [[PUBLIC_ADDRESS], ["169.254.169.254"]]
    lookups = []

    async def resolve(host, port=443):
        lookups.append(host)
        return answers.pop(0) if len(answers) > 1 else answers[0]

    monkeypatch.setattr(client, "resolve", resolve)
    assert await post_json(target(), BODY, idempotency_key="d") == 200
    assert (await failure()).code == "not_allowed"
    assert len(lookups) == 2 and len(tls.requests) == 1


async def test_unresolvable_host_is_transient(tls, monkeypatch):
    async def resolve(host, port=443):
        raise OSError("no such host")

    monkeypatch.setattr(client, "resolve", resolve)
    failed = await failure()
    assert failed.code == "unreachable" and not failed.permanent


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_redirects_are_refused_and_not_followed(tls, status):
    tls.script.answers = [(status, {"Location": "https://other.example.org/"}, b"")]
    failed = await failure(
        target=target(auth="header", auth_name="Authorization", secret="Token s")
    )
    assert failed.code == "redirect_refused" and failed.permanent
    assert failed.http_status == status
    assert len(tls.requests) == 1  # never followed, so the credential went nowhere else


@pytest.mark.parametrize(
    "status,code,permanent",
    [
        (400, "http_4xx", True),
        (401, "http_4xx", True),
        (404, "http_4xx", True),
        (408, "http_4xx", False),
        (429, "http_4xx", False),
        (500, "http_5xx", False),
        (503, "http_5xx", False),
    ],
)
async def test_status_classes(tls, status, code, permanent):
    tls.script.answers = [(status, {}, b"the destination's own words")]
    failed = await failure()
    assert (failed.code, failed.permanent, failed.http_status) == (
        code,
        permanent,
        status,
    )
    # our error never carries the destination's text
    assert "words" not in str(failed)


async def test_retry_after_is_honoured_up_to_an_hour(tls):
    tls.script.answers = [(429, {"Retry-After": "120"}, b"")]
    assert (await failure()).retry_after == 120
    tls.script.answers = [(503, {"Retry-After": "999999"}, b"")]
    assert (await failure()).retry_after == client.MAX_RETRY_AFTER_S


async def test_request_body_is_capped(tls, monkeypatch):
    monkeypatch.setattr(client, "MAX_BODY_BYTES", 10)
    with pytest.raises(SendFailed) as raised:
        await post_json(target(), b"x" * 11, idempotency_key="d")
    assert raised.value.code == "too_large" and raised.value.permanent
    assert tls.requests == []


async def test_a_huge_reply_is_read_only_up_to_the_cap(tls, monkeypatch):
    monkeypatch.setattr(client, "MAX_REPLY_BYTES", 1024)
    tls.script.answers = [(200, {}, b"y" * 50_000)]
    assert await post_json(target(), BODY, idempotency_key="d") == 200


async def test_a_slow_destination_times_out(tls, monkeypatch):
    monkeypatch.setattr(client, "TOTAL_TIMEOUT_S", 0.2)
    tls.script.delay = 2
    failed = await failure()
    assert failed.code == "timeout" and not failed.permanent


async def test_read_timeout(tls, monkeypatch):
    monkeypatch.setattr(client, "TIMEOUTS", {**client.TIMEOUTS, "read": 0.2})
    tls.script.delay = 2
    assert (await failure()).code == "timeout"


async def test_untrusted_certificate_is_refused(tls, monkeypatch):
    import ssl

    monkeypatch.setattr(client, "ssl_context", lambda: ssl.create_default_context())
    failed = await failure()
    assert failed.code == "tls_error" and not failed.permanent
    assert tls.requests == []


async def test_certificate_for_another_host_is_refused(tls, monkeypatch):
    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(client, "resolve", resolve)
    failed = await failure(target=Target(base_url="https://another.example.org/"))
    assert failed.code == "tls_error"


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(auth="header", auth_name="X\r\nEvil", secret="v"),
        dict(auth="header", auth_name="X-Key", secret="a\r\nEvil: 1"),
        dict(auth="header", auth_name="X-Key", secret="a\x00b"),
    ],
)
async def test_headers_cannot_be_smuggled(tls, kwargs):
    failed = await failure(target=target(**kwargs))
    assert failed.code == "config_invalid" and failed.permanent
    assert tls.requests == []


async def test_connect_error_is_transient(monkeypatch):
    class Refusing(httpcore.AsyncNetworkBackend):
        async def connect_tcp(self, *args, **kwargs):
            raise httpcore.ConnectError("refused")

        async def connect_unix_socket(self, *a, **k):
            raise httpcore.ConnectError("x")

        async def sleep(self, seconds):
            await asyncio.sleep(seconds)

    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(client, "resolve", resolve)
    monkeypatch.setattr(
        client, "network_backend", lambda h, a: PinnedBackend(h, a, inner=Refusing())
    )
    failed = await failure()
    assert failed.code == "unreachable" and not failed.permanent


# ----------------------------------------------- GET, token auth, kept replies


async def test_a_token_goes_after_the_word_token(tls):
    await request(target(auth="token", secret="abc123"), "GET", idempotency_key=None)
    assert tls.requests[0].headers["authorization"] == "Token abc123"


@pytest.mark.parametrize(
    "secret", [None, "", "two words", "tab\there", "tökén", "a\nb"]
)
async def test_a_token_that_cannot_be_a_header_value_is_refused_unsent(tls, secret):
    with pytest.raises(SendFailed) as raised:
        await request(target(auth="token", secret=secret), "GET")
    assert raised.value.code == "config_invalid" and raised.value.permanent
    assert tls.requests == []


async def test_a_get_carries_an_encoded_query_and_no_body(tls):
    reply = await request(
        target(path="objects"),
        "GET",
        query=[("type", "https://t.example.org/a b"), ("data_attr", "a__exact__1&x=2")],
        keep_reply=True,
    )
    assert reply.status == 200
    (seen,) = tls.requests
    assert seen.method == "GET" and seen.body == b""
    assert "content-length" not in seen.headers and "content-type" not in seen.headers
    assert seen.target.startswith("/api/objects?")
    assert dict(parse_qsl(urlsplit(seen.target).query)) == {
        "type": "https://t.example.org/a b",
        "data_attr": "a__exact__1&x=2",  # one value, not two parameters
    }


async def test_a_kept_reply_is_returned_up_to_the_cap_and_flagged_beyond_it(
    tls, monkeypatch
):
    tls.script.answers = [(200, {}, b'{"results":[]}')]
    reply = await request(target(), "GET", keep_reply=True)
    assert reply.body == b'{"results":[]}' and not reply.truncated
    # a reply is dropped unless the caller asks for it
    assert (await request(target(), "GET")).body == b""
    monkeypatch.setattr(client, "MAX_REPLY_BYTES", 10)
    tls.script.answers = [(200, {}, b"x" * 100)]
    big = await request(target(), "GET", keep_reply=True)
    assert big.truncated and big.body == b""


async def test_only_get_and_post_exist(tls):
    with pytest.raises(SendFailed):
        await request(target(), "DELETE")
    assert tls.requests == []


async def test_a_get_follows_the_same_address_rules(tls, monkeypatch):
    with pytest.raises(SendFailed) as raised:
        await request(
            Target(base_url="https://case.example.org:8443/"), "GET", query=[("a", "b")]
        )
    assert raised.value.code == "invalid_url"
    tls.script.answers = [(302, {"Location": "https://x.example.org/"}, b"")]
    with pytest.raises(SendFailed) as raised:
        await request(target(), "GET", query=[("a", "b")])
    assert raised.value.code == "redirect_refused"

    async def resolve(host, port=443):
        return ["10.1.1.1"]

    monkeypatch.setattr(client, "resolve", resolve)
    with pytest.raises(SendFailed) as raised:
        await request(target(), "GET", query=[("a", "b")])
    assert raised.value.code == "not_allowed" and len(tls.requests) == 1
