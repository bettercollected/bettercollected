"""The TXT check, with dnspython's resolver replaced (no network)."""

import dns.exception
import dns.resolver
import pytest

from backend.app.services.domains import dns_txt

NAME = "_bettercollected-verification.acme.com"


@pytest.fixture
def resolver():
    return dns_txt.make_resolver(1.5, ["192.0.2.53"])


def test_record_format():
    assert dns_txt.record_name("acme.com") == NAME
    assert (
        dns_txt.record_value("abc123") == "bettercollected-domain-verification=abc123"
    )


def test_resolver_has_no_cache_and_bounded_time():
    resolver = dns_txt.make_resolver(4.0, ["192.0.2.53", "192.0.2.54"])
    assert resolver.cache is None
    assert resolver.lifetime == 4.0
    assert resolver.timeout <= 2.0
    assert resolver.nameservers == ["192.0.2.53", "192.0.2.54"]


async def test_match(fake_dns, resolver):
    fake_dns.set_txt(NAME, "v=spf1 -all", "bettercollected-domain-verification=tok-1")
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result == dns_txt.CheckResult(True)
    # asked for exactly that name's TXT records, without search domains
    assert fake_dns.queries == [(NAME, "TXT", False)]


async def test_long_record_split_into_strings_still_matches(fake_dns, resolver):
    token = "x" * 300
    fake_dns.set_txt(NAME, dns_txt.record_value(token))
    assert (await dns_txt.check_token(resolver, "acme.com", token)).verified


async def test_mismatch(fake_dns, resolver):
    fake_dns.set_txt(NAME, "bettercollected-domain-verification=someone-else")
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result == dns_txt.CheckResult(False, dns_txt.TOKEN_MISMATCH)


async def test_token_must_match_exactly(fake_dns, resolver):
    fake_dns.set_txt(NAME, "bettercollected-domain-verification=tok-12")
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result.error == dns_txt.TOKEN_MISMATCH


async def test_nxdomain(fake_dns, resolver):
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result == dns_txt.CheckResult(False, dns_txt.NO_RECORD)


async def test_name_without_txt_records(fake_dns, resolver):
    fake_dns.set_txt(NAME)
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result == dns_txt.CheckResult(False, dns_txt.NO_RECORD)


async def test_apex_record_does_not_count(fake_dns, resolver):
    fake_dns.set_txt("acme.com", "bettercollected-domain-verification=tok-1")
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result.error == dns_txt.NO_RECORD


async def test_timeout(fake_dns, resolver):
    fake_dns.fail(NAME, dns.resolver.LifetimeTimeout(timeout=1.5, errors={}))
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result == dns_txt.CheckResult(False, dns_txt.DNS_TIMEOUT)


@pytest.mark.parametrize(
    "error",
    [
        dns.resolver.NoNameservers(),
        dns.exception.DNSException("servfail"),
        OSError("network unreachable"),
    ],
)
async def test_resolver_errors(fake_dns, resolver, error):
    fake_dns.fail(NAME, error)
    result = await dns_txt.check_token(resolver, "acme.com", "tok-1")
    assert result == dns_txt.CheckResult(False, dns_txt.DNS_ERROR)
    assert dns_txt.DNS_ERROR in dns_txt.TRANSIENT_ERRORS
