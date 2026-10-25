"""``touch_last_used`` through the routed repository under ``dual`` (Mongo
primary): Mongo's conditional ``$set`` stores what ``save()`` stores, and a
Postgres copy that is stale (still live) or missing is converged from the
primary instead of keeping the key live there. Drives a Mongo server;
skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.postgres.identity import (
    PostgresWorkspaceAPIKeyRepository,
)
from backend.app.repositories.workspace_api_key_repository import (
    WorkspaceAPIKeyRepository,
)
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.db.models import WorkspaceApiKeyRow
from common.db import RoutingRepository, load_flags

NOW = dt.datetime(2030, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)


@pytest.fixture
def postgres(clean_postgres):
    return PostgresWorkspaceAPIKeyRepository(container.pg_sessionmaker())


@pytest.fixture
def repo(postgres):
    return RoutingRepository(
        group="identity",
        flags=load_flags({"DB_WRITE_MODE": "dual", "DB_READ_SOURCE": "mongo"}),
        mongo=WorkspaceAPIKeyRepository(),
        postgres=postgres,
        on_mirror_failure=container.outbox_recorder(),
    )


def key(**extra):
    return WorkspaceAPIKeyDocument(
        id=PydanticObjectId(),
        workspace_id=PydanticObjectId(),
        name="ci",
        key_hash=f"hash-{PydanticObjectId()}",
        prefix="hash-x",
        scopes=["forms:read"],
        created_by="tester",
        **extra,
    )


async def postgres_copy(key_id):
    async with container.pg_sessionmaker()() as session:
        return (
            await session.execute(
                select(WorkspaceApiKeyRow.doc).where(
                    WorkspaceApiKeyRow.id == str(key_id)
                )
            )
        ).scalar_one_or_none()


async def test_both_stores_record_the_use_as_save_does(repo):
    document = key()
    await repo.save(document)
    assert await repo.touch_last_used(document.id, NOW) is True
    raw = await WorkspaceAPIKeyDocument.get_pymongo_collection().find_one(
        {"_id": document.id}
    )
    assert raw["last_used_at"] == NOW.isoformat()  # the document's encoder
    assert (await postgres_copy(document.id))["last_used_at"] == NOW.isoformat()


async def test_a_stale_live_postgres_copy_converges_to_revoked(repo, postgres):
    document = key()
    await repo.save(document)
    # revoked in Mongo only: the Postgres copy is stale and still live
    await WorkspaceAPIKeyDocument.get_pymongo_collection().update_one(
        {"_id": document.id}, {"$set": {"revoked": True}}
    )
    assert await repo.touch_last_used(document.id, NOW) is False
    copy = await postgres_copy(document.id)
    assert copy["revoked"] is True and copy.get("last_used_at") is None


async def test_a_missing_postgres_copy_is_converged_from_the_primary(repo):
    document = key()
    await document.save()  # Mongo only
    assert await postgres_copy(document.id) is None
    assert await repo.touch_last_used(document.id, NOW) is True
    copy = await postgres_copy(document.id)
    assert copy is not None and copy["last_used_at"] == NOW.isoformat()
