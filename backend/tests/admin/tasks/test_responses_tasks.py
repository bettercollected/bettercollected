"""The responses data tasks end to end: the runner on its own database, the data
stores (Mongo and Postgres of the app's test setup) seeded with a known dataset.

Both tasks are read through the runner (`world`), so the gates, refusals,
locks, events and audit are the real ones. The datasets are the ones the CLI
scripts' tests use."""

from __future__ import annotations

import json
import os
import re

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import RespondentFeedback

from backend.admin.tasks import catalog
from backend.admin.tasks.catalog import responses_backfill as backfill_meta
from backend.admin.tasks.catalog import responses_check as check_meta
from backend.admin.tasks.impl import responses_backfill_task as backfill_task
from backend.admin.tasks.impl import responses_check as check_task
from backend.admin.tasks.impl.responses_backfill import (
    MongoStore as BackfillMongo,
)
from backend.admin.tasks.impl.responses_backfill import (
    PostgresStore as BackfillPostgres,
)
from backend.admin.tasks.impl.responses_common import (
    StoreConfig,
    open_stores,
)
from backend.admin.tasks.registry import RegistryError, check_meta as registry_check
from backend.admin.tasks.spec import Result
from backend.app.container import container
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.db.models import ResponseDeletionRequestRow
from scripts.backfill_response_workspaces import _parse
from tests.admin.conftest import needs_postgres
from tests.conftest import (
    TEST_DATABASE_URL,
    TEST_MONGO_DB,
    TEST_MONGO_URI,
    _clear_mongo,
    _postgres_configured,
    _truncate_postgres,
)
from tests.scripts.test_backfill_response_workspaces import (
    WS_A,
    WS_B,
    _documents,
    _stamped,
)
from tests.scripts.test_check_undecryptable_values import (
    WS as SCAN_WS,
)
from tests.scripts.test_check_undecryptable_values import (
    _documents as _scan_documents,
)

pytestmark = needs_postgres

PII = "jane.doe@example.org +31 6 12345678"
STORES = ["mongo", "postgres"]


# --------------------------------------------------------------------- helpers
def _stores():
    return {
        "mongo": BackfillMongo(container.database_client()[TEST_MONGO_DB]),
        "postgres": BackfillPostgres(container.pg_engine()),
    }


async def _seed(links, responses, requests=()):
    for document in (*links, *responses, *requests):
        await document.save()
    sessions = container.pg_sessionmaker()
    workspace_forms = PostgresWorkspaceFormRepository(sessions, None)
    responses_repo = PostgresFormResponseRepository(sessions, None, None)
    for link in links:
        await workspace_forms.upsert(link)
    for document in responses:
        await responses_repo.upsert(document)
    for request in requests:
        await responses_repo.upsert(request, row=ResponseDeletionRequestRow)


async def _reset():
    await _clear_mongo(container.database_client()[TEST_MONGO_DB])
    await _truncate_postgres()


@pytest.fixture(autouse=True)
def data_env(monkeypatch, _initialized_app):
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)


@pytest.fixture
async def seeded():
    await _reset()
    await _seed(*_documents())


@pytest.fixture
def tiny_batches(monkeypatch):
    """Two records per batch (the parameter's minimum is 100)."""
    real_backfill, real_check = backfill_task.backfill_store, check_task.check_store

    async def backfill(*args, **kw):
        kw["batch_size"] = 2
        return await real_backfill(*args, **kw)

    async def check(store, opens, batch_size, on_batch=None):
        return await real_check(store, opens, 2, on_batch)

    monkeypatch.setattr(backfill_task, "backfill_store", backfill)
    monkeypatch.setattr(check_task, "check_store", check)


def _hook_after_batch(monkeypatch, world, run_id_box, *, after: int, act):
    """Run ``act()`` once, after the ``after``-th batch of the backfill."""
    real = backfill_task.backfill_store
    state = {"n": 0}

    async def wrapped(*args, on_batch=None, **kw):
        async def hooked(phase, key, seen):
            state["n"] += 1
            if state["n"] == after:
                await act()
            return await on_batch(phase, key, seen)

        return await real(*args, on_batch=hooked, **kw)

    monkeypatch.setattr(backfill_task, "backfill_store", wrapped)


async def _copies(response_id: str) -> list:
    """The workspace of every response row with this response id, sorted
    (unstamped first); the table's row order is not defined."""
    from sqlalchemy import select

    from backend.db.models import FormResponseRow

    async with container.pg_engine().connect() as conn:
        rows = await conn.execute(
            select(FormResponseRow.workspace_id).where(
                FormResponseRow.response_id == response_id
            )
        )
    return sorted((w for (w,) in rows), key=lambda w: (w is not None, w or ""))


async def _later(world, seconds=1):
    world.clock.advance(seconds)
    return world.clock.now()


async def _run(world, task, params, *, dry_run=False, resumes=None):
    run_id = await world.enqueue(
        task, params, dry_run=dry_run, resumes=resumes, requested_at=await _later(world)
    )
    await world.drain()
    return run_id, await world.run(run_id)


async def _everything_recorded(world, *run_ids) -> str:
    """All that the runner stored about the runs, as one string."""
    parts = []
    for run_id in run_ids:
        parts.append(json.dumps(await world.run(run_id), default=str))
        parts.append(json.dumps(await world.events(run_id), default=str))
    parts.append(json.dumps(await world.audit_rows(), default=str))
    return "\n".join(parts)


def _assert_no_content(recorded: str):
    for needle in (
        "an answer",
        "secret note",
        "jane.doe",
        "+31 6",
        "sh_a",
        "sh_b",
        "sh_x",
        "legacy",
        "damaged",
        '"single"',
        '"shared"',
        str(WS_A),
        str(WS_B),
        str(SCAN_WS),
    ):
        assert needle not in recorded, needle


BUCKETS = {
    "unstamped": 5,
    "single_workspace": 1,
    "attributed_by_encryption": 2,
    "ambiguous": 1,
    "orphaned": 1,
}


def _only(buckets: dict) -> dict:
    return {k: v for k, v in buckets.items() if v}


# ------------------------------------------------------------------ backfill: dry run
@pytest.mark.parametrize("store", STORES + ["both"])
async def test_backfill_dry_run_counts_match_and_change_nothing(world, seeded, store):
    before = {n: await _stamped(s) for n, s in _stores().items()}
    run_id, run = await _run(
        world, "responses.backfill_workspaces", {"stores": store}, dry_run=True
    )

    assert run["state"] == "succeeded", run
    result = backfill_meta.BackfillResult.model_validate(run["result"])
    assert result.complete
    wanted = STORES if store == "both" else [store]
    for name in STORES:
        got = getattr(result, name)
        if name not in wanted:
            assert got is None
            continue
        assert got.forms_linked_to_several_workspaces == 1
        assert _only(got.responses.model_dump()) == BUCKETS
        assert _only(got.deletion_requests.model_dump()) == {
            "unstamped": 3,
            "from_response": 2,
            "ambiguous": 1,
        }
        assert got.responses.stamped == 0 and got.deletion_requests.stamped == 0
    assert {n: await _stamped(s) for n, s in _stores().items()} == before
    assert [e["code"] for e in await world.events(run_id)] == [
        f"backfilled_{n}" for n in wanted
    ]
    assert await world.locks() == []
    _assert_no_content(await _everything_recorded(world, run_id))


async def test_a_real_run_needs_a_prior_dry_run(world, seeded):
    _, run = await _run(world, "responses.backfill_workspaces", {"stores": "mongo"})
    assert run["state"] == "refused" and run["refusal_code"] == "dry_run_required"


# ---------------------------------------------------------------- backfill: real run
EXPECTED = {
    "s1": str(WS_A),
    "sh_a": str(WS_A),
    "sh_b": str(WS_B),
    "sh_x": None,  # ambiguous: left alone
    "sh_ok": str(WS_B),
    "o1": None,  # orphaned: left alone
    "dr:sh_a": str(WS_A),
    "dr:sh_x": None,
    "dr:s1": str(WS_A),
}


@pytest.mark.parametrize("store", STORES)
async def test_backfill_stamps_the_attributable_and_is_a_no_op_the_second_time(world, seeded, store):
    params = {"stores": store}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    first_id, first = await _run(world, "responses.backfill_workspaces", params)

    assert first["state"] == "succeeded", first
    got = getattr(backfill_meta.BackfillResult.model_validate(first["result"]), store)
    assert got.responses.stamped == 3 and got.deletion_requests.stamped == 2
    stores = _stores()
    assert await _stamped(stores[store]) == EXPECTED
    other = "postgres" if store == "mongo" else "mongo"
    assert all(v is None for k, v in (await _stamped(stores[other])).items() if k in ("s1", "sh_a"))

    after_first = await _stamped(stores[store])
    second_id, second = await _run(world, "responses.backfill_workspaces", params)
    again = getattr(backfill_meta.BackfillResult.model_validate(second["result"]), store)
    assert again.responses.stamped == 0 and again.deletion_requests.stamped == 0
    # what is left is exactly the ambiguous and the orphaned, counted the same
    assert _only(again.responses.model_dump()) == {"unstamped": 2, "ambiguous": 1, "orphaned": 1}
    assert _only(again.deletion_requests.model_dump()) == {"unstamped": 1, "ambiguous": 1}
    assert await _stamped(stores[store]) == after_first
    assert backfill_meta.META.idempotent is True
    _assert_no_content(await _everything_recorded(world, first_id, second_id))


async def test_backfill_both_stores_stamps_each(world, seeded):
    params = {"stores": "both"}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    _, run = await _run(world, "responses.backfill_workspaces", params)
    assert run["state"] == "succeeded"
    for store in _stores().values():
        assert await _stamped(store) == EXPECTED


# ---------------------------------------------------------------------- filters
@pytest.mark.parametrize("store", STORES)
async def test_backfill_can_be_limited_to_a_workspace_or_forms(world, seeded, store):
    stores = _stores()
    params = {"stores": store, "workspace_id": str(WS_B)}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    _, run = await _run(world, "responses.backfill_workspaces", params)
    got = getattr(backfill_meta.BackfillResult.model_validate(run["result"]), store)
    # only the form linked to B (the shared one): two attributed by key, one ambiguous
    assert _only(got.responses.model_dump()) == {
        "unstamped": 3,
        "attributed_by_encryption": 2,
        "ambiguous": 1,
        "stamped": 2,
    }
    stamped = await _stamped(stores[store])
    assert stamped["sh_a"] == str(WS_A) and stamped["sh_b"] == str(WS_B)
    assert stamped["s1"] is None and stamped["dr:s1"] is None  # other forms untouched

    params = {"stores": store, "form_ids": ["single"]}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    await _run(world, "responses.backfill_workspaces", params)
    stamped = await _stamped(stores[store])
    assert stamped["s1"] == str(WS_A) and stamped["dr:s1"] == str(WS_A)

    # both filters: the forms satisfying both (none: "single" is not linked to B)
    params = {"stores": store, "workspace_id": str(WS_B), "form_ids": ["single"]}
    _, dry = await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    got = getattr(backfill_meta.BackfillResult.model_validate(dry["result"]), store)
    assert got.responses.unstamped == 0


def test_the_script_takes_the_same_filters_and_keeps_its_old_defaults():
    assert vars(_parse(["--apply"])) == {"apply": True, "store": "all", "batch_size": 500}
    args = _parse(["--workspace-id", "w1", "--form-id", "f1", "--form-id", "f2"])
    assert args.workspace_id == "w1" and args.form_ids == ["f1", "f2"]


# ------------------------------------------------------- backfill: resume and cancel
async def _state_after_full_run(world, store):
    await _reset()
    await _seed(*_documents())
    params = {"stores": store}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    await _run(world, "responses.backfill_workspaces", params)
    return await _stamped(_stores()[store])


@pytest.mark.parametrize("store", STORES)
async def test_a_resumed_run_ends_in_the_state_of_an_uninterrupted_one(
    world, seeded, tiny_batches, monkeypatch, store
):
    expected = await _state_after_full_run(world, store)
    assert expected == EXPECTED

    await _reset()
    await _seed(*_documents())
    params = {"stores": store}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)

    first_box = {}

    async def interrupt():
        await world.cancel(first_box["id"])

    # the interruption comes after the first batch (two responses) is stamped
    first_box["id"] = await world.enqueue(
        "responses.backfill_workspaces", params, requested_at=await _later(world)
    )
    _hook_after_batch(monkeypatch, world, first_box, after=1, act=interrupt)
    await world.drain()
    first = await world.run(first_box["id"])
    assert first["state"] == "cancelled"
    partial = await _stamped(_stores()[store])
    assert partial != expected and partial["s1"] == str(WS_A)
    assert first["result"]["complete"] is False

    second_id, second = await _run(
        world, "responses.backfill_workspaces", params, resumes=first_box["id"]
    )
    assert second["state"] == "succeeded", second
    assert await _stamped(_stores()[store]) == expected
    # the resume continued after the cursor: it did not look at the first batch again
    got = getattr(backfill_meta.BackfillResult.model_validate(second["result"]), store)
    assert got.responses.unstamped < 5
    assert await world.locks() == []


@pytest.mark.parametrize("store", STORES)
async def test_cancel_between_batches_stops_cleanly(world, seeded, tiny_batches, monkeypatch, store):
    params = {"stores": store}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    box = {}

    async def cancel():
        await world.cancel(box["id"])

    box["id"] = await world.enqueue(
        "responses.backfill_workspaces", params, requested_at=await _later(world)
    )
    _hook_after_batch(monkeypatch, world, box, after=1, act=cancel)
    await world.drain()
    run = await world.run(box["id"])
    assert run["state"] == "cancelled" and run["result"]["complete"] is False
    stamped = await _stamped(_stores()[store])
    assert stamped["s1"] == str(WS_A) and stamped["sh_b"] is None  # batch 2 never ran
    assert await world.locks() == []
    assert (await world.events(box["id"]))[-1]["code"] == "cancelled"


async def test_the_run_checkpoints_and_reports_progress(world, seeded, tiny_batches):
    params = {"stores": "mongo"}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    run_id, run = await _run(world, "responses.backfill_workspaces", params)
    assert run["state"] == "succeeded"
    assert run["progress"]["done"] == 8  # 5 responses + 3 deletion requests
    from sqlalchemy import text

    async with world.owner.connect() as conn:
        cursor = (
            await conn.execute(
                text("SELECT cursor FROM tasks.checkpoints WHERE run_id = :i ORDER BY id DESC LIMIT 1"),
                {"i": run_id},
            )
        ).scalar()
    assert set(cursor) - {"_fp"} == {"store", "phase", "after", "done"}
    assert cursor["_fp"]  # the keyset fingerprint, so a resume under another keyset is refused


# ---------------------------------------------------------------------- refusals
@pytest.mark.parametrize(
    "task,params",
    [
        ("responses.backfill_workspaces", {"stores": "mongo"}),
        ("responses.check_undecryptable", {"stores": "mongo"}),
    ],
)
async def test_refusals(world, seeded, monkeypatch, task, params):
    dry = task.endswith("backfill_workspaces")

    # no keyset: refused, not "everything ambiguous"
    before = await _stamped(_stores()["mongo"])
    keyset = os.environ["MASTER_ENCRYPTION_KEYSET"]
    monkeypatch.delenv("MASTER_ENCRYPTION_KEYSET")
    _, run = await _run(world, task, params, dry_run=dry)
    assert run["state"] == "refused" and run["refusal_code"] == "keyset_missing"
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", "   ")
    _, run = await _run(world, task, params, dry_run=dry)
    assert run["refusal_code"] == "keyset_missing"
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", "definitely-not-a-keyset")
    _, run = await _run(world, task, params, dry_run=dry)
    assert run["refusal_code"] == "keyset_unreadable"
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", keyset)
    assert await _stamped(_stores()["mongo"]) == before

    # a store that is not configured, named or implied
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    for stores in ("postgres", "both"):
        _, run = await _run(world, task, {**params, "stores": stores}, dry_run=dry)
        assert run["refusal_code"] == "store_not_configured", stores
    monkeypatch.setenv("MONGO_URI", "")
    monkeypatch.setenv("DB_WRITE_MODE", "mongo")
    _, run = await _run(world, task, {**params, "stores": "auto"}, dry_run=dry)
    assert run["refusal_code"] == "store_not_configured"


@pytest.mark.parametrize(
    "task,params",
    [
        ("responses.backfill_workspaces", {"stores": "mongo"}),
        ("responses.check_undecryptable", {"stores": "mongo"}),
    ],
)
async def test_the_keyset_comes_from_the_settings_store_when_the_runner_has_none(
    world, seeded, monkeypatch, task, params
):
    """On a 4.0 stack the keyset lives in the settings store and nowhere else (a new
    stack generates it there; an upgrade imports it): the tasks read it from there,
    as the keyset tasks do. They read only the runner's environment, so every such
    stack refused with keyset_missing until the operator also put the keyset in the
    runner's environment."""
    from tests.admin.tasks.keyset_support import import_keyset

    keyset = os.environ["MASTER_ENCRYPTION_KEYSET"]
    monkeypatch.delenv("MASTER_ENCRYPTION_KEYSET")
    _, run = await _run(world, task, params, dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "keyset_missing"
    await import_keyset(world.admin, keyset)
    _, run = await _run(world, task, params, dry_run=True)
    assert run["state"] == "succeeded", run
    # the store wins over the environment (as for the keyset tasks)
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", "definitely-not-a-keyset")
    _, run = await _run(world, task, params, dry_run=True)
    assert run["state"] == "succeeded", run


@pytest.mark.parametrize(
    "task", ["responses.backfill_workspaces", "responses.check_undecryptable"]
)
async def test_an_empty_store_is_refused_not_reported_clean(world, task, monkeypatch):
    await _reset()  # the wrong database, or one with nothing in it
    for stores in STORES:
        _, run = await _run(
            world, task, {"stores": stores}, dry_run=task.endswith("workspaces")
        )
        assert run["state"] == "refused" and run["refusal_code"] == "store_empty", stores
    assert await world.locks() == []


async def test_an_unreachable_store_is_refused(world, seeded, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://nobody:x@127.0.0.1:1/bctest_nowhere"
    )
    for task in ("responses.check_undecryptable", "responses.backfill_workspaces"):
        _, run = await _run(
            world, task, {"stores": "postgres"}, dry_run=task.endswith("workspaces")
        )
        assert run["refusal_code"] == "store_unreachable", task
        assert "nobody" not in await _everything_recorded(world, run["id"])


async def test_the_backfill_waits_for_another_mutating_task(world, seeded):
    from sqlalchemy import text

    params = {"stores": "mongo"}
    before = await _stamped(_stores()["mongo"])
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    other = await world.enqueue("selftest_slow", {"items": 5}, requested_at=await _later(world))
    async with world.owner.begin() as conn:  # another mutating run holds the global lock
        await conn.execute(
            text("UPDATE tasks.runs SET state = 'running', runner_id = 'other', started_at = now(), heartbeat_at = now() WHERE id = :i"),
            {"i": other},
        )
        await conn.execute(
            text("INSERT INTO tasks.locks (name, run_id, runner_id) VALUES ('mutating:global', :i, 'other')"),
            {"i": other},
        )
    run_id, run = await _run(world, "responses.backfill_workspaces", params)
    assert run["state"] == "refused" and run["refusal_code"] == "lock_held"
    assert await _stamped(_stores()["mongo"]) == before


async def test_a_dry_run_cannot_write_to_the_data_store(seeded):
    config = StoreConfig.from_env()
    async with open_stores(
        config,
        ["postgres"],
        {"postgres": BackfillPostgres},
        read_only=True,
    ) as (store,):
        (key,) = [
            r["key"]
            for r in await store.unstamped("form_responses", None, 1)
        ]
        with pytest.raises(Exception, match="read-only"):
            await store.stamp("form_responses", key, str(WS_A))


# ---------------------------------------------------------------- check_undecryptable
async def _seed_scan():
    await _reset()
    link, responses = _scan_documents()
    extra = FormResponseDocument(
        id=PydanticObjectId(),
        response_id="pii",
        form_id="f1",
        workspace_id=SCAN_WS,
        respondent_feedback=[
            RespondentFeedback(id="e", status="Open", message=f"v1:{PII}".encode())
        ],
    )
    await _seed([link], [*responses, extra])


@pytest.mark.parametrize("store", STORES + ["both"])
async def test_check_counts_per_store_and_field(world, tiny_batches, store):
    await _seed_scan()
    run_id, run = await _run(world, "responses.check_undecryptable", {"stores": store})

    assert run["state"] == "succeeded", run
    result = check_meta.CheckResult.model_validate(run["result"])
    assert result.complete
    wanted = STORES if store == "both" else [store]
    for name in STORES:
        got = getattr(result, name)
        if name not in wanted:
            assert got is None
            continue
        assert got.responses == 5 and got.does_not_decrypt == 3
        assert _only(got.answers.model_dump()) == {"prefixed": 2, "decrypts": 2}
        assert _only(got.hidden_fields.model_dump()) == {"prefixed": 1, "decrypts": 1}
        assert _only(got.internal_answers.model_dump()) == {
            "prefixed": 1,
            "does_not_decrypt": 1,
            "of_which_binary": 1,
        }
        assert _only(got.feedback_message.model_dump()) == {
            "prefixed": 4,
            "decrypts": 2,
            "does_not_decrypt": 2,
            "of_which_text": 2,
        }
    assert run["progress"]["done"] == 5 * len(wanted)
    assert [e["code"] for e in await world.events(run_id)] == [f"scanned_{n}" for n in wanted]
    # read-only: no lock besides the task's own, which is released
    assert await world.locks() == []
    recorded = await _everything_recorded(world, run_id)
    _assert_no_content(recorded)
    for needle in ("legacy", "pii", "secret note"):
        assert needle not in recorded


# ------------------------------------- auto: every store the services still write
WRITTEN = {
    "mongo": ["mongo"],
    "dual": ["mongo", "postgres"],
    "postgres_primary_dual": ["postgres", "mongo"],
    "postgres": ["postgres"],
}


def _write_mode(monkeypatch, default=None, responses=None):
    for name in list(os.environ):
        if name.upper().startswith("DB_WRITE_MODE"):
            monkeypatch.delenv(name)
    if default is not None:
        monkeypatch.setenv("DB_WRITE_MODE", default)
    if responses is not None:
        monkeypatch.setenv("DB_WRITE_MODE__responses", responses)


@pytest.mark.parametrize("default", [None, *WRITTEN])
@pytest.mark.parametrize("responses", [None, *WRITTEN])
def test_auto_is_every_store_the_services_write_never_fewer(monkeypatch, default, responses):
    from backend.admin.tasks.catalog.responses_common import StoreChoice
    from backend.admin.tasks.spec import Refusal

    _write_mode(monkeypatch, default, responses)
    mode = responses or default
    config = StoreConfig.from_env()
    if mode is None:
        with pytest.raises(Refusal) as caught:
            config.resolve(StoreChoice.auto)
        assert caught.value.code == "write_mode_unknown"
        assert config.resolve(StoreChoice.both) == ["mongo", "postgres"]
        return
    written = WRITTEN[mode]
    names = config.resolve(StoreChoice.auto)
    # the written stores first (primary first), then any other configured store
    assert names[: len(written)] == written and sorted(names) == ["mongo", "postgres"]
    # only the written stores configured: exactly those
    if written == ["postgres"]:
        monkeypatch.setenv("MONGO_URI", "")
    if written == ["mongo"]:
        monkeypatch.setenv("DATABASE_URL", "")
    assert StoreConfig.from_env().resolve(StoreChoice.auto) == written
    # a written store the runner has no connection for: refused
    for missing in written:
        monkeypatch.setenv("MONGO_URI", "" if missing == "mongo" else TEST_MONGO_URI)
        monkeypatch.setenv("DATABASE_URL", "" if missing == "postgres" else TEST_DATABASE_URL)
        with pytest.raises(Refusal) as caught:
            StoreConfig.from_env().resolve(StoreChoice.auto)
        assert caught.value.code == "store_not_configured", missing


@pytest.mark.parametrize("mode", list(WRITTEN))
async def test_check_auto_follows_the_write_mode(world, monkeypatch, mode):
    """Mongo gone after the cutover (postgres mode, no MONGO_URI), or no
    Postgres yet (mongo mode): the check runs on what the services write."""
    await _seed_scan()
    _write_mode(monkeypatch, mode)
    written = WRITTEN[mode]
    if "mongo" not in written:
        monkeypatch.setenv("MONGO_URI", "")
    if "postgres" not in written:
        monkeypatch.setenv("DATABASE_URL", "")
    _, run = await _run(world, "responses.check_undecryptable", {})
    assert run["state"] == "succeeded", run
    assert [n for n in STORES if run["result"].get(n)] == sorted(written)


@pytest.mark.parametrize(
    "task", ["responses.backfill_workspaces", "responses.check_undecryptable"]
)
async def test_auto_refuses_without_the_services_write_mode(world, seeded, monkeypatch, task):
    _write_mode(monkeypatch)
    dry = task.endswith("workspaces")
    _, run = await _run(world, task, {}, dry_run=dry)
    assert run["state"] == "refused" and run["refusal_code"] == "write_mode_unknown"
    # the runner says postgres, but the responses group still writes Mongo, which
    # the runner cannot reach: refused, never fewer stores
    _write_mode(monkeypatch, "postgres", "postgres_primary_dual")
    monkeypatch.setenv("MONGO_URI", "")
    _, run = await _run(world, task, {}, dry_run=dry)
    assert run["state"] == "refused" and run["refusal_code"] == "store_not_configured"
    # a named store needs no write mode
    _write_mode(monkeypatch)
    _, run = await _run(world, task, {"stores": "postgres"}, dry_run=dry)
    assert run["state"] == "succeeded", run


async def test_check_cancel_between_batches(world, tiny_batches, monkeypatch):
    await _seed_scan()
    real = check_task.check_store
    box = {}

    async def wrapped(store, opens, batch_size, on_batch=None):
        async def hooked(name, responses):
            if responses == 2:
                await world.cancel(box["id"])
            return await on_batch(name, responses)

        return await real(store, opens, batch_size, hooked)

    monkeypatch.setattr(check_task, "check_store", wrapped)
    box["id"] = await world.enqueue(
        "responses.check_undecryptable", {"stores": "mongo"}, requested_at=await _later(world)
    )
    await world.drain()
    run = await world.run(box["id"])
    assert run["state"] == "cancelled"
    assert run["result"]["complete"] is False and run["result"]["mongo"]["responses"] == 2


async def test_check_does_not_change_the_data(world):
    await _seed_scan()
    stores = _stores()
    from tests.scripts.test_check_undecryptable_values import MongoStore, PostgresStore

    mongo = MongoStore(stores["mongo"].db)
    postgres = PostgresStore(stores["postgres"].engine)
    before = (await mongo.batch(None, 100), await postgres.batch(None, 100))
    _, run = await _run(world, "responses.check_undecryptable", {"stores": "both"})
    assert run["state"] == "succeeded"
    assert (await mongo.batch(None, 100), await postgres.batch(None, 100)) == before


# ------------------------------------------------------------------- registry
def test_the_tasks_declare_what_the_portal_needs():
    for meta, mutating in ((check_meta.META, False), (backfill_meta.META, True)):
        registry_check(meta)  # no secret-looking parameter names, results are counters
        assert meta.mutating is mutating
        assert {r.value for r in meta.refusals} >= {
            "store_not_configured",
            "keyset_missing",
            "store_empty",
        }
    assert backfill_meta.META.resources == ("responses.stamping",)
    assert backfill_meta.META.resumable and backfill_meta.META.requires_prior_dry_run
    assert check_meta.META.resumable is False
    assert {m.name for m in catalog.all_meta({})} == {
        "keyset.add_key",
        "keyset.promote",
        "keyset.reencrypt",
        "keyset.verify",
        "keyset.drop_old",
        "responses.check_undecryptable",
        "responses.backfill_workspaces",
    }


@pytest.mark.parametrize("meta", [check_meta.META, backfill_meta.META])
def test_parameters_are_validated(meta):
    params = meta.params
    assert params().batch_size == 500 and params().stores.value == "auto"
    for bad in ({"batch_size": 99}, {"batch_size": 1001}, {"stores": "all"}, {"surprise": 1}):
        with pytest.raises(Exception):
            params(**bad)


def test_filter_parameters_are_ids_only():
    params = backfill_meta.BackfillParams
    params(workspace_id="65e5501d00000000000000a1", form_ids=["f1", "f2"])
    for bad in ({"workspace_id": "a b"}, {"form_ids": ["x" * 65]}, {"form_ids": ["ok"] * 101}):
        with pytest.raises(Exception):
            params(**bad)


def test_results_may_nest_counters_but_not_free_text():
    from backend.admin.tasks.spec import Id

    class Inner(Result):
        n: int = 0

    class Good(Result):
        inner: Inner = Inner()

    class BadInner(Result):
        note: str

    class Bad(Result):
        inner: BadInner

    from backend.admin.tasks.registry import check_result

    check_result(Good)
    with pytest.raises(RegistryError):
        check_result(Bad)
    assert re.match(r"^[a-z]", "ok") and Id


# ------------------------------------------------- empty filters, dry-run guard, conflicts
def test_an_empty_filter_never_selects_everything():
    params = backfill_meta.BackfillParams
    for bad in ({"form_ids": []}, {"workspace_id": ""}):
        with pytest.raises(Exception):
            params(**bad)
    from backend.admin.tasks.impl.responses_backfill import allowed_forms

    for args in (("w", []), ("", None), (" ", None)):
        with pytest.raises(ValueError):
            allowed_forms({"f": ["w"]}, *args)
    for argv in (["--workspace-id", ""], ["--form-id", ""], ["--form-id", " "]):
        with pytest.raises(SystemExit):
            _parse(argv)


async def test_a_dry_run_cannot_write_to_mongo(seeded):
    from backend.admin.tasks.impl.responses_common import ReadOnlyViolation

    config = StoreConfig.from_env()
    async with open_stores(
        config, ["mongo"], {"mongo": BackfillMongo}, read_only=True
    ) as (store,):
        assert await store.count_responses() > 0  # reads work
        (record,) = await store.unstamped("form_responses", None, 1)
        with pytest.raises(ReadOnlyViolation):
            await store.stamp("form_responses", record["key"], str(WS_A))
        for method in ("update_one", "delete_many", "insert_one", "drop", "bulk_write"):
            with pytest.raises(ReadOnlyViolation):
                getattr(store.db["form_responses"], method)
        with pytest.raises(ReadOnlyViolation):
            await store.db.command("dropDatabase")
    # a writable run does stamp
    async with open_stores(
        config, ["mongo"], {"mongo": BackfillMongo}, read_only=False
    ) as (store,):
        assert await store.stamp("form_responses", record["key"], str(WS_A)) == 1


async def test_a_record_whose_copy_is_already_stamped_is_counted_and_skipped(world):
    await _reset()
    links, responses, requests = _documents()
    twin = FormResponseDocument(
        id=PydanticObjectId(), response_id="dup", form_id="single", provider="google"
    )
    stamped_copy = FormResponseDocument(
        id=PydanticObjectId(),
        response_id="dup",
        form_id="single",
        provider="typeform",
        workspace_id=WS_A,
    )
    await _seed(links, [*responses, twin, stamped_copy], requests)
    params = {"stores": "postgres"}
    await _run(world, "responses.backfill_workspaces", params, dry_run=True)
    run_id, run = await _run(world, "responses.backfill_workspaces", params)

    assert run["state"] == "succeeded", run  # the conflicting row does not fail the run
    got = backfill_meta.BackfillResult.model_validate(run["result"]).postgres
    assert got.responses.conflict == 1 and got.responses.stamped == 3
    # both copies of "dup" are read from the table: ``_stamped`` keys by response
    # id, so with two rows the one it kept depended on the (unordered) scan order
    assert await _copies("dup") == [None, str(WS_A)]  # the other copy stays unstamped
    # a second run finishes too, counting the same row again
    _, again = await _run(world, "responses.backfill_workspaces", params)
    assert again["state"] == "succeeded"
    assert backfill_meta.BackfillResult.model_validate(again["result"]).postgres.responses.conflict == 1
