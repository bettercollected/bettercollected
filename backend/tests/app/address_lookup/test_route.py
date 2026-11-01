"""The public address lookup route: only for a published form of the
workspace that has an address question asking for a lookup, only while both
switches are on, strict input, rate limits per client and form and per form,
the provider's failures answered as "type it yourself", nothing stored and
nothing logged of what was asked. The service is given a fake transport; the
real one is never called."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.services.address_lookup import provider, service as service_module
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1

T0 = 1_900_000_040.0  # 20s into a 60s window
POSTCODE, NUMBER = "1015 CS", "12"
DOC = {"straatnaam": "Keizersgracht", "woonplaatsnaam": "Amsterdam", "postcode": "1015CS", "huisnummer": 12}


def _url(workspace_id, form_id) -> str:
    return f"/api/v1/workspaces/{workspace_id}/forms/{form_id}/address-lookup"


def _ask(field_id="ad", postcode=POSTCODE, number=NUMBER, **extra):
    return {"fieldId": field_id, "postcode": postcode, "houseNumber": number, **extra}


def _reply(*docs):
    return json.dumps({"response": {"docs": list(docs)}}).encode()


class FakeTransport:
    """Records every query it is given; answers what it is told to."""

    def __init__(self, answer=None):
        self.answer = answer if answer is not None else _reply(DOC)
        self.queries = []

    async def __call__(self, query):
        self.queries.append(list(query))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(settings, "ADDRESS_QUESTION_ENABLED", True)
    monkeypatch.setattr(settings, "ADDRESS_LOOKUP_ENABLED", True)
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")


@pytest.fixture()
def clock(monkeypatch):
    now = {"t": T0}
    monkeypatch.setattr(container.rate_limiter(), "_clock", lambda: now["t"])
    return now


@pytest.fixture()
def transport(monkeypatch):
    fake = FakeTransport()
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_transport", fake)
    # a fresh service state for every test
    for name, value in (("_forms_cache", {}), ("_in_flight", 0), ("_failures", 0), ("_open_until", 0.0), ("counts", {})):
        monkeypatch.setattr(lookup, name, value)
    monkeypatch.setattr(lookup, "_results", type(lookup._results)())
    return fake


def _form(address_properties=None, extra=None, internal=False):
    address = {"id": "ad", "type": "address", "title": "Home", "properties": address_properties or {}}
    if internal:
        address["internal"] = True
    fields = [{"id": "name", "type": "short_text", "title": "Name"}, address, *(extra or [])]
    page = {"id": "p1", "index": 0, "type": "slide", "properties": {"fields": fields}}
    return _parse_form_body(json.dumps({"title": "Where", "builderVersion": "v2", "fields": [page]}))


async def _published(workspace, body=None, publish=True):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, body or _form(), testUser)
    if publish:
        await service.publish_form(workspace.id, form.form_id, testUser)
    return form


@pytest.fixture()
async def form(workspace):
    return await _published(workspace)


# --- the answer ----------------------------------------------------------------------


async def test_a_postcode_and_a_number_find_street_and_city(client: AsyncClient, workspace, form, transport):
    response = await client.post(_url(workspace.id, form.form_id), json=_ask())
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "found", "street": "Keizersgracht", "city": "Amsterdam"}
    assert response.headers["Cache-Control"] == "no-store"
    # what was sent: the two values with the space gone, and constants
    assert len(transport.queries) == 1
    assert dict(transport.queries[0])["q"] == "postcode:1015CS and huisnummer:12"


async def test_the_input_is_normalised_before_it_is_sent(client: AsyncClient, workspace, form, transport):
    for postcode in ("1015cs", "1015 CS", " 1015CS ", "1015 cS"):
        response = await client.post(_url(workspace.id, form.form_id), json=_ask(postcode=postcode, number=" 12 "))
        assert response.status_code == 200, response.text
    assert {dict(q)["q"] for q in transport.queries} == {"postcode:1015CS and huisnummer:12"}
    # one call: the rest came from the cache
    assert len(transport.queries) == 1


async def test_no_match_is_not_found(client: AsyncClient, workspace, form, transport):
    transport.answer = _reply()
    response = await client.post(_url(workspace.id, form.form_id), json=_ask())
    assert response.status_code == 200
    assert response.json() == {"status": "not_found"}


async def test_a_question_inside_a_repeating_group_can_be_looked_up(client: AsyncClient, workspace, transport):
    group = {
        "id": "grp",
        "type": "group",
        "title": "People",
        "properties": {
            "repeat": {"minItems": 1, "maxItems": 3},
            "fields": [{"id": "gad", "type": "address", "title": "Home"}],
        },
    }
    form = await _published(workspace, _form(extra=[group]))
    response = await client.post(_url(workspace.id, form.form_id), json=_ask(field_id="gad"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "found"


# --- who may ask ---------------------------------------------------------------------


async def _is_plain_404(client, url, body):
    response = await client.post(url, json=body)
    assert response.status_code == 404, response.text
    assert response.json() == "Not found"


async def test_unknown_unpublished_and_other_forms_are_the_same_404(client: AsyncClient, workspace, form, transport):
    unpublished = await _published(workspace, publish=False)
    for form_id in ("65f0c0ffee0000000000abcd", "no-such-slug", "x" * 200, unpublished.form_id):
        await _is_plain_404(client, _url(workspace.id, form_id), _ask())
    assert transport.queries == []


async def test_another_workspaces_form_is_not_found(client: AsyncClient, workspace, workspace_1, transport, monkeypatch):
    other = await container.workspace_form_service().create_form(workspace_1.id, _form(), testUser1)
    await container.workspace_form_service().publish_form(workspace_1.id, other.form_id, testUser1)
    await _is_plain_404(client, _url(workspace.id, other.form_id), _ask())
    assert transport.queries == []


async def test_a_question_that_is_not_an_address_question_is_the_same_404(client: AsyncClient, workspace, form, transport):
    for field_id in ("name", "nope", "p1", "x" * 64):
        await _is_plain_404(client, _url(workspace.id, form.form_id), _ask(field_id=field_id))
    assert transport.queries == []


async def test_a_question_that_asks_for_no_lookup_is_the_same_404(client: AsyncClient, workspace, transport):
    for properties in ({"addressLookup": False}, {"countries": ["BE", "DE"]}):
        form = await _published(workspace, _form(properties))
        await _is_plain_404(client, _url(workspace.id, form.form_id), _ask())
    assert transport.queries == []


async def test_an_internal_address_question_is_not_looked_up(client: AsyncClient, workspace, transport):
    form = await _published(workspace, _form(internal=True))
    await _is_plain_404(client, _url(workspace.id, form.form_id), _ask())


async def test_the_switches_decide(client: AsyncClient, workspace, form, transport, monkeypatch):
    url = _url(workspace.id, form.form_id)
    monkeypatch.setattr(settings, "ADDRESS_LOOKUP_ENABLED", False)
    await _is_plain_404(client, url, _ask())
    monkeypatch.setattr(settings, "ADDRESS_LOOKUP_ENABLED", True)
    monkeypatch.setattr(settings, "ADDRESS_QUESTION_ENABLED", False)
    await _is_plain_404(client, url, _ask())
    monkeypatch.setattr(settings, "ADDRESS_QUESTION_ENABLED", True)
    assert (await client.post(url, json=_ask())).status_code == 200
    assert len(transport.queries) == 1  # no call while off


async def test_a_form_without_an_address_question_is_not_found(client: AsyncClient, workspace, published_form, transport):
    await _is_plain_404(client, _url(workspace.id, published_form.form_id), _ask())


# --- the input ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        _ask(postcode="1015"),
        _ask(postcode="ABCD EF"),
        _ask(postcode="0123 AB"),
        _ask(postcode="1015 SS"),
        _ask(number="0"),
        _ask(number="12a"),
        _ask(number="123456"),
        _ask(number="1 OR 1=1"),
        _ask(postcode="1015CS OR x"),
        _ask(postcode="*:*"),
        _ask(postcode="1015 CS\nq=x"),
        _ask(postcode="1015%20CS"),
        _ask(number="12&rows=1000"),
    ],
)
async def test_input_that_is_not_a_postcode_and_a_number_is_refused_unsent(
    client: AsyncClient, workspace, form, transport, body
):
    response = await client.post(_url(workspace.id, form.form_id), json=body)
    assert response.status_code == 422, response.text
    assert transport.queries == []


@pytest.mark.parametrize(
    "body",
    [
        {"fieldId": "ad", "postcode": POSTCODE},
        {"postcode": POSTCODE, "houseNumber": NUMBER},
        {**_ask(), "houseNumberAddition": "A"},
        {**_ask(), "url": "https://example.test"},
        _ask(postcode="1" * 13),
        _ask(number="1" * 11),
        _ask(field_id="x" * 65),
        {**_ask(), "postcode": ["1015 CS"]},
        {**_ask(), "houseNumber": 12},
        {**_ask(), "fieldId": ""},
    ],
)
async def test_a_malformed_body_is_refused_unsent(client: AsyncClient, workspace, form, transport, body):
    response = await client.post(_url(workspace.id, form.form_id), json=body)
    assert response.status_code == 422, response.text
    assert transport.queries == []


async def test_the_addition_is_never_sent(client: AsyncClient, workspace, form, transport):
    # a body with an addition is refused outright: it has nowhere to go
    response = await client.post(_url(workspace.id, form.form_id), json={**_ask(), "houseNumberAddition": "A"})
    assert response.status_code == 422
    assert transport.queries == []


# --- the service does not answer ------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        provider.LookupUnavailable("timeout"),
        provider.LookupUnavailable("server_error"),
        RuntimeError("SECRET-DETAIL 1015 CS 12 Keizersgracht"),
        b"not json",
        b'{"response": {"docs": 3}}',
    ],
)
async def test_a_failure_is_unavailable_with_nothing_of_it_shown(
    client: AsyncClient, workspace, form, transport, failure, caplog
):
    transport.answer = failure
    response = await client.post(_url(workspace.id, form.form_id), json=_ask())
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "lookup_unavailable"
    assert response.headers["Retry-After"] == "30"
    for secret in ("SECRET-DETAIL", "1015", "Keizersgracht"):
        assert secret not in response.text, secret
        assert secret not in caplog.text, secret


async def test_an_error_is_not_cached(client: AsyncClient, workspace, form, transport):
    transport.answer = provider.LookupUnavailable("timeout")
    url = _url(workspace.id, form.form_id)
    assert (await client.post(url, json=_ask())).status_code == 503
    transport.answer = _reply(DOC)
    assert (await client.post(url, json=_ask())).json()["status"] == "found"
    assert len(transport.queries) == 2


async def test_the_circuit_opens_after_repeated_failures_and_closes_again(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    now = {"t": 1000.0}
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_monotonic", lambda: now["t"])
    transport.answer = provider.LookupUnavailable("timeout")
    url = _url(workspace.id, form.form_id)
    for number in range(1, 6):
        assert (await client.post(url, json=_ask(number=str(number)))).status_code == 503
    assert len(transport.queries) == 5
    # open: answered at once, nothing is called
    assert (await client.post(url, json=_ask(number="9"))).status_code == 503
    assert len(transport.queries) == 5
    # after the pause one call goes through again
    now["t"] += service_module.BREAKER_OPEN_S + 1
    transport.answer = _reply(DOC)
    assert (await client.post(url, json=_ask(number="12"))).json()["status"] == "found"
    assert len(transport.queries) == 6


async def test_only_so_many_calls_are_in_flight(client: AsyncClient, workspace, form, transport, monkeypatch):
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_in_flight", service_module.MAX_IN_FLIGHT)
    response = await client.post(_url(workspace.id, form.form_id), json=_ask())
    assert response.status_code == 503
    assert transport.queries == []
    # a cached answer needs no call
    monkeypatch.setattr(lookup, "_in_flight", 0)
    assert (await client.post(_url(workspace.id, form.form_id), json=_ask())).status_code == 200
    monkeypatch.setattr(lookup, "_in_flight", service_module.MAX_IN_FLIGHT)
    assert (await client.post(_url(workspace.id, form.form_id), json=_ask())).status_code == 200
    assert len(transport.queries) == 1


async def test_the_counter_of_calls_in_flight_comes_back(client: AsyncClient, workspace, form, transport):
    lookup = container.address_lookup_service()
    transport.answer = provider.LookupUnavailable("timeout")
    await client.post(_url(workspace.id, form.form_id), json=_ask())
    transport.answer = RuntimeError("x")
    await client.post(_url(workspace.id, form.form_id), json=_ask())
    assert lookup._in_flight == 0


async def test_answers_are_cached_and_not_found_expires_sooner(client: AsyncClient, workspace, form, transport, monkeypatch):
    now = {"t": 1000.0}
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_monotonic", lambda: now["t"])
    url = _url(workspace.id, form.form_id)
    transport.answer = _reply()
    assert (await client.post(url, json=_ask())).json() == {"status": "not_found"}
    assert (await client.post(url, json=_ask())).json() == {"status": "not_found"}
    assert len(transport.queries) == 1
    now["t"] += service_module.NOT_FOUND_TTL_S + 1
    transport.answer = _reply(DOC)
    assert (await client.post(url, json=_ask())).json()["status"] == "found"
    assert len(transport.queries) == 2
    now["t"] += service_module.NOT_FOUND_TTL_S + 1  # a found answer lasts longer
    assert (await client.post(url, json=_ask())).json()["status"] == "found"
    assert len(transport.queries) == 2
    now["t"] += service_module.FOUND_TTL_S
    assert (await client.post(url, json=_ask())).json()["status"] == "found"
    assert len(transport.queries) == 3


async def test_the_cache_is_bounded(client: AsyncClient, workspace, form, transport, monkeypatch):
    monkeypatch.setattr(service_module, "CACHE_SIZE", 3)
    url = _url(workspace.id, form.form_id)
    for number in range(1, 8):
        await client.post(url, json=_ask(number=str(number)))
    assert len(container.address_lookup_service()._results) == 3


# --- rate limits -----------------------------------------------------------------------


@pytest.fixture()
def limits(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "ADDRESS_LOOKUP_PER_WINDOW", 3)
    monkeypatch.setattr(settings.api_settings, "ADDRESS_LOOKUP_FORM_PER_WINDOW", 5)
    monkeypatch.setattr(settings.api_settings, "ADDRESS_LOOKUP_WINDOW_SECONDS", 60)


async def test_a_client_is_limited_per_form_until_the_window_ends(
    client: AsyncClient, workspace, form, transport, clock, limits
):
    url = _url(workspace.id, form.form_id)
    alice = {"X-Forwarded-For": "203.0.113.7"}
    for _ in range(3):
        assert (await client.post(url, json=_ask(), headers=alice)).status_code == 200
    refused = await client.post(url, json=_ask(), headers=alice)
    assert refused.status_code == 429, refused.text
    assert refused.headers["Retry-After"] == "40"
    # another client is counted on its own, a spoofed hop changes nothing
    assert (await client.post(url, json=_ask(), headers={"X-Forwarded-For": "198.51.100.23"})).status_code == 200
    assert (await client.post(url, json=_ask(), headers={"X-Forwarded-For": "192.0.2.1, 203.0.113.7"})).status_code == 429
    clock["t"] = T0 + 40
    assert (await client.post(url, json=_ask(), headers=alice)).status_code == 200


async def test_all_clients_of_a_form_together_are_limited(
    client: AsyncClient, workspace, form, transport, clock, limits
):
    url = _url(workspace.id, form.form_id)
    for index in range(5):
        sent = await client.post(url, json=_ask(), headers={"X-Forwarded-For": f"203.0.113.{index + 10}"})
        assert sent.status_code == 200, sent.text
    refused = await client.post(url, json=_ask(), headers={"X-Forwarded-For": "203.0.113.99"})
    assert refused.status_code == 429


async def test_a_cached_answer_still_counts(client: AsyncClient, workspace, form, transport, clock, limits):
    url = _url(workspace.id, form.form_id)
    headers = {"X-Forwarded-For": "203.0.113.50"}
    for _ in range(3):
        assert (await client.post(url, json=_ask(), headers=headers)).status_code == 200
    assert len(transport.queries) == 1
    assert (await client.post(url, json=_ask(), headers=headers)).status_code == 429


async def test_a_form_that_does_not_exist_creates_no_counter(client: AsyncClient, workspace, form, transport, clock):
    from backend.db.models import RateLimitCounterRow

    async def counters():
        async with container.pg_sessionmaker()() as session:
            return len(list((await session.execute(select(RateLimitCounterRow))).scalars()))

    before = await counters()
    for _ in range(3):
        await client.post(_url(workspace.id, "65f0c0ffee0000000000abcd"), json=_ask())
        await client.post(_url(workspace.id, form.form_id), json=_ask(field_id="name"))
    assert await counters() == before


async def test_nothing_that_was_asked_is_stored_or_logged(
    client: AsyncClient, workspace, form, transport, clock, caplog
):
    from backend.db.models import RateLimitCounterRow

    address = "203.0.113.77"
    await client.post(_url(workspace.id, form.form_id), json=_ask(), headers={"X-Forwarded-For": address})
    async with container.pg_sessionmaker()() as session:
        rows = (await session.execute(select(RateLimitCounterRow))).scalars()
        stored = "\n".join(repr((r.id, r.doc)) for r in rows)
    assert stored
    for secret in (address, "203.0.113", "1015", "Keizersgracht", "Amsterdam"):
        assert secret not in stored, secret
        assert secret not in caplog.text, secret
