"""Concurrent writes to one document whose mirror writes land in the opposite
order to their primary writes still leave both stores with the newer version.

Each test holds the mirror write of a first write (W1) until a second write
(W2) to the same document has reached both stores, then lets W1's mirror
write land last: the order the race produces when two requests write the same
document at once. ``dual`` (Mongo primary, Postgres mirror) and
``postgres_primary_dual`` (Postgres primary, Mongo mirror) are set on the
repositories built here, whatever mode the suite runs in. The last tests do
the same to ``reconcile``, which copies from one store to the other and must
not overwrite a copy the application changed after reconcile read it.
Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt
import functools
import os
import time

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.models import FormRow, MigrationProgress
from backend.migrate.__main__ import _tables
import common.db.convergence as convergence
import common.db.routing as routing
from common.db import ReadSource, RoutingRepository, load_flags
from common.db.outbox import MirrorWriteFailureDocument
from common.db.beanie_bridge import store_exactly
from common.db.canonical import canonical_document, checksum
from common.db.migrate import Runner, Target
from common.models.standard_form import StandardForm
from sqlalchemy import select, update
from tests.app.db.beanie_originals import (
    FormDocument,
    FormRepository,
    PostgresFormRepository,
)

MODES = ["dual", "postgres_primary_dual"]


@pytest.fixture
def target(clean_postgres):
    return Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=os.environ["DATABASE_URL"],
    )


class Held:
    """``store`` whose next mirror write, once armed, starts and then waits
    until ``release`` is set. A replayed write reaches the mirror through
    ``replay_write``; for the Mongo store that is the routing layer's
    exact store of each document."""

    def __init__(self, store, method):
        self._store = store
        self._method = method
        self._armed = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    def arm(self):
        self._armed = True

    async def _hold(self):
        if self._armed:
            self._armed = False
            self.entered.set()
            await self.release.wait()

    async def replay_write(self, documents):
        await self._hold()
        hook = getattr(self._store, "replay_write", None)
        if hook is not None:
            return await hook(documents)
        for document in documents:
            await store_exactly(document)

    def __getattr__(self, name):
        target = getattr(self._store, name)
        if name != self._method:
            return target

        @functools.wraps(target)
        async def held(*args, **kwargs):
            await self._hold()
            return await target(*args, **kwargs)

        return held


def forms_repo(mode, method):
    """The routed forms repository under ``mode``, reading from its primary
    (as the cutover does), its mirror store held on ``method``."""
    read = "mongo" if mode == "dual" else "postgres"
    flags = load_flags({"DB_WRITE_MODE": mode, "DB_READ_SOURCE": read})
    mongo = FormRepository()
    postgres = PostgresFormRepository(container.pg_sessionmaker())
    if flags.mirror_store("forms") is ReadSource.POSTGRES:
        postgres = held = Held(postgres, method)
    else:
        mongo = held = Held(mongo, method)
    repo = RoutingRepository(
        group="forms",
        flags=flags,
        mongo=mongo,
        postgres=postgres,
        on_mirror_failure=container.outbox_recorder(),
    )
    return repo, held


async def both_copies(form_id):
    """(Mongo's raw document, Postgres' doc) of the draft ``form_id`` (None when absent)."""
    mongo = await FormDocument.get_pymongo_collection().find_one({"form_id": form_id})
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(select(FormRow.doc).where(FormRow.form_id == form_id))
        ).scalar_one_or_none()
    return mongo, doc


async def verify(target, *collections):
    async with Runner(target) as runner:
        reports = await runner.verify(list(collections))
    return {r.collection: r.as_dict() for r in reports if not r.clean}


async def new_form(repo, title="Draft"):
    return await repo.create_form(
        StandardForm(form_id=str(PydanticObjectId()), title=title, builder_version="v2")
    )


async def out_of_order(held, first, second):
    """Run ``first`` until its mirror write is held, run ``second`` to the
    end, then let ``first``'s mirror write land."""
    held.arm()
    task = asyncio.create_task(first())
    await held.entered.wait()
    await second()
    held.release.set()
    await task


@pytest.mark.parametrize("mode", MODES)
async def test_saves_mirrored_out_of_order_leave_the_newer_version(target, mode):
    repo, held = forms_repo(mode, "save_form")
    created = await new_form(repo)
    one = await repo.get_form_document_by_id(created.form_id)
    two = await repo.get_form_document_by_id(created.form_id)
    one.title, two.title = "One", "Two"

    await out_of_order(held, lambda: repo.save_form(one), lambda: repo.save_form(two))

    mongo, doc = await both_copies(created.form_id)
    assert mongo["title"] == doc["title"] == "Two"
    assert await verify(target, "forms") == {}
    assert repo.metrics.mirror_repairs[("forms", "save_form")] == 1


@pytest.mark.parametrize("mode", MODES)
async def test_field_updates_mirrored_out_of_order_leave_the_newer_value(target, mode):
    repo, held = forms_repo(mode, "set_form_logo")
    created = await new_form(repo)

    await out_of_order(
        held,
        lambda: repo.set_form_logo(created.form_id, "https://one.example/logo.png"),
        lambda: repo.set_form_logo(created.form_id, "https://two.example/logo.png"),
    )

    mongo, doc = await both_copies(created.form_id)
    assert mongo["logo"] == doc["logo"] == "https://two.example/logo.png"
    assert await verify(target, "forms") == {}


@pytest.mark.parametrize("mode", MODES)
async def test_replayed_writes_mirrored_out_of_order_leave_the_newer_version(
    target, mode
):
    repo, held = forms_repo(mode, "update_form_if_unchanged")
    created = await new_form(repo)
    stored = await repo.get_form_document_by_id(created.form_id)

    async def second():
        current = await repo.get_form_document_by_id(created.form_id)
        await repo.update_form_if_unchanged(
            PydanticObjectId(created.form_id),
            StandardForm(form_id=created.form_id, title="Two", builder_version="v2"),
            current.updated_at,
        )

    await out_of_order(
        held,
        lambda: repo.update_form_if_unchanged(
            PydanticObjectId(created.form_id),
            StandardForm(form_id=created.form_id, title="One", builder_version="v2"),
            stored.updated_at,
        ),
        second,
    )

    mongo, doc = await both_copies(created.form_id)
    assert mongo["title"] == doc["title"] == "Two"
    assert await verify(target, "forms") == {}


@pytest.mark.parametrize("mode", MODES)
async def test_a_save_mirrored_after_a_delete_does_not_bring_the_document_back(
    target, mode
):
    repo, held = forms_repo(mode, "save_form")
    created = await new_form(repo)
    kept = await new_form(repo, "Kept")
    one = await repo.get_form_document_by_id(created.form_id)
    one.title = "One"

    await out_of_order(
        held,
        lambda: repo.save_form(one),
        lambda: repo.delete_form(created.form_id),
    )

    assert await both_copies(created.form_id) == (None, None)
    mongo, doc = await both_copies(kept.form_id)
    assert mongo["title"] == doc["title"] == "Kept"
    assert await verify(target, "forms") == {}


async def set_postgres_title(form_document_id, title):
    """Change the Postgres copy behind the application's back (its
    updated_at stays: the application did not write it)."""
    table = FormRow.__table__
    async with container.pg_sessionmaker()() as session, session.begin():
        doc = (
            await session.execute(
                select(table.c.doc).where(table.c.id == str(form_document_id))
            )
        ).scalar_one()
        doc = {**doc, "title": title}
        await session.execute(
            update(table)
            .where(table.c.id == str(form_document_id))
            .values(doc=doc, _bc_checksum=checksum(doc))
        )


@pytest.mark.allow_mirror_failures
async def test_a_mirror_that_keeps_changing_is_a_reported_mirror_failure(
    target, monkeypatch
):
    """The copy-and-check rounds are bounded: a document that still differs
    after them is reported like a failed mirror write (outbox, counter)."""
    import common.db.convergence as convergence

    repo, _ = forms_repo("dual", "save_form")
    created = await new_form(repo)
    document = await repo.get_form_document_by_id(created.form_id)
    document.title = "Changed"
    real_read = convergence._read

    async def drifting_read(entry, ids, store):
        if store is ReadSource.POSTGRES:  # another writer keeps changing the mirror
            await set_postgres_title(created.id, f"Drifted {PydanticObjectId()}")
        return await real_read(entry, ids, store)

    monkeypatch.setattr(convergence, "_read", drifting_read)
    await repo.save_form(document)

    assert repo.metrics.mirror_failures[("forms", "save_form")] == 1
    async with Runner(target) as runner:
        assert (await runner.status())["outbox"]["mongo"] == 1


class Interleaved(Runner):
    """A reconcile run that lets ``between`` (a write by the application)
    run once, after reading both stores and before its first write."""

    between = None

    async def _run_between_once(self):
        between, type(self).between = type(self).between, None
        if between is not None:
            await between()

    async def _apply_to_postgres(self, table, writes):
        await self._run_between_once()
        return await super()._apply_to_postgres(table, writes)

    async def _apply_to_mongo(self, coll, table, document, read, row_checksum):
        await self._run_between_once()
        return await super()._apply_to_mongo(coll, table, document, read, row_checksum)


@pytest.mark.parametrize(
    "mode, direction",
    [("dual", "mongo->postgres"), ("postgres_primary_dual", "postgres->mongo")],
)
async def test_reconcile_never_overwrites_a_copy_changed_after_it_read_it(
    target, mode, direction
):
    """Reconcile reads both stores, the application then writes the document
    (primary and mirror), and reconcile's copy, now older, must not land."""
    repo, _ = forms_repo(mode, "save_form")
    created = await new_form(repo)
    # the mirror's copy is stale, as after a failed mirror write
    collection = FormDocument.get_pymongo_collection()
    if mode == "dual":
        await set_postgres_title(created.id, "Stale")
    else:
        await collection.update_one({"_id": created.id}, {"$set": {"title": "Stale"}})
    assert (await verify(target, "forms"))["forms"]["mismatched"] == 1

    async def application_write():
        document = await repo.get_form_document_by_id(created.form_id)
        document.title = "Newer"
        await repo.save_form(document)

    Interleaved.between = application_write
    async with Interleaved(target) as runner:
        result = await runner.reconcile(["forms"], direction=direction)

    assert result["forms"]["skipped"] == 1
    mongo, doc = await both_copies(created.form_id)
    assert mongo["title"] == doc["title"] == "Newer"
    assert await verify(target, "forms") == {}


# -- review follow-ups: a deleted row never stays in the mirror -------------


def primary_of(mode):
    return ReadSource.MONGO if mode == "dual" else ReadSource.POSTGRES


async def make_mirror_stale(mode, form):
    if mode == "dual":
        await set_postgres_title(form.id, "Stale")
    else:
        await FormDocument.get_pymongo_collection().update_one(
            {"_id": form.id}, {"$set": {"title": "Stale"}}
        )


async def delete_in_both_stores(form):
    """Another request deletes the form, primary and mirror."""
    await FormDocument.get_pymongo_collection().delete_one({"_id": form.id})
    async with container.pg_sessionmaker()() as session, session.begin():
        row = await session.get(FormRow, str(form.id))
        if row is not None:
            await session.delete(row)


def touched_form(form):
    with convergence.collecting() as touched:
        PostgresFormRepository(container.pg_sessionmaker())._touch(
            FormRow, [form.id]
        )
    return touched


def delete_before_first_write(monkeypatch, form, after_write=None):
    """The first copy convergence makes was read before another request
    deleted the row in both stores, and lands after that delete."""
    real_write = convergence._write
    state = {"first": True}

    async def write(entry, copies, store):
        if state["first"]:
            state["first"] = False
            await delete_in_both_stores(form)
            await real_write(entry, copies, store)
            if after_write is not None:
                await after_write()
            return
        await real_write(entry, copies, store)

    monkeypatch.setattr(convergence, "_write", write)


@pytest.mark.parametrize("mode", MODES)
async def test_a_delete_landing_before_the_last_copy_is_not_left_in_the_mirror(
    target, mode, monkeypatch
):
    repo, _ = forms_repo(mode, "save_form")
    created = await new_form(repo)
    await make_mirror_stale(mode, created)
    delete_before_first_write(monkeypatch, created)

    # one copying round: the copy is the last one, the re-check after it only reads
    await convergence.converge(touched_form(created), primary_of(mode), rounds=1)

    assert await both_copies(created.form_id) == (None, None)


@pytest.mark.parametrize("mode", MODES)
async def test_a_timeout_right_after_a_copy_still_rechecks_it(
    target, mode, monkeypatch
):
    repo, _ = forms_repo(mode, "save_form")
    created = await new_form(repo)
    await make_mirror_stale(mode, created)
    deadline = time.monotonic() + 0.2

    async def past_the_deadline():
        await asyncio.sleep(max(0.0, deadline - time.monotonic()) + 0.05)

    delete_before_first_write(monkeypatch, created, after_write=past_the_deadline)

    await convergence.converge(
        touched_form(created), primary_of(mode), deadline=deadline
    )

    assert await both_copies(created.form_id) == (None, None)


@pytest.mark.parametrize("mode", MODES)
async def test_a_failed_primary_read_changes_nothing(target, mode, monkeypatch):
    repo, _ = forms_repo(mode, "save_form")
    created = await new_form(repo)
    await make_mirror_stale(mode, created)
    real_read = convergence._read
    primary = primary_of(mode)

    async def read(entry, ids, store):
        if store is primary:
            raise ConnectionError("primary unreachable")
        return await real_read(entry, ids, store)

    monkeypatch.setattr(convergence, "_read", read)
    with pytest.raises(ConnectionError):
        await convergence.converge(touched_form(created), primary)

    mongo, doc = await both_copies(created.form_id)
    stale, fresh = (doc, mongo) if mode == "dual" else (mongo, doc)
    assert stale["title"] == "Stale" and fresh["title"] == "Draft"


@pytest.mark.parametrize(
    "mode, direction",
    [("dual", "mongo->postgres"), ("postgres_primary_dual", "postgres->mongo")],
)
async def test_reconcile_never_brings_back_a_row_deleted_after_it_read_it(
    target, mode, direction
):
    repo, _ = forms_repo(mode, "save_form")
    created = await new_form(repo)
    if mode == "dual":
        await set_postgres_title(created.id, "Stale")  # a row to update
    else:  # a document to insert: missing from Mongo, not deleted by the application
        collection = FormDocument.get_pymongo_collection()
        await collection.database[collection.name].delete_one({"_id": created.id})

    async def application_delete():
        await repo.delete_form(created.form_id)

    Interleaved.between = application_delete
    async with Interleaved(target) as runner:
        result = await runner.reconcile(["forms"], direction=direction)

    assert result["forms"]["skipped"] == 1 and result["forms"]["fixed"] == 0
    assert await both_copies(created.form_id) == (None, None)


async def test_a_reconcile_that_skipped_copies_keeps_the_outbox_open(target):
    repo, _ = forms_repo("dual", "save_form")
    created = await new_form(repo)
    await set_postgres_title(created.id, "Stale")
    await MirrorWriteFailureDocument(
        table_name="FormRepository", row_id=str(created.id), op="save_form", error="-"
    ).insert()

    async def application_write():
        document = await repo.get_form_document_by_id(created.form_id)
        document.title = "Newer"
        await repo.save_form(document)

    Interleaved.between = application_write
    async with Interleaved(target) as runner:
        result = await runner.reconcile(direction="mongo->postgres")
        assert result["forms"]["skipped"] == 1
        assert (await runner.status())["outbox"]["mongo"] == 1


async def test_a_bulk_delete_is_left_to_verify(target, monkeypatch):
    monkeypatch.setattr(routing, "MAX_CONVERGED_IDS", 2)
    repo, _ = forms_repo("dual", "save_form")
    forms = [await new_form(repo, f"Form {i}") for i in range(3)]

    await repo.delete_forms([f.form_id for f in forms])

    assert repo.metrics.mirror_converge_skipped[("forms", "delete_forms")] == 1
    assert not repo.metrics.mirror_failures
    for form in forms:
        assert await both_copies(form.form_id) == (None, None)


# -- 4.0.7 follow-ups: an unchecked copy needs a clean verify; an overall cap --


@pytest.mark.allow_mirror_failures
async def test_a_copy_whose_recheck_fails_stays_open_until_a_clean_verify(
    target, monkeypatch
):
    """The mirror got a copy but the re-check after it failed: the copy may
    come from a stale read. Its outbox entry survives a full reconcile and is
    resolved only by a clean full verify."""
    repo, _ = forms_repo("dual", "save_form")
    created = await new_form(repo)
    document = await repo.get_form_document_by_id(created.form_id)
    document.title = "Changed"
    real_read = convergence._read
    reads = []

    async def read(entry, ids, store):
        reads.append(store)
        if len(reads) == 2:
            return {}  # the mirror looks stale: a copy is made
        if len(reads) == 3:
            raise ConnectionError("primary unreachable for the re-check")
        return await real_read(entry, ids, store)

    monkeypatch.setattr(convergence, "_read", read)
    await repo.save_form(document)
    monkeypatch.setattr(convergence, "_read", real_read)

    assert repo.metrics.mirror_failures[("forms", "save_form")] == 1
    (entry,) = await MirrorWriteFailureDocument.find_all().to_list()
    assert entry.error.startswith("CopyUnverified:")

    from backend.migrate.__main__ import build_target

    async with Runner(build_target(os.environ["DATABASE_URL"])) as runner:
        await runner.reconcile(direction="mongo->postgres")
        assert (await runner.status())["outbox"]["mongo"] == 1  # still open
        outcome = await runner.record_verify(await runner.verify())
        assert outcome["marker"] == "written"
        assert (await runner.status())["outbox"]["mongo"] == 0


@pytest.mark.parametrize("mode", MODES)
async def test_a_hung_copy_is_cut_off_and_still_rechecked(target, mode, monkeypatch):
    """An overall cap bounds the whole step, writes included; the re-check
    still runs after a cut-off copy, and the copy is reported unverified."""
    repo, _ = forms_repo(mode, "save_form")
    created = await new_form(repo)
    await make_mirror_stale(mode, created)
    real_read = convergence._read
    reads_after_write = []
    wrote = []

    async def read(entry, ids, store):
        if wrote:
            reads_after_write.append(store)
        return await real_read(entry, ids, store)

    async def hung_write(entry, copies, store):
        wrote.append(store)
        await asyncio.sleep(30)

    monkeypatch.setattr(convergence, "_read", read)
    monkeypatch.setattr(convergence, "_write", hung_write)
    started = time.monotonic()
    with pytest.raises(convergence.CopyUnverified):
        await convergence.converge(
            touched_form(created),
            primary_of(mode),
            deadline=started + 0.1,
            read_timeout=2,
            cap=started + 0.3,
        )
    assert time.monotonic() - started < 5
    assert reads_after_write == [primary_of(mode), convergence._other(primary_of(mode))]


@pytest.mark.allow_mirror_failures
async def test_a_cut_off_copy_is_reported_even_when_the_recheck_is_clean(
    target, monkeypatch
):
    """The cap cuts a copy off after it was sent: the re-check may find the
    stores alike, yet the write can still land later. It is reported."""
    flags = load_flags({"DB_WRITE_MODE": "dual", "DB_READ_SOURCE": "mongo"})
    repo = RoutingRepository(
        group="forms",
        flags=flags,
        mongo=FormRepository(),
        postgres=PostgresFormRepository(container.pg_sessionmaker()),
        on_mirror_failure=container.outbox_recorder(),
        mirror_timeout_s=0.3,
    )
    created = await new_form(repo)
    document = await repo.get_form_document_by_id(created.form_id)
    document.title = "Changed"
    real_read, real_write = convergence._read, convergence._write
    reads = []

    async def read(entry, ids, store):
        reads.append(store)
        if len(reads) == 2:
            return {}  # the mirror looks stale: a copy is made
        return await real_read(entry, ids, store)

    async def slow_write(entry, copies, store):
        await real_write(entry, copies, store)  # it lands...
        await asyncio.sleep(5)  # ...but is not acknowledged before the cap

    monkeypatch.setattr(convergence, "_read", read)
    monkeypatch.setattr(convergence, "_write", slow_write)
    await repo.save_form(document)

    assert repo.metrics.mirror_failures[("forms", "save_form")] == 1
    (entry,) = await MirrorWriteFailureDocument.find_all().to_list()
    assert entry.error.startswith("CopyUnverified:")


async def test_any_failure_after_a_copy_is_an_unverified_copy(target, monkeypatch):
    repo, _ = forms_repo("dual", "save_form")
    created = await new_form(repo)
    await make_mirror_stale("dual", created)
    real_write = convergence._write

    async def write_then_fail(entry, copies, store):
        await real_write(entry, copies, store)
        raise RuntimeError("connection reset after the copy")

    monkeypatch.setattr(convergence, "_write", write_then_fail)
    with pytest.raises(convergence.CopyUnverified):
        await convergence.converge(touched_form(created), ReadSource.MONGO)


async def test_a_clean_verify_resolves_only_unverified_copies_recorded_before_it(
    target,
):
    from backend.migrate.__main__ import build_target

    async def unverified(row_id):
        await MirrorWriteFailureDocument(
            table_name="FormRepository",
            row_id=row_id,
            op="save_form",
            error="CopyUnverified: forms: test",
        ).insert()

    await unverified("before")
    async with Runner(build_target(os.environ["DATABASE_URL"])) as runner:
        reports = await runner.verify()
        await unverified("during")  # recorded while that verify ran
        outcome = await runner.record_verify(reports)
    assert outcome["marker"] == "written"
    open_entries = await MirrorWriteFailureDocument.find(
        MirrorWriteFailureDocument.resolved_at == None  # noqa: E711 — Beanie query
    ).to_list()
    assert [e.row_id for e in open_entries] == ["during"]
