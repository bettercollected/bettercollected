"""The Postgres twin of the import repository behaves like the Mongo original.
Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.form_import_repository import FormImportRepository
from backend.app.repositories.postgres.forms import PostgresFormImportRepository
from backend.app.schemas.form_import import (
    FormImportDocument,
    ImportStatus,
    PageAnalysis,
)
from tests.app.repositories.test_refdata_parity import parity

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def record(ws, form_id, status, minutes_ago=0):
    created = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    return FormImportDocument(
        id=PydanticObjectId(),
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
    ws, other = PydanticObjectId(), PydanticObjectId()
    old = record(ws, "f-old", ImportStatus.COMPLETED, minutes_ago=60 * 30)
    recent = record(ws, "f-recent", ImportStatus.RUNNING, minutes_ago=5)
    queued = record(ws, "f-queued", ImportStatus.QUEUED, minutes_ago=1)
    elsewhere = record(other, "f-else", ImportStatus.RUNNING)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    await parity(
        FormImportRepository(),
        PostgresFormImportRepository(sessions),
        [
            ("save", lambda: (old,)),
            ("save", lambda: (recent,)),
            ("save", lambda: (queued,)),
            ("save", lambda: (elsewhere,)),
            ("get", lambda: (recent.id,)),
            ("get", lambda: (PydanticObjectId(),)),
            ("list_by_workspace", lambda: (ws,)),
            ("count_active", lambda: (ws,)),
            ("delete_by_form_ids", lambda: (["f-queued", "f-missing"],)),
            ("count_active", lambda: (ws,)),
            ("list_by_workspace", lambda: (ws, 1)),
        ],
    )
    # the daily window counts by creation time in both stores
    assert await FormImportRepository().count_created_since(ws, since) == 1
    assert (
        await PostgresFormImportRepository(sessions).count_created_since(ws, since) == 1
    )


def _repo(store, sessions):
    return (
        FormImportRepository()
        if store == "mongo"
        else PostgresFormImportRepository(sessions)
    )


@pytest.mark.parametrize("store", ["mongo", "postgres"])
async def test_parallel_creates_respect_the_limits(sessions, store, monkeypatch):
    """Each store's create_within_limits is atomic on its own (the Mongo lock
    document, the Postgres advisory lock), whichever one is primary.

    Every start pauses between reading the counts and inserting, so without
    the lock all of them would read the same counts and pass: the test fails
    every time the lock is missing, not only when the scheduler happens to
    interleave the starts. The lock wait is lengthened so a loaded machine
    cannot turn a slow start into a refusal."""
    import asyncio

    from backend.app.repositories import form_import_repository as module
    from backend.app.repositories.form_import_repository import ImportLimitReached

    monkeypatch.setattr(module, "LOCK_WAIT_S", 120.0)
    repo = _repo(store, sessions)
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
                record(ws, f"f-{PydanticObjectId()}", ImportStatus.QUEUED),
                max_active,
                max_per_day,
                since,
            )
            return "ok"
        except ImportLimitReached as reached:
            return reached.code

    ws = PydanticObjectId()
    results = await asyncio.gather(*[attempt(ws, 1, 10) for _ in range(6)])
    assert sorted(results) == ["import_in_progress"] * 5 + ["ok"]
    assert await repo.count_active(ws) == 1

    ws = PydanticObjectId()
    results = await asyncio.gather(*[attempt(ws, 10, 2) for _ in range(6)])
    assert sorted(results) == ["daily_limit"] * 4 + ["ok"] * 2
    assert await repo.count_created_since(ws, since) == 2
    # other workspaces are not held up
    assert await attempt(PydanticObjectId(), 1, 1) == "ok"


@pytest.mark.parametrize("store", ["mongo", "postgres"])
async def test_a_start_that_waits_too_long_is_refused_as_busy(
    sessions, store, monkeypatch
):
    """A workspace whose lock stays held (a stuck start) refuses new starts
    with the usual "an import is already running", in both stores, instead of
    a database error."""
    from sqlalchemy import func, select

    from backend.app.repositories import form_import_repository as module
    from backend.app.repositories.form_import_repository import (
        LOCKS,
        ImportLimitReached,
    )

    monkeypatch.setattr(module, "LOCK_WAIT_S", 0.3)
    repo = _repo(store, sessions)
    ws = PydanticObjectId()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    new = record(ws, "f-new", ImportStatus.QUEUED)
    if store == "mongo":
        locks = FormImportDocument.get_pymongo_collection().database[LOCKS]
        await locks.insert_one(
            {
                "_id": str(ws),
                "token": "someone-else",
                "expires_at": dt.datetime.now(dt.timezone.utc)
                + dt.timedelta(minutes=1),
            }
        )
        try:
            with pytest.raises(ImportLimitReached) as refused:
                await repo.create_within_limits(new, 1, 10, since)
        finally:
            await locks.delete_one({"_id": str(ws)})
    else:
        async with sessions() as holder, holder.begin():
            await holder.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(f"form_imports:{ws}", 0)
                    )
                )
            )
            with pytest.raises(ImportLimitReached) as refused:
                await repo.create_within_limits(new, 1, 10, since)
    assert refused.value.code == "import_in_progress"
    assert await repo.count_active(ws) == 0
    # once the lock is free the start goes through
    await repo.create_within_limits(new, 1, 10, since)
    assert await repo.count_active(ws) == 1


@pytest.mark.parametrize("store", ["mongo", "postgres"])
async def test_stale_imports_are_expired_and_healthy_ones_kept(sessions, store):
    """Each store fails the workspace's active imports without progress since
    the threshold (``interrupted``) and leaves everything else alone; the
    heartbeat changes only ``heartbeat_at`` and only while active."""
    repo = _repo(store, sessions)
    now = dt.datetime.now(dt.timezone.utc)
    stale_before = now - dt.timedelta(minutes=10)
    ws, other = PydanticObjectId(), PydanticObjectId()

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


@pytest.mark.parametrize("store", ["mongo", "postgres"])
async def test_parallel_starts_expiring_a_stale_import_let_one_through(
    sessions, store, monkeypatch
):
    """Expiry and the limit check take the same workspace lock: parallel
    starts that each expire first and then insert still admit exactly one."""
    from backend.app.repositories import form_import_repository as module
    from backend.app.repositories.form_import_repository import ImportLimitReached

    monkeypatch.setattr(module, "LOCK_WAIT_S", 120.0)
    repo = _repo(store, sessions)
    now = dt.datetime.now(dt.timezone.utc)
    stale_before = now - dt.timedelta(minutes=10)
    since = now - dt.timedelta(days=1)
    ws = PydanticObjectId()
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
                record(ws, f"f-{PydanticObjectId()}", ImportStatus.QUEUED),
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
