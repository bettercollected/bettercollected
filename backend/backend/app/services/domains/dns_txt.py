"""The DNS TXT check behind domain verification.

The workspace publishes ``bettercollected-domain-verification=<token>`` as a
TXT record on ``_bettercollected-verification.<domain>``. A dedicated name
keeps the record apart from the apex's SPF/other TXT records and lets several
workspaces' pending claims coexist (each has its own token).

Every check asks the resolver afresh: no cache on our side (dnspython's
resolver has none unless one is set), the configured resolver's own cache
aside.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence

import dns.asyncresolver
import dns.exception
import dns.resolver

RECORD_PREFIX = "_bettercollected-verification"
VALUE_PREFIX = "bettercollected-domain-verification="

# check outcomes (``CheckResult.error``)
NO_RECORD = "no_record"  # NXDOMAIN, or the name has no TXT records
TOKEN_MISMATCH = "token_mismatch"  # TXT records exist, none carries our token
DNS_TIMEOUT = "dns_timeout"
DNS_ERROR = "dns_error"  # SERVFAIL / no nameserver answered / other failures
# outcomes caused by the resolver rather than by the domain's records
TRANSIENT_ERRORS = frozenset({DNS_TIMEOUT, DNS_ERROR})


def record_name(domain: str) -> str:
    return f"{RECORD_PREFIX}.{domain}"


def record_value(token: str) -> str:
    return f"{VALUE_PREFIX}{token}"


@dataclass(frozen=True)
class CheckResult:
    verified: bool
    error: Optional[str] = None


def make_resolver(
    timeout_s: float, nameservers: Sequence[str] = ()
) -> dns.asyncresolver.Resolver:
    resolver = dns.asyncresolver.Resolver(configure=not nameservers)
    if nameservers:
        resolver.nameservers = list(nameservers)
    resolver.cache = None
    resolver.lifetime = timeout_s
    resolver.timeout = min(timeout_s, 2.0)
    return resolver


async def lookup_txt(resolver: dns.asyncresolver.Resolver, name: str) -> List[str]:
    """The TXT strings at ``name`` (each record's character-strings joined,
    as a record longer than 255 bytes is split). Raises dnspython errors."""
    answer = await resolver.resolve(name, "TXT", search=False, raise_on_no_answer=False)
    if answer.rrset is None:
        return []
    return [
        b"".join(rdata.strings).decode("utf-8", errors="replace")
        for rdata in answer.rrset
    ]


async def check_token(
    resolver: dns.asyncresolver.Resolver, domain: str, token: str
) -> CheckResult:
    expected = record_value(token)
    try:
        values = await lookup_txt(resolver, record_name(domain))
    except dns.resolver.NXDOMAIN:
        return CheckResult(False, NO_RECORD)
    except dns.exception.Timeout:
        return CheckResult(False, DNS_TIMEOUT)
    except (dns.exception.DNSException, OSError):
        return CheckResult(False, DNS_ERROR)
    if any(value.strip() == expected for value in values):
        return CheckResult(True)
    return CheckResult(False, TOKEN_MISMATCH if values else NO_RECORD)
