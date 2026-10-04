"""The SSRF guard on metadata and discovery URLs handed to Polis."""

import pytest

from backend.app.services.sso.url_guard import (
    UnsafeUrl,
    check_public_https_url,
    is_public_address,
)


def resolver_for(*addresses):
    async def resolve(host):
        return list(addresses)

    return resolve


async def failing_resolver(host):
    raise OSError("no such host")


async def test_a_public_https_url_is_accepted():
    url = "https://idp.example-corp.com/app/metadata.xml?x=1"
    assert await check_public_https_url(url, resolver_for("93.184.216.34")) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://idp.example-corp.com/metadata",
        "ftp://idp.example-corp.com/metadata",
        "file:///etc/passwd",
        "gopher://idp/",
        "//idp.example-corp.com/metadata",
        "idp.example-corp.com/metadata",
    ],
)
async def test_only_https_is_accepted(url):
    with pytest.raises(UnsafeUrl) as refused:
        await check_public_https_url(url, resolver_for("93.184.216.34"))
    assert refused.value.code in ("https_required", "invalid_url")


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@idp.example-corp.com/metadata",
        "https://idp.example-corp.com@169.254.169.254/",
        "https://idp.example-corp.com/meta data",
        "https://idp.example-corp.com\\@evil/",
        "https:///nohost",
        "https://idp.example-corp.com:99999/",
        "",
        "https://" + "a" * 2050 + ".com/",
    ],
)
async def test_malformed_urls_are_refused(url):
    with pytest.raises(UnsafeUrl) as refused:
        await check_public_https_url(url, resolver_for("93.184.216.34"))
    assert refused.value.code == "invalid_url"


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.5",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # carrier-grade NAT
        "0.0.0.0",
        "[::1]",
        "[fe80::1]",
        "[fc00::1]",
        "[::ffff:127.0.0.1]",
        "224.0.0.1",
    ],
)
async def test_private_ip_literals_are_refused(host):
    with pytest.raises(UnsafeUrl) as refused:
        await check_public_https_url(f"https://{host}/metadata", resolver_for())
    assert refused.value.code == "private_address"


@pytest.mark.parametrize(
    "addresses",
    [
        ("127.0.0.1",),
        ("10.0.0.7",),
        ("93.184.216.34", "192.168.0.10"),  # any private answer refuses
        ("169.254.169.254",),
        ("::1",),
        ("fd12:3456::1",),
    ],
)
async def test_names_resolving_to_private_addresses_are_refused(addresses):
    with pytest.raises(UnsafeUrl) as refused:
        await check_public_https_url(
            "https://metadata.example-corp.com/", resolver_for(*addresses)
        )
    assert refused.value.code == "private_address"


@pytest.mark.parametrize("host", ["localhost", "polis.localhost", "LOCALHOST."])
async def test_localhost_names_are_refused_without_resolving(host):
    with pytest.raises(UnsafeUrl) as refused:
        await check_public_https_url(f"https://{host}/", failing_resolver)
    assert refused.value.code == "private_address"


async def test_an_unresolvable_name_is_refused():
    with pytest.raises(UnsafeUrl) as refused:
        await check_public_https_url(
            "https://nowhere.example-corp.com/", failing_resolver
        )
    assert refused.value.code == "unresolvable_host"
    with pytest.raises(UnsafeUrl):
        await check_public_https_url(
            "https://nowhere.example-corp.com/", resolver_for()
        )


def test_public_addresses():
    assert is_public_address("93.184.216.34")
    assert is_public_address("2606:2800:220:1:248:1893:25c8:1946")
    assert not is_public_address("not-an-ip")
    assert not is_public_address("192.0.2.1")  # documentation range
