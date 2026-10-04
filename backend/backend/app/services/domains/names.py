"""Email domain names: canonical form and which ones a workspace may claim.

A claimed domain is stored in its ASCII (IDNA/punycode) form, lower case,
without a trailing dot. Sub-domains are separate domains: verifying
``acme.com`` says nothing about ``eng.acme.com``.

Claimable means a registrable name under a public suffix the Public Suffix
List knows (``publicsuffixlist`` ships the list; it is updated with the
package, see docs/verified-domains.md), and not a public suffix itself
(``com``, ``co.uk``, ``github.io``), not a free-mail provider and not reserved
by the operator.
"""

import re
from functools import lru_cache
from typing import Iterable, Optional

import idna
from publicsuffixlist import PublicSuffixList

MAX_DOMAIN_LENGTH = 253
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

# Mailbox providers anyone can sign up with. A verified domain hands its
# addresses to the workspace's identity provider, so these are never
# claimable. Checked against the domain and its registrable parent.
FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "passport.com",
        "yahoo.com",
        "ymail.com",
        "rocketmail.com",
        "aol.com",
        "aim.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "proton.me",
        "protonmail.com",
        "protonmail.ch",
        "pm.me",
        "tutanota.com",
        "tutanota.de",
        "tuta.io",
        "tuta.com",
        "gmx.com",
        "gmx.net",
        "gmx.de",
        "web.de",
        "mail.com",
        "email.com",
        "inbox.com",
        "zoho.com",
        "zohomail.com",
        "fastmail.com",
        "fastmail.fm",
        "hey.com",
        "yandex.com",
        "yandex.ru",
        "ya.ru",
        "mail.ru",
        "bk.ru",
        "list.ru",
        "inbox.ru",
        "rambler.ru",
        "qq.com",
        "163.com",
        "126.com",
        "yeah.net",
        "sina.com",
        "naver.com",
        "daum.net",
        "hanmail.net",
        "rediffmail.com",
        "seznam.cz",
        "wp.pl",
        "o2.pl",
        "interia.pl",
        "libero.it",
        "virgilio.it",
        "laposte.net",
        "orange.fr",
        "free.fr",
        "sfr.fr",
        "t-online.de",
        "freenet.de",
        "btinternet.com",
        "comcast.net",
        "verizon.net",
        "att.net",
        "sbcglobal.net",
        "cox.net",
        "earthlink.net",
        "duck.com",
        "mailbox.org",
        "posteo.de",
        "hushmail.com",
        "gmx.at",
        "gmx.ch",
        "bluewin.ch",
    }
)

# Providers that run the same free service under many country domains
# (yahoo.co.uk, hotmail.fr, gmail.de redirects): refused under any suffix.
FREE_MAIL_BRANDS = frozenset(
    {
        "gmail",
        "googlemail",
        "hotmail",
        "outlook",
        "yahoo",
        "ymail",
        "aol",
        "gmx",
        "yandex",
    }
)

# Names that are not on the public internet or are documentation-only.
SPECIAL_USE = frozenset({"onion", "example.com", "example.net", "example.org", "arpa"})


class DomainRefused(ValueError):
    """``code`` is stable for clients: invalid_domain, unknown_suffix,
    public_suffix, free_mail_domain, reserved_domain."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@lru_cache(maxsize=1)
def _psl() -> PublicSuffixList:
    return PublicSuffixList()


def canonical_domain(raw: str) -> str:
    """The ASCII, lower-case form of a domain name, or DomainRefused
    ``invalid_domain``. Accepts Unicode names; no wildcards, ports, paths or
    addresses."""
    if not isinstance(raw, str):
        raise DomainRefused("invalid_domain", "Enter a domain name like acme.com.")
    value = raw.strip()
    if value.endswith("."):
        value = value[:-1]
    if not value or any(ch in value for ch in "*@/:\\? \t\r\n"):
        raise DomainRefused(
            "invalid_domain",
            "Enter a domain name like acme.com, without wildcards, addresses or paths.",
        )
    try:
        ascii_name = idna.encode(value, uts46=True, transitional=False).decode("ascii")
    except (idna.IDNAError, UnicodeError):
        raise DomainRefused("invalid_domain", "That is not a valid domain name.")
    ascii_name = ascii_name.lower()
    labels = ascii_name.split(".")
    if (
        len(ascii_name) > MAX_DOMAIN_LENGTH
        or len(labels) < 2
        or not all(_LABEL.match(label) for label in labels)
        or labels[-1].isdigit()
    ):
        raise DomainRefused("invalid_domain", "That is not a valid domain name.")
    return ascii_name


def display_domain(ascii_name: str) -> str:
    """The Unicode form for display; the ASCII form if it cannot be decoded."""
    try:
        return idna.decode(ascii_name)
    except (idna.IDNAError, UnicodeError):
        return ascii_name


def registrable_domain(ascii_name: str) -> Optional[str]:
    """``eng.acme.co.uk`` -> ``acme.co.uk``; None for a public suffix or an
    unknown top-level domain."""
    return _psl().privatesuffix(ascii_name, accept_unknown=False)


def _covered(ascii_name: str, domains: Iterable[str]) -> bool:
    return any(ascii_name == d or ascii_name.endswith("." + d) for d in domains)


def claimable_domain(raw: str, reserved: Iterable[str] = ()) -> str:
    """Canonical form of a domain a workspace may claim, or DomainRefused."""
    name = canonical_domain(raw)
    psl = _psl()
    if psl.publicsuffix(name, accept_unknown=False) is None:
        raise DomainRefused(
            "unknown_suffix",
            "That domain does not end in a known top-level domain.",
        )
    registrable = registrable_domain(name)
    if registrable is None or psl.is_public(name):
        raise DomainRefused(
            "public_suffix",
            "That is a public suffix shared by many owners; claim your own domain under it.",
        )
    if _covered(name, SPECIAL_USE) or psl.publicsuffix(name) in SPECIAL_USE:
        raise DomainRefused("reserved_domain", "That domain cannot be claimed.")
    brand = registrable.split(".", 1)[0]
    if _covered(name, FREE_MAIL_DOMAINS) or brand in FREE_MAIL_BRANDS:
        raise DomainRefused(
            "free_mail_domain",
            "Free email providers' domains cannot be claimed by a workspace.",
        )
    reserved_names = []
    for domain in reserved:
        try:
            reserved_names.append(canonical_domain(domain))
        except DomainRefused:
            continue
    if _covered(name, reserved_names):
        raise DomainRefused("reserved_domain", "That domain cannot be claimed.")
    return name


def domain_of(email_or_domain: str) -> Optional[str]:
    """Canonical domain of an email address or a domain name; None when it is
    not one."""
    if not isinstance(email_or_domain, str):
        return None
    value = email_or_domain.strip()
    if "@" in value:
        local, _, value = value.rpartition("@")
        if not local:
            return None
    try:
        return canonical_domain(value)
    except DomainRefused:
        return None
