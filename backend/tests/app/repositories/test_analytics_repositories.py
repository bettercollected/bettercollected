"""The analytics repositories (flow events, rate-limit counters), Postgres
only since 4.1. Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt

import pytest
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.postgres.analytics import (
    PostgresFlowEventRepository,
    PostgresRateLimitRepository,
)
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.db.models import RateLimitCounterRow


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _soon(minutes=2):
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)


# -- flow events -------------------------------------------------------------------


async def test_flow_events_are_listed_per_form_in_order(sessions):
    repo = PostgresFlowEventRepository(sessions)
    first = await repo.add("f1", "s1", "p1", "p2")
    await repo.add("f1", "s1", "p2", "p3")
    await repo.add("f2", "s2", "p1", "p2")
    events = await repo.list_by_form_id("f1")
    assert [(e.from_page, e.to_page) for e in events] == [("p1", "p2"), ("p2", "p3")]
    assert events[0].id == first.id and events[0].session_id == "s1"
    assert await repo.list_by_form_id("f3") == []


async def test_flow_events_older_than_a_cutoff_are_deleted(sessions):
    repo = PostgresFlowEventRepository(sessions)
    await repo.add("f1", "s1", "p1", "p2")
    assert await repo.delete_older_than(_soon(-60)) == 0
    assert await repo.delete_older_than(_soon()) == 1
    assert await repo.list_by_form_id("f1") == []


# -- rate-limit counters ---------------------------------------------------------


async def test_hits_count_up_per_counter(sessions):
    repo = PostgresRateLimitRepository(sessions)
    a, b = "a" * 24, "b" * 24
    assert [await repo.hit(a, _soon()) for _ in range(3)] == [1, 2, 3]
    assert await repo.hit(b, _soon()) == 1


async def test_hits_add_an_amount_and_zero_reads(sessions):
    # the AI daily token budget adds a call's tokens, and reads with 0
    repo = PostgresRateLimitRepository(sessions)
    counter, fresh = "f" * 24, "9" * 24
    assert await repo.hit(counter, _soon(), 250) == 250
    assert await repo.hit(counter, _soon(), 0) == 250
    assert await repo.hit(counter, _soon()) == 251
    assert await repo.hit(fresh, _soon(), 0) == 0


async def test_concurrent_hits_are_all_counted(sessions):
    repo = PostgresRateLimitRepository(sessions)
    counter = "c" * 24
    counts = await asyncio.gather(*(repo.hit(counter, _soon()) for _ in range(10)))
    assert sorted(counts) == list(range(1, 11))


async def test_expired_counters_are_dropped(sessions):
    repo = PostgresRateLimitRepository(sessions)
    await repo.hit("d" * 24, _soon(-1))
    await repo.hit("e" * 24, _soon())  # a new counter sweeps expired ones
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
