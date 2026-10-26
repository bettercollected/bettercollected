"""Accounts whose emails differ only in case: the internal routes the admin
task ``auth.resolve_case_duplicate_accounts`` calls
(services/case_duplicate_accounts.py, controllers/admin_tasks_router.py).

Runs in every storage mode of the suite. The auth service is faked at its
HTTP edge (groups by id, user lookup, account deletion); everything else is
the product's own account deletion, run in process: the drop starts the
deletion workflow, whose job body (``AuthService.delete_user``) runs here.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from common.ids import RecordId
from bson import ObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
import httpx
from httpx import AsyncClient

from backend.app.container import container
from backend.app.controllers.admin_tasks_router import KEY_HEADER
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import case_duplicate_accounts as rules
from backend.app.services import workspace_service
from backend.config import settings
from tests.app.controllers.data import formData

KEY = "admin-tasks-test-key"
INTERNAL_KEY = "auth-internal-test-key"
INTERNAL_KEY_HEADER = "X-Internal-Key"
BASE = "/api/v1/internal/admin-tasks/case-duplicate-accounts"
T0 = datetime(2023, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def client(internal_client):
    # the admin-task routes answer on the internal listener only
    return internal_client


def _id(days: int) -> str:
    return str(ObjectId.from_datetime(T0 + timedelta(days=days)))


# Group A: one account with forms, two without (a group of 3)
A1, A2, A3 = _id(1), _id(2), _id(3)
# Group B: none with forms -> the one created last stays
B1, B2 = _id(4), _id(5)
# Group C: two with forms (one owns, one imported) and one without
C1, C2, C3 = _id(6), _id(7), _id(8)
# not a case variant of anyone
SOLO = _id(9)

EMAILS = {
    A1: "Alex@example.com",
    A2: "alex@example.com",
    A3: "ALEX@example.com",
    B1: "Bo@example.com",
    B2: "bo@example.com",
    C1: "Cy@example.com",
    C2: "cy@example.com",
    C3: "CY@example.com",
    SOLO: "solo@example.com",
}


def _user(user_id: str) -> User:
    return User(id=user_id, sub=EMAILS[user_id])


class FakeAuth:
    """The auth service's side: which accounts exist, grouped by address."""

    def __init__(self):
        self.users = set(EMAILS)
        # set by a test: how calls to auth fail (a response or an error), and
        # which call ("/users" or "/users/case-duplicates"; None: every one)
        self.failure = None
        self.failing_path = None

    def groups(self):
        by_address = {}
        for user_id in sorted(self.users):
            by_address.setdefault(EMAILS[user_id].lower(), []).append(user_id)
        return [ids for ids in by_address.values() if len(ids) > 1]

    async def request(self, method, url, *args, **kwargs):
        assert method == "GET", "unexpected auth call"
        # every call carries the internal key and its own timeout
        assert (kwargs.get("headers") or {}).get(INTERNAL_KEY_HEADER) == INTERNAL_KEY
        assert kwargs.get("timeout"), "an auth call without a timeout"
        request = httpx.Request(method, url)
        failing = self.failing_path is None or url.endswith(self.failing_path)
        if failing and isinstance(self.failure, type):
            if issubclass(self.failure, httpx.RequestError):
                raise self.failure("auth down", request=request)
            raise self.failure("auth down")  # InvalidURL takes no request
        if failing and self.failure is not None:
            return self.failure
        if url.endswith("/users/case-duplicates"):
            return httpx.Response(200, json={"groups": self.groups()}, request=request)
        if url.endswith("/users"):
            ids = (kwargs.get("params") or {}).get("user_ids") or []
            return httpx.Response(
                200,
                json={
                    "users_info": [
                        {"_id": i, "email": EMAILS[i]} for i in ids if i in self.users
                    ]
                },
                request=request,
            )
        raise AssertionError("unexpected auth call")


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", KEY)
    return {KEY_HEADER: KEY}


@pytest.fixture()
def auth(monkeypatch):
    monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", INTERNAL_KEY)
    fake = FakeAuth()
    with patch("common.services.http_client.HttpClient.request", side_effect=fake.request):
        yield fake


@pytest.fixture()
def deletions(monkeypatch, auth):
    """The deletion workflow, started as the product starts it, runs its job
    body (``AuthService.delete_user``) at once. Its calls out of the backend
    (the integrations, the auth account, S3) are faked."""
    service = container.auth_service()
    started = []

    async def start(deletion):
        started.append(deletion.user_id)
        await service.delete_user(User(id=deletion.user_id, sub=deletion.email))
        return "Job Started"

    async def delete_from_auth(user):
        auth.users.discard(user.id)

    monkeypatch.setattr(service.temporal_service, "start_user_deletion_workflow", start)
    monkeypatch.setattr(service, "delete_credentials_from_integrations", AsyncMock())
    monkeypatch.setattr(service, "delete_user_form_auth", delete_from_auth)
    monkeypatch.setattr(
        "backend.app.services.auth_service.event_logger_service",
        SimpleNamespace(send_event=AsyncMock()),
    )
    monkeypatch.setattr(
        container.aws_service(), "delete_folder_from_s3", lambda *a, **k: None
    )
    return started


async def _workspace_of(user_id: str):
    await workspace_service.create_workspace(_user(user_id))
    return await container.workspace_repo().get_default_workspace_by_owner_id(user_id)


async def _form(workspace, user_id: str):
    await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**formData), _user(user_id)
    )


async def _session(user_id: str):
    now = datetime.now(timezone.utc)
    await container.session_repo().save(
        SessionDocument(
            id=RecordId(),
            user_id=user_id,
            refresh_jti="jti-" + user_id[-6:],
            last_refreshed_at=now,
            expires_at=now + timedelta(days=30),
            email_verified=True,
            user_agent="test",
            created_at=now,
            updated_at=now,
        )
    )


@pytest.fixture()
async def world(auth):
    """Every account has a default workspace and a session; A1 and C1 have a
    form in their own workspace, C2 imported a form into SOLO's workspace; A2
    is a member of B2's workspace."""
    workspaces = {i: await _workspace_of(i) for i in EMAILS}
    await _form(workspaces[A1], A1)
    await _form(workspaces[C1], C1)
    await container.workspace_form_repo().save(
        WorkspaceFormDocument(
            id=RecordId(),
            workspace_id=workspaces[SOLO].id,
            form_id="imported-by-c2",
            user_id=C2,
        )
    )
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspaces[B2].id,
            user_id=A2,
            roles=[WorkspaceRoles.COLLABORATOR],
        )
    )
    for user_id in EMAILS:
        await _session(user_id)
    return workspaces


async def _plan(client, key):
    reply = await client.get(BASE, headers=key)
    assert reply.status_code == 200, reply.text
    return reply.json()["groups"]


async def _workspace_in_each_store(workspace_id) -> list:
    """The workspace as the store holds it: identity is served from Postgres
    alone since 4.1 (``POSTGRES_ONLY_GROUPS``), so there is one copy."""
    return [await container.workspace_repo().find_by_id(workspace_id)]


def _decisions(groups):
    return {a["id"]: a["decision"] for group in groups for a in group}


# ------------------------------------------------------------------- rules
def test_the_rules():
    old, new = _id(1), _id(2)
    assert rules.decide({old: 2, new: 0}) == {old: "keep", new: "drop"}
    assert rules.decide({old: 0, new: 0}) == {old: "drop", new: "keep"}
    assert rules.decide({old: 1, new: 3, _id(3): 0}) == {
        old: "manual",
        new: "manual",
        _id(3): "drop",
    }
    # created at the same second: the larger id stays
    a, b = str(ObjectId(old[:8] + "0" * 15 + "1")), str(ObjectId(old[:8] + "0" * 15 + "2"))
    assert rules.decide({a: 0, b: 0}) == {a: "drop", b: "keep"}
    assert rules.created_at(old) == T0 + timedelta(days=1)


# -------------------------------------------------------------- the key
async def test_the_routes_need_the_admin_task_key(client: AsyncClient, auth, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", "")
    assert (await client.get(BASE, headers={KEY_HEADER: ""})).status_code == 503
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", KEY)
    for headers in ({}, {KEY_HEADER: "wrong"}, {"api-key": KEY}):
        assert (await client.get(BASE, headers=headers)).status_code == 403
        reply = await client.post(f"{BASE}/{A2}/drop", headers=headers)
        assert reply.status_code == 403
    reply = await client.post(f"{BASE}/not-an-id/drop", headers={KEY_HEADER: KEY})
    assert reply.status_code == 400


# ------------------------------------------------------------ the plan
async def test_the_plan_names_ids_forms_and_decisions_never_emails(
    client: AsyncClient, key, world
):
    groups = await _plan(client, key)
    assert [[a["id"] for a in g] for g in groups] == [[A1, A2, A3], [B1, B2], [C1, C2, C3]]
    assert _decisions(groups) == {
        A1: "keep", A2: "drop", A3: "drop",
        B1: "drop", B2: "keep",
        C1: "manual", C2: "manual", C3: "drop",
    }
    forms = {a["id"]: a["forms"] for g in groups for a in g}
    # C2's form is one it imported into SOLO's workspace
    assert forms == {A1: 1, A2: 0, A3: 0, B1: 0, B2: 0, C1: 1, C2: 1, C3: 0}
    created = {a["id"]: a["created_at"] for g in groups for a in g}
    assert created[B2] == (T0 + timedelta(days=5)).isoformat()
    assert "@" not in str(groups)


# ------------------------------------------------------------- dropping
async def test_drops_go_through_the_account_deletion_and_take_everything(
    client: AsyncClient, key, world, deletions
):
    drops = [i for i, d in _decisions(await _plan(client, key)).items() if d == "drop"]
    for user_id in drops:
        reply = await client.post(f"{BASE}/{user_id}/drop", headers=key)
        assert reply.json() == {"status": "queued"}, user_id
    assert sorted(deletions) == sorted([A2, A3, B1, C3])

    for user_id in drops:
        assert await _workspace_in_each_store(world[user_id].id) == [None] * len(
            await _workspace_in_each_store(world[A1].id)
        )
        assert await container.session_repo().list_active_by_user(user_id) == []
    # A2's membership in B2's workspace went with it
    assert (
        await container.workspace_user_repo().find_workspace_user(
            world[B2].id, RecordId(A2)
        )
        is None
    )
    for user_id in (A1, B2, C1, C2, SOLO):
        assert await container.workspace_repo().find_by_id(world[user_id].id) is not None
        assert await container.session_repo().list_active_by_user(user_id) != []

    # what is left: the manual group only; nothing more to drop
    groups = await _plan(client, key)
    assert _decisions(groups) == {C1: "manual", C2: "manual"}
    for user_id in drops:
        reply = await client.post(f"{BASE}/{user_id}/drop", headers=key)
        assert reply.json() == {"status": "not_found"}
    assert len(deletions) == 4


async def test_a_drop_re_evaluates_and_never_takes_a_kept_or_manual_account(
    client: AsyncClient, key, world, deletions
):
    for user_id, status in ((A1, "kept"), (B2, "kept"), (C1, "manual"), (C2, "manual"),
                            (SOLO, "not_found")):
        reply = await client.post(f"{BASE}/{user_id}/drop", headers=key)
        assert reply.json() == {"status": status}, user_id
    # A3 gets a form after the dry run: A1 and A3 now both have forms
    await _form(world[A3], A3)
    reply = await client.post(f"{BASE}/{A3}/drop", headers=key)
    assert reply.json() == {"status": "manual"}
    assert deletions == []


async def test_a_deletion_already_running_is_not_started_twice(
    client: AsyncClient, key, world, deletions, monkeypatch
):
    service = container.auth_service()
    monkeypatch.setattr(
        service.temporal_service, "start_user_deletion_workflow", AsyncMock(return_value=None)
    )
    reply = await client.post(f"{BASE}/{A2}/drop", headers=key)
    assert reply.json() == {"status": "already_queued"}


async def test_the_product_refusal_is_reported_not_overridden(
    client: AsyncClient, key, world, deletions
):
    """B1 is the billing owner of its workspace and B2 a second owner of it:
    the account deletion refuses (409), so the drop reports ``refused``."""
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=world[B1].id, user_id=B2, roles=[WorkspaceRoles.OWNER]
        )
    )
    reply = await client.post(f"{BASE}/{B1}/drop", headers=key)
    assert reply.json() == {"status": "refused"}
    assert deletions == []
    assert await container.workspace_repo().find_by_id(world[B1].id) is not None


async def test_a_former_duplicate_whose_keeper_is_gone_is_left_alone(
    client: AsyncClient, key, world, deletions, auth
):
    """B2 (the keeper) is deleted out of band after the dry run: B1 is no
    longer a case variant of anyone, so it is not dropped."""
    auth.users.discard(B2)
    reply = await client.post(f"{BASE}/{B1}/drop", headers=key)
    assert reply.json() == {"status": "not_found"}
    assert deletions == []
    assert await container.workspace_repo().find_by_id(world[B1].id) is not None


@pytest.mark.parametrize(
    "failure,code,status",
    [
        (httpx.ConnectError, "auth_unreachable", None),
        (httpx.ReadTimeout, "auth_unreachable", None),
        (httpx.Response(403, json={"detail": "nope"}), "auth_refused", 403),
        (httpx.Response(401), "auth_refused", 401),
        (httpx.Response(503, text="no key"), "auth_error", 503),
        (httpx.Response(500, text="boom"), "auth_error", 500),
        (httpx.Response(404, json={"detail": "x"}), "auth_error", 404),
        (httpx.Response(200, text="<html>"), "auth_error", 200),
        (httpx.Response(200, json=["x"]), "auth_error", 200),
    ],
)
async def test_an_auth_failure_is_a_502_with_its_code_not_auths_status(
    client: AsyncClient, key, world, deletions, auth, failure, code, status
):
    """A failing call to auth is reported as such (502 + a stable code and
    auth's status), never passed through as the API's own 503/403, and never
    with auth's body."""
    auth.failure = failure
    reply = await client.get(BASE, headers=key)
    assert reply.status_code == 502
    assert reply.json() == {"code": code, "status": status}
    reply = await client.post(f"{BASE}/{A2}/drop", headers=key)
    assert reply.status_code == 502
    assert reply.json() == {"code": code, "status": status}
    assert deletions == []


async def test_the_runner_reaches_these_routes_without_a_redirect(
    _initialized_app, key, world, deletions, monkeypatch
):
    """The task runner's client against this app's real routes: both calls
    answer 200 (a trailing slash would be a 307 the runner does not follow)."""
    from backend.admin.tasks.impl import case_duplicates as runner
    from backend.app.services.internal_routes import internal_port

    # the internal listener, as the runner reaches it inside the stack
    listener = httpx.ASGITransport(app=_initialized_app, client=("172.18.0.5", 40000))
    url = f"http://backend:{internal_port()}"
    monkeypatch.setattr(runner, "transport", listener)
    async with runner.Backend(url + "/api/v1", KEY) as backend:
        groups = await backend.groups()
        assert _decisions(groups)[A2] == "drop"
        assert await backend.drop(A2) == "queued"
    assert deletions == [A2]
    async with AsyncClient(transport=listener, base_url=url) as raw:
        assert (await raw.get(BASE + "/", headers=key)).status_code == 307


@pytest.mark.parametrize(
    "failure,code,status",
    [
        (httpx.ConnectError, "auth_unreachable", None),
        (httpx.InvalidURL, "auth_misconfigured", None),
        (httpx.Response(403), "auth_refused", 403),
        (httpx.Response(500, text="boom"), "auth_error", 500),
    ],
)
async def test_the_drops_second_auth_call_failing_is_reported_too(
    client: AsyncClient, key, world, deletions, auth, failure, code, status
):
    """The groups come through; the account lookup (``/users``) fails."""
    auth.failure, auth.failing_path = failure, "/users"
    assert (await client.get(BASE, headers=key)).status_code == 200
    reply = await client.post(f"{BASE}/{A2}/drop", headers=key)
    assert reply.status_code == 502
    assert reply.json() == {"code": code, "status": status}
    assert deletions == []


async def test_an_invalid_auth_url_is_misconfigured_not_a_crash(
    client: AsyncClient, key, world, auth
):
    auth.failure = httpx.InvalidURL
    reply = await client.get(BASE, headers=key)
    assert reply.status_code == 502
    assert reply.json() == {"code": "auth_misconfigured", "status": None}


async def test_a_deletion_that_cannot_start_is_deletion_unavailable_not_a_503(
    client: AsyncClient, key, world, deletions, monkeypatch
):
    """Temporal unreachable: the product's deletion raises 503 ("Cannot
    connect to temporal server"). The route answers 502
    ``deletion_unavailable``: 503 is only ever the API's own missing key."""
    temporal = container.auth_service().temporal_service
    from backend.app.services.temporal_service import TemporalService

    monkeypatch.setattr(
        temporal,
        "start_user_deletion_workflow",
        TemporalService.start_user_deletion_workflow.__get__(temporal),
    )
    monkeypatch.setattr(temporal, "_on_postgres", lambda *a, **k: False)
    monkeypatch.setattr(temporal, "temporal_client", None)
    monkeypatch.setattr(temporal, "connect_to_temporal_server", AsyncMock())
    reply = await client.post(f"{BASE}/{A2}/drop", headers=key)
    assert reply.status_code == 502
    assert reply.json() == {"code": "deletion_unavailable", "status": 503}
    # no deletion started: the account is still there and still a drop
    assert _decisions(await _plan(client, key))[A2] == "drop"

    # any other failure to start it (the jobs queue, say): no status
    monkeypatch.setattr(
        temporal,
        "start_user_deletion_workflow",
        AsyncMock(side_effect=RuntimeError("queue down")),
    )
    reply = await client.post(f"{BASE}/{A2}/drop", headers=key)
    assert reply.status_code == 502
    assert reply.json() == {"code": "deletion_unavailable", "status": None}


async def test_a_503_inside_a_route_is_never_the_keys_503(
    client: AsyncClient, key, world, monkeypatch
):
    from backend.app.exceptions import HTTPException

    async def unavailable(*args, **kwargs):
        raise HTTPException(503, "a dependency")

    monkeypatch.setattr(
        container.case_duplicate_accounts(), "forms_of", unavailable
    )
    reply = await client.get(BASE, headers=key)
    assert reply.status_code == 500
    assert reply.json() == {"code": "backend_error", "status": 503}


async def test_a_whitespace_key_counts_as_unset(client: AsyncClient, auth, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", "   ")
    for headers in ({KEY_HEADER: "   "}, {KEY_HEADER: ""}, {}):
        assert (await client.get(BASE, headers=headers)).status_code == 503
        reply = await client.post(f"{BASE}/{A2}/drop", headers=headers)
        assert reply.status_code == 503
