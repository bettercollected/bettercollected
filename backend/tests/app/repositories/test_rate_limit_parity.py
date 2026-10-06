"""The Postgres twin of the rate-limit counters behaves like the Mongo
original (#767). Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt

import pytest
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.postgres.ai import PostgresRateLimitRepository
from backend.app.repositories.rate_limit_repository import RateLimitRepository
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.db.models import RateLimitCounterRow


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _soon(minutes=2):
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)


async def test_hits_count_up_per_counter(sessions):
    mongo, postgres = RateLimitRepository(), PostgresRateLimitRepository(sessions)
    a, b = "a" * 24, "b" * 24
    for repo in (mongo, postgres):
        assert [await repo.hit(a, _soon()) for _ in range(3)] == [1, 2, 3]
        assert await repo.hit(b, _soon()) == 1


async def test_concurrent_hits_are_all_counted(sessions):
    mongo, postgres = RateLimitRepository(), PostgresRateLimitRepository(sessions)
    counter = "c" * 24
    for repo in (mongo, postgres):
        counts = await asyncio.gather(*(repo.hit(counter, _soon()) for _ in range(10)))
        assert sorted(counts) == list(range(1, 11))


async def test_postgres_drops_expired_counters(sessions):
    postgres = PostgresRateLimitRepository(sessions)
    await postgres.hit("d" * 24, _soon(-1))
    await postgres.hit("e" * 24, _soon())  # a new counter sweeps expired ones
    async with sessions() as session:
        ids = (await session.execute(select(RateLimitCounterRow.id))).scalars().all()
    assert ids == ["e" * 24]


async def test_counter_ids_are_keyed_hashes():
    limiter = FixedWindowRateLimiter(repo=None, secret="one")
    other = FixedWindowRateLimiter(repo=None, secret="two")
    client = "203.0.113.5"
    counter = limiter.counter_id("flow-events", client, 7)
    assert len(counter) == 24 and int(counter, 16) >= 0
    assert counter == limiter.counter_id("flow-events", client, 7)
    assert counter != limiter.counter_id("flow-events", client, 8)
    assert counter != limiter.counter_id("other", client, 7)
    assert counter != other.counter_id("flow-events", client, 7)
