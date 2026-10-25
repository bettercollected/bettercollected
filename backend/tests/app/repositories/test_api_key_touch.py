"""``touch_last_used`` of the API keys' Postgres twin: a locked conditional
update of ``last_used_at`` alone, only while the key is not revoked. Skipped
unless DATABASE_URL points at a *_test database."""

import datetime as dt

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.postgres.identity import (
    PostgresWorkspaceAPIKeyRepository,
)
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument

NOW = dt.datetime(2030, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)


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


@pytest.fixture
def repo(clean_postgres):
    return PostgresWorkspaceAPIKeyRepository(container.pg_sessionmaker())


async def test_touch_last_used_changes_only_that_field(repo):
    stored = key()
    await repo.save(stored)
    stale = await repo.get_or_404(stored.id)
    renamed = await repo.get_or_404(stored.id)
    renamed.name = "renamed"
    await repo.save(renamed)
    assert await repo.touch_last_used(stale.id, NOW) is True
    found = await repo.get_or_404(stored.id)
    assert found.last_used_at == NOW and found.name == "renamed"


async def test_a_revoked_or_unknown_key_is_not_touched(repo):
    revoked = key(revoked=True)
    await repo.save(revoked)
    assert await repo.touch_last_used(revoked.id, NOW) is False
    assert await repo.touch_last_used(PydanticObjectId(), NOW) is False
    found = await repo.get_or_404(revoked.id)
    assert found.revoked is True and found.last_used_at is None
