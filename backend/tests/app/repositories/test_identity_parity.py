"""The Postgres twin of each identity repository behaves like the Mongo original.

Same harness as the refdata parity tests: each step runs on both stores and the
results are compared after stripping the fields that legitimately differ.
Skipped unless DATABASE_URL points at a *_test database.
"""

import datetime as dt

import pytest
from beanie import PydanticObjectId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.invitation_request import InvitationRequest
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.blacklisted_refresh_token_repository import (
    BlacklistedRefreshTokenRepository,
)
from backend.app.repositories.postgres.identity import (
    PostgresBlacklistedRefreshTokenRepository,
    PostgresUserTagsRepository,
    PostgresWorkspaceAPIKeyRepository,
    PostgresWorkspaceInvitationRepo,
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
)
from backend.app.repositories.user_tags_repository import UserTagsRepository
from backend.app.repositories.workspace_api_key_repository import (
    WorkspaceAPIKeyRepository,
)
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.action_document import WorkspaceActionsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.enums.workspace_invitation_status import InvitationStatus
from common.exceptions import NotFoundError
from common.models.user import User
from tests.app.repositories.test_refdata_parity import parity, strip


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def workspace(name, owner, **extra):
    return WorkspaceDocument(
        id=PydanticObjectId(),
        title=name,
        workspace_name=name,
        owner_id=owner,
        **extra,
    )


async def both_raise(exc_type, mongo_call, postgres_call):
    with pytest.raises(exc_type) as m:
        await mongo_call()
    with pytest.raises(exc_type) as p:
        await postgres_call()
    if exc_type is HTTPException:
        assert m.value.status_code == p.value.status_code
    else:
        assert str(m.value) == str(p.value)


async def test_workspaces(sessions):
    owner = str(PydanticObjectId())
    default = workspace("acme", owner, default=True)
    other = workspace("beta", owner, custom_domain="beta.example")
    hidden = workspace(
        "gamma", owner, custom_domain="gamma.example", custom_domain_disabled=True
    )
    mongo = WorkspaceRepository()
    postgres = PostgresWorkspaceRepository(sessions, ActionRepository(crypto=None))
    await parity(
        mongo,
        postgres,
        [
            ("save", lambda: (default,)),
            ("save", lambda: (other,)),
            ("save", lambda: (hidden,)),
            ("find_by_id", lambda: (default.id,)),
            ("find_by_id", lambda: (PydanticObjectId(),)),
            ("find_by_name", lambda: ("beta",)),
            ("find_by_custom_domain", lambda: ("beta.example",)),
            ("get_or_404", lambda: (other.id,)),
            ("get_workspace_by_id", lambda: (other.id,)),
            ("get_workspace_by_query", lambda: ("acme",)),
            ("get_workspace_by_query", lambda: ("beta.example",)),
            ("get_user_workspaces", lambda: (owner,)),
            ("get_workspace_by_ids", lambda: ([default.id, hidden.id],)),
            ("get_default_workspace_by_owner_id", lambda: (owner,)),
            ("get_default_workspace_by_owner_id", lambda: ("nobody",)),
            ("set_fields", lambda: (other, {"custom_domain_verified": True})),
            ("find_by_id", lambda: (other.id,)),
        ],
    )
    # a disabled custom domain is not reachable by domain, and a missing one 404s
    await both_raise(
        HTTPException,
        lambda: mongo.get_workspace_by_query("gamma.example"),
        lambda: postgres.get_workspace_by_query("gamma.example"),
    )
    await both_raise(
        HTTPException,
        lambda: mongo.get_workspace_by_id(PydanticObjectId()),
        lambda: postgres.get_workspace_by_id(PydanticObjectId()),
    )
    missing = PydanticObjectId()
    await both_raise(
        NotFoundError,
        lambda: mongo.get_or_404(missing),
        lambda: postgres.get_or_404(missing),
    )
    await both_raise(
        HTTPException,
        lambda: mongo.update(missing, default),
        lambda: postgres.update(missing, default),
    )
    default.title = "ACME"
    await parity(
        mongo,
        postgres,
        [
            ("update", lambda: (default.id, default)),
            ("delete_workspaces_with_ids", lambda: ([hidden.id],)),
            ("get_user_workspaces", lambda: (owner,)),
        ],
    )


async def test_workspace_with_action_composes_over_the_actions_store(sessions):
    """Mongo joins workspace_actions with $lookup; the twin asks the (routed)
    actions repository — here the Mongo one, as in a staged cutover."""
    owner = str(PydanticObjectId())
    ws = workspace("delta", owner)
    action_id = PydanticObjectId()
    await WorkspaceActionsDocument(
        workspace_id=ws.id,
        action_id=action_id,
        parameters=[{"name": "Sheet", "value": "abc"}],
        secrets=None,
    ).save()
    mongo = WorkspaceRepository()
    postgres = PostgresWorkspaceRepository(sessions, ActionRepository(crypto=None))
    await mongo.save(ws)
    await postgres.save(ws)
    m = await mongo.get_workspace_with_action_by_id(ws.id, action_id)
    p = await postgres.get_workspace_with_action_by_id(ws.id, action_id)
    assert strip(m) == strip(p)
    assert p["parameters"][str(action_id)][0]["value"] == "abc"
    assert p["id"] == ws.id
    await both_raise(
        HTTPException,
        lambda: mongo.get_workspace_with_action_by_id(ws.id, PydanticObjectId()),
        lambda: postgres.get_workspace_with_action_by_id(ws.id, PydanticObjectId()),
    )


async def test_workspace_users(sessions):
    owner = User(id=str(PydanticObjectId()), sub="owner@example.com")
    member = User(id=str(PydanticObjectId()), sub="member@example.com")
    ws = workspace("epsilon", owner.id)
    for repo in (
        WorkspaceRepository(),
        PostgresWorkspaceRepository(sessions, ActionRepository(crypto=None)),
    ):
        await repo.save(ws)

    def wu(user, roles):
        return WorkspaceUserDocument(
            id=PydanticObjectId(),
            workspace_id=ws.id,
            user_id=PydanticObjectId(user.id),
            roles=roles,
        )

    owner_row, member_row = wu(owner, [WorkspaceRoles.ADMIN]), wu(member, [])
    mongo, postgres = WorkspaceUserRepository(), PostgresWorkspaceUserRepository(
        sessions
    )
    await parity(
        mongo,
        postgres,
        [
            ("save", lambda: (owner_row,)),
            ("save", lambda: (member_row,)),
            ("has_user_access_in_workspace", lambda: (ws.id, member)),
            ("has_user_access_in_workspace", lambda: (ws.id, None)),
            ("is_user_admin_in_workspace", lambda: (ws.id, owner)),
            ("is_user_admin_in_workspace", lambda: (ws.id, member)),
            ("get_workspace_users", lambda: (ws.id,)),
            ("find_workspace_user", lambda: (ws.id, member_row.user_id)),
            ("get_mine_workspaces", lambda: (member.id,)),
            ("disable_other_users_in_workspace", lambda: (ws.id, owner_row.user_id)),
            ("has_user_access_in_workspace", lambda: (ws.id, member)),
            ("get_workspace_users", lambda: (ws.id,)),
            ("enable_all_user_in_workspace", lambda: (ws.id,)),
            ("has_user_access_in_workspace", lambda: (ws.id, member)),
            ("delete", lambda: (ws.id, member_row.user_id)),
            ("get_workspace_users", lambda: (ws.id,)),
            ("delete_user_form_all_workspaces", lambda: (owner,)),
            ("get_workspace_users", lambda: (ws.id,)),
        ],
    )
    await both_raise(
        HTTPException,
        lambda: mongo.delete(ws.id, member_row.user_id),
        lambda: postgres.delete(ws.id, member_row.user_id),
    )
    gone = PydanticObjectId()
    await both_raise(
        NotFoundError,
        lambda: mongo.is_user_admin_in_workspace(gone, owner),
        lambda: postgres.is_user_admin_in_workspace(gone, owner),
    )


async def test_invitations(sessions):
    ws_id = PydanticObjectId()
    mongo, postgres = WorkspaceInvitationRepo(), PostgresWorkspaceInvitationRepo(
        sessions
    )
    request = InvitationRequest(
        email="new@example.com", role=WorkspaceRoles.COLLABORATOR
    )

    # tokens are minted inside the call, so results are compared shape-wise
    m = await mongo.create_workspace_invitation(ws_id, request)
    p = await postgres.create_workspace_invitation(ws_id, request)
    assert strip(m) | {"invitation_token": 0, "expiry": 0} == strip(p) | {
        "invitation_token": 0,
        "expiry": 0,
    }
    # re-inviting the same address renews the existing invitation
    m2 = await mongo.create_workspace_invitation(ws_id, request)
    p2 = await postgres.create_workspace_invitation(ws_id, request)
    assert m2.id == m.id and p2.id == p.id

    seeded = WorkspaceUserInvitesDocument(
        id=PydanticObjectId(),
        workspace_id=ws_id,
        email="seeded@example.com",
        invitation_token="tok-seeded",
        expiry=0,
        invitation_status=InvitationStatus.EXPIRED,
    )
    accepted = WorkspaceUserInvitesDocument(
        id=PydanticObjectId(),
        workspace_id=ws_id,
        email="done@example.com",
        invitation_token="tok-done",
        expiry=0,
        invitation_status=InvitationStatus.ACCEPTED,
    )
    with set_page(Page), set_params(Params(page=1, size=10)):
        await parity(
            mongo,
            postgres,
            [
                ("save", lambda: (seeded,)),
                ("save", lambda: (accepted,)),
                ("get_workspace_invitation_by_token", lambda: (ws_id, "tok-seeded")),
                ("update_status_to_removed", lambda: (ws_id, "seeded@example.com")),
                ("update_status_to_removed", lambda: (ws_id, "nobody@example.com")),
                ("get_workspace_invitation_by_token", lambda: (ws_id, "tok-seeded")),
            ],
        )
        m_page = await mongo.get_workspace_invitations(ws_id)
        p_page = await postgres.get_workspace_invitations(ws_id)
    assert (
        m_page.total == p_page.total == 1
    )  # pending only; removed and accepted excluded
    assert [i["email"] for i in strip(m_page.items)] == [
        i["email"] for i in strip(p_page.items)
    ]
    await both_raise(
        HTTPException,
        lambda: mongo.get_workspace_invitation_by_token(ws_id, "nope"),
        lambda: postgres.get_workspace_invitation_by_token(ws_id, "nope"),
    )
    await both_raise(
        HTTPException,
        lambda: mongo.delete_invitation_by_token_if_pending_state("tok-done"),
        lambda: postgres.delete_invitation_by_token_if_pending_state("tok-done"),
    )
    await both_raise(
        HTTPException,
        lambda: mongo.delete_invitation_by_token_if_pending_state("nope"),
        lambda: postgres.delete_invitation_by_token_if_pending_state("nope"),
    )
    await mongo.delete_invitation_by_token_if_pending_state(m2.invitation_token)
    await postgres.delete_invitation_by_token_if_pending_state(p2.invitation_token)
    await both_raise(
        HTTPException,
        lambda: mongo.get_workspace_invitation_by_token(ws_id, m2.invitation_token),
        lambda: postgres.get_workspace_invitation_by_token(ws_id, p2.invitation_token),
    )


async def test_api_keys(sessions):
    ws_id = PydanticObjectId()

    def key(name, h):
        return WorkspaceAPIKeyDocument(
            id=PydanticObjectId(),
            workspace_id=ws_id,
            name=name,
            key_hash=h,
            prefix=h[:6],
            scopes=["forms:read"],
            created_by="tester",
        )

    a, b = key("ci", "hash-a"), key("ops", "hash-b")
    mongo, postgres = WorkspaceAPIKeyRepository(), PostgresWorkspaceAPIKeyRepository(
        sessions
    )
    await parity(
        mongo,
        postgres,
        [
            ("save", lambda: (a,)),
            ("save", lambda: (b,)),
            ("list_by_workspace", lambda: (ws_id,)),
            ("list_by_workspace", lambda: (PydanticObjectId(),)),
            ("get_or_404", lambda: (a.id,)),
            ("find_by_key_hash", lambda: ("hash-b",)),
            ("find_by_key_hash", lambda: ("hash-z",)),
        ],
    )
    a.revoked = True
    await parity(
        mongo, postgres, [("save", lambda: (a,)), ("get_or_404", lambda: (a.id,))]
    )
    missing = PydanticObjectId()
    await both_raise(
        NotFoundError,
        lambda: mongo.get_or_404(missing),
        lambda: postgres.get_or_404(missing),
    )


async def test_blacklisted_tokens(sessions):
    expiry = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
    await parity(
        BlacklistedRefreshTokenRepository(),
        PostgresBlacklistedRefreshTokenRepository(sessions),
        [
            ("find_by_token", lambda: ("t1",)),
            ("add", lambda: ("t1", expiry)),
            ("find_by_token", lambda: ("t1",)),
            ("find_by_token", lambda: ("t2",)),
        ],
    )


async def test_user_tags(sessions):
    user_id = str(PydanticObjectId())
    await parity(
        UserTagsRepository(),
        PostgresUserTagsRepository(sessions),
        [
            ("get_tags_by_id", lambda: (user_id,)),
            ("insert_user_tag", lambda: (user_id, UserTagType.NEW_USER)),
            ("insert_user_tag", lambda: (user_id, UserTagType.NEW_USER)),  # $addToSet
            (
                "insert_user_tag",
                lambda: (user_id, UserTagType.DELETION_REQUEST_RECEIVED),
            ),
            ("get_tags_by_id", lambda: (user_id,)),
            ("list", lambda: ()),
        ],
    )
