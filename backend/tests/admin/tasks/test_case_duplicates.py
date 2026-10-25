"""``auth.resolve_case_duplicate_accounts`` end to end through the real runner,
against a fake of the API's internal admin-task routes (the routes themselves,
the rules and the account deletion in every storage mode are tested in
``tests/app/controllers/test_case_duplicate_accounts.py``).

The fake holds accounts (id, address, forms) and applies the same rules on
every call, as the API does; a drop it accepts is "deleted" after a poll or
two, as a deletion job would be.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from backend.admin.tasks import catalog
from backend.admin.tasks.catalog import case_duplicates as meta
from backend.admin.tasks.impl import case_duplicates as impl
from backend.admin.tasks.registry import check_meta
from tests.admin.conftest import needs_postgres

pytestmark = needs_postgres

TASK = meta.META.name
BASE_PATH = "/api/v1/internal/admin-tasks/case-duplicate-accounts"
KEY = "runner-test-key"
T0 = datetime(2023, 1, 1, tzinfo=timezone.utc)


def _id(days: int) -> str:
    return str(ObjectId.from_datetime(T0 + timedelta(days=days)))


A1, A2, A3 = _id(1), _id(2), _id(3)  # one with forms, two without
B1, B2 = _id(4), _id(5)  # none with forms: B2, created last, stays
C1, C2, C3 = _id(6), _id(7), _id(8)  # two with forms (manual) and one without
EMAILS = {
    A1: "Alex@example.com", A2: "alex@example.com", A3: "ALEX@example.com",
    B1: "Bo@example.com", B2: "bo@example.com",
    C1: "Cy@example.com", C2: "cy@example.com", C3: "CY@example.com",
}
FORMS = {A1: 2, A2: 0, A3: 0, B1: 0, B2: 0, C1: 1, C2: 4, C3: 0}


def _decide(forms):
    with_forms = [i for i, n in forms.items() if n]
    if len(with_forms) >= 2:
        return {i: "manual" if forms[i] else "drop" for i in forms}
    keeper = with_forms[0] if with_forms else max(forms)
    return {i: "keep" if i == keeper else "drop" for i in forms}


class FakeApi:
    def __init__(self, polls_until_deleted: int = 1):
        self.forms = dict(FORMS)
        self.deleting = {}  # id -> polls left
        self.polls_until_deleted = polls_until_deleted
        self.requests = []
        self.keys = []

    def groups(self):
        by = {}
        for i in sorted(self.forms):
            by.setdefault(EMAILS[i].lower(), []).append(i)
        out = []
        for ids in by.values():
            if len(ids) > 1:
                decisions = _decide({i: self.forms[i] for i in ids})
                out.append([
                    {"id": i, "created_at": "x", "forms": self.forms[i], "decision": decisions[i]}
                    for i in ids
                ])
        return out

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))
        self.keys.append(request.headers.get(impl.KEY_HEADER))
        if request.url.path.endswith("/"):
            # as FastAPI answers a route requested with a trailing slash
            return httpx.Response(
                307, headers={"location": str(request.url).rstrip("/")}
            )
        if not request.url.path.startswith(BASE_PATH):
            return httpx.Response(404)
        if request.headers.get(impl.KEY_HEADER) != KEY:
            return httpx.Response(403)
        if request.method == "GET":
            for i in list(self.deleting):
                self.deleting[i] -= 1
                if self.deleting[i] < 0:
                    del self.deleting[i]
                    del self.forms[i]
            return httpx.Response(200, json={"groups": self.groups()})
        account = request.url.path.split("/")[-2]
        if account in self.deleting:
            return httpx.Response(200, json={"status": "already_queued"})
        group = next((g for g in self.groups() if account in [a["id"] for a in g]), None)
        if group is None:
            return httpx.Response(200, json={"status": "not_found"})
        decision = next(a["decision"] for a in group if a["id"] == account)
        if decision != "drop":
            return httpx.Response(200, json={"status": "kept" if decision == "keep" else "manual"})
        self.deleting[account] = self.polls_until_deleted
        return httpx.Response(200, json={"status": "queued"})

    def posts(self):
        return [path.split("/")[-2] for method, path in self.requests if method == "POST"]


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(impl, "transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(impl, "POLL_SECONDS", 0)
    monkeypatch.setenv(impl.KEY_ENV, KEY)
    monkeypatch.setenv(impl.URL_ENV, "http://backend.test/api/v1")
    return fake


async def _run(world, *, dry_run=False):
    world.clock.advance(1)
    run_id = await world.enqueue(TASK, {}, dry_run=dry_run, requested_at=world.clock.now())
    await world.drain()
    return run_id, await world.run(run_id)


async def _both(world):
    dry_id, dry = await _run(world, dry_run=True)
    assert dry["state"] == "succeeded", dry
    return await _run(world)


def _no_emails(*things):
    """No account's email, in any case (the operator's own, as requester, is
    the runner's bookkeeping)."""
    dumped = json.dumps(things, default=str).lower()
    for email in EMAILS.values():
        assert email.lower() not in dumped
        assert email.lower().split("@")[0] + "@" not in dumped
    assert "example.com" not in dumped


# ----------------------------------------------------------------- catalog
def test_the_task_is_in_the_catalog_and_needs_a_dry_run_and_a_confirmation():
    check_meta(meta.META)
    assert meta.META in catalog.all_meta({})
    assert meta.META.mutating and meta.META.requires_prior_dry_run and meta.META.idempotent


# ---------------------------------------------------------------- dry run
async def test_the_dry_run_lists_every_group_and_drops_nothing(world, api):
    run_id, run = await _run(world, dry_run=True)
    assert run["state"] == "succeeded", run
    assert run["result"] == {
        **meta.ResolveResult().model_dump(),
        "groups": 3, "accounts": 8, "keep": 2, "drop": 4, "manual": 2, "manual_groups": 1,
    }
    assert impl.KEY_HEADER and set(api.keys) == {KEY}
    assert api.posts() == []
    events = await world.events(run_id)
    listed = [(e["code"], e["counts"]["group"], e["counts"]["forms"], e["ids"])
              for e in events if e["code"] in ("keep", "drop", "manual")]
    assert listed == [
        ("keep", 1, 2, [A1, "2023-01-02T00:00:00Z"]),
        ("drop", 1, 0, [A2, "2023-01-03T00:00:00Z"]),
        ("drop", 1, 0, [A3, "2023-01-04T00:00:00Z"]),
        ("drop", 2, 0, [B1, "2023-01-05T00:00:00Z"]),
        ("keep", 2, 0, [B2, "2023-01-06T00:00:00Z"]),
        ("manual", 3, 1, [C1, "2023-01-07T00:00:00Z"]),
        ("manual", 3, 4, [C2, "2023-01-08T00:00:00Z"]),
        ("drop", 3, 0, [C3, "2023-01-09T00:00:00Z"]),
    ]
    assert await world.audit_rows(impl.AUDIT_ACTION) == []
    _no_emails(run["result"], events)


async def test_apply_needs_a_prior_dry_run(world, api):
    _, run = await _run(world)
    assert run["state"] == "refused" and run["refusal_code"] == "dry_run_required", run
    assert api.posts() == []


# ------------------------------------------------------------------ apply
async def test_apply_drops_exactly_the_formless_accounts_then_nothing(world, api):
    run_id, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert sorted(api.posts()) == sorted([A2, A3, B1, C3])
    assert set(api.forms) == {A1, B2, C1, C2}
    result = run["result"]
    assert (result["drops_started"], result["changed"], result["refused"], result["pending"]) == (
        4, 0, 0, 0
    )
    # afterwards: the manual group remains, and only it
    assert (result["remaining_groups"], result["remaining_manual_groups"]) == (1, 1)
    events = await world.events(run_id)
    assert [e["ids"] for e in events if e["code"] == "remaining"] == [[C1, C2]]
    assert sorted(e["ids"][0] for e in events if e["code"] == "drop_started") == sorted(
        [A2, A3, B1, C3]
    )
    (row,) = await world.audit_rows(impl.AUDIT_ACTION)
    assert row["request_id"] == str(run_id)
    detail = row["detail"]
    assert (detail["drops_started"], detail["remaining_groups"], detail["drop"]) == (4, 1, 4)
    _no_emails(row, result, events)

    # a second run drops nothing
    before = len(api.posts())
    again_id, again = await _both(world)
    assert again["state"] == "succeeded", again
    assert again["result"]["drop"] == 0 and again["result"]["drops_started"] == 0
    assert len(api.posts()) == before
    assert again["result"]["remaining_groups"] == 1


async def test_a_change_since_the_dry_run_is_honoured(world, api):
    _, dry = await _run(world, dry_run=True)
    assert dry["result"]["drop"] == 4
    # A3 gets forms after the dry run: A1 and A3 now both have forms
    api.forms[A3] = 1
    _, run = await _run(world)
    assert run["state"] == "succeeded", run
    assert A3 not in api.posts() and A3 in api.forms
    assert run["result"]["drops_started"] == 3
    assert run["result"]["manual_groups"] == 2


async def test_drops_the_api_no_longer_makes_are_counted_as_changed(world, api, monkeypatch):
    """The API decides each drop again: one it answers ``kept`` is skipped."""
    real = api.handler

    def racing(request):
        if request.method == "POST" and request.url.path.split("/")[-2] == B1:
            return httpx.Response(200, json={"status": "kept"})
        return real(request)

    monkeypatch.setattr(impl, "transport", httpx.MockTransport(racing))
    run_id, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert run["result"]["changed"] == 1 and B1 in api.forms
    skipped = [e["ids"] for e in await world.events(run_id) if e["code"] == "drop_skipped"]
    assert skipped == [[B1, "kept"]]


async def test_deletions_still_running_are_reported_pending(world, api, monkeypatch):
    api.polls_until_deleted = 10_000
    monkeypatch.setattr(impl, "WAIT_SECONDS", 0)
    _, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert run["result"]["pending"] == 4 and run["result"]["remaining_groups"] == 3


# ------------------------------------------------------------ the paths
async def test_the_routes_are_requested_by_their_exact_path(world, api):
    """No trailing slash: the API answers ``.../case-duplicate-accounts/``
    with a redirect (307), which the runner does not follow."""
    _, run = await _both(world)
    assert run["state"] == "succeeded", run
    paths = {(method, path) for method, path in api.requests}
    assert ("GET", BASE_PATH) in paths
    assert ("POST", f"{BASE_PATH}/{A2}/drop") in paths
    assert {path for _, path in paths} <= {BASE_PATH} | {
        f"{BASE_PATH}/{i}/drop" for i in FORMS
    }


@pytest.mark.parametrize("url", ["http://backend.test/api/v1", "http://backend.test/api/v1/"])
async def test_the_exact_path_whatever_the_configured_url_ends_with(url):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"groups": [], "status": "queued"})

    impl_transport, impl.transport = impl.transport, httpx.MockTransport(handler)
    try:
        async with impl.Backend(url, KEY) as backend:
            await backend.groups()
            await backend.drop(A2)
    finally:
        impl.transport = impl_transport
    assert seen == [("GET", BASE_PATH), ("POST", f"{BASE_PATH}/{A2}/drop")]


# --------------------------------------------------------------- refusals
@pytest.mark.parametrize(
    "env,status,code",
    [
        ({impl.KEY_ENV: ""}, 200, "backend_not_configured"),
        ({impl.URL_ENV: "file:///etc"}, 200, "backend_not_configured"),
        ({}, 403, "backend_key_refused"),
        ({}, 503, "backend_key_missing"),
        ({}, 500, "backend_unreachable"),
    ],
)
async def test_refusals(world, api, monkeypatch, env, status, code):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    if status != 200:
        monkeypatch.setattr(
            impl, "transport", httpx.MockTransport(lambda request: httpx.Response(status))
        )
    _, run = await _run(world, dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == code, run


async def test_an_unreachable_api_refuses(world, api, monkeypatch):
    def down(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(impl, "transport", httpx.MockTransport(down))
    _, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "backend_unreachable", run


async def test_a_malformed_reply_carries_nothing_into_events(world, api, monkeypatch):
    def leaky(request):
        return httpx.Response(
            200, json={"groups": [[{"id": "someone@example.com", "forms": 0, "decision": "drop"},
                                   {"id": A1, "forms": 1, "decision": "keep"}]]}
        )

    monkeypatch.setattr(impl, "transport", httpx.MockTransport(leaky))
    run_id, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "backend_unreachable", run
    _no_emails(await world.events(run_id))
