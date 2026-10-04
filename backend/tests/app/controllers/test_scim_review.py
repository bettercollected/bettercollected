"""SCIM directory sync, review follow-ups (docs/sso.md, "Directory sync"):
paging through Polis's capped pages, the resync safety stop, disable reasons
(plan vs directory), seats, the auth outage, one membership per workspace and
user, rotation clean-up and group matching, and the signature header."""

import datetime as dt
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from beanie import PydanticObjectId
from common.models.user import User

from backend.app.container import container
from backend.app.handlers.database import ensure_membership_unique_index
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.scim import ScimUserState
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.scim.polis_dsync import PolisDirectoryClient
from backend.app.services.scim.signature import BadSignature, sign, verify
from backend.app.services.scim.sync_service import AuthUnavailable
from backend.app.services.sso.polis_client import PolisError, PolisUnavailable
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser
from tests.app.scim_helpers import (  # noqa: F401 — fixtures
    create_directory,
    deliver,
    event,
    group_data,
    member_of,
    members_list,
    scim_on,
    signed,
    user_data,
)
from tests.app.sso_helpers import DOMAIN, sso_on  # noqa: F401

JANE = "jane@" + DOMAIN


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


OWNER = _cookies(testUser)


def url(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/scim{suffix}"


@pytest.fixture()
async def directory(client, workspace, scim_on, members_list):
    document, _ = await create_directory(client, workspace, OWNER)
    return document


@pytest.fixture()
def seats(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 500)


def person(n: int) -> str:
    return f"user{n:03d}@{DOMAIN}"


async def _directory(workspace):
    return await container.scim_directory_repo().find_by_workspace(workspace.id)


async def _record(directory, polis_id):
    return await container.scim_user_repo().find(directory.id, polis_id)


# -- paging: Polis caps every page (db.pageLimit, 50 by default) ----------------
class CappedPolis:
    """Polis's dsync listing endpoints, capping each page at ``cap`` like
    normalizeOffsetAndLimit in 26.2.0."""

    def __init__(self, users, groups=(), members=None, cap=50):
        self.users = list(users)
        self.groups = list(groups)
        self.members = members or {}
        self.cap = cap
        self.requests = []
        self.odd = False

    def _page(self, items, query):
        offset = int(query.get("pageOffset", ["0"])[0])
        limit = int(query.get("pageLimit", ["0"])[0] or 0)
        limit = self.cap if limit <= 0 or limit > self.cap else limit
        return items[offset : offset + limit]

    def handler(self, request: httpx.Request) -> httpx.Response:
        query = parse_qs(urlsplit(str(request.url)).query)
        path = request.url.path
        self.requests.append(path)
        if self.odd:
            return httpx.Response(200, json={"data": {"oops": True}})
        if path == "/api/v1/dsync/users":
            return httpx.Response(200, json={"data": self._page(self.users, query)})
        if path == "/api/v1/dsync/groups":
            return httpx.Response(200, json={"data": self._page(self.groups, query)})
        if path.startswith("/api/v1/dsync/groups/") and path.endswith("/members"):
            group_id = path.split("/")[5]
            members = [{"user_id": u} for u in self.members.get(group_id, [])]
            return httpx.Response(200, json={"data": self._page(members, query)})
        return httpx.Response(404, json={"error": {"message": "nope"}})


def real_client(fake: CappedPolis) -> PolisDirectoryClient:
    return PolisDirectoryClient(
        settings.sso, transport=httpx.MockTransport(fake.handler)
    )


async def test_pages_follow_the_servers_cap(sso_on):
    users = [user_data(f"u{n}", person(n)) for n in range(120)]
    fake = CappedPolis(users, members={"g1": [f"u{n}" for n in range(77)]})
    client = real_client(fake)

    listed = await client.list_users("t", "d", page_size=100)
    members = await client.list_group_members("t", "d", "g1", page_size=100)

    assert [u["id"] for u in listed] == [f"u{n}" for n in range(120)]
    assert len(members) == 77
    # 50 + 50 + 20, then an empty page ends it
    assert fake.requests.count("/api/v1/dsync/users") == 4


async def test_an_odd_reply_is_an_error_not_an_empty_directory(sso_on):
    fake = CappedPolis([user_data("u1", JANE)])
    fake.odd = True
    with pytest.raises(PolisError):
        await real_client(fake).list_users("t", "d")


async def test_a_resync_of_120_users_through_capped_pages(
    client, workspace, directory, scim_on, seats, monkeypatch
):
    polis, auth = scim_on
    users = [user_data(f"u{n}", person(n)) for n in range(120)]
    fake = CappedPolis(
        users,
        groups=[group_data("g1", "Staff")],
        members={"g1": [f"u{n}" for n in range(60, 120)]},
    )
    monkeypatch.setattr(container.scim_directory_service(), "_polis", real_client(fake))

    first = await client.post(url(workspace, "/resync"), cookies=OWNER)
    again = await client.post(url(workspace, "/resync"), cookies=OWNER)

    assert first.status_code == 200, first.text
    assert first.json()["summary"]["provisioned"] == 120
    assert again.json()["summary"]["users"] == 120
    assert again.json()["summary"]["deprovisioned"] == 0
    assert again.json()["summary"]["removed"] == 0
    for n in (0, 49, 50, 119):
        member = await member_of(workspace.id, auth.accounts[person(n)]["id"])
        assert member is not None and not member.disabled
    overview = (await client.get(url(workspace), cookies=OWNER)).json()
    assert overview["groups"][0]["members"] == 60


# -- the safety stop -------------------------------------------------------------
async def _provision(client, directory, polis, count):
    for n in range(count):
        await deliver(
            client,
            directory,
            polis,
            event(directory, "user.created", user_data(f"u{n}", person(n))),
        )


async def test_a_resync_that_would_empty_the_workspace_is_refused(
    client, workspace, directory, scim_on, seats
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 10)
    polis.users = [user_data(f"u{n}", person(n)) for n in range(4)]  # 6 missing

    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)

    assert reply.status_code == 409, reply.text
    body = reply.json()
    assert body["code"] == "mass_deprovision_refused"
    assert body["summary"]["wouldDeprovision"] == 6
    for n in range(10):
        member = await member_of(workspace.id, auth.accounts[person(n)]["id"])
        assert not member.disabled
    fresh = await _directory(workspace)
    assert fresh.last_resync_error == "mass_deprovision_refused"

    forced = await client.post(
        url(workspace, "/resync"), json={"force": True}, cookies=OWNER
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["summary"]["removed"] == 6
    assert (await member_of(workspace.id, auth.accounts[person(9)]["id"])).disabled


async def test_no_users_from_polis_is_refused(client, workspace, directory, scim_on):
    polis, auth = scim_on
    await _provision(client, directory, polis, 2)
    polis.users = []
    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)
    assert reply.status_code == 409
    assert not (await member_of(workspace.id, auth.accounts[person(0)]["id"])).disabled


async def test_a_few_departures_are_applied(
    client, workspace, directory, scim_on, seats
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 10)
    polis.users = [user_data(f"u{n}", person(n)) for n in range(8)]  # 2 left
    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)
    assert reply.status_code == 200, reply.text
    assert reply.json()["summary"]["removed"] == 2


async def test_the_nightly_resync_records_a_refusal_and_goes_on(
    client, workspace, directory, scim_on, seats, monkeypatch
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 2)
    polis.users = []
    service = container.scim_directory_service()
    result = await service.resync_all("schedule")
    assert result == {"directories": 0, "failed": 1}
    assert (await _directory(workspace)).last_resync_error == (
        "mass_deprovision_refused"
    )

    # one directory blowing up does not stop the others
    async def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service._sync, "reconcile", boom)
    assert await service.resync_all("schedule") == {"directories": 0, "failed": 1}
    assert (await _directory(workspace)).last_resync_error == "resync_failed"


# -- disable reasons: plan vs directory ------------------------------------------
async def test_a_plan_downgrade_is_not_undone_by_the_directory(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 1)
    jane = auth.accounts[person(0)]["id"]
    workspace.default = True  # the owner's default workspace stays available
    await container.workspace_repo().save(workspace)
    await container.workspace_service().downgrade_user_workspace(testUser.id)
    assert (await member_of(workspace.id, jane)).disabled_reasons == ["plan"]

    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u0", person(0))),
    )
    assert (await member_of(workspace.id, jane)).disabled

    await container.workspace_service().upgrade_user_workspace(testUser.id)
    assert not (await member_of(workspace.id, jane)).disabled


async def test_an_upgrade_does_not_undo_the_directory(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 1)
    jane = auth.accounts[person(0)]["id"]
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u0", person(0), active=False)),
    )
    workspace.default = True
    await container.workspace_repo().save(workspace)
    await container.workspace_service().downgrade_user_workspace(testUser.id)
    member = await member_of(workspace.id, jane)
    assert sorted(member.disabled_reasons) == ["directory", "plan"]

    await container.workspace_service().upgrade_user_workspace(testUser.id)
    member = await member_of(workspace.id, jane)
    assert member.disabled and member.disabled_reasons == ["directory"]
    # the fixture's collaborator, disabled by the plan only, is back
    assert not (await member_of(workspace.id, invited_user.id)).disabled


async def test_legacy_disabled_memberships_count_as_plan(workspace):
    legacy = WorkspaceUserDocument(
        workspace_id=workspace.id, user_id=PydanticObjectId(), disabled=True
    )
    assert legacy.enable_for("directory") is False and legacy.disabled
    assert legacy.enable_for("plan") is True and not legacy.disabled


# -- seats: a disabled membership frees its seat -------------------------------
async def test_a_disabled_membership_frees_its_seat(
    client, workspace, directory, scim_on, monkeypatch
):
    polis, auth = scim_on
    # the owner and the fixture's collaborator fill it
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 1)
    service = container.workspace_user_service()
    assert not await service.has_free_seat(workspace.id)
    collaborator = await member_of(workspace.id, invited_user.id)
    collaborator.disable_for("plan")
    await container.workspace_user_repo().save(collaborator)
    assert await service.has_free_seat(workspace.id)

    await _provision(client, directory, polis, 1)
    jane = auth.accounts[person(0)]["id"]
    assert not (await member_of(workspace.id, jane)).disabled

    # deactivated, the seat is taken by someone else, reactivated: no seat
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u0", person(0), active=False)),
    )
    collaborator.enable_for("plan")
    await container.workspace_user_repo().save(collaborator)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u0", person(0), active=True)),
    )
    assert (await member_of(workspace.id, jane)).disabled
    record = await _record(directory, "u0")
    assert (record.state, record.reason) == (ScimUserState.FAILED, "seat_limit")


# -- the auth service is down ----------------------------------------------------
async def test_an_auth_outage_answers_503_and_decides_nothing(
    client, workspace, directory, scim_on, monkeypatch
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 1)
    jane = auth.accounts[person(0)]["id"]
    before = await _record(directory, "u0")
    sync = container.scim_sync_service()

    async def down(*args, **kwargs):
        raise AuthUnavailable()

    original = sync._account
    monkeypatch.setattr(sync, "_account", down)
    record = before
    record.user_id = None  # so deprovisioning has to ask auth
    await container.scim_user_repo().save(record)
    payload = event(directory, "user.updated", user_data("u0", person(0), active=False))
    body = json.dumps(payload).encode()
    headers = signed(body, polis.secret("dir-1"))
    reply = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )

    assert reply.status_code == 503
    after = await _record(directory, "u0")
    assert after.active is True and after.state == ScimUserState.PROVISIONED
    assert not (await member_of(workspace.id, jane)).disabled

    # Polis retries once auth is back: applied, not a duplicate
    monkeypatch.setattr(sync, "_account", original)
    reply = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )
    assert reply.json() == {"applied": 1, "duplicates": 0}
    assert (await member_of(workspace.id, jane)).disabled


async def test_an_auth_outage_during_a_resync_skips_users(
    client, workspace, directory, scim_on, monkeypatch
):
    polis, auth = scim_on
    polis.users = [user_data("u0", person(0)), user_data("u1", person(1))]
    sync = container.scim_sync_service()

    async def down(*args, **kwargs):
        raise AuthUnavailable()

    monkeypatch.setattr(sync, "_account", down)
    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)
    assert reply.status_code == 503 and reply.json()["code"] == "auth_unavailable"
    fresh = await _directory(workspace)
    assert fresh.last_resync_summary["skipped"] == 2
    record = await _record(directory, "u0")
    assert (record.state, record.reason) == (ScimUserState.IGNORED, "pending")
    assert person(0) not in auth.accounts


# -- one membership per workspace and user ---------------------------------------
async def test_a_second_membership_for_the_same_user_is_not_created(workspace):
    repo = container.workspace_user_repo()
    first = await repo.add_if_absent(
        WorkspaceUserDocument(
            id=PydanticObjectId(),
            workspace_id=workspace.id,
            user_id=PydanticObjectId(invited_user.id),
            roles=[WorkspaceRoles.ADMIN],
        )
    )
    # the fixture's collaborator membership is the one that stays
    assert first.roles == [WorkspaceRoles.COLLABORATOR]
    members = await repo.get_workspace_users(workspace_id=workspace.id)
    assert len([m for m in members if str(m.user_id) == invited_user.id]) == 1
    added = await container.workspace_user_service().add_directory_member(
        workspace.id, invited_user.id, WorkspaceRoles.VIEWER
    )
    assert str(added.id) == str(first.id)


async def test_the_unique_index_and_the_duplicate_report(monkeypatch):
    client = container.database_client()
    app_db = settings.mongo_settings.DB
    name = app_db + "_dups"
    db = client[name]
    try:
        ws, user = PydanticObjectId(), PydanticObjectId()
        await db["workspace_users"].insert_many(
            [
                {"workspace_id": ws, "user_id": user, "roles": ["ADMIN"]},
                {"workspace_id": ws, "user_id": user, "roles": ["VIEWER"]},
            ]
        )
        assert await ensure_membership_unique_index(db) is False  # logged, no crash

        from backend import membership_duplicates

        monkeypatch.setattr(settings.mongo_settings, "DB", name)
        found = membership_duplicates.mongo_duplicates()
        assert [(d["workspace_id"], d["user_id"]) for d in found] == [
            (str(ws), str(user))
        ]
        assert len(found[0]["memberships"]) == 2

        await db["workspace_users"].delete_many({"roles": ["VIEWER"]})
        assert await ensure_membership_unique_index(db) is True
    finally:
        await client.drop_database(name)
    # the application's database got the index at startup
    info = await client[app_db]["workspace_users"].index_information()
    assert info["uq_workspace_users_workspace_user"]["unique"] is True


# -- rotation ----------------------------------------------------------------------
async def test_a_rotation_that_could_not_delete_the_old_directory_says_so(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    polis.fail_delete = PolisUnavailable()
    reply = await client.post(url(workspace, "/directory/rotate"), cookies=OWNER)
    assert reply.status_code == 200
    assert reply.json()["previousDirectoryDeleted"] is False
    overview = (await client.get(url(workspace), cookies=OWNER)).json()
    assert overview["directory"]["previousDirectoryPendingDelete"] is True

    retry = await client.post(url(workspace, "/directory/cleanup"), cookies=OWNER)
    assert retry.status_code == 503
    polis.fail_delete = None
    retry = await client.post(url(workspace, "/directory/cleanup"), cookies=OWNER)
    assert retry.status_code == 200
    assert retry.json()["previousDirectoryPendingDelete"] is False
    assert ("delete", "dir-1") in polis.calls


async def test_groups_sharing_a_name_lose_their_mapping_on_rotation(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    sync = container.scim_sync_service()
    for polis_id, role in (("g1", "ADMIN"), ("g2", "VIEWER"), ("g3", "EDITOR")):
        name = "Staff" if polis_id != "g3" else "Editors"
        group = await sync.apply_group(directory, group_data(polis_id, name))
        group.role = role
        await container.scim_group_repo().save(group)
    await client.post(url(workspace, "/directory/rotate"), cookies=OWNER)
    rotated = await _directory(workspace)

    await deliver(
        client,
        rotated,
        polis,
        event(rotated, "group.created", group_data("n1", "Staff")),
    )
    await deliver(
        client,
        rotated,
        polis,
        event(rotated, "group.created", group_data("n3", "Editors")),
    )
    groups = (await client.get(url(workspace), cookies=OWNER)).json()["groups"]
    by_polis = {
        g.polis_group_id: g
        for g in await container.scim_group_repo().list_by_directory(directory.id)
    }
    assert by_polis["n1"].role is None and by_polis["n1"].needs_review == (
        "duplicate_name"
    )
    assert by_polis["n3"].role == "EDITOR"  # one group of that name: carried over
    assert any(g["needsReview"] == "duplicate_name" for g in groups)

    # the owner maps it again: the flag goes
    reply = await client.put(
        url(workspace, f"/groups/{by_polis['n1'].id}"),
        json={"role": "VIEWER"},
        cookies=OWNER,
    )
    assert reply.json()["needsReview"] is None


async def test_no_removals_during_the_rotation_grace(
    client, workspace, directory, scim_on, seats
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 3)
    await client.post(url(workspace, "/directory/rotate"), cookies=OWNER)
    # the identity provider has re-pushed one user so far
    polis.users = [user_data("new0", person(0))]
    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)
    assert reply.status_code == 200, reply.text
    assert reply.json()["summary"]["removed"] == 0
    for n in range(3):
        assert not (
            await member_of(workspace.id, auth.accounts[person(n)]["id"])
        ).disabled

    # once the grace is over, the ones not re-pushed are gone
    directory = await _directory(workspace)
    directory.rotated_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
    await container.scim_directory_repo().save(directory)
    reply = await client.post(
        url(workspace, "/resync"), json={"force": True}, cookies=OWNER
    )
    assert reply.json()["summary"]["removed"] == 2


async def test_a_deactivated_user_stays_refused_after_rotation(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await _provision(client, directory, polis, 1)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u0", person(0), active=False)),
    )
    sync = container.scim_sync_service()
    assert await sync.is_deprovisioned(workspace.id, person(0))
    await client.post(url(workspace, "/directory/rotate"), cookies=OWNER)
    assert await sync.is_deprovisioned(workspace.id, person(0))


# -- the signature header --------------------------------------------------------
async def test_only_the_boxyhq_header_is_read(client, workspace, directory, scim_on):
    polis, auth = scim_on
    body = json.dumps(event(directory, "user.created", user_data("u1", JANE))).encode()
    header = sign(polis.secret("dir-1"), body, int(time.time() * 1000))
    reply = await client.post(
        f"/api/v1/scim/webhook/{directory.id}",
        content=body,
        headers={"Content-Type": "application/json", "Ory-Polis-Signature": header},
    )
    assert reply.status_code == 401
    # a non-ASCII signature (headers arrive latin-1 decoded) is refused, not a 500
    now = time.time()
    with pytest.raises(BadSignature):
        verify(f"t={int(now * 1000)},s=" + "\u00e9" * 64, body, "s", 300, now=now)


async def test_identical_events_in_one_batch_are_both_applied(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    same = event(directory, "user.created", user_data("u1", JANE))
    reply = await deliver(client, directory, polis, [same, same])
    assert reply.json() == {"applied": 2, "duplicates": 0}
