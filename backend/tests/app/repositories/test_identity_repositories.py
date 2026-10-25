"""The identity group's repositories (workspaces, members, invitations, API
keys, email domains, SSO connections and used states, SCIM directory sync,
sessions, user tags), Postgres only since 4.1.

These steps ran against the 4.0 Mongo repositories too while both stores
existed (the parity tests of the dual run); the results they agreed on are
pinned here. Skipped unless DATABASE_URL points at a *_test database.
"""

import datetime as dt
import os

import pytest
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.invitation_request import InvitationRequest
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.identity import (
    DomainAlreadyClaimed,
    DomainVerifiedElsewhere,
    PostgresScimDirectoryRepository,
    PostgresScimEventRepository,
    PostgresScimGroupMemberRepository,
    PostgresScimGroupRepository,
    PostgresScimUserRepository,
    PostgresSessionRepository,
    PostgresSsoConnectionRepository,
    PostgresSsoUsedStateRepository,
    PostgresUserTagsRepository,
    PostgresWorkspaceAPIKeyRepository,
    PostgresWorkspaceDomainRepository,
    PostgresWorkspaceInvitationRepo,
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
    ScimDirectoryExists,
    ScimEventSeen,
    SsoConnectionExists,
    StateAlreadyUsed,
)
from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimEventDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
    ScimUserState,
)
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
    SsoConnectionType,
)
from backend.app.schemas.sso_used_state import SsoUsedStateDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_domain import DomainStatus, WorkspaceDomainDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import DISABLED_BY_PLAN, WorkspaceUserDocument
from backend.db.models import WorkspaceActionRow
from common.enums.workspace_invitation_status import InvitationStatus
from common.exceptions import NotFoundError
from common.models.standard_form import ParameterValue
from common.models.user import User
from common.records import RecordId, derived_id
from tests.app.repositories.parity import strip


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def same(found, expected) -> bool:
    """The same document (or list of them), timestamps aside."""
    return strip(found) == strip(expected)


def ids(documents) -> list:
    return [d.id for d in documents]


def workspace(name, owner, **extra):
    return WorkspaceDocument(
        id=RecordId(), title=name, workspace_name=name, owner_id=owner, **extra
    )


def workspaces_repo(sessions):
    return PostgresWorkspaceRepository(sessions, PostgresActionRepository(sessions, None))


# -------------------------------------------------------------------- workspaces
async def test_workspaces(sessions):
    owner = str(RecordId())
    default = workspace("acme", owner, default=True)
    other = workspace(
        "beta", owner, custom_domain="beta.example", custom_domain_id="dom-beta"
    )
    hidden = workspace(
        "gamma", owner, custom_domain="gamma.example", custom_domain_disabled=True
    )
    repo = workspaces_repo(sessions)
    for document in (default, other, hidden):
        assert same(await repo.save(document), document)

    assert same(await repo.find_by_id(default.id), default)
    assert await repo.find_by_id(RecordId()) is None
    assert same(await repo.find_by_name("beta"), other)
    assert same(await repo.find_by_custom_domain("beta.example"), other)
    assert same(await repo.find_by_custom_domain_id("dom-beta"), other)
    assert await repo.find_by_custom_domain_id("dom-missing") is None
    assert same(await repo.get_or_404(other.id), other)
    assert same(await repo.get_workspace_by_id(other.id), other)
    assert same(await repo.get_workspace_by_query("acme"), default)
    assert same(await repo.get_workspace_by_query("beta.example"), other)
    assert ids(await repo.get_user_workspaces(owner)) == ids((default, other, hidden))
    assert ids(await repo.get_workspace_by_ids([default.id, hidden.id])) == ids(
        (default, hidden)
    )
    assert same(await repo.get_default_workspace_by_owner_id(owner), default)
    assert await repo.get_default_workspace_by_owner_id("nobody") is None
    assert await repo.set_fields(other, {"custom_domain_verified": True}) is None
    assert other.custom_domain_verified is True  # the instance follows
    assert (await repo.find_by_id(other.id)).custom_domain_verified is True

    # a disabled custom domain is not reachable by domain, and a missing one 404s
    with pytest.raises(HTTPException) as refused:
        await repo.get_workspace_by_query("gamma.example")
    assert refused.value.status_code == 404
    missing = RecordId()
    with pytest.raises(HTTPException) as refused:
        await repo.get_workspace_by_id(missing)
    assert refused.value.status_code == 404
    with pytest.raises(NotFoundError):
        await repo.get_or_404(missing)
    with pytest.raises(HTTPException) as refused:
        await repo.update(missing, default)
    assert refused.value.status_code == 404

    default.title = "ACME"
    assert (await repo.update(default.id, default)).title == "ACME"
    assert (await repo.find_by_id(default.id)).title == "ACME"
    assert await repo.delete_workspaces_with_ids([hidden.id]) == 1
    assert ids(await repo.get_user_workspaces(owner)) == ids((default, other))


async def test_the_owner_is_replaced_only_while_it_is_the_expected_one(sessions):
    repo = workspaces_repo(sessions)
    ws = workspace("eta", "owner-1")
    await repo.save(ws)
    assert await repo.set_owner_if(ws.id, "someone-else", "owner-2") is None
    assert await repo.set_owner_if(RecordId(), "owner-1", "owner-2") is None
    assert (await repo.set_owner_if(ws.id, "owner-1", "owner-2")).owner_id == "owner-2"
    assert (await repo.find_by_id(ws.id)).owner_id == "owner-2"


async def test_workspace_with_action_composes_over_the_actions_repository(sessions):
    """The workspace with its copy of an action, the shape the action runner
    gets (the 4.0 ``$lookup`` into workspace_actions)."""
    owner = str(RecordId())
    ws = workspace("delta", owner)
    actions = PostgresActionRepository(sessions, None)
    action = await actions.create_global_action(
        ActionDto(
            name="sheet",
            action_code="print(1)",
            parameters=[ParameterValue(name="Sheet", value="abc")],
        ),
        User(id=owner, sub="owner@example.com"),
    )
    copy = await actions.create_action_in_workspace_from_action(ws.id, action.id)
    copy.parameters = [ParameterValue(name="Sheet", value="abc")]
    await actions.save_document(copy, row=WorkspaceActionRow)
    repo = PostgresWorkspaceRepository(sessions, actions)
    await repo.save(ws)

    found = await repo.get_workspace_with_action_by_id(ws.id, action.id)
    assert found["parameters"][str(action.id)][0]["value"] == "abc"
    assert found["secrets"][str(action.id)] is None
    assert found["id"] == ws.id and found["_id"] == ws.id
    assert found["workspace_name"] == "delta"
    for workspace_id, action_id in ((ws.id, RecordId()), (RecordId(), action.id)):
        with pytest.raises(HTTPException) as refused:
            await repo.get_workspace_with_action_by_id(workspace_id, action_id)
        assert refused.value.status_code == 404


def _minted_at(moment: dt.datetime) -> RecordId:
    """An id created at ``moment`` (random tail, so ids never collide)."""
    stamp = RecordId.from_datetime(moment).binary[:4]
    return RecordId(stamp + os.urandom(8))


async def test_workspace_counts(sessions):
    """Workspaces are dated by their id (the platform metrics)."""
    now = dt.datetime(2026, 3, 18, 12, 0, tzinfo=dt.timezone.utc)  # a Wednesday
    weeks = [dt.datetime(2026, 3, d, tzinfo=dt.timezone.utc) for d in (2, 9, 16, 23)]
    repo = workspaces_repo(sessions)
    owner = str(RecordId())

    def dated(name, created, **extra):
        return WorkspaceDocument(
            id=_minted_at(created), workspace_name=name, owner_id=owner, **extra
        )

    for document in (
        dated("old", now - dt.timedelta(days=40)),
        dated("week-one", weeks[0]),  # exactly on a boundary
        dated("week-two", now - dt.timedelta(days=5), disabled=True),
        dated("today", now - dt.timedelta(days=0.5), disabled=False),
    ):
        await repo.save(document)
    assert await repo.count_workspaces() == 4
    assert await repo.count_workspaces(now - dt.timedelta(days=30)) == 3
    assert await repo.count_disabled_workspaces() == 1
    # 2–9 March holds the boundary one; 9–16 March the one 5 days back
    # (13 March); 16–23 March the one from this morning.
    assert await repo.count_workspaces_created_per_period(weeks) == [1, 1, 1]
    assert await repo.count_workspaces_created_per_period(weeks[:1]) == []


# ----------------------------------------------------------------------- members
def _member(ws, user, roles):
    return WorkspaceUserDocument(
        id=RecordId(), workspace_id=ws.id, user_id=RecordId(user.id), roles=roles
    )


async def test_workspace_users(sessions):
    owner = User(id=str(RecordId()), sub="owner@example.com")
    member = User(id=str(RecordId()), sub="member@example.com")
    ws = workspace("epsilon", owner.id)
    await workspaces_repo(sessions).save(ws)
    owner_row = _member(ws, owner, [WorkspaceRoles.ADMIN])
    member_row = _member(ws, member, [])
    repo = PostgresWorkspaceUserRepository(sessions)
    await repo.save(owner_row)
    await repo.save(member_row)

    assert ids(await repo.get_workspace_users(ws.id)) == ids((owner_row, member_row))
    assert same(await repo.find_workspace_user(ws.id, member_row.user_id), member_row)
    assert ids(await repo.get_mine_workspaces(member.id)) == [member_row.id]

    await repo.disable_other_users_in_workspace(ws.id, owner_row.user_id)
    stored = await repo.find_workspace_user(ws.id, member_row.user_id)
    assert stored.disabled and stored.disabled_reasons == [DISABLED_BY_PLAN]
    assert not (await repo.find_workspace_user(ws.id, owner_row.user_id)).disabled
    assert await repo.enable_all_user_in_workspace(ws.id) == 1
    stored = await repo.find_workspace_user(ws.id, member_row.user_id)
    assert not stored.disabled and stored.disabled_reasons == []

    assert await repo.delete(ws.id, member_row.user_id) == 1
    assert ids(await repo.get_workspace_users(ws.id)) == [owner_row.id]
    assert await repo.delete_user_form_all_workspaces(owner) == 1
    assert await repo.get_workspace_users(ws.id) == []
    with pytest.raises(HTTPException) as refused:
        await repo.delete(ws.id, member_row.user_id)
    assert refused.value.status_code == 404


async def test_a_disabled_admin_membership_comes_back_on_upgrade(sessions):
    """A plan downgrade disables an ADMIN membership (never the one the
    downgrade is for) and an upgrade enables it again: the authorization
    service grants a disabled membership nothing."""
    owner = User(id=str(RecordId()), sub="owner@example.com")
    admin = User(id=str(RecordId()), sub="admin@example.com")
    ws = workspace("zeta", owner.id)
    owner_row = _member(ws, owner, [WorkspaceRoles.ADMIN])
    admin_row = _member(ws, admin, [WorkspaceRoles.ADMIN])
    repo = PostgresWorkspaceUserRepository(sessions)
    for row in (owner_row, admin_row):
        await repo.save(row)
    await repo.disable_other_users_in_workspace(ws.id, owner_row.user_id)
    assert (await repo.find_workspace_user(ws.id, admin_row.user_id)).disabled
    assert not (await repo.find_workspace_user(ws.id, owner_row.user_id)).disabled
    assert await repo.enable_all_user_in_workspace(ws.id) == 1
    assert not (await repo.find_workspace_user(ws.id, admin_row.user_id)).disabled


async def test_one_membership_per_workspace_and_user(sessions):
    repo = PostgresWorkspaceUserRepository(sessions)
    ws = workspace("theta", "o")
    user = User(id=str(RecordId()), sub="u@example.com")
    first = await repo.add_if_absent(_member(ws, user, [WorkspaceRoles.ADMIN]))
    again = await repo.add_if_absent(_member(ws, user, [WorkspaceRoles.VIEWER]))
    assert again.id == first.id and again.roles == [WorkspaceRoles.ADMIN]
    assert ids(await repo.get_workspace_users(ws.id)) == [first.id]


# ------------------------------------------------------------------- invitations
async def test_invitations(sessions):
    ws_id = RecordId()
    repo = PostgresWorkspaceInvitationRepo(sessions)
    request = InvitationRequest(
        email="new@example.com", role=WorkspaceRoles.COLLABORATOR
    )
    first = await repo.create_workspace_invitation(ws_id, request, invited_by="u1")
    assert first.invitation_status == InvitationStatus.PENDING
    assert first.workspace_id == ws_id and first.invited_by == "u1"
    assert len(first.invitation_token) == 32
    # re-inviting the same address renews the existing invitation
    renewed = await repo.create_workspace_invitation(ws_id, request)
    assert renewed.id == first.id
    assert renewed.invitation_token != first.invitation_token
    assert renewed.invited_by is None

    def invite(email, token, status):
        return WorkspaceUserInvitesDocument(
            id=RecordId(),
            workspace_id=ws_id,
            email=email,
            invitation_token=token,
            expiry=0,
            invitation_status=status,
        )

    seeded = invite("seeded@example.com", "tok-seeded", InvitationStatus.EXPIRED)
    accepted = invite("done@example.com", "tok-done", InvitationStatus.ACCEPTED)
    with set_page(Page), set_params(Params(page=1, size=10)):
        await repo.save(seeded)
        await repo.save(accepted)
        assert same(
            await repo.get_workspace_invitation_by_token(ws_id, "tok-seeded"), seeded
        )
        assert await repo.update_status_to_removed(ws_id, "seeded@example.com") is None
        assert await repo.update_status_to_removed(ws_id, "nobody@example.com") is None
        stored = await repo.get_workspace_invitation_by_token(ws_id, "tok-seeded")
        assert stored.invitation_status == InvitationStatus.REMOVED
        page = await repo.get_workspace_invitations(ws_id)
    # pending and expired only: removed and accepted are left out
    assert page.total == 1
    assert [i.email for i in page.items] == ["new@example.com"]

    for token in ("nope", "tok-done"):  # unknown; not pending
        with pytest.raises(HTTPException):
            await repo.delete_invitation_by_token_if_pending_state(ws_id, token)
    with pytest.raises(HTTPException) as refused:
        await repo.get_workspace_invitation_by_token(ws_id, "nope")
    assert refused.value.status_code == 404
    # a pending token is not found from another workspace, and stays put
    with pytest.raises(HTTPException) as refused:
        await repo.delete_invitation_by_token_if_pending_state(
            RecordId(), renewed.invitation_token
        )
    assert refused.value.status_code == 404
    stored = await repo.get_workspace_invitation_by_token(
        ws_id, renewed.invitation_token
    )
    assert stored.invitation_status == InvitationStatus.PENDING
    await repo.delete_invitation_by_token_if_pending_state(
        ws_id, renewed.invitation_token
    )
    with pytest.raises(HTTPException):
        await repo.get_workspace_invitation_by_token(ws_id, renewed.invitation_token)


# ---------------------------------------------------------------------- API keys
async def test_api_keys(sessions):
    ws_id = RecordId()

    def key(name, key_hash):
        return WorkspaceAPIKeyDocument(
            id=RecordId(),
            workspace_id=ws_id,
            name=name,
            key_hash=key_hash,
            prefix=key_hash[:6],
            scopes=["forms:read"],
            created_by="tester",
        )

    a, b = key("ci", "hash-a"), key("ops", "hash-b")
    repo = PostgresWorkspaceAPIKeyRepository(sessions)
    await repo.save(a)
    await repo.save(b)
    assert ids(await repo.list_by_workspace(ws_id)) == ids((a, b))
    assert await repo.list_by_workspace(RecordId()) == []
    assert same(await repo.get_or_404(a.id), a)
    assert same(await repo.find_by_key_hash("hash-b"), b)
    assert await repo.find_by_key_hash("hash-z") is None
    a.revoked = True
    await repo.save(a)
    assert (await repo.get_or_404(a.id)).revoked is True
    with pytest.raises(NotFoundError):
        await repo.get_or_404(RecordId())


# ------------------------------------------------------------------- the sessions
async def test_sessions(sessions):
    t0 = dt.datetime(2030, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
    later = t0 + dt.timedelta(minutes=5)
    user, other = str(RecordId()), str(RecordId())

    def session(user_id, jti, minutes):
        at = t0 + dt.timedelta(minutes=minutes)
        return SessionDocument(
            id=RecordId(),
            user_id=user_id,
            refresh_jti=jti,
            last_refreshed_at=at,
            expires_at=t0 + dt.timedelta(days=30),
            email_verified=True,
            user_agent="Firefox",
            created_at=at,
            updated_at=at,
        )

    repo = PostgresSessionRepository(sessions)
    a, b, c = session(user, "a1", 0), session(user, "b1", 1), session(other, "c1", 2)
    for document in (a, b, c):
        await repo.save(document)
    assert same(await repo.get(str(a.id)), a)
    assert await repo.get("not-an-id") is None
    assert await repo.get(str(RecordId())) is None
    assert ids(await repo.list_active_by_user(user)) == [b.id, a.id]  # newest first

    # compare-and-set: only the current jti rotates
    rotated = await repo.rotate(str(a.id), "a1", "a2", later, later)
    assert (rotated.refresh_jti, rotated.previous_refresh_jti) == ("a2", "a1")
    assert rotated.rotated_at == later and rotated.expires_at == later
    assert await repo.rotate(str(a.id), "a1", "a3", later, later) is None
    assert await repo.rotate("not-an-id", "a1", "a3", later, later) is None
    assert (await repo.get(str(a.id))).refresh_jti == "a2"

    assert await repo.touch(str(b.id), later) == 1
    assert await repo.touch(str(RecordId()), later) == 0
    assert await repo.revoke(str(b.id), "logout", later) == 1
    assert await repo.revoke(str(b.id), "logout", later) == 0  # already revoked
    assert await repo.rotate(str(b.id), "b1", "b2", later, later) is None  # revoked
    assert await repo.touch(str(b.id), later) == 0
    revoked = await repo.get(str(b.id))
    assert (revoked.revoked_at, revoked.revoke_reason) == (later, "logout")
    assert ids(await repo.list_active_by_user(user)) == [a.id]

    d = session(user, "d1", 3)
    await repo.save(d)
    assert (
        await repo.revoke_all_for_user(user, "logout_everywhere", later, str(a.id)) == 1
    )
    assert ids(await repo.list_active_by_user(user)) == [a.id]
    assert await repo.revoke_all_for_user(user, "account_deleted", later) == 1
    assert await repo.list_active_by_user(user) == []
    assert ids(await repo.list_active_by_user(other)) == [c.id]
    assert (await repo.get(str(a.id))).revoke_reason == "account_deleted"

    # the expiry sweep: every session expires 30 days after t0
    assert await repo.delete_expired(t0) == 0
    assert await repo.delete_expired(t0 + dt.timedelta(days=31)) == 4
    assert await repo.get(str(c.id)) is None
    await repo.save(session(other, "e1", 4))
    assert await repo.delete_all_for_user(other) == 1
    assert await repo.delete_all_for_user(other) == 0
    assert await repo.list_active_by_user(other) == []


# --------------------------------------------------------------------- user tags
async def test_user_tags(sessions):
    user_id = str(RecordId())
    repo = PostgresUserTagsRepository(sessions)
    assert await repo.get_tags_by_id(user_id) is None
    first = await repo.insert_user_tag(user_id, UserTagType.NEW_USER)
    assert first.user_id == RecordId(user_id) and first.tags == [UserTagType.NEW_USER]
    again = await repo.insert_user_tag(user_id, UserTagType.NEW_USER)  # a set
    assert again.id == first.id and again.tags == [UserTagType.NEW_USER]
    await repo.insert_user_tag(user_id, UserTagType.DELETION_REQUEST_RECEIVED)
    stored = await repo.get_tags_by_id(user_id)
    assert stored.tags == [UserTagType.NEW_USER, UserTagType.DELETION_REQUEST_RECEIVED]
    assert ids(await repo.list()) == [first.id]


# ----------------------------------------------------------------- email domains
def _hours_ago(hours: float) -> dt.datetime:
    return _now() - dt.timedelta(hours=hours)


def _claim(ws, domain, **extra):
    return WorkspaceDomainDocument(
        id=RecordId(),
        workspace_id=ws,
        domain=domain,
        verification_token=f"tok-{domain}",
        created_by="u1",
        **extra,
    )


def _verified(ws, domain, checked_hours_ago):
    return _claim(
        ws,
        domain,
        status=DomainStatus.VERIFIED,
        verified_domain=domain,
        verified_at=_hours_ago(100),
        last_checked_at=_hours_ago(checked_hours_ago),
    )


async def test_workspace_domains(sessions):
    ws, other = RecordId(), RecordId()
    acme = _verified(ws, "acme.com", checked_hours_ago=30)
    beta = _verified(ws, "beta.io", checked_hours_ago=48)
    fresh = _verified(other, "fresh.org", checked_hours_ago=1)
    pending = _claim(ws, "zeta.net")
    rival = _claim(other, "acme.com")  # a claim, not verified: allowed
    repo = PostgresWorkspaceDomainRepository(sessions)
    for document in (pending, acme, beta, fresh, rival):
        assert same(await repo.create(document), document)
    assert same(await repo.get(acme.id), acme)
    assert await repo.get(RecordId()) is None
    assert await repo.get("not-an-id") is None
    assert ids(await repo.list_by_workspace(ws)) == ids((acme, beta, pending))  # by name
    assert await repo.list_by_workspace(RecordId()) == []
    assert await repo.count_by_workspace(ws) == 3
    assert same(await repo.find_verified("acme.com"), acme)
    assert await repo.find_verified("zeta.net") is None
    # verified and last checked before the cut-off, the oldest check first
    assert ids(await repo.list_due_for_recheck(_hours_ago(24), 10)) == ids((beta, acme))
    assert ids(await repo.list_due_for_recheck(_hours_ago(24), 1)) == [beta.id]
    assert await repo.delete(beta.id) == 1
    assert ids(await repo.list_by_workspace(ws)) == ids((acme, pending))
    assert await repo.delete_by_workspace_ids([other]) == 2
    assert await repo.find_verified("fresh.org") is None
    assert await repo.count_by_workspace(other) == 0


async def test_a_domain_is_claimed_once_per_workspace_and_verified_once(sessions):
    repo = PostgresWorkspaceDomainRepository(sessions)
    ws, other = RecordId(), RecordId()
    holder = _verified(ws, "acme.com", 1)
    await repo.create(holder)
    # a second claim of the same domain in the same workspace
    with pytest.raises(DomainAlreadyClaimed):
        await repo.create(_claim(ws, "acme.com"))
    # another workspace may hold a claim, but cannot store it as verified
    rival = _claim(other, "acme.com")
    await repo.create(rival)
    rival.status = DomainStatus.VERIFIED
    rival.verified_domain = "acme.com"
    with pytest.raises(DomainVerifiedElsewhere):
        await repo.save(rival)
    assert (await repo.get(rival.id)).verified_domain is None
    assert (await repo.find_verified("acme.com")).workspace_id == ws
    # once the holder lets go, the other workspace's verification goes through
    await repo.delete(holder.id)
    await repo.save(rival)
    assert (await repo.find_verified("acme.com")).workspace_id == other


# --------------------------------------------------------------- SSO connections
def _connection(ws, client_id, enabled_minutes_ago=None):
    enabled = enabled_minutes_ago is not None
    return SsoConnectionDocument(
        id=RecordId(),
        workspace_id=ws,
        type=SsoConnectionType.SAML,
        name=f"IdP {client_id}",
        status=SsoConnectionStatus.ENABLED if enabled else SsoConnectionStatus.DISABLED,
        polis_client_id=client_id,
        polis_tenant=str(ws),
        polis_product="bettercollected",
        created_by="u1",
        enabled_at=_now() - dt.timedelta(minutes=enabled_minutes_ago)
        if enabled
        else None,
    )


async def test_sso_connections(sessions):
    ws, other = RecordId(), RecordId()
    old = _connection(ws, "c-old", enabled_minutes_ago=30)
    new = _connection(ws, "c-new", enabled_minutes_ago=5)
    off = _connection(ws, "c-off")
    elsewhere = _connection(other, "c-else", enabled_minutes_ago=1)
    now = _now()
    repo = PostgresSsoConnectionRepository(sessions)
    for document in (old, new, off, elsewhere):
        assert same(await repo.create(document), document)
    assert same(await repo.get(old.id), old)
    assert same(await repo.find_by_polis_client_id("c-new"), new)
    assert await repo.find_by_polis_client_id("nope") is None
    assert await repo.get(RecordId()) is None
    assert await repo.get("not-an-id") is None
    assert ids(await repo.list_by_workspace(ws)) == ids((old, new, off))
    assert await repo.count_by_workspace(ws) == 3
    assert (await repo.find_enabled(ws)).id == new.id  # the latest enabled
    assert await repo.find_enabled(RecordId()) is None

    assert await repo.disable_others(ws, new.id, "u2", now) == 1
    stored = await repo.get(old.id)
    assert stored.status == SsoConnectionStatus.DISABLED
    assert (stored.disabled_by, stored.disabled_at) == ("u2", now)
    assert (await repo.find_enabled(ws)).id == new.id
    assert (await repo.find_enabled(other)).id == elsewhere.id
    assert await repo.delete(off.id) == 1
    assert await repo.count_by_workspace(ws) == 2

    # a deleted workspace whose connection Polis could not release
    assert await repo.list_release_pending(10) == []
    assert await repo.mark_release_pending([other], now) == 1
    assert await repo.mark_release_pending([other], now) == 0
    [pending] = await repo.list_release_pending(10)
    assert pending.id == elsewhere.id
    assert pending.status == SsoConnectionStatus.RELEASE_PENDING
    assert await repo.touch_release_pending([other], now) == 1
    assert await repo.touch_release_pending([ws], now) == 0
    assert await repo.find_enabled(other) is None
    assert await repo.delete_by_workspace_ids([other]) == 1
    assert await repo.list_release_pending(10) == []
    assert await repo.list_by_workspace(other) == []


async def test_one_record_per_polis_connection(sessions):
    repo = PostgresSsoConnectionRepository(sessions)
    ws = RecordId()
    await repo.create(_connection(ws, "same-client"))
    with pytest.raises(SsoConnectionExists):
        await repo.create(_connection(ws, "same-client"))


async def test_used_states_are_accepted_once(sessions):
    repo = PostgresSsoUsedStateRepository(sessions)
    now = _now()

    def state(nonce, minutes=20):
        return SsoUsedStateDocument(
            id=RecordId(), nonce_hash=nonce, expires_at=now + dt.timedelta(minutes=minutes)
        )

    await repo.claim(state("n1"), now)
    await repo.claim(state("n2"), now)
    with pytest.raises(StateAlreadyUsed):
        await repo.claim(state("n1"), now)
    # an expired record no longer blocks: it is deleted on the next claim
    await repo.claim(state("old", minutes=-1), now)
    await repo.claim(state("old"), now)


# -------------------------------------------------------------------------- SCIM
def _directory(ws, polis_id):
    return ScimDirectoryDocument(
        id=RecordId(),
        workspace_id=ws,
        polis_directory_id=polis_id,
        polis_tenant=str(ws),
        polis_product="bettercollected",
        type="okta-scim-v2",
        name="Okta",
        webhook_secret="ciphertext",
        created_by="u1",
    )


async def test_scim_directories(sessions):
    ws, other = RecordId(), RecordId()
    one, two = _directory(ws, "d-1"), _directory(other, "d-2")
    repo = PostgresScimDirectoryRepository(sessions)
    for document in (one, two):
        assert same(await repo.create(document), document)
    assert same(await repo.get(one.id), one)
    assert await repo.get("not-an-id") is None
    assert await repo.get(RecordId()) is None
    assert same(await repo.find_by_workspace(ws), one)
    assert await repo.find_by_workspace(RecordId()) is None
    assert ids(await repo.list_all()) == sorted(ids((one, two)), key=str)
    assert await repo.update_fields(one.id, {"last_event_type": "user.created"}) == 1
    assert await repo.update_fields(RecordId(), {"last_event_type": "x"}) == 0
    assert (await repo.get(one.id)).last_event_type == "user.created"
    assert await repo.delete(two.id) == 1
    assert ids(await repo.list_all()) == [one.id]


async def test_one_scim_directory_per_workspace(sessions):
    repo = PostgresScimDirectoryRepository(sessions)
    ws = RecordId()
    await repo.create(_directory(ws, "d-a"))
    with pytest.raises(ScimDirectoryExists):
        await repo.create(_directory(ws, "d-b"))


async def test_scim_users_groups_and_members(sessions):
    ws, d = RecordId(), RecordId()
    jane = ScimUserDocument(
        id=derived_id("scim_user", d, "u-1"),
        directory_id=d,
        workspace_id=ws,
        polis_user_id="u-1",
        email="jane@acme.org",
        user_id="a1",
    )
    bob = ScimUserDocument(
        id=derived_id("scim_user", d, "u-2"),
        directory_id=d,
        workspace_id=ws,
        polis_user_id="u-2",
        email="bob@acme.org",
        active=False,
        state=ScimUserState.DEPROVISIONED,
    )
    admins = ScimGroupDocument(
        id=RecordId(),
        directory_id=d,
        workspace_id=ws,
        polis_group_id="g-1",
        name="Admins",
        role="ADMIN",
    )
    link = ScimGroupMemberDocument(
        id=derived_id(admins.id, jane.id),
        directory_id=d,
        group_id=admins.id,
        scim_user_id=jane.id,
    )
    users = PostgresScimUserRepository(sessions)
    await users.save(jane)
    await users.save(bob)
    assert same(await users.get(jane.id), jane)
    assert same(await users.find(d, "u-2"), bob)
    assert await users.find(d, "nope") is None
    assert ids(await users.find_by_email(ws, "jane@acme.org")) == [jane.id]
    assert await users.find_by_email(ws, "nobody@acme.org") == []
    assert set(ids(await users.list_by_directory(d))) == {jane.id, bob.id}
    assert set(ids(await users.list_by_ids([bob.id, jane.id]))) == {jane.id, bob.id}
    assert await users.list_by_ids([]) == []

    groups = PostgresScimGroupRepository(sessions)
    await groups.save(admins)
    assert same(await groups.get(admins.id), admins)
    assert same(await groups.find(d, "g-1"), admins)
    assert await groups.find(d, "g-x") is None
    assert ids(await groups.list_by_directory(d)) == [admins.id]

    members = PostgresScimGroupMemberRepository(sessions)
    await members.add(link)
    await members.add(link)  # the same pair: one row
    assert ids(await members.list_by_user(jane.id)) == [link.id]
    assert ids(await members.list_by_group(admins.id)) == [link.id]
    assert ids(await members.list_by_directory(d)) == [link.id]
    assert await members.remove(admins.id, jane.id) == 1
    assert await members.list_by_group(admins.id) == []
    for remove in (
        lambda: members.delete_by_user(jane.id),
        lambda: members.delete_by_group(admins.id),
        lambda: members.delete_by_directory(d),
    ):
        await members.add(link)
        assert await remove() == 1
    assert await members.list_by_directory(d) == []

    assert await groups.delete(admins.id) == 1
    assert await groups.delete_by_directory(d) == 0
    assert await users.delete_by_directory(d) == 2
    assert await users.list_by_directory(d) == []


async def test_scim_events_are_accepted_once(sessions):
    repo = PostgresScimEventRepository(sessions)
    now = _now()

    def event(key, minutes=60):
        return ScimEventDocument(
            id=RecordId(),
            event_key=key,
            directory_id=RecordId(),
            event_type="user.created",
            expires_at=now + dt.timedelta(minutes=minutes),
        )

    await repo.claim(event("k1"), now)
    with pytest.raises(ScimEventSeen):
        await repo.claim(event("k1"), now)
    # released (processing failed): the retry is accepted
    assert await repo.release("k1") == 1
    await repo.claim(event("k1"), now)
    # an expired record no longer blocks: it is deleted on the next claim
    await repo.claim(event("old", minutes=-1), now)
    await repo.claim(event("old"), now)


# ------------------------------------------- partial updates keep the others' writes
async def test_set_fields_on_stale_copies_keeps_both_changes(sessions):
    """Mongo's ``$set`` changed only the named fields; so does the locked
    read-modify-write: two holders of the same (stale) workspace each set a
    different field, and both values are stored. A whole-document save from
    the stale copy would have switched the first change back."""
    repo = workspaces_repo(sessions)
    ws = workspace("iota", "owner", ai_enabled=False, sso_required=False)
    await repo.save(ws)
    consent = await repo.find_by_id(ws.id)  # e.g. the AI consent request
    sso = await repo.find_by_id(ws.id)  # e.g. the SSO enforcement request

    await repo.set_fields(consent, {"ai_enabled": True, "ai_enabled_by": "admin"})
    await repo.set_fields(sso, {"sso_required": True})

    stored = await repo.find_by_id(ws.id)
    assert stored.ai_enabled is True and stored.ai_enabled_by == "admin"
    assert stored.sso_required is True
    # each caller's copy is refreshed from what was stored
    assert sso.ai_enabled is True and sso.sso_required is True
    assert consent.sso_required is False  # set after its refresh


async def test_concurrent_set_fields_lose_no_write(sessions):
    import asyncio

    repo = workspaces_repo(sessions)
    ws = workspace("kappa", "owner")
    await repo.save(ws)
    copies = [await repo.find_by_id(ws.id) for _ in range(6)]
    fields = [
        {"ai_enabled": True},
        {"sso_required": True},
        {"sso_default_role": "VIEWER"},
        {"custom_domain_verified": True},
        {"ai_provider": "openai"},
        {"title": "Kappa"},
    ]
    await asyncio.gather(*(repo.set_fields(c, f) for c, f in zip(copies, fields)))
    stored = await repo.find_by_id(ws.id)
    for change in fields:
        for name, value in change.items():
            assert getattr(stored, name) == value, name


async def test_set_fields_of_a_workspace_not_stored_stores_nothing(sessions):
    repo = workspaces_repo(sessions)
    ws = workspace("lambda", "owner")
    await repo.set_fields(ws, {"sso_required": True})
    assert ws.sso_required is True
    assert await repo.find_by_id(ws.id) is None


async def test_removing_an_invitation_keeps_a_concurrent_renewal(sessions):
    repo = PostgresWorkspaceInvitationRepo(sessions)
    ws_id = RecordId()
    request = InvitationRequest(email="x@example.com", role=WorkspaceRoles.VIEWER)
    first = await repo.create_workspace_invitation(ws_id, request)
    stale = await repo.get_workspace_invitation_by_token(ws_id, first.invitation_token)
    renewed = await repo.create_workspace_invitation(ws_id, request)
    await repo.update_status_to_removed(ws_id, "x@example.com")
    stored = await repo.get_workspace_invitation_by_token(
        ws_id, renewed.invitation_token
    )
    assert stored.invitation_status == InvitationStatus.REMOVED
    assert stored.invitation_token == renewed.invitation_token != stale.invitation_token


async def test_disable_others_changes_only_the_status_of_enabled_ones(sessions):
    ws = RecordId()
    keep = _connection(ws, "c-keep", enabled_minutes_ago=1)
    other = _connection(ws, "c-other", enabled_minutes_ago=10)
    repo = PostgresSsoConnectionRepository(sessions)
    for document in (keep, other):
        await repo.create(document)
    # what else the other connection holds (a test result) is kept
    tested = await repo.get(other.id)
    tested.last_test_error = "boom"
    await repo.save(tested)
    now = _now()
    assert await repo.disable_others(ws, keep.id, "u2", now) == 1
    assert await repo.disable_others(ws, keep.id, "u2", now) == 0
    stored = await repo.get(other.id)
    assert stored.status == SsoConnectionStatus.DISABLED
    assert stored.last_test_error == "boom"
    assert (await repo.get(keep.id)).status == SsoConnectionStatus.ENABLED
