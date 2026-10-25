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
from beanie import PydanticObjectId
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
BASE = "/api/v1/internal/admin-tasks/case-duplicate-accounts"
T0 = datetime(2023, 1, 1, tzinfo=timezone.utc)


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

    def groups(self):
        by_address = {}
        for user_id in sorted(self.users):
            by_address.setdefault(EMAILS[user_id].lower(), []).append(user_id)
        return [ids for ids in by_address.values() if len(ids) > 1]

    async def get(self, url, *args, **kwargs):
        if url.endswith("/users/case-duplicates"):
            return {"groups": self.groups()}
        if url.endswith("/users"):
            ids = (kwargs.get("params") or {}).get("user_ids") or []
            return {
                "users_info": [
                    {"_id": i, "email": EMAILS[i]} for i in ids if i in self.users
                ]
            }
        raise AssertionError("unexpected auth call")


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", KEY)
    return {KEY_HEADER: KEY}


@pytest.fixture()
def auth(monkeypatch):
    fake = FakeAuth()
    with patch("common.services.http_client.HttpClient.get", side_effect=fake.get):
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
            id=PydanticObjectId(),
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
            id=PydanticObjectId(),
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
    """The workspace as each store the services write holds it (both in the
    dual mode: the deletion must leave neither copy)."""
    from common.db.flags import ReadSource

    repo, flags = container.workspace_repo(), container.flags()
    found = []
    for source, writes in (
        (ReadSource.MONGO, flags.writes_mongo("identity")),
        (ReadSource.POSTGRES, flags.writes_postgres("identity")),
    ):
        if writes:
            found.append(await repo._stores[source].find_by_id(workspace_id))
    assert found
    return found


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
            world[B2].id, PydanticObjectId(A2)
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


async def test_the_runner_reaches_these_routes_without_a_redirect(
    _initialized_app, key, world, deletions, monkeypatch
):
    """The task runner's client against this app's real routes: both calls
    answer 200 (a trailing slash would be a 307 the runner does not follow)."""
    from backend.admin.tasks.impl import case_duplicates as runner

    monkeypatch.setattr(runner, "transport", httpx.ASGITransport(app=_initialized_app))
    async with runner.Backend("http://test/api/v1", KEY) as backend:
        groups = await backend.groups()
        assert _decisions(groups)[A2] == "drop"
        assert await backend.drop(A2) == "queued"
    assert deletions == [A2]
    async with AsyncClient(
        transport=httpx.ASGITransport(app=_initialized_app), base_url="http://test"
    ) as raw:
        assert (await raw.get(BASE + "/", headers=key)).status_code == 307


async def test_a_whitespace_key_counts_as_unset(client: AsyncClient, auth, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", "   ")
    for headers in ({KEY_HEADER: "   "}, {KEY_HEADER: ""}, {}):
        assert (await client.get(BASE, headers=headers)).status_code == 503
        reply = await client.post(f"{BASE}/{A2}/drop", headers=headers)
        assert reply.status_code == 503


async def test_a_deleted_accounts_email_never_reaches_the_marketing_tracker(monkeypatch):
    """The account deletion's event (also sent for a case-duplicate drop)
    goes to the tracker without the email: ``ACCOUNT_DELETED`` is never
    tracked, so the keeper's contact (same address, other case) is untouched.
    Other events are tracked as before."""
    from backend.app.models.dtos.brevo_event_dto import UserEventType
    from backend.app.services.brevo_service import BrevoService

    service = BrevoService()
    tracked = AsyncMock()
    monkeypatch.setattr(service, "track_event", tracked)
    monkeypatch.setattr(settings.event_webhook_settings, "enabled", False)
    await service.send_brevo_event(UserEventType.ACCOUNT_DELETED, A2, EMAILS[A2])
    tracked.assert_not_called()
    await service.send_brevo_event(UserEventType.USER_CREATED, A2, EMAILS[A2])
    tracked.assert_awaited_once()
