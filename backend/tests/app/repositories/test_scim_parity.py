"""The Postgres twins of the SCIM repositories behave like the Mongo
originals. Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt

import pytest
from beanie import PydanticObjectId
from common.db.beanie_bridge import derived_object_id

from backend.app.container import container
from backend.app.repositories.postgres.identity import (
    PostgresScimDirectoryRepository,
    PostgresScimEventRepository,
    PostgresScimGroupMemberRepository,
    PostgresScimGroupRepository,
    PostgresScimUserRepository,
)
from backend.app.repositories.scim_repository import (
    ScimDirectoryExists,
    ScimDirectoryRepository,
    ScimEventRepository,
    ScimEventSeen,
    ScimGroupMemberRepository,
    ScimGroupRepository,
    ScimUserRepository,
)
from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimEventDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
    ScimUserState,
)
from tests.app.repositories.test_identity_parity import both_raise
from tests.app.repositories.test_refdata_parity import parity


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _now() -> dt.datetime:
    # millisecond precision: what Mongo stores
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def directory(ws, polis_id):
    return ScimDirectoryDocument(
        id=PydanticObjectId(),
        workspace_id=ws,
        polis_directory_id=polis_id,
        polis_tenant=str(ws),
        polis_product="bettercollected",
        type="okta-scim-v2",
        name="Okta",
        webhook_secret="ciphertext",
        created_by="u1",
    )


async def test_directories(sessions):
    ws, other = PydanticObjectId(), PydanticObjectId()
    one, two = directory(ws, "d-1"), directory(other, "d-2")
    await parity(
        ScimDirectoryRepository(),
        PostgresScimDirectoryRepository(sessions),
        [
            ("create", lambda: (one,)),
            ("create", lambda: (two,)),
            ("get", lambda: (one.id,)),
            ("get", lambda: ("not-an-id",)),
            ("get", lambda: (PydanticObjectId(),)),
            ("find_by_workspace", lambda: (ws,)),
            ("find_by_workspace", lambda: (PydanticObjectId(),)),
            ("list_all", lambda: ()),
            ("delete", lambda: (two.id,)),
            ("list_all", lambda: ()),
        ],
    )


async def test_one_directory_per_workspace(sessions):
    mongo = ScimDirectoryRepository()
    postgres = PostgresScimDirectoryRepository(sessions)
    ws = PydanticObjectId()
    for repo in (mongo, postgres):
        await repo.create(directory(ws, "d-a"))
    await both_raise(
        ScimDirectoryExists,
        lambda: mongo.create(directory(ws, "d-b")),
        lambda: postgres.create(directory(ws, "d-b")),
    )


async def test_users_groups_and_members(sessions):
    ws, d = PydanticObjectId(), PydanticObjectId()
    jane = ScimUserDocument(
        id=derived_object_id("scim_user", d, "u-1"),
        directory_id=d,
        workspace_id=ws,
        polis_user_id="u-1",
        email="jane@acme.org",
        user_id="a1",
    )
    bob = ScimUserDocument(
        id=derived_object_id("scim_user", d, "u-2"),
        directory_id=d,
        workspace_id=ws,
        polis_user_id="u-2",
        email="bob@acme.org",
        active=False,
        state=ScimUserState.DEPROVISIONED,
    )
    admins = ScimGroupDocument(
        id=PydanticObjectId(),
        directory_id=d,
        workspace_id=ws,
        polis_group_id="g-1",
        name="Admins",
        role="ADMIN",
    )
    link = ScimGroupMemberDocument(
        id=derived_object_id(admins.id, jane.id),
        directory_id=d,
        group_id=admins.id,
        scim_user_id=jane.id,
    )
    await parity(
        ScimUserRepository(),
        PostgresScimUserRepository(sessions),
        [
            ("save", lambda: (jane,)),
            ("save", lambda: (bob,)),
            ("get", lambda: (jane.id,)),
            ("find", lambda: (d, "u-2")),
            ("find", lambda: (d, "nope")),
            ("find_by_email", lambda: (ws, "jane@acme.org")),
            ("find_by_email", lambda: (ws, "nobody@acme.org")),
            ("list_by_directory", lambda: (d,)),
            ("list_by_ids", lambda: ([bob.id, jane.id],)),
            ("list_by_ids", lambda: ([],)),
        ],
    )
    await parity(
        ScimGroupRepository(),
        PostgresScimGroupRepository(sessions),
        [
            ("save", lambda: (admins,)),
            ("get", lambda: (admins.id,)),
            ("find", lambda: (d, "g-1")),
            ("find", lambda: (d, "g-x")),
            ("list_by_directory", lambda: (d,)),
        ],
    )
    await parity(
        ScimGroupMemberRepository(),
        PostgresScimGroupMemberRepository(sessions),
        [
            ("add", lambda: (link,)),
            ("add", lambda: (link,)),  # the same pair: one row
            ("list_by_user", lambda: (jane.id,)),
            ("list_by_group", lambda: (admins.id,)),
            ("list_by_directory", lambda: (d,)),
            ("remove", lambda: (admins.id, jane.id)),
            ("list_by_group", lambda: (admins.id,)),
            ("add", lambda: (link,)),
            ("delete_by_user", lambda: (jane.id,)),
            ("add", lambda: (link,)),
            ("delete_by_group", lambda: (admins.id,)),
            ("add", lambda: (link,)),
            ("delete_by_directory", lambda: (d,)),
            ("list_by_directory", lambda: (d,)),
        ],
    )
    await parity(
        ScimGroupRepository(),
        PostgresScimGroupRepository(sessions),
        [("delete", lambda: (admins.id,)), ("delete_by_directory", lambda: (d,))],
    )
    await parity(
        ScimUserRepository(),
        PostgresScimUserRepository(sessions),
        [
            ("delete_by_directory", lambda: (d,)),
            ("list_by_directory", lambda: (d,)),
        ],
    )


async def test_events_are_accepted_once(sessions):
    mongo, postgres = ScimEventRepository(), PostgresScimEventRepository(sessions)
    now = _now()

    def event(key, minutes=60):
        return ScimEventDocument(
            id=PydanticObjectId(),
            event_key=key,
            directory_id=PydanticObjectId(),
            event_type="user.created",
            expires_at=now + dt.timedelta(minutes=minutes),
        )

    for repo in (mongo, postgres):
        await repo.claim(event("k1"), now)
    await both_raise(
        ScimEventSeen,
        lambda: mongo.claim(event("k1"), now),
        lambda: postgres.claim(event("k1"), now),
    )
    # released (processing failed): the retry is accepted
    for repo in (mongo, postgres):
        assert await repo.release("k1") == 1
        await repo.claim(event("k1"), now)
    # an expired record no longer blocks (Postgres deletes it on claim)
    await postgres.claim(event("old", minutes=-1), now)
    await postgres.claim(event("old"), now)
