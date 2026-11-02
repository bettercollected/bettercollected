"""The sites a workspace lets frame its forms: what is accepted and how it is stored."""

import pytest

from backend.app.services.form_embed import (
    MAX_ORIGINS,
    OriginRefused,
    canonical_origin,
    normalize_origins,
)


@pytest.mark.parametrize(
    "raw, stored",
    [
        ("https://www.example.org", "https://www.example.org"),
        ("  HTTPS://WWW.Example.ORG/  ", "https://www.example.org"),
        ("https://example.org:8443", "https://example.org:8443"),
        # the default port is dropped: the browser's origin has none
        ("https://example.org:443", "https://example.org"),
        ("https://*.example.org", "https://*.example.org"),
        ("https://*.eng.example.co.uk", "https://*.eng.example.co.uk"),
        ("https://*.example.org:8443", "https://*.example.org:8443"),
        # an IDN is stored as punycode, as the browser sends it
        ("https://bücher.example.org", "https://xn--bcher-kva.example.org"),
        ("http://localhost", "http://localhost"),
        ("http://localhost:3000", "http://localhost:3000"),
        ("http://127.0.0.1:5173", "http://127.0.0.1:5173"),
        ("https://localhost:3000", "https://localhost:3000"),
    ],
)
def test_accepted_origins_are_stored_canonically(raw, stored):
    assert canonical_origin(raw) == stored


@pytest.mark.parametrize(
    "raw, code",
    [
        ("", "invalid_origin"),
        ("   ", "invalid_origin"),
        ("www.example.org", "origin_scheme"),
        ("ftp://example.org", "origin_scheme"),
        ("javascript:alert(1)", "origin_scheme"),
        ("http://example.org", "origin_scheme"),
        ("http://*.example.org", "origin_scheme"),
        ("https://example.org/embed", "origin_path"),
        ("https://example.org/?x=1", "origin_path"),
        ("https://example.org#top", "origin_path"),
        ("https://user:secret@example.org", "invalid_origin"),
        ("https://example.org:", "invalid_origin"),
        ("https://[::1]", "invalid_origin"),
        ("https://[abc", "invalid_origin"),
        ("https://example.org:0", "origin_port"),
        ("https://example.org:70000", "origin_port"),
        # no wildcards except a leading "*." under a registrable domain
        ("https://*", "origin_wildcard"),
        ("https://*.com", "origin_wildcard"),
        ("https://*.co.uk", "origin_wildcard"),
        ("https://*.github.io", "origin_wildcard"),
        ("https://*.*.example.org", "origin_wildcard"),
        ("https://www.*.example.org", "origin_wildcard"),
        ("https://exa*mple.org", "origin_wildcard"),
        ("*.example.org", "origin_scheme"),
        # addresses and one-label names are not sites
        ("https://192.168.0.1", "origin_host"),
        ("https://intranet", "origin_host"),
        ("https://exa mple.org", "invalid_origin"),
        ("https://example.org\nhttps://evil.example", "invalid_origin"),
        # nothing that would add a source to the policy
        ("https://example.org; script-src *", "invalid_origin"),
        ("https://example.org 'unsafe-inline'", "invalid_origin"),
    ],
)
def test_refused_origins(raw, code):
    with pytest.raises(OriginRefused) as refused:
        canonical_origin(raw)
    assert refused.value.code == code


def test_not_a_string_is_refused():
    for bad in (None, 5, ["https://example.org"]):
        with pytest.raises(OriginRefused):
            canonical_origin(bad)  # type: ignore[arg-type]


def test_duplicates_collapse_and_order_is_kept():
    assert normalize_origins(
        [
            "https://b.example.org",
            "https://A.example.org",
            "https://b.example.org/",
            "https://a.example.org:443",
        ]
    ) == ["https://b.example.org", "https://a.example.org"]


def test_the_list_is_capped():
    origins = [f"https://site{i}.example.org" for i in range(MAX_ORIGINS)]
    assert len(normalize_origins(origins)) == MAX_ORIGINS
    with pytest.raises(OriginRefused) as refused:
        normalize_origins(origins + ["https://one-more.example.org"])
    assert refused.value.code == "too_many_origins"


def test_the_first_bad_entry_is_named_by_its_index():
    with pytest.raises(OriginRefused) as refused:
        normalize_origins(["https://ok.example.org", "https://*.com"])
    assert refused.value.index == 1  # type: ignore[attr-defined]
