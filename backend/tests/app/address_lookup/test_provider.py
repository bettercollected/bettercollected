"""The client of the address service, against a fake transport: what it sends
(only two validated values and constants, to one fixed address) and how it
reads what comes back. The real service is never called."""

import json

import pytest

from backend.app.services.address_lookup import provider
from backend.app.services.registration import client


def _doc(**kw):
    base = {"straatnaam": "Keizersgracht", "woonplaatsnaam": "Amsterdam", "postcode": "1015CS", "huisnummer": 12}
    base.update(kw)
    return base


def _body(*docs):
    return json.dumps({"response": {"numFound": len(docs), "docs": list(docs)}}).encode()


# --- what is sent ----------------------------------------------------------------


def test_the_query_is_two_values_and_constants():
    query = provider.build_query("1015CS", "12")
    assert dict(query) == {
        "q": "postcode:1015CS and huisnummer:12",
        "fq": "type:adres",
        "fl": "straatnaam,woonplaatsnaam,postcode,huisnummer",
        "rows": "20",
    }


@pytest.mark.parametrize(
    "postcode, number",
    [
        ("1015 CS", "12"),  # a space
        ("1015cs", "12"),
        ("0123AB", "12"),
        ("1015SS", "12"),
        ("1015SA", "12"),
        ("1015SD", "12"),
        ("1015CS", "0"),
        ("1015CS", "012"),
        ("1015CS", "123456"),
        ("1015CS", "12a"),
        ("1015CS", "12 or 1=1"),
        ("1015CS", "12\n"),
        ("1015CS)", "12"),
        ("1015CS OR huisnummer:1", "12"),
        ("1015CS", "12) OR (1"),
        ("*:*", "12"),
        ("1015CS", "*"),
        ("1015CS", "-1"),
        ("", ""),
        ("1015CS١", "12"),
        ("1015CS", "١٢"),
    ],
)
def test_nothing_but_the_two_forms_reaches_the_query(postcode, number):
    with pytest.raises(ValueError):
        provider.build_query(postcode, number)


def test_the_address_is_a_constant_of_the_module():
    assert provider.BASE_URL == "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
    assert provider.PATH == "free"
    # nothing in the settings names it
    from backend.config import settings

    names = [name for name in dir(settings) if "LOOKUP" in name.upper() and "URL" in name.upper()]
    assert names == []


async def test_the_real_transport_goes_through_the_guarded_client_to_the_fixed_address(monkeypatch):
    seen = {}

    async def fake_request(target, method, **kwargs):
        seen.update(target=target, method=method, **kwargs)
        return client.Reply(200, b"{}", False)

    monkeypatch.setattr(client, "request", fake_request)
    body = await provider.http_transport(provider.build_query("1015CS", "12"))
    assert body == b"{}"
    assert (seen["target"].base_url, seen["target"].path, seen["method"]) == (provider.BASE_URL, "free", "GET")
    assert seen["target"].auth == "none" and seen["target"].secret is None
    assert seen["keep_reply"] is True and seen["max_reply"] == 64 * 1024
    assert seen["user_agent"] == b"bettercollected-address-lookup/1"
    assert seen["total_timeout"] <= 5.0 and max(seen["timeouts"].values()) <= 3.0


@pytest.mark.parametrize(
    "failure, code",
    [
        ("timeout", "timeout"),
        ("tls_error", "tls_error"),
        ("unreachable", "unreachable"),
        ("http_5xx", "server_error"),
        ("http_4xx", "refused"),
        ("redirect_refused", "refused"),
        ("not_allowed", "refused"),
        ("invalid_url", "refused"),
    ],
)
async def test_the_clients_failures_become_our_codes(monkeypatch, failure, code):
    async def fail(*args, **kwargs):
        raise client.SendFailed(failure, permanent=False, http_status=500)

    monkeypatch.setattr(client, "request", fail)
    with pytest.raises(provider.LookupUnavailable) as error:
        await provider.http_transport(provider.build_query("1015CS", "12"))
    assert error.value.code == code


async def test_a_reply_over_the_cap_is_unavailable(monkeypatch):
    async def long_reply(*args, **kwargs):
        return client.Reply(200, b"", True)

    monkeypatch.setattr(client, "request", long_reply)
    with pytest.raises(provider.LookupUnavailable) as error:
        await provider.http_transport(provider.build_query("1015CS", "12"))
    assert error.value.code == "too_large"


async def test_the_real_transport_refuses_a_host_that_is_not_public(monkeypatch):
    """Down to the guarded client: the host name is resolved at the call and an
    answer that is not a public address is refused, with the client's own checks
    (no network is used: the resolver is replaced)."""

    async def private(host, port=443):
        return ["10.0.0.5"]

    monkeypatch.setattr(client, "resolve", private)
    monkeypatch.setattr(
        client, "network_backend", lambda host, address: pytest.fail("a connection was made")
    )
    with pytest.raises(provider.LookupUnavailable) as error:
        await provider.http_transport(provider.build_query("1015CS", "12"))
    assert error.value.code == "refused"


# --- what is read ------------------------------------------------------------------


def test_one_place_is_found():
    place = provider.parse_reply(_body(_doc()), "1015CS", "12")
    assert place == provider.Place("Keizersgracht", "Amsterdam")


def test_documents_for_the_same_place_agree():
    docs = [_doc(), _doc(huisnummer="12")]
    assert provider.parse_reply(_body(*docs), "1015CS", "12") == provider.Place("Keizersgracht", "Amsterdam")


def test_no_document_is_not_found():
    assert provider.parse_reply(_body(), "1015CS", "12") is None


def test_different_places_are_not_found_never_guessed():
    docs = [_doc(), _doc(woonplaatsnaam="Elsewhere")]
    assert provider.parse_reply(_body(*docs), "1015CS", "12") is None


def test_a_fuzzy_match_is_not_the_address_asked_for():
    for other in (_doc(huisnummer=13), _doc(postcode="1015CT"), _doc(huisnummer=None)):
        assert provider.parse_reply(_body(other), "1015CS", "12") is None


@pytest.mark.parametrize(
    "doc",
    [
        _doc(straatnaam=None),
        _doc(woonplaatsnaam=""),
        _doc(straatnaam=12),
        _doc(straatnaam="x" * 101),
        _doc(woonplaatsnaam="Amster​dam"),
        _doc(straatnaam=" Keizersgracht"),
        _doc(woonplaatsnaam=["Amsterdam"]),
    ],
)
def test_text_that_is_not_clean_is_dropped(doc):
    assert provider.parse_reply(_body(doc), "1015CS", "12") is None


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not json",
        b"[]",
        b'{"response": []}',
        b'{"response": {"docs": "x"}}',
        b'{"response": {"docs": null}}',
        b"\xff\xfe",
        b"[" * 100000,
    ],
)
def test_a_reply_that_is_not_the_services_is_unavailable(body):
    with pytest.raises(provider.LookupUnavailable) as error:
        provider.parse_reply(body, "1015CS", "12")
    assert error.value.code in ("bad_reply", "too_large")


def test_a_reply_over_the_cap_is_unavailable():
    with pytest.raises(provider.LookupUnavailable) as error:
        provider.parse_reply(b" " * (provider.MAX_REPLY_BYTES + 1), "1015CS", "12")
    assert error.value.code == "too_large"


def test_other_documents_and_odd_entries_are_skipped():
    docs = [_doc(), "text", 5, None, {"a": 1}]
    assert provider.parse_reply(_body(*docs), "1015CS", "12") == provider.Place("Keizersgracht", "Amsterdam")
