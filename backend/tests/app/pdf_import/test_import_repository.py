"""The PDF import repository (Postgres only since 4.1): its records, the
per-workspace start limits and lock, and the expiry of interrupted imports.
The listing steps ran against the 4.0 Mongo repository too while both stores
existed; the results they agreed on are pinned here. Skipped unless
DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt

import pytest

from backend.app.container import container
from backend.app.repositories.postgres import forms as module
from backend.app.repositories.postgres.forms import (
    ImportLimitReached,
    PostgresFormImportRepository,
)
from backend.app.schemas.form_import import (
    FormImportDocument,
    ImportStatus,
    PageAnalysis,
)
from common.records import RecordId

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def record(ws, form_id, status, minutes_ago=0):
    created = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    return FormImportDocument(
        id=RecordId(),
        workspace_id=ws,
        form_id=form_id,
        created_by="u1",
        status=status,
        file_name=f"{form_id}.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        source_key=f"private/{ws}/{form_id}/imports/x/source.pdf",
        page_count=1,
        pages=[PageAnalysis(number=1, width=595, height=842, route="text")],
        created_at=created,
        updated_at=created,
    )


async def test_form_imports(sessions):
    ws, other = RecordId(), RecordId()
    old = record(ws, "f-old", ImportStatus.COMPLETED, minutes_ago=60 * 30)
    recent = record(ws, "f-recent", ImportStatus.RUNNING, minutes_ago=5)
    queued = record(ws, "f-queued", ImportStatus.QUEUED, minutes_ago=1)
    elsewhere = record(other, "f-else", ImportStatus.RUNNING)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    repo = PostgresFormImportRepository(sessions)
    for r in (old, recent, queued, elsewhere):
        assert await repo.save(r) is r
    got = await repo.get(recent.id)
    assert (got.id, got.form_id, got.status) == (recent.id, "f-recent", "running")
    assert got.pages == recent.pages
    assert await repo.get(RecordId()) is None
    # newest first, this workspace's only
    listed = await repo.list_by_workspace(ws)
    assert [r.form_id for r in listed] == ["f-queued", "f-recent", "f-old"]
    assert await repo.count_active(ws) == 2
    assert await repo.delete_by_form_ids(["f-queued", "f-missing"]) == 1
    assert await repo.count_active(ws) == 1
    assert [r.form_id for r in await repo.list_by_workspace(ws, 1)] == ["f-recent"]
    # the daily window counts by creation time
    assert await repo.count_created_since(ws, since) == 1


async def test_parallel_creates_respect_the_limits(sessions, monkeypatch):
    """create_within_limits is atomic (the workspace's advisory lock).

    Every start pauses between reading the counts and inserting, so without
    the lock all of them would read the same counts and pass: the test fails
    every time the lock is missing, not only when the scheduler happens to
    interleave the starts. The lock wait is lengthened so a loaded machine
    cannot turn a slow start into a refusal."""

    monkeypatch.setattr(module, "LOCK_WAIT_S", 120.0)
    repo = PostgresFormImportRepository(sessions)
    counts = repo._limit_counts

    async def slow_counts(*args):
        result = await counts(*args)
        await asyncio.sleep(0.05)  # the window a missing lock would let others in
        return result

    monkeypatch.setattr(repo, "_limit_counts", slow_counts)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)

    async def attempt(ws, max_active, max_per_day):
        try:
            await repo.create_within_limits(
                record(ws, f"f-{RecordId()}", ImportStatus.QUEUED),
                max_active,
                max_per_day,
                since,
            )
            return "ok"
        except ImportLimitReached as reached:
            return reached.code

    ws = RecordId()
    results = await asyncio.gather(*[attempt(ws, 1, 10) for _ in range(6)])
    assert sorted(results) == ["import_in_progress"] * 5 + ["ok"]
    assert await repo.count_active(ws) == 1

    ws = RecordId()
    results = await asyncio.gather(*[attempt(ws, 10, 2) for _ in range(6)])
    assert sorted(results) == ["daily_limit"] * 4 + ["ok"] * 2
    assert await repo.count_created_since(ws, since) == 2
    # other workspaces are not held up
    assert await attempt(RecordId(), 1, 1) == "ok"


async def test_a_start_that_waits_too_long_is_refused_as_busy(sessions, monkeypatch):
    """A workspace whose lock stays held (a stuck start) refuses new starts
    with the usual "an import is already running", instead of a database
    error."""
    from sqlalchemy import func, select

    monkeypatch.setattr(module, "LOCK_WAIT_S", 0.3)
    repo = PostgresFormImportRepository(sessions)
    ws = RecordId()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    new = record(ws, "f-new", ImportStatus.QUEUED)
    async with sessions() as holder, holder.begin():
        await holder.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended(f"form_imports:{ws}", 0))
            )
        )
        with pytest.raises(ImportLimitReached) as refused:
            await repo.create_within_limits(new, 1, 10, since)
    assert refused.value.code == "import_in_progress"
    assert await repo.count_active(ws) == 0
    # once the lock is free the start goes through
    await repo.create_within_limits(new, 1, 10, since)
    assert await repo.count_active(ws) == 1


async def test_stale_imports_are_expired_and_healthy_ones_kept(sessions):
    """The workspace's active imports without progress since
    the threshold fail (``interrupted``) and everything else is left alone; the
    heartbeat changes only ``heartbeat_at`` and only while active."""
    repo = PostgresFormImportRepository(sessions)
    now = dt.datetime.now(dt.timezone.utc)
    stale_before = now - dt.timedelta(minutes=10)
    ws, other = RecordId(), RecordId()

    stuck = record(ws, "f-stuck", ImportStatus.RUNNING, minutes_ago=60)
    stuck.heartbeat_at = now - dt.timedelta(minutes=20)
    lost = record(ws, "f-lost", ImportStatus.QUEUED, minutes_ago=30)  # no heartbeat
    healthy = record(ws, "f-healthy", ImportStatus.RUNNING, minutes_ago=180)
    healthy.heartbeat_at = now - dt.timedelta(seconds=5)
    fresh = record(ws, "f-fresh", ImportStatus.QUEUED, minutes_ago=1)
    done = record(ws, "f-done", ImportStatus.COMPLETED, minutes_ago=600)
    elsewhere = record(other, "f-else", ImportStatus.RUNNING, minutes_ago=60)
    for r in (stuck, lost, healthy, fresh, done, elsewhere):
        await repo.save(r)

    assert set(await repo.stale_workspaces(stale_before)) == {ws, other}
    expired = await repo.expire_stale(ws, stale_before, now)
    assert {r.id for r in expired} == {stuck.id, lost.id}
    for r in (stuck, lost):
        stored = await repo.get(r.id)
        assert stored.status == ImportStatus.FAILED
        assert stored.error_code == "interrupted"
        assert stored.report["refused"] == "interrupted"
        assert stored.finished_at is not None
        assert stored.form_id == r.form_id  # the service removes the draft
    for r in (healthy, fresh, elsewhere):
        assert (await repo.get(r.id)).status == r.status
    assert (await repo.get(done.id)).status == ImportStatus.COMPLETED
    assert await repo.count_active(ws) == 2
    # nothing left to expire there
    assert await repo.expire_stale(ws, stale_before, now) == []
    assert await repo.stale_workspaces(stale_before) == [other]

    # the heartbeat: only while active, and only that field
    stored = await repo.get(healthy.id)
    stored.stage = "render"
    await repo.save(stored)
    beat = now + dt.timedelta(seconds=1)
    assert await repo.touch(healthy.id, beat) is True
    touched = await repo.get(healthy.id)
    assert touched.stage == "render" and touched.status == ImportStatus.RUNNING
    seen = touched.heartbeat_at
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=dt.timezone.utc)
    assert abs(seen - beat) < dt.timedelta(milliseconds=2)
    assert await repo.touch(stuck.id, beat) is False
    assert (await repo.get(stuck.id)).status == ImportStatus.FAILED


async def test_parallel_starts_expiring_a_stale_import_let_one_through(
    sessions, monkeypatch
):
    """Expiry and the limit check take the same workspace lock: parallel
    starts that each expire first and then insert still admit exactly one."""
    monkeypatch.setattr(module, "LOCK_WAIT_S", 120.0)
    repo = PostgresFormImportRepository(sessions)
    now = dt.datetime.now(dt.timezone.utc)
    stale_before = now - dt.timedelta(minutes=10)
    since = now - dt.timedelta(days=1)
    ws = RecordId()
    stuck = record(ws, "f-stuck", ImportStatus.RUNNING, minutes_ago=60)
    await repo.save(stuck)
    counts = repo._limit_counts

    async def slow_counts(*args):
        result = await counts(*args)
        await asyncio.sleep(0.05)
        return result

    monkeypatch.setattr(repo, "_limit_counts", slow_counts)

    async def start():
        await repo.expire_stale(ws, stale_before, now)
        try:
            await repo.create_within_limits(
                record(ws, f"f-{RecordId()}", ImportStatus.QUEUED),
                1,
                10,
                since,
            )
            return "ok"
        except ImportLimitReached as reached:
            return reached.code

    results = await asyncio.gather(*[start() for _ in range(5)])
    assert sorted(results) == ["import_in_progress"] * 4 + ["ok"]
    assert await repo.count_active(ws) == 1
    assert (await repo.get(stuck.id)).error_code == "interrupted"
