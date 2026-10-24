"""The public flow-events endpoint (#767): only published forms of the
workspace, only their pages, and a per-client, per-form rate limit."""

import uuid
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.container import container
from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.config import settings

T0 = 1_900_000_040.0  # 20s into a 60s window


def _url(workspace_id, form_id) -> str:
    return f"/api/v1/workspaces/{workspace_id}/forms/{form_id}/flow-events"


def _event(from_page="__welcome__", to_page="string", session_id=None) -> dict:
    return {
        "sessionId": session_id or str(uuid.uuid4()),
        "fromPage": from_page,
        "toPage": to_page,
    }


async def _stored_events(form_id: str):
    return await container.flow_event_repo().list_by_form_id(form_id)


@pytest.fixture(autouse=True)
def behind_a_proxy(monkeypatch):
    """The test client connects from 127.0.0.1: treat it as the reverse proxy
    whose X-Forwarded-For is believed (the default trusts nobody)."""
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")


@pytest.fixture()
def clock(monkeypatch):
    now = {"t": T0}
    monkeypatch.setattr(container.rate_limiter(), "_clock", lambda: now["t"])
    return now


@pytest.fixture()
def limit(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "FLOW_EVENTS_PER_WINDOW", 3)
    monkeypatch.setattr(settings.api_settings, "FLOW_EVENTS_WINDOW_SECONDS", 60)
    return 3


async def test_a_valid_event_is_recorded(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
):
    sent = await client.post(
        _url(workspace.id, published_form.form_id), json=_event()
    )
    assert sent.status_code == 200, sent.text
    events = await _stored_events(published_form.form_id)
    assert [(e.from_page, e.to_page) for e in events] == [("__welcome__", "string")]

    # by its custom slug too, stored under the form's id
    sent = await client.post(
        _url(workspace.id, "string"), json=_event("string", "__submit__")
    )
    assert sent.status_code == 200, sent.text
    assert len(await _stored_events(published_form.form_id)) == 2
    assert await _stored_events("string") == []


async def test_an_unknown_form_is_not_found(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
):
    for form_id in ("65f0c0ffee0000000000abcd", "no-such-slug", "x" * 200):
        sent = await client.post(_url(workspace.id, form_id), json=_event())
        assert sent.status_code == 404, sent.text
        assert sent.json() == "Form not found"


async def test_an_unpublished_form_is_not_found_alike(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    sent = await client.post(
        _url(workspace.id, workspace_form.form_id), json=_event()
    )
    assert sent.status_code == 404, sent.text
    assert sent.json() == "Form not found"
    assert await _stored_events(workspace_form.form_id) == []


async def test_another_workspaces_form_is_not_found(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form_1: Coroutine[Any, Any, FormDocument],
):
    sent = await client.post(
        _url(workspace.id, published_form_1.form_id), json=_event()
    )
    assert sent.status_code == 404, sent.text
    assert await _stored_events(published_form_1.form_id) == []


@pytest.mark.parametrize(
    "body",
    [
        _event(to_page="not-a-page"),
        _event(from_page="nope", to_page="__submit__"),
    ],
)
async def test_a_page_not_in_the_form_is_refused(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    body: dict,
):
    sent = await client.post(_url(workspace.id, published_form.form_id), json=body)
    assert sent.status_code == 422, sent.text
    assert await _stored_events(published_form.form_id) == []


@pytest.mark.parametrize(
    "body",
    [
        {**_event(), "toPage": "p" * 65},
        {**_event(), "sessionId": "s" * 65},
        {**_event(), "sessionId": "short"},
        {**_event(), "fromPage": ""},
        {**_event(), "toPage": "<script>"},
        {**_event(), "answers": {"q": "secret"}},
        {"sessionId": str(uuid.uuid4()), "fromPage": "__welcome__"},
        {**_event(), "toPage": ["string"]},
    ],
)
async def test_a_malformed_event_is_refused(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    body: dict,
):
    sent = await client.post(_url(workspace.id, published_form.form_id), json=body)
    assert sent.status_code == 422, sent.text
    assert await _stored_events(published_form.form_id) == []


async def test_a_client_is_limited_per_form_until_the_window_ends(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
    limit,
):
    url = _url(workspace.id, published_form.form_id)
    alice = {"X-Forwarded-For": "203.0.113.7"}
    for _ in range(limit):
        sent = await client.post(url, json=_event(), headers=alice)
        assert sent.status_code == 200, sent.text

    refused = await client.post(url, json=_event(), headers=alice)
    assert refused.status_code == 429, refused.text
    assert refused.headers["Retry-After"] == "40"
    assert len(await _stored_events(published_form.form_id)) == limit

    # another client is counted on its own
    bob = {"X-Forwarded-For": "198.51.100.23"}
    assert (await client.post(url, json=_event(), headers=bob)).status_code == 200

    # a spoofed hop in front of the proxy's entry changes nothing
    spoofed = {"X-Forwarded-For": "192.0.2.1, 203.0.113.7"}
    assert (await client.post(url, json=_event(), headers=spoofed)).status_code == 429

    # the next window starts afresh
    clock["t"] = T0 + 40
    assert (await client.post(url, json=_event(), headers=alice)).status_code == 200


async def test_refused_events_count_towards_the_limit(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
    limit,
):
    url = _url(workspace.id, published_form.form_id)
    headers = {"X-Forwarded-For": "203.0.113.8"}
    for _ in range(limit):
        bad = await client.post(url, json=_event(to_page="nope"), headers=headers)
        assert bad.status_code == 422
    sent = await client.post(url, json=_event(), headers=headers)
    assert sent.status_code == 429


async def _stored_counter_text() -> str:
    """Everything the counters hold, in whichever stores are written."""
    flags = container.flags()
    parts = (
        [
            repr(doc)
            async for doc in RateLimitCounterDocument.get_pymongo_collection().find({})
        ]
        if flags.writes_mongo("analytics")
        else []
    )
    if flags.requires_postgres():
        from backend.db.models import RateLimitCounterRow

        async with container.pg_sessionmaker()() as session:
            rows = (await session.execute(select(RateLimitCounterRow))).scalars()
            parts.extend(repr((r.id, r.doc)) for r in rows)
    return "\n".join(parts)


async def test_the_client_address_is_not_stored(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
):
    address = "203.0.113.99"
    sent = await client.post(
        _url(workspace.id, published_form.form_id),
        json=_event(),
        headers={"X-Forwarded-For": address},
    )
    assert sent.status_code == 200, sent.text
    stored = await _stored_counter_text()
    assert stored  # a counter was written
    assert address not in stored
    assert "203.0.113" not in stored
    events = await _stored_events(published_form.form_id)
    assert address not in repr([e.model_dump() for e in events])


async def test_respondents_behind_cloudflare_are_counted_apart(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
    limit,
    monkeypatch,
):
    # the test client connects from 127.0.0.1: make it the trusted proxy
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")
    url = _url(workspace.id, published_form.form_id)
    edge = "172.70.1.2"  # one Cloudflare edge for everyone

    def via_cloudflare(address):
        return {"X-Forwarded-For": edge, "CF-Connecting-IP": address}

    alice, bob = via_cloudflare("203.0.113.1"), via_cloudflare("203.0.113.2")
    for _ in range(limit):
        sent = await client.post(url, json=_event(), headers=alice)
        assert sent.status_code == 200, sent.text
    assert (await client.post(url, json=_event(), headers=alice)).status_code == 429
    assert (await client.post(url, json=_event(), headers=bob)).status_code == 200


async def test_forged_headers_from_an_untrusted_peer_do_not_split_the_limit(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
    limit,
    monkeypatch,
):
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "")
    url = _url(workspace.id, published_form.form_id)
    for n in range(limit):
        sent = await client.post(
            url, json=_event(), headers={"X-Forwarded-For": f"198.51.100.{n}"}
        )
        assert sent.status_code == 200, sent.text
    forged = {"X-Forwarded-For": "198.51.100.200", "CF-Connecting-IP": "203.0.113.7"}
    assert (await client.post(url, json=_event(), headers=forged)).status_code == 429


async def test_ipv6_clients_are_limited_per_slash_64(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
    limit,
    monkeypatch,
):
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")
    url = _url(workspace.id, published_form.form_id)

    def from_address(address):
        return {"X-Forwarded-For": address}

    for n in range(limit):  # rotating through one /64
        sent = await client.post(
            url, json=_event(), headers=from_address(f"2001:db8:1:2::{n + 1:x}")
        )
        assert sent.status_code == 200, sent.text
    same_net = from_address("2001:db8:1:2:ffff::9")
    assert (await client.post(url, json=_event(), headers=same_net)).status_code == 429
    other_net = from_address("2001:db8:1:3::1")
    assert (await client.post(url, json=_event(), headers=other_net)).status_code == 200
    # IPv4 stays per address
    one = from_address("198.51.100.1")
    for _ in range(limit):
        assert (await client.post(url, json=_event(), headers=one)).status_code == 200
    assert (await client.post(url, json=_event(), headers=one)).status_code == 429
    two = from_address("198.51.100.2")
    assert (await client.post(url, json=_event(), headers=two)).status_code == 200


async def test_old_flow_events_are_deleted(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    clock,
    monkeypatch,
):
    import datetime as dt

    from backend.app.services import flow_event_service

    repo = container.flow_event_repo()
    form_id = published_form.form_id
    url = _url(workspace.id, form_id)
    days = settings.api_settings.FLOW_EVENTS_RETENTION_DAYS
    assert days == 395  # 13 months by default
    real_now = dt.datetime.now(dt.timezone.utc)

    # nothing recorded just now is older than a day ago
    await repo.add(form_id=form_id, session_id="kept", from_page="a", to_page="b")
    assert await repo.delete_older_than(real_now - dt.timedelta(days=1)) == 0
    assert len(await _stored_events(form_id)) == 1

    # time passes: the write path sweeps once, then not again for 6 hours
    class Later(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return real_now + dt.timedelta(days=days + 5)

    monkeypatch.setattr(flow_event_service, "datetime", Later)
    service = container.flow_event_service()
    service._last_sweep = None
    sent = await client.post(url, json=_event(session_id="fresh-session"))
    assert sent.status_code == 200, sent.text
    # in this fake future every stored event is past the period, and the sweep
    # runs after the new one is stored
    assert await _stored_events(form_id) == []
    await repo.add(form_id=form_id, session_id="again", from_page="a", to_page="b")
    await service._sweep_expired()  # throttled
    assert len(await _stored_events(form_id)) == 1

    # 0 keeps everything
    monkeypatch.setattr(settings.api_settings, "FLOW_EVENTS_RETENTION_DAYS", 0)
    service._last_sweep = None
    await service._sweep_expired()
    assert len(await _stored_events(form_id)) == 1


def test_mongo_flow_events_have_a_ttl_index_on_created_at():
    from backend.app.schemas.flow_event import FlowEventDocument

    ttl = [
        i
        for i in FlowEventDocument.Settings.indexes
        if i.document.get("expireAfterSeconds") is not None
    ]
    assert len(ttl) == 1
    assert dict(ttl[0].document["key"]) == {"created_at": 1}
    assert ttl[0].document["expireAfterSeconds"] == 395 * 86400
