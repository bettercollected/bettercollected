"""Which email domains a workspace may claim, and their canonical form."""

import pytest

from backend.app.services.domains.names import (
    DomainRefused,
    canonical_domain,
    claimable_domain,
    display_domain,
    domain_of,
    registrable_domain,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("acme.com", "acme.com"),
        ("  ACME.Com.  ", "acme.com"),
        ("eng.acme.co.uk", "eng.acme.co.uk"),
        ("acme.co.uk", "acme.co.uk"),
        ("Bücher.de", "xn--bcher-kva.de"),
        ("xn--bcher-kva.de", "xn--bcher-kva.de"),
        ("例え.jp", "xn--r8jz45g.jp"),
        ("myteam.github.io", "myteam.github.io"),
        ("my-company.io", "my-company.io"),
    ],
)
def test_claimable_domains_are_normalised(raw, expected):
    assert claimable_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "*.acme.com",
        "acme",
        "user@acme.com",
        "https://acme.com",
        "acme.com/path",
        "acme.com:443",
        "acme..com",
        "-acme.com",
        "acme-.com",
        "acme_corp.com",
        "1.2.3.4",
        "a" * 64 + ".com",
        ".".join(["abcdefghij"] * 25) + ".com",
        "ac me.com",
        None,
    ],
)
def test_invalid_names_are_refused(raw):
    with pytest.raises(DomainRefused) as refused:
        claimable_domain(raw)
    assert refused.value.code == "invalid_domain"


@pytest.mark.parametrize(
    "raw", ["co.uk", "github.io", "gov.uk", "ac.uk", "blogspot.com", "s3.amazonaws.com"]
)
def test_public_suffixes_are_refused(raw):
    with pytest.raises(DomainRefused) as refused:
        claimable_domain(raw)
    assert refused.value.code == "public_suffix"


def test_a_bare_top_level_domain_is_not_a_domain_name():
    with pytest.raises(DomainRefused) as refused:
        claimable_domain("com")
    assert refused.value.code == "invalid_domain"


@pytest.mark.parametrize(
    "raw", ["acme.local", "acme.internal", "acme.test", "acme.notarealtld", "acme.lan"]
)
def test_unknown_top_level_domains_are_refused(raw):
    with pytest.raises(DomainRefused) as refused:
        claimable_domain(raw)
    assert refused.value.code == "unknown_suffix"


@pytest.mark.parametrize(
    "raw",
    [
        "gmail.com",
        "GMAIL.COM",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "hotmail.fr",
        "yahoo.com",
        "yahoo.co.uk",
        "mail.yahoo.com",
        "icloud.com",
        "proton.me",
        "gmx.de",
        "aol.com",
    ],
)
def test_free_mail_domains_are_refused(raw):
    with pytest.raises(DomainRefused) as refused:
        claimable_domain(raw)
    assert refused.value.code == "free_mail_domain"


@pytest.mark.parametrize("raw", ["example.com", "sub.example.org", "acme.onion"])
def test_special_use_domains_are_refused(raw):
    with pytest.raises(DomainRefused) as refused:
        claimable_domain(raw)
    assert refused.value.code == "reserved_domain"


def test_operator_reserved_domains_and_their_subdomains_are_refused():
    reserved = ["bettercollected.com", "Sireto.io", "not a domain"]
    for raw in ["bettercollected.com", "eng.bettercollected.com", "sireto.io"]:
        with pytest.raises(DomainRefused) as refused:
            claimable_domain(raw, reserved)
        assert refused.value.code == "reserved_domain"
    # a look-alike is not covered
    assert claimable_domain("notbettercollected.com", reserved) == (
        "notbettercollected.com"
    )


def test_platform_admin_email_domains_are_reserved(monkeypatch):
    from backend.config.verified_domain_settings import VerifiedDomainSettings

    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", "ops@operator.example, Boss@Sireto.io")
    monkeypatch.setenv("VERIFIED_DOMAINS_RESERVED", "acme-ops.com")
    config = VerifiedDomainSettings()
    assert config.reserved_domains == {"operator.example", "sireto.io", "acme-ops.com"}


def test_canonical_domain_does_not_apply_claim_policy():
    assert canonical_domain("Gmail.com") == "gmail.com"
    assert registrable_domain("eng.acme.co.uk") == "acme.co.uk"
    assert registrable_domain("co.uk") is None


def test_display_domain_shows_unicode():
    assert display_domain("xn--bcher-kva.de") == "bücher.de"
    assert display_domain("acme.com") == "acme.com"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Jane@ACME.com", "acme.com"),
        ("jane@bücher.de", "xn--bcher-kva.de"),
        ("acme.com", "acme.com"),
        ("@acme.com", None),
        ("jane@", None),
        ("not an email", None),
        (None, None),
    ],
)
def test_domain_of(value, expected):
    assert domain_of(value) == expected
