"""The public address lookup route: only for a published form of the
workspace that has an address question asking for a lookup, only while both
switches are on, strict input, rate limits per client and form and per form,
the provider's failures answered as "type it yourself", nothing stored and
nothing logged of what was asked. The service is given a fake transport; the
real one is never called."""

import datetime as dt
import json
from collections import OrderedDict

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.services.address_lookup import provider, service as service_module
from backend.config import settings
from common.models.user import User
from common.records import RecordId
from tests.app.auth_helpers import access_token
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
    for name, value in (("_forms_cache", OrderedDict()), ("_unservable", OrderedDict()), ("_coarse", OrderedDict()), ("_in_flight", 0), ("_failures", 0), ("_open_until", 0.0), ("counts", {})):
        monkeypatch.setattr(lookup, name, value)
    monkeypatch.setattr(lookup, "_budget", service_module._CallBudget())
    monkeypatch.setattr(lookup, "_form_budgets", OrderedDict())
    monkeypatch.setattr(lookup, "_access", OrderedDict())
    monkeypatch.setattr(lookup, "_budget_logged_at", None)
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


# --- forms that take no lookups right now (the submit gate's reading) -----------------


async def _settings(workspace, form_id, **values) -> None:
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(workspace_id=workspace.id, query=str(form_id))
    for key, value in values.items():
        setattr(link.settings, key, value)
    await repo.update(link.id, link)


def _in(**delta) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(**delta)).replace(microsecond=0).isoformat()


@pytest.mark.parametrize(
    "settings_",
    [
        {"form_close_date": _in(days=-1)},
        {"form_close_date": "2001-01-01T00:00:00+02:00"},
        {"form_open_date": _in(days=3)},
        {"private": True},
        {"hidden": True},
    ],
    ids=["closed", "closed-with-offset", "not-yet-open", "private", "hidden"],
)
async def test_a_form_that_takes_no_responses_for_the_public_answers_the_same_404(
    client: AsyncClient, workspace, form, transport, settings_
):
    url = _url(workspace.id, form.form_id)
    assert (await client.post(url, json=_ask())).status_code == 200
    await _settings(workspace, form.form_id, **settings_)
    container.address_lookup_service()._forms_cache.clear()
    for number in ("12", "13"):
        await _is_plain_404(client, url, _ask(number=number))
    assert len(transport.queries) == 1  # the one before the change


# --- a private form answers the signed-in respondents its groups admit ---------------------


def _cookies(user) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


STRANGER = User(id=str(RecordId()), sub="stranger@elsewhere.test")


async def _private_form(workspace, member=testUser1):
    """A published private form whose one group admits ``member`` by email."""
    form = await _published(workspace)
    await _settings(workspace, form.form_id, private=True)
    groups = container.responder_groups_repository()
    group = await groups.create_group(workspace.id, "Neighbours")
    await groups.add_emails_to_group(group.id, [member.sub])
    await groups.add_groups_to_form(str(form.form_id), [group.id])
    return form


async def test_a_member_of_a_private_forms_group_can_look_up_an_address(
    client: AsyncClient, workspace, transport
):
    form = await _private_form(workspace)
    url = _url(workspace.id, form.form_id)
    response = await client.post(url, json=_ask(), cookies=_cookies(testUser1))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "found"
    assert len(transport.queries) == 1


async def test_anonymous_and_non_members_get_the_same_404_for_a_private_form(
    client: AsyncClient, workspace, transport
):
    form = await _private_form(workspace)
    url = _url(workspace.id, form.form_id)
    await _is_plain_404(client, url, _ask())
    for user in (STRANGER, testUser):  # signed in, not in the group (the owner is not either)
        refused = await client.post(url, json=_ask(), cookies=_cookies(user))
        assert refused.status_code == 404, refused.text
        assert refused.json() == "Not found"
    # a broken session counts as no one
    await _is_plain_404(client, url, _ask())
    bad = await client.post(url, json=_ask(), cookies={"Authorization": "x.y.z", "RefreshToken": "x.y.z"})
    assert bad.status_code == 404 and bad.json() == "Not found"
    assert transport.queries == []


async def test_one_users_access_to_a_private_form_never_serves_another(
    client: AsyncClient, workspace, transport
):
    form = await _private_form(workspace)
    url = _url(workspace.id, form.form_id)
    member, stranger = _cookies(testUser1), _cookies(STRANGER)
    # the member is asked first and the form (and the member's access) is cached ...
    assert (await client.post(url, json=_ask(), cookies=member)).status_code == 200
    # ... and neither the cached form nor the cached access answers anyone else
    await _is_plain_404(client, url, _ask(number="13"))
    assert (await client.post(url, json=_ask(number="13"), cookies=stranger)).status_code == 404
    assert (await client.post(url, json=_ask(number="14"), cookies=member)).status_code == 200
    lookup = container.address_lookup_service()
    assert {key[2] for key in lookup._access} == {testUser1.sub, STRANGER.sub}
    # a refusal is remembered per user as well: the stranger stays out, the member in
    assert [allowed for (_, _, who), (allowed, _) in lookup._access.items() if who == STRANGER.sub] == [False]
    assert (await client.post(url, json=_ask(number="15"), cookies=member)).status_code == 200


async def test_access_to_a_private_form_is_read_again_after_the_cache_time(
    client: AsyncClient, workspace, transport, monkeypatch
):
    form = await _private_form(workspace)
    url = _url(workspace.id, form.form_id)
    lookup = container.address_lookup_service()
    now = {"t": 1000.0}
    monkeypatch.setattr(lookup, "_monotonic", lambda: now["t"])
    member = _cookies(testUser1)
    assert (await client.post(url, json=_ask(), cookies=member)).status_code == 200
    # the group no longer admits the member
    groups = container.responder_groups_repository()
    await groups.add_groups_to_form(str(form.form_id), [])
    assert (await client.post(url, json=_ask(number="13"), cookies=member)).status_code == 200
    now["t"] += service_module.FORM_CACHE_S + 1
    assert (await client.post(url, json=_ask(number="14"), cookies=member)).status_code == 404


async def test_a_private_form_that_is_also_hidden_answers_nobody(
    client: AsyncClient, workspace, transport
):
    form = await _private_form(workspace)
    await _settings(workspace, form.form_id, hidden=True)
    await _is_plain_404(client, _url(workspace.id, form.form_id), _ask())
    refused = await client.post(_url(workspace.id, form.form_id), json=_ask(), cookies=_cookies(testUser1))
    assert refused.status_code == 404
    assert transport.queries == []


async def test_the_user_is_read_only_for_a_private_form(client: AsyncClient, workspace, form, transport, monkeypatch):
    from backend.app.controllers import workspace_responses

    reads = []

    async def spy(request, response):
        reads.append(1)
        return None

    monkeypatch.setattr(workspace_responses, "get_user_if_logged_in", spy)
    assert (await client.post(_url(workspace.id, form.form_id), json=_ask())).status_code == 200
    assert reads == []  # a public form never looks at the session
    await _settings(workspace, form.form_id, private=True)
    container.address_lookup_service()._forms_cache.clear()
    await _is_plain_404(client, _url(workspace.id, form.form_id), _ask(number="13"))
    assert reads == [1]


async def test_a_deleted_form_stops_answering_after_the_cache_time(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    url = _url(workspace.id, form.form_id)
    lookup = container.address_lookup_service()
    now = {"t": 1000.0}
    monkeypatch.setattr(lookup, "_monotonic", lambda: now["t"])
    assert (await client.post(url, json=_ask())).status_code == 200
    await container.workspace_form_repo().delete_form_in_workspace(workspace.id, str(form.form_id))
    # the entry that was read is served for its 30 seconds ...
    assert (await client.post(url, json=_ask(number="13"))).status_code == 200
    # ... then the form is read again and is gone
    now["t"] += service_module.FORM_CACHE_S + 1
    await _is_plain_404(client, url, _ask(number="14"))


async def test_a_form_whose_workspace_link_has_no_settings_is_servable(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    from types import SimpleNamespace

    lookup = container.address_lookup_service()
    real = lookup._workspace_forms.get_workspace_form_with_custom_slug_form_id

    async def without_settings(**kwargs):
        link = await real(**kwargs)
        return SimpleNamespace(form_id=link.form_id, settings=None)

    monkeypatch.setattr(lookup._workspace_forms, "get_workspace_form_with_custom_slug_form_id", without_settings)
    served = await client.post(_url(workspace.id, form.form_id), json=_ask())
    assert served.status_code == 200, served.text
    entry = next(iter(lookup._forms_cache.values()))
    assert entry.private is False and entry.dates == (None, None)


async def test_an_open_form_with_dates_around_now_answers(client: AsyncClient, workspace, form, transport):
    await _settings(workspace, form.form_id, form_open_date=_in(days=-1), form_close_date=_in(days=1))
    assert (await client.post(_url(workspace.id, form.form_id), json=_ask())).status_code == 200


async def test_the_dates_are_judged_at_every_call_not_when_the_form_was_loaded(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    url = _url(workspace.id, form.form_id)
    opens = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    closes = opens + dt.timedelta(days=1)
    await _settings(workspace, form.form_id, form_open_date=opens.isoformat(), form_close_date=closes.isoformat())
    now = {"t": dt.datetime.now(dt.timezone.utc)}
    monkeypatch.setattr("common.clock.utcnow", lambda: now["t"])
    await _is_plain_404(client, url, _ask())
    # the form is cached as servable once it was loaded in its open time ...
    now["t"] = opens + dt.timedelta(minutes=1)
    assert (await client.post(url, json=_ask())).status_code == 200
    # ... and the cached entry stops answering at the close instant
    now["t"] = closes
    await _is_plain_404(client, url, _ask(number="13"))
    assert len(transport.queries) == 1


async def _submit(client, workspace, form_id):
    return await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
        data={"response": json.dumps({"answers": {}})},
    )


async def test_a_full_form_answers_the_same_404_and_a_free_slot_answers_again(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    url = _url(workspace.id, form.form_id)
    await _settings(workspace, form.form_id, response_limit=2)
    assert (await client.post(url, json=_ask())).status_code == 200
    for _ in range(2):
        assert (await _submit(client, workspace, form.form_id)).status_code == 200
    # the form's entry is read again after its cache time
    now = {"t": 5000.0}
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_monotonic", lambda: now["t"])
    lookup._forms_cache.clear()
    await _is_plain_404(client, url, _ask(number="13"))
    # a form that has not used its limit up answers
    await _settings(workspace, form.form_id, response_limit=3)
    now["t"] += service_module.FORM_CACHE_S + 1
    assert (await client.post(url, json=_ask(number="14"))).status_code == 200
    assert len(transport.queries) == 2


async def test_the_responses_are_counted_only_for_a_form_with_a_limit(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    counted = []

    class Counter:
        async def count_responses_for_form_ids(self, scope):
            counted.append(1)
            return 0

    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_responses", Counter())
    url = _url(workspace.id, form.form_id)
    assert (await client.post(url, json=_ask())).status_code == 200
    assert counted == []
    await _settings(workspace, form.form_id, response_limit=5)
    lookup._forms_cache.clear()
    assert (await client.post(url, json=_ask(number="13"))).status_code == 200
    assert (await client.post(url, json=_ask(number="14"))).status_code == 200
    assert counted == [1]  # once per cache lifetime


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


async def test_a_form_that_is_not_servable_is_looked_up_once_per_half_minute(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    lookup = container.address_lookup_service()
    clock = {"t": 1000.0}
    monkeypatch.setattr(lookup, "_monotonic", lambda: clock["t"])
    loads = []
    real = lookup._load

    async def counted(*args, **kwargs):
        loads.append(1)
        return await real(*args, **kwargs)

    monkeypatch.setattr(lookup, "_load", counted)
    url = _url(workspace.id, "no-such-slug")
    for _ in range(5):
        await _is_plain_404(client, url, _ask())
    assert len(loads) == 1
    clock["t"] += service_module.FORM_CACHE_S + 1
    await _is_plain_404(client, url, _ask())
    assert len(loads) == 2
    assert transport.queries == []


async def test_the_memory_of_forms_that_are_not_servable_is_bounded(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    monkeypatch.setattr(service_module, "NEGATIVE_CACHE_SIZE", 3)
    for index in range(8):
        await _is_plain_404(client, _url(workspace.id, f"missing-{index}"), _ask())
    assert len(container.address_lookup_service()._unservable) <= 3


async def test_a_client_that_floods_is_stopped_before_the_database_is_asked(
    client: AsyncClient, workspace, form, transport, limits, monkeypatch
):
    lookup = container.address_lookup_service()
    loads = []

    async def refuse(*args, **kwargs):
        loads.append(1)
        return None

    monkeypatch.setattr(lookup, "_load", refuse)
    flood = {"X-Forwarded-For": "203.0.113.77"}
    allowed = 3 * service_module.COARSE_FACTOR
    for index in range(allowed):
        # a different form every time: nothing is cached
        response = await client.post(_url(workspace.id, f"missing-{index}"), json=_ask(), headers=flood)
        assert response.status_code == 404
    assert len(loads) == allowed
    refused = await client.post(_url(workspace.id, "missing-next"), json=_ask(), headers=flood)
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) >= 1
    assert len(loads) == allowed
    # another client is not affected
    other = await client.post(
        _url(workspace.id, "missing-next"), json=_ask(), headers={"X-Forwarded-For": "198.51.100.5"}
    )
    assert other.status_code == 404


# --- bounded LRU tables and the outbound call rate -------------------------------------


def test_the_tables_drop_the_entry_used_longest_ago_first():
    table = OrderedDict()
    for key in ("a", "b", "c"):
        service_module._put(table, key, 1, 3)
    table.move_to_end("a")  # "a" was used again: "b" is now the oldest
    service_module._put(table, "d", 1, 3)
    assert list(table) == ["c", "a", "d"]
    service_module._put(table, "c", 2, 3)  # an update makes it the newest
    service_module._put(table, "e", 1, 3)
    assert list(table) == ["d", "c", "e"]


async def test_a_flood_of_new_clients_does_not_reset_an_active_clients_counter(
    client: AsyncClient, workspace, form, transport, limits, monkeypatch
):
    monkeypatch.setattr(service_module, "COARSE_SIZE", 4)
    heavy = {"X-Forwarded-For": "203.0.113.200"}
    allowed = 3 * service_module.COARSE_FACTOR
    for round_ in range(allowed):
        # a different form every time, so only the in-memory counter counts
        sent = await client.post(_url(workspace.id, f"missing-{round_}"), json=_ask(), headers=heavy)
        assert sent.status_code == 404
        # between the heavy client's requests new clients arrive: clearing the
        # table whenever it is full would forget the heavy client's count
        for other in range(2):
            await client.post(
                _url(workspace.id, "missing-x"), json=_ask(), headers={"X-Forwarded-For": f"198.51.100.{round_ * 2 + other + 1}"}
            )
    refused = await client.post(_url(workspace.id, "missing-next"), json=_ask(), headers=heavy)
    assert refused.status_code == 429
    assert len(container.address_lookup_service()._coarse) <= 4


async def test_the_forms_cache_and_the_negative_cache_drop_the_oldest_first(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    monkeypatch.setattr(service_module, "NEGATIVE_CACHE_SIZE", 3)
    lookup = container.address_lookup_service()
    for index in range(3):
        await _is_plain_404(client, _url(workspace.id, f"missing-{index}"), _ask())
    # missing-0 is used again, so missing-1 is the oldest
    await _is_plain_404(client, _url(workspace.id, "missing-0"), _ask())
    await _is_plain_404(client, _url(workspace.id, "missing-3"), _ask())
    assert [key[1] for key in lookup._unservable] == ["missing-2", "missing-0", "missing-3"]

    monkeypatch.setattr(service_module, "FORM_CACHE_SIZE", 2)
    other = await _published(workspace)
    third = await _published(workspace)
    for form_id in (form.form_id, other.form_id):
        assert (await client.post(_url(workspace.id, form_id), json=_ask())).status_code == 200
    assert (await client.post(_url(workspace.id, form.form_id), json=_ask())).status_code == 200  # first is newest
    assert (await client.post(_url(workspace.id, third.form_id), json=_ask())).status_code == 200
    kept = [key[1] for key in lookup._forms_cache]
    assert kept == [form.form_id, third.form_id]


def test_the_call_budget_caps_a_second_and_a_minute(monkeypatch):
    monkeypatch.setattr(service_module, "CALLS_PER_SECOND", 3)
    monkeypatch.setattr(service_module, "CALLS_PER_MINUTE", 5)
    budget = service_module._CallBudget()
    assert [budget.take(100.0 + i * 0.1) for i in range(4)] == [True, True, True, False]
    assert budget.take(101.5) is True  # the second moved on
    assert budget.take(101.6) is True
    assert budget.take(102.0) is False  # five in the minute
    assert budget.take(160.5) is True  # the first calls left the minute
    assert len(budget._made) <= 5


async def test_over_the_call_rate_the_answer_is_unavailable_without_a_call(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    monkeypatch.setattr(service_module, "CALLS_PER_SECOND", 2)
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_monotonic", lambda: 1000.0)
    url = _url(workspace.id, form.form_id)
    for number in ("1", "2"):
        assert (await client.post(url, json=_ask(number=number))).status_code == 200
    over = await client.post(url, json=_ask(number="3"))
    assert over.status_code == 503, over.text
    assert over.json()["code"] == "lookup_unavailable"
    assert len(transport.queries) == 2
    # a cached answer needs no call, so it is still served over the rate
    assert (await client.post(url, json=_ask(number="1"))).status_code == 200
    # the breaker is not touched by a refusal of the rate
    assert lookup._failures == 0
    monkeypatch.setattr(lookup, "_monotonic", lambda: 1001.5)
    assert (await client.post(url, json=_ask(number="3"))).status_code == 200
    assert len(transport.queries) == 3


async def test_one_form_cannot_use_up_the_process_budget(
    client: AsyncClient, workspace, form, transport, monkeypatch
):
    monkeypatch.setattr(service_module, "FORM_CALLS_PER_MINUTE", 3)
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_monotonic", lambda: 1000.0)
    other = await _published(workspace)
    url = _url(workspace.id, form.form_id)
    for number in ("1", "2", "3"):
        assert (await client.post(url, json=_ask(number=number))).status_code == 200
    over = await client.post(url, json=_ask(number="4"))
    assert over.status_code == 503 and over.json()["code"] == "lookup_unavailable"
    assert lookup.counts.get("budget") == 1
    assert len(transport.queries) == 3
    # a cached answer for the form is still served, another form still has its share
    assert (await client.post(url, json=_ask(number="1"))).status_code == 200
    assert (await client.post(_url(workspace.id, other.form_id), json=_ask(number="4"))).status_code == 200
    # the form's share is a minute wide
    monkeypatch.setattr(lookup, "_monotonic", lambda: 1061.0)
    assert (await client.post(url, json=_ask(number="5"))).status_code == 200
    # the process's window is a minute wide too: only the new call is in it
    assert len(lookup._budget._made) == 1


async def test_the_form_budgets_are_a_bounded_lru(client: AsyncClient, workspace, transport, monkeypatch):
    monkeypatch.setattr(service_module, "FORM_BUDGET_SIZE", 2)
    lookup = container.address_lookup_service()
    forms = [await _published(workspace) for _ in range(3)]
    for number, one in enumerate(forms, start=1):
        assert (await client.post(_url(workspace.id, one.form_id), json=_ask(number=str(number)))).status_code == 200
    assert list(lookup._form_budgets) == [str(forms[1].form_id), str(forms[2].form_id)]


async def test_a_refusal_by_the_budget_has_its_own_outcome_and_one_warning_a_minute(
    client: AsyncClient, workspace, form, transport, monkeypatch, caplog
):
    from loguru import logger

    lines = []
    handle = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    try:
        monkeypatch.setattr(service_module, "CALLS_PER_SECOND", 1)
        lookup = container.address_lookup_service()
        now = {"t": 1000.0}
        monkeypatch.setattr(lookup, "_monotonic", lambda: now["t"])
        url = _url(workspace.id, form.form_id)
        assert (await client.post(url, json=_ask(number="1"))).status_code == 200
        for number in ("2", "3", "4"):
            assert (await client.post(url, json=_ask(number=number))).status_code == 503
        assert lookup.counts["budget"] == 3
        assert lookup.counts.get("unavailable", 0) == 0  # not a failure of the service
        assert lookup._failures == 0
        assert [m for m in lines if "budget" in m] == ["address lookup call budget reached: 1 refused so far"]
        now["t"] += service_module.BUDGET_LOG_EVERY_S + 1
        assert (await client.post(url, json=_ask(number="5"))).status_code == 200
        assert (await client.post(url, json=_ask(number="6"))).status_code == 503
        # the new refusal after the quiet minute is logged again (counts only)
        assert [m for m in lines if "budget" in m][-1] == f"address lookup call budget reached: {lookup.counts['budget']} refused so far"
        assert len([m for m in lines if "budget" in m]) == 2
    finally:
        logger.remove(handle)
    for secret in ("1015", "Keizersgracht", "203.0.113"):
        assert not any(secret in m for m in lines)


async def test_a_refusal_by_the_budget_still_counts_as_a_lookup_of_the_client(
    client: AsyncClient, workspace, form, transport, clock, limits, monkeypatch
):
    # documented: the limiter counts before the call and has no refund
    monkeypatch.setattr(service_module, "CALLS_PER_SECOND", 1)
    lookup = container.address_lookup_service()
    monkeypatch.setattr(lookup, "_monotonic", lambda: 1000.0)
    url = _url(workspace.id, form.form_id)
    headers = {"X-Forwarded-For": "203.0.113.31"}
    assert (await client.post(url, json=_ask(number="1"), headers=headers)).status_code == 200
    assert (await client.post(url, json=_ask(number="2"), headers=headers)).status_code == 503
    assert (await client.post(url, json=_ask(number="3"), headers=headers)).status_code == 503
    assert (await client.post(url, json=_ask(number="1"), headers=headers)).status_code == 429


async def test_a_client_over_the_coarse_limit_counts_as_recently_used(
    client: AsyncClient, workspace, form, transport, limits, monkeypatch
):
    lookup = container.address_lookup_service()
    heavy = {"X-Forwarded-For": "203.0.113.90"}
    for index in range(3 * service_module.COARSE_FACTOR):
        await client.post(_url(workspace.id, f"missing-{index}"), json=_ask(), headers=heavy)
    await client.post(_url(workspace.id, "missing-x"), json=_ask(), headers={"X-Forwarded-For": "198.51.100.1"})
    assert (await client.post(_url(workspace.id, "missing-y"), json=_ask(), headers=heavy)).status_code == 429
    # the refused client's entry was moved to the recent end, behind the other client's
    assert "203.0.113.90" in next(reversed(lookup._coarse))


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
