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
    parts = [
        repr(doc)
        async for doc in RateLimitCounterDocument.get_pymongo_collection().find({})
    ]
    flags = container.flags()
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
):
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
