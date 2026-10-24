"""``responses.purge_orphaned_forms`` end to end: the runner on its own database,
Mongo and Postgres of the app's test setup seeded with the same records, plus
the scope rule on its own.

The dataset (the same in both stores unless a test says otherwise):

* ``kept``: linked to workspace A; responses, a deletion request, a version, a
  group link: never touched;
* ``gone_old`` (responses from 2023) and ``gone_new`` (2024, no form document):
  in no workspace, unstamped responses: the orphans;
* ``link_pg`` / ``link_mongo``: linked in one store only: not orphans;
* ``stamped``: in no workspace, but one response carries a workspace: skipped;
* ``empty``: in no workspace and no responses: never touched.
"""

from __future__ import annotations

import datetime as dt
import json
import os

import pytest
from bson import ObjectId

from backend.admin.tasks.catalog import responses_purge as purge_meta
from backend.admin.tasks.impl import responses_purge as core
from backend.admin.tasks.impl import responses_purge_task as purge_task
from backend.admin.tasks.registry import check_meta as registry_check
from backend.app.container import container
from backend.db import models
from common.db.canonical import canonical_document, checksum
from tests.admin.conftest import needs_postgres
from tests.conftest import (
    TEST_DATABASE_URL,
    TEST_MONGO_DB,
    TEST_MONGO_URI,
    _clear_mongo,
    _postgres_configured,
    _truncate_postgres,
)

pytestmark = needs_postgres

TASK = "responses.purge_orphaned_forms"
WS_A = ObjectId("65e5501d00000000000000a1")
WS_B = ObjectId("65e5501d00000000000000b2")
TITLE = "Secret survey title"
ANSWER = "jane.doe@example.org"
D2023 = dt.datetime(2023, 4, 3, tzinfo=dt.timezone.utc)
D2024 = dt.datetime(2024, 5, 6, tzinfo=dt.timezone.utc)
D2025 = dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc)

COLLECTIONS = {
    "workspace_forms": models.WorkspaceFormRow,
    "forms": models.FormRow,
    "form_versions": models.FormVersionRow,
    "responder_group_form": models.ResponderGroupFormRow,
    "form_responses": models.FormResponseRow,
    "responses_deletion_requests": models.ResponseDeletionRequestRow,
}
ORPHAN_COUNTS = {
    "form_documents": 1,  # gone_new has none
    "responses": 4,
    "deletion_requests": 1,
    "versions": 2,
    "group_links": 1,
}


# --------------------------------------------------------------------- dataset
class _Ids:
    def __init__(self):
        self.n = 0

    def __call__(self, when: dt.datetime = D2025) -> ObjectId:
        self.n += 1
        return ObjectId(f"{int(when.timestamp()):08x}{self.n:016x}")


def _dataset() -> dict:
    oid = _Ids()
    data: dict = {name: [] for name in COLLECTIONS}

    def link(form, workspace):
        return {"_id": oid(), "form_id": form, "workspace_id": workspace, "user_id": "u1"}

    def form(form_id):
        data["forms"].append({"_id": oid(), "form_id": form_id, "title": TITLE})

    def response(form_id, response_id, when=D2025, workspace=None):
        doc = {"_id": oid(when), "form_id": form_id, "response_id": response_id,
               "answers": ANSWER}
        if workspace is not None:
            doc["workspace_id"] = workspace
        data["form_responses"].append(doc)

    # kept: linked, with everything a form has
    data["workspace_forms"].append(link("kept", WS_A))
    form("kept")
    data["form_versions"].append({"_id": oid(), "form_id": "kept", "version": 1, "title": TITLE})
    data["responder_group_form"].append({"_id": oid(), "form_id": "kept", "group_id": oid()})
    response("kept", "k1")
    response("kept", "k2", D2023)
    data["responses_deletion_requests"].append(
        {"_id": oid(), "form_id": "kept", "response_id": "k1"}
    )
    # the orphans
    form("gone_old")
    for version in (1, 2):
        data["form_versions"].append(
            {"_id": oid(), "form_id": "gone_old", "version": version, "title": TITLE}
        )
    data["responder_group_form"].append({"_id": oid(), "form_id": "gone_old", "group_id": oid()})
    response("gone_old", "g1", D2023)
    response("gone_old", "g2", D2023 + dt.timedelta(days=30))
    response("gone_old", "g3", D2023 + dt.timedelta(days=60))
    data["responses_deletion_requests"].append(
        {"_id": oid(), "form_id": "gone_old", "response_id": "g1"}
    )
    response("gone_new", "n1", D2024)  # responses only: the form document is gone
    # not orphans
    form("stamped")
    response("stamped", "s1", D2023)
    response("stamped", "s2", D2023, workspace=WS_B)
    form("empty")
    form("link_pg")
    response("link_pg", "lp1", D2023)
    form("link_mongo")
    response("link_mongo", "lm1", D2023)
    return data


async def _seed(data: dict, skip: dict | None = None) -> None:
    """Both stores; ``skip``: {store: {collection: predicate}} leaves records out."""
    skip = skip or {}
    database = container.database_client()[TEST_MONGO_DB]
    for name, documents in data.items():
        for doc in documents:
            if skip.get("mongo", {}).get(name, lambda d: False)(doc):
                continue
            await database[name].insert_one(dict(doc))
    for name, documents in data.items():
        table = COLLECTIONS[name].__table__
        async with container.pg_engine().begin() as conn:
            for doc in documents:
                if skip.get("postgres", {}).get(name, lambda d: False)(doc):
                    continue
                body = canonical_document(dict(doc))
                await conn.execute(
                    table.insert().values(
                        {"id": str(doc["_id"]), "doc": body, "_bc_checksum": checksum(body)}
                    )
                )
    # the one-store links
    await database["workspace_forms"].insert_one(
        {"_id": ObjectId(), "form_id": "link_mongo", "workspace_id": WS_A, "user_id": "u1"}
    )
    body = canonical_document(
        {"_id": ObjectId(), "form_id": "link_pg", "workspace_id": WS_A, "user_id": "u1"}
    )
    async with container.pg_engine().begin() as conn:
        await conn.execute(
            models.WorkspaceFormRow.__table__.insert().values(
                {"id": body["_id"]["$oid"], "doc": body, "_bc_checksum": checksum(body)}
            )
        )


async def _snapshot() -> dict:
    """Per store: collection -> sorted (form_id, id) of every record."""
    database = container.database_client()[TEST_MONGO_DB]
    mongo = {}
    for name in COLLECTIONS:
        mongo[name] = sorted(
            [(str(d.get("form_id")), str(d["_id"])) async for d in database[name].find({})]
        )
    postgres = {}
    from sqlalchemy import select

    async with container.pg_engine().connect() as conn:
        for name, row in COLLECTIONS.items():
            postgres[name] = sorted(
                (str(f), i) for f, i in await conn.execute(select(row.form_id, row.id))
            )
    return {"mongo": mongo, "postgres": postgres}


def _without(snapshot: dict, forms: set) -> dict:
    return {
        store: {name: [r for r in rows if r[0] not in forms] for name, rows in by.items()}
        for store, by in snapshot.items()
    }


@pytest.fixture(autouse=True)
def data_env(monkeypatch, _initialized_app):
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)


@pytest.fixture
async def seeded():
    await _clear_mongo(container.database_client()[TEST_MONGO_DB])
    await _truncate_postgres()
    await _seed(_dataset())
    return await _snapshot()


async def _later(world, seconds=1):
    world.clock.advance(seconds)
    return world.clock.now()


async def _run(world, params, *, dry_run=False, resumes=None):
    run_id = await world.enqueue(
        TASK, params, dry_run=dry_run, resumes=resumes, requested_at=await _later(world)
    )
    await world.drain()
    return run_id, await world.run(run_id)


async def _dry_then_apply(world, params):
    _, dry = await _run(world, params, dry_run=True)
    assert dry["state"] == "succeeded", dry
    run_id, run = await _run(world, params)
    return dry, run_id, run


def _result(run) -> purge_meta.PurgeResult:
    return purge_meta.PurgeResult.model_validate(run["result"])


async def _recorded(world, *run_ids) -> str:
    parts = []
    for run_id in run_ids:
        parts.append(json.dumps(await world.run(run_id), default=str))
        parts.append(json.dumps(await world.events(run_id), default=str))
    parts.append(json.dumps(await world.audit_rows(), default=str))
    return "\n".join(parts)


EXPECTED = {"expected_forms": 2, "expected_responses": 4}


# ------------------------------------------------------------------ dry run
@pytest.mark.parametrize("stores", ["both", "mongo", "postgres"])
async def test_the_dry_run_counts_the_orphans_and_changes_nothing(world, seeded, stores):
    run_id, run = await _run(world, {"stores": stores}, dry_run=True)
    assert run["state"] == "succeeded", run
    got = _result(run)
    assert (got.forms, got.responses) == (2, 4)
    assert (got.skipped_stamped, got.skipped_newer, got.skipped_changed) == (1, 0, 0)
    assert got.stores_agree and got.expected_counts_match is None and got.complete
    assert (got.oldest_response, got.newest_response) == ("2023-04-03", "2024-05-06")
    covered = ["mongo", "postgres"] if stores == "both" else [stores]
    for name in ("mongo", "postgres"):
        counts = getattr(got, name)
        assert (counts.model_dump() if counts else None) == (
            ORPHAN_COUNTS if name in covered else None
        )
    assert await _snapshot() == seeded
    codes = [e["code"] for e in await world.events(run_id)]
    assert codes == ["orphans_found", *(f"purged_{n}" for n in covered)]
    assert await world.locks() == []


async def test_a_dry_run_with_expected_counts_says_whether_they_match(world, seeded):
    _, run = await _run(world, {"stores": "both", **EXPECTED}, dry_run=True)
    assert _result(run).expected_counts_match is True
    _, run = await _run(
        world, {"stores": "both", "expected_forms": 2, "expected_responses": 5}, dry_run=True
    )
    assert run["state"] == "succeeded" and _result(run).expected_counts_match is False


# --------------------------------------------------------------- the guards
async def test_an_apply_needs_a_prior_dry_run_and_the_expected_counts(world, seeded):
    _, run = await _run(world, {"stores": "both", **EXPECTED})
    assert run["state"] == "refused" and run["refusal_code"] == "dry_run_required"
    _, _, run = await _dry_then_apply(world, {"stores": "both"})
    assert run["state"] == "refused" and run["refusal_code"] == "expected_counts_missing"
    _, _, run = await _dry_then_apply(world, {"stores": "both", "expected_forms": 2})
    assert run["refusal_code"] == "expected_counts_missing"
    assert await _snapshot() == seeded


@pytest.mark.parametrize(
    "expected", [{"expected_forms": 3, "expected_responses": 4}, {"expected_forms": 2, "expected_responses": 3}]
)
async def test_an_apply_refuses_when_the_scope_is_not_what_was_confirmed(world, seeded, expected):
    _, run_id, run = await _dry_then_apply(world, {"stores": "both", **expected})
    assert run["state"] == "refused" and run["refusal_code"] == "expected_counts_mismatch"
    assert await _snapshot() == seeded
    assert await world.locks() == []


async def test_an_apply_refuses_when_the_scope_grew_after_the_dry_run(world, seeded):
    params = {"stores": "both", **EXPECTED}
    _, dry = await _run(world, params, dry_run=True)
    assert _result(dry).expected_counts_match is True
    # a link disappears: one more orphan than the operator confirmed
    database = container.database_client()[TEST_MONGO_DB]
    await database["workspace_forms"].delete_many({"form_id": "link_mongo"})
    _, run = await _run(world, params)
    assert run["refusal_code"] == "expected_counts_mismatch"
    after = await _snapshot()
    assert after["postgres"] == seeded["postgres"]


async def test_an_apply_refuses_when_the_stores_disagree(world, seeded):
    from sqlalchemy import delete

    async with container.pg_engine().begin() as conn:
        await conn.execute(
            delete(models.FormResponseRow).where(models.FormResponseRow.response_id == "g3")
        )
    _, dry = await _run(world, {"stores": "both"}, dry_run=True)
    assert _result(dry).stores_agree is False
    _, _, run = await _dry_then_apply(world, {"stores": "both", **EXPECTED})
    assert run["state"] == "refused" and run["refusal_code"] == "stores_disagree"


async def test_an_empty_store_is_refused(world):
    await _clear_mongo(container.database_client()[TEST_MONGO_DB])
    await _truncate_postgres()
    for stores in ("mongo", "postgres"):
        _, run = await _run(world, {"stores": stores}, dry_run=True)
        assert run["state"] == "refused" and run["refusal_code"] == "store_empty"


async def test_auto_follows_the_write_mode(world, seeded, monkeypatch):
    for name in list(os.environ):
        if name.upper().startswith("DB_WRITE_MODE"):
            monkeypatch.delenv(name)
    _, run = await _run(world, {}, dry_run=True)
    assert run["refusal_code"] == "write_mode_unknown"
    monkeypatch.setenv("DB_WRITE_MODE", "postgres_primary_dual")
    _, run = await _run(world, {}, dry_run=True)
    assert run["state"] == "succeeded"
    assert _result(run).mongo is not None and _result(run).postgres is not None


# ------------------------------------------------------------------- apply
async def test_the_apply_deletes_exactly_the_orphans_in_both_stores(world, seeded):
    params = {"stores": "both", **EXPECTED}
    dry, run_id, run = await _dry_then_apply(world, params)
    assert run["state"] == "succeeded", run
    got = _result(run)
    assert got.complete and (got.forms, got.responses) == (2, 4)
    # the dry run counted exactly what the apply deleted, in each store
    assert got.mongo == _result(dry).mongo == purge_meta.StorePurge(**ORPHAN_COUNTS)
    assert got.postgres == _result(dry).postgres == purge_meta.StorePurge(**ORPHAN_COUNTS)
    after = await _snapshot()
    assert after == _without(seeded, {"gone_old", "gone_new"})
    # both stores hold the same records afterwards
    assert {k: [r for r in v] for k, v in after["mongo"].items() if k != "workspace_forms"} == {
        k: v for k, v in after["postgres"].items() if k != "workspace_forms"
    }
    codes = [e["code"] for e in await world.events(run_id)]
    assert codes[0] == "orphans_found" and codes[-2:] == ["purged_mongo", "purged_postgres"]
    batch = [e for e in await world.events(run_id) if e["code"] == "purged_batch"]
    assert sorted(i for e in batch for i in e["ids"]) == ["gone_new", "gone_old"]
    recorded = await _recorded(world, run_id)
    assert TITLE not in recorded and ANSWER not in recorded
    assert await world.locks() == []


async def test_a_second_run_finds_nothing(world, seeded):
    await _dry_then_apply(world, {"stores": "both", **EXPECTED})
    once = await _snapshot()
    zero = {"stores": "both", "expected_forms": 0, "expected_responses": 0}
    dry, _, run = await _dry_then_apply(world, zero)
    assert run["state"] == "succeeded", run
    for got in (_result(dry), _result(run)):
        assert (got.forms, got.responses) == (0, 0)
        assert got.mongo == got.postgres == purge_meta.StorePurge()
    assert await _snapshot() == once
    assert purge_meta.META.idempotent


async def test_one_store_alone_still_honours_the_links_of_the_other(world, seeded):
    """Covering Mongo alone: the form linked in Postgres only is still kept, and
    Postgres is not written."""
    _, _, run = await _dry_then_apply(world, {"stores": "mongo", **EXPECTED})
    assert run["state"] == "succeeded", run
    after = await _snapshot()
    assert after["postgres"] == seeded["postgres"]
    assert after["mongo"] == _without(seeded, {"gone_old", "gone_new"})["mongo"]


async def test_newest_response_before_narrows_the_scope(world, seeded):
    params = {"stores": "both", "newest_response_before": "2024-01-01"}
    _, dry = await _run(world, params, dry_run=True)
    got = _result(dry)
    assert (got.forms, got.responses, got.skipped_newer) == (1, 3, 1)
    assert got.newest_response == "2023-06-02"
    params.update(expected_forms=1, expected_responses=3)
    _, _, run = await _dry_then_apply(world, params)
    assert run["state"] == "succeeded", run
    assert await _snapshot() == _without(seeded, {"gone_old"})


async def test_a_form_that_changes_before_its_batch_is_skipped(world, seeded, monkeypatch):
    real = core.still_orphans

    async def linked_meanwhile(stores, forms):
        if "gone_old" in forms:
            database = container.database_client()[TEST_MONGO_DB]
            await database["workspace_forms"].insert_one(
                {"_id": ObjectId(), "form_id": "gone_old", "workspace_id": WS_B}
            )
        return await real(stores, forms)

    monkeypatch.setattr(purge_task, "still_orphans", linked_meanwhile)
    params = {"stores": "both", **EXPECTED, "forms_per_batch": 1}
    _, run_id, run = await _dry_then_apply(world, params)
    assert run["state"] == "succeeded", run
    got = _result(run)
    assert got.skipped_changed == 1 and got.mongo.responses == 1  # gone_new only
    skipped = [e for e in await world.events(run_id) if e["code"] == "skipped_changed"]
    assert skipped[0]["ids"] == ["gone_old"]
    after = await _snapshot()
    assert after["postgres"] == _without(seeded, {"gone_new"})["postgres"]


# ------------------------------------------------------- cancel and resume
async def test_a_cancelled_run_resumes_to_the_same_end(world, seeded, monkeypatch):
    params = {"stores": "both", **EXPECTED, "forms_per_batch": 1}
    await _run(world, params, dry_run=True)
    box = {}
    real = core.MongoPurgeStore.delete

    async def cancel_on_first(self, forms):
        out = await real(self, forms)
        if not box.get("done"):
            box["done"] = True
            await world.cancel(box["id"])
        return out

    monkeypatch.setattr(core.MongoPurgeStore, "delete", cancel_on_first)
    box["id"] = await world.enqueue(TASK, params, requested_at=await _later(world))
    await world.drain()
    first = await world.run(box["id"])
    assert first["state"] == "cancelled" and first["result"]["complete"] is False
    assert await _snapshot() == _without(seeded, {"gone_new"})  # the first batch only

    second_id, second = await _run(world, params, resumes=box["id"])
    assert second["state"] == "succeeded", second
    got = _result(second)
    # the totals of the whole purge, the first run's included
    assert (got.forms, got.responses) == (2, 4)
    assert got.mongo == got.postgres == purge_meta.StorePurge(**ORPHAN_COUNTS)
    assert await _snapshot() == _without(seeded, {"gone_old", "gone_new"})
    assert await world.locks() == []


async def test_a_run_that_failed_half_way_through_a_batch_resumes(world, seeded, monkeypatch):
    """The batch is gone from Mongo (the primary of ``both``) but not from
    Postgres: the resume finishes it, and the confirmed counts still add up."""
    params = {"stores": "both", **EXPECTED, "forms_per_batch": 1}
    await _run(world, params, dry_run=True)
    real = core.PostgresPurgeStore.delete

    async def fail(self, forms):
        raise RuntimeError("connection lost")

    monkeypatch.setattr(core.PostgresPurgeStore, "delete", fail)
    first_id, first = await _run(world, params)
    assert first["state"] == "failed", first
    half = await _snapshot()
    assert half["mongo"] == _without(seeded, {"gone_new"})["mongo"]
    assert half["postgres"] == seeded["postgres"]

    monkeypatch.setattr(core.PostgresPurgeStore, "delete", real)
    _, second = await _run(world, params, resumes=first_id)
    assert second["state"] == "succeeded", second
    assert await _snapshot() == _without(seeded, {"gone_old", "gone_new"})
    got = _result(second)
    assert (got.forms, got.responses) == (2, 4)
    assert got.postgres == purge_meta.StorePurge(**ORPHAN_COUNTS)


# ------------------------------------------------------------ the scope rule
def _stats(**forms):
    return {f: core.FormStats(*v) for f, v in forms.items()}


OLD = f"{int(D2023.timestamp()):08x}" + "0" * 16
NEW = f"{int(D2025.timestamp()):08x}" + "0" * 16


def test_a_link_or_a_stamp_in_any_store_keeps_a_form():
    stats = {
        "mongo": _stats(a=(1, 0, OLD, OLD), b=(1, 0, OLD, OLD), c=(2, 0, OLD, NEW)),
        "postgres": _stats(a=(1, 0, OLD, OLD), b=(1, 1, OLD, OLD), c=(2, 0, OLD, NEW)),
    }
    plan = core.plan_orphans({"x"}, stats, ["mongo"])
    # b is stamped in Postgres, which the run does not cover: still kept
    assert plan.forms == ["a", "c"] and plan.skipped_stamped == 1
    plan = core.plan_orphans({"a"}, stats, ["mongo", "postgres"])
    assert plan.forms == ["c"]
    assert plan.store_responses("mongo") == plan.store_responses("postgres") == 2


def test_newest_response_before_uses_the_newest_response_in_any_store():
    stats = {
        "mongo": _stats(a=(1, 0, OLD, OLD)),
        "postgres": _stats(a=(1, 0, OLD, NEW)),
    }
    plan = core.plan_orphans(set(), stats, ["mongo", "postgres"], dt.date(2024, 1, 1))
    assert plan.forms == [] and plan.skipped_newer == 1
    # an id without a readable date is never old enough
    plan = core.plan_orphans(
        set(), {"mongo": _stats(a=(1, 0, "x", "x"))}, ["mongo"], dt.date(2024, 1, 1)
    )
    assert plan.forms == [] and plan.skipped_newer == 1
    plan = core.plan_orphans(set(), {"mongo": _stats(a=(1, 0, "x", "x"))}, ["mongo"])
    assert plan.forms == ["a"] and plan.oldest is None


def test_a_form_without_responses_is_never_in_scope():
    assert core.plan_orphans(set(), {"mongo": {}}, ["mongo"]).forms == []


def test_the_stores_must_agree_per_form():
    stats = {"mongo": _stats(a=(2, 0, OLD, OLD)), "postgres": _stats(a=(1, 0, OLD, OLD))}
    assert core.plan_orphans(set(), stats, ["mongo", "postgres"]).stores_agree() is False
    assert core.plan_orphans(set(), stats, ["mongo"]).stores_agree() is True


# ---------------------------------------------------------------- metadata
def test_the_task_declares_what_the_portal_needs():
    meta = purge_meta.META
    registry_check(meta)
    assert meta.mutating and meta.requires_prior_dry_run and meta.resumable and meta.idempotent
    assert meta.resources == ("responses.purge",)
    assert {r.value for r in meta.refusals} >= {
        "expected_counts_missing",
        "expected_counts_mismatch",
        "stores_disagree",
        "store_empty",
    }


def test_parameters_are_validated():
    params = purge_meta.PurgeParams
    assert params().forms_per_batch == 10 and params().expected_forms is None
    assert params(newest_response_before="2024-06-01").newest_response_before == dt.date(2024, 6, 1)
    for bad in (
        {"forms_per_batch": 0},
        {"forms_per_batch": 21},
        {"expected_forms": -1},
        {"expected_responses": -1},
        {"newest_response_before": "soon"},
        {"stores": "all"},
        {"surprise": 1},
    ):
        with pytest.raises(Exception):
            params(**bad)


def test_the_parameter_form_can_express_every_parameter():
    from backend.admin.services import taskform

    fields = taskform.fields_for(purge_meta.META)
    assert taskform.can_submit(fields)
    assert all(f.supported for f in fields), [f.name for f in fields if not f.supported]
