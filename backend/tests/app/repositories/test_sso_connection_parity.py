"""The Postgres twin of the SSO connection repository behaves like the Mongo
original. Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.postgres.identity import PostgresSsoConnectionRepository
from backend.app.repositories.sso_connection_repository import (
    SsoConnectionExists,
    SsoConnectionRepository,
)
from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
    SsoConnectionType,
)
from tests.app.repositories.test_identity_parity import both_raise
from tests.app.repositories.test_refdata_parity import parity


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _at(minutes_ago: int) -> dt.datetime:
    # millisecond precision: what Mongo stores
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return now - dt.timedelta(minutes=minutes_ago)


def connection(ws, client_id, enabled_minutes_ago=None):
    return SsoConnectionDocument(
        id=PydanticObjectId(),
        workspace_id=ws,
        type=SsoConnectionType.SAML,
        name=f"IdP {client_id}",
        status=(
            SsoConnectionStatus.ENABLED
            if enabled_minutes_ago is not None
            else SsoConnectionStatus.DISABLED
        ),
        polis_client_id=client_id,
        polis_tenant=str(ws),
        polis_product="bettercollected",
        created_by="u1",
        enabled_at=(
            _at(enabled_minutes_ago) if enabled_minutes_ago is not None else None
        ),
    )


async def test_sso_connections(sessions):
    ws, other = PydanticObjectId(), PydanticObjectId()
    old = connection(ws, "c-old", enabled_minutes_ago=30)
    new = connection(ws, "c-new", enabled_minutes_ago=5)
    off = connection(ws, "c-off")
    elsewhere = connection(other, "c-else", enabled_minutes_ago=1)
    now = _at(0)
    await parity(
        SsoConnectionRepository(),
        PostgresSsoConnectionRepository(sessions),
        [
            ("create", lambda: (old,)),
            ("create", lambda: (new,)),
            ("create", lambda: (off,)),
            ("create", lambda: (elsewhere,)),
            ("get", lambda: (old.id,)),
            ("get", lambda: (PydanticObjectId(),)),
            ("get", lambda: ("not-an-id",)),
            ("list_by_workspace", lambda: (ws,)),
            ("count_by_workspace", lambda: (ws,)),
            ("find_enabled", lambda: (ws,)),
            ("find_enabled", lambda: (PydanticObjectId(),)),
            ("disable_others", lambda: (ws, new.id, "u2", now)),
            ("list_by_workspace", lambda: (ws,)),
            ("find_enabled", lambda: (ws,)),
            ("find_enabled", lambda: (other,)),
            ("delete", lambda: (off.id,)),
            ("count_by_workspace", lambda: (ws,)),
            ("delete_by_workspace_ids", lambda: ([other],)),
            ("list_by_workspace", lambda: (other,)),
        ],
    )


async def test_one_record_per_polis_connection(sessions):
    mongo, postgres = SsoConnectionRepository(), PostgresSsoConnectionRepository(
        sessions
    )
    ws = PydanticObjectId()
    for repo in (mongo, postgres):
        await repo.create(connection(ws, "same-client"))
    await both_raise(
        SsoConnectionExists,
        lambda: mongo.create(connection(ws, "same-client")),
        lambda: postgres.create(connection(ws, "same-client")),
    )
