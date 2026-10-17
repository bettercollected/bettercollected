"""The Postgres twin of the Idempotency-Key records behaves like the Mongo
original. Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.idempotency_repository import IdempotencyRepository
from backend.app.repositories.postgres.ai import PostgresIdempotencyRepository
from backend.app.schemas.api_idempotency_record import ApiIdempotencyRecordDocument
from backend.db.models import ApiIdempotencyKeyRow


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _record(record_id: str, minutes: int = 60, request_hash: str = "h1"):
    return ApiIdempotencyRecordDocument(
        id=PydanticObjectId(record_id),
        key_id="k" * 24,
        request_hash=request_hash,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes),
    )


async def test_claim_once_then_complete_and_find(sessions):
    mongo, postgres = IdempotencyRepository(), PostgresIdempotencyRepository(sessions)
    record_id = "a" * 24
    for repo in (mongo, postgres):
        assert await repo.find(record_id) is None
        assert await repo.claim(_record(record_id)) is True
        assert await repo.claim(_record(record_id, request_hash="h2")) is False
        found = await repo.find(record_id)
        assert (found.state, found.request_hash) == ("pending", "h1")
        await repo.complete(record_id, 201, '{"ok": true}', '"etag-1"')
        found = await repo.find(record_id)
        assert (found.state, found.status_code, found.body, found.etag) == (
            "done",
            201,
            '{"ok": true}',
            '"etag-1"',
        )
        # a release only drops an unfinished claim
        await repo.release(record_id)
        assert (await repo.find(record_id)).state == "done"


async def test_release_lets_a_retry_claim_again(sessions):
    mongo, postgres = IdempotencyRepository(), PostgresIdempotencyRepository(sessions)
    record_id = "b" * 24
    for repo in (mongo, postgres):
        assert await repo.claim(_record(record_id)) is True
        await repo.release(record_id)
        assert await repo.find(record_id) is None
        assert await repo.claim(_record(record_id)) is True


async def test_an_expired_record_is_not_found_and_gives_way(sessions):
    mongo, postgres = IdempotencyRepository(), PostgresIdempotencyRepository(sessions)
    record_id = "c" * 24
    for repo in (mongo, postgres):
        assert await repo.claim(_record(record_id, minutes=-1)) is True
        assert await repo.find(record_id) is None
        assert await repo.claim(_record(record_id, request_hash="new")) is True
        assert (await repo.find(record_id)).request_hash == "new"


async def test_concurrent_claims_have_one_winner(sessions):
    mongo, postgres = IdempotencyRepository(), PostgresIdempotencyRepository(sessions)
    record_id = "d" * 24
    for repo in (mongo, postgres):
        won = await asyncio.gather(*(repo.claim(_record(record_id)) for _ in range(8)))
        assert sorted(won) == [False] * 7 + [True]


async def test_postgres_drops_expired_records(sessions):
    postgres = PostgresIdempotencyRepository(sessions)
    await postgres.claim(_record("e" * 24, minutes=-1))
    await postgres.claim(_record("f" * 24))  # a new record sweeps expired ones
    async with sessions() as session:
        ids = (await session.execute(select(ApiIdempotencyKeyRow.id))).scalars().all()
    assert ids == ["f" * 24]
