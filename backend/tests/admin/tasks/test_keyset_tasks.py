"""The keyset rotation tasks end to end, through the real runner: the runner role
on its own database (the settings store, the heartbeats, the audit trail), the
data stores (Mongo and Postgres of the app's test setup) seeded with the
dataset the rotation script's tests use, and the keyset in the settings store.

The sequence add_key -> promote -> reencrypt -> verify -> drop_old runs per
store choice (mongo, postgres, both = a dual write mode), and every guard has
its own refusal test.
"""

from __future__ import annotations

import base64
import json
import os

import pytest
from sqlalchemy import text

from backend.admin.tasks import catalog
from backend.admin.tasks.catalog import keyset as meta
from backend.admin.tasks.impl import keyset_core as core
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.registry import check_meta
from backend.admin.tasks.runner.runner import lock_names
from common.services.keyset import (
    CryptoService,
    add_secondary_key,
    ciphertext_key_id,
    encode_keyset,
    key_digest,
    key_ids,
    parse_keyset,
    promote,
)
from tests.admin.conftest import needs_postgres
from tests.admin.tasks.keyset_support import (
    KEY,
    generated_keyset,
    heartbeat,
    import_keyset,
)
from tests.conftest import TEST_DATABASE_URL
from tests.scripts.test_rotate_response_keyset import (  # noqa: F401 - fixtures
    Data,
    google_table,
    seed,
    store_objects,
    stored_values,
    stores,
)

pytestmark = needs_postgres

OLD = os.environ.get("MASTER_ENCRYPTION_KEYSET", "")
PLAIN = ("an answer", "a hidden value", "an internal note", "a message", "refresh-me")


@pytest.fixture(autouse=True)
def data_env(monkeypatch, _initialized_app):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)


class Flow:
    """One rotation on one store choice."""

    def __init__(self, world, choice, data):
        self.world, self.choice, self.data = world, choice, data
        self.versions = [OLD]  # every keyset the store has held

    async def run(self, task, params=None, *, dry_run=False, resumes=None):
        self.world.clock.advance(1)
        run_id = await self.world.enqueue(
            task, params or {}, dry_run=dry_run, resumes=resumes, requested_at=self.world.clock.now()
        )
        await self.world.drain()
        return run_id, await self.world.run(run_id)

    async def both(self, task, params=None):
        """The dry run, then the real run (the runner demands the dry run)."""
        _, dry = await self.run(task, params, dry_run=True)
        assert dry["state"] == "succeeded", dry
        run_id, run = await self.run(task, params)
        return run_id, run

    async def stored(self):
        async with self.world.tasks.connect() as conn:
            return await state.read_stored(conn, state.runner_keys())

    async def beat(self, *, google=True, **kw):
        """Every consumer restarted onto the store's current keyset and revision."""
        stored = await self.stored()
        kw.setdefault("revision", stored.revision)
        await heartbeat(self.world.owner, "backend", stored.value, **kw)
        await heartbeat(self.world.owner, "backend", stored.value, instance="i2", **kw)
        if google:
            await heartbeat(self.world.owner, "google", stored.value, **kw)
        return stored

    def params(self, **extra):
        return {"typeform_acknowledged": True, **extra}

    async def rotate_to_new_primary(self):
        """add_key and promote, with consumers following each step."""
        _, added = await self.both("keyset.add_key")
        assert added["state"] == "succeeded", added
        new_id = added["result"]["added_key_id"]
        await self.beat()
        _, promoted = await self.both("keyset.promote", self.params(new_primary_id=new_id))
        assert promoted["state"] == "succeeded", promoted
        await self.beat()
        return new_id

    async def recorded(self, *run_ids):
        """Everything the runner and the store keep, as one string."""
        parts = [json.dumps(await self.world.audit_rows(), default=str)]
        async with self.world.owner.connect() as conn:
            for table in ("runs", "run_events", "checkpoints"):
                rows = await conn.execute(text(f"SELECT * FROM tasks.{table}"))
                parts.append(json.dumps([dict(r) for r in rows.mappings()], default=str))
            for table in ("entries", "history", "manifest"):
                rows = await conn.execute(text(f"SELECT * FROM settings.{table}"))
                parts.append(json.dumps([dict(r) for r in rows.mappings()], default=str))
        return "\n".join(parts)


@pytest.fixture
async def flow(world, stores):
    data = Data()
    await seed(stores, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, stores, data)
    await flow.beat()
    return flow


def fragments(*keysets: str):
    """What no record may contain: a keyset, its JSON, its key material."""
    out = []
    for value in keysets:
        parsed = parse_keyset(value)
        out += [value, base64.b64decode(value).decode()[:60]]
        for key in parsed.key:
            out += [base64.b64encode(key.key_data.value).decode(), key_digest(key)]
    return out


async def all_readable(flow, keyset_value):
    """Every encrypted value decrypts to its plaintext under ``keyset_value``;
    returns the key ids the values are on."""
    cipher = CryptoService(keyset_value)
    seen = set()
    found = await stored_values(flow.choice)
    assert found
    for (store, target, record, path), value in found.items():
        seen.add(ciphertext_key_id(value))
        if (target, record, path) not in flow.data.expected:
            continue  # stored by the repository from plain data: no known context
        context, plaintext = flow.data.expected[(target, record, path)]
        assert cipher.decrypt(*context, value) == plaintext
    return seen


# ------------------------------------------------------------- the catalog
def test_the_five_tasks_meet_the_registry_rules():
    for task in meta.ALL:
        check_meta(task)
    names = [t.name for t in meta.ALL]
    assert names == [
        "keyset.add_key",
        "keyset.promote",
        "keyset.reencrypt",
        "keyset.verify",
        "keyset.drop_old",
    ]
    assert [t.name for t in catalog.all_meta({}) if t.name.startswith("keyset.")] == names


def test_flags_resources_and_locks():
    for task in meta.ALL:
        assert task.resources == ("keyset", "responses.encryption")
        assert "keyset" in lock_names(task) and "responses.encryption" in lock_names(task)
        assert task.requires_prior_dry_run == task.mutating
    assert {t.name for t in meta.ALL if t.mutating} == {
        "keyset.add_key", "keyset.promote", "keyset.reencrypt", "keyset.drop_old",
    }
    assert [t.name for t in meta.ALL if t.resumable] == ["keyset.reencrypt"]
    assert not meta.VERIFY.mutating


def test_drop_old_has_no_target_or_store_selection():
    assert set(meta.DropOldParams.model_fields) == {
        "typeform_acknowledged", "google_in_use", "allow_empty_google", "batch_size",
    }
    for extra in ({"targets": ["responses"]}, {"stores": "mongo"}, {"target": "responses"}):
        with pytest.raises(Exception):
            meta.DropOldParams.model_validate({"typeform_acknowledged": True, **extra})


# ------------------------------------------------------------ the sequence
async def test_the_whole_rotation_ends_with_every_value_readable_and_the_old_key_gone(
    world, flow, caplog
):
    old_id = parse_keyset(OLD).primary_key_id
    assert await all_readable(flow, OLD) == {old_id}
    before = await stored_values(flow.choice)

    # add_key: a secondary; the primary does not move; the dry run changes nothing
    _, dry = await flow.run("keyset.add_key", dry_run=True)
    assert dry["state"] == "succeeded" and dry["result"]["changed"] is False
    assert (await flow.stored()).value == OLD
    added_id, added = await flow.both("keyset.add_key")
    assert added["state"] == "succeeded", added
    stored = await flow.stored()
    added_keyset = parse_keyset(stored.value)
    new_id = added["result"]["added_key_id"]
    assert added["result"]["primary_id"] == old_id and len(added_keyset.key) == 2
    assert added_keyset.primary_key_id == old_id and new_id in key_ids(added_keyset)
    flow.versions.append(stored.value)
    # nothing re-encrypted yet
    assert await stored_values(flow.choice) == before

    # promote (the consumers hold the new key as a secondary)
    await flow.beat()
    _, promoted = await flow.both("keyset.promote", flow.params(new_primary_id=new_id))
    assert promoted["state"] == "succeeded", promoted
    assert promoted["result"]["changed"] and promoted["result"]["previous_primary_id"] == old_id
    stored = await flow.stored()
    flow.versions.append(stored.value)
    assert parse_keyset(stored.value).primary_key_id == new_id
    assert len(parse_keyset(stored.value).key) == 2

    # reencrypt: a dry run counts, changes nothing; the real run moves everything
    await flow.beat()
    params = flow.params(primary_id=new_id, stores=flow.choice)
    _, counted = await flow.run("keyset.reencrypt", params, dry_run=True)
    assert counted["state"] == "succeeded", counted
    assert counted["result"]["values_stale"] > 0
    assert await stored_values(flow.choice) == before
    run_id, run = await flow.both("keyset.reencrypt", params)
    assert run["state"] == "succeeded", run
    result = meta.ScanResult.model_validate(run["result"])
    assert result.complete and result.primary_id == new_id and result.values_unopenable == 0
    assert result.responses.model_dump()  # per store counts
    assert await all_readable(flow, stored.value) == {new_id}
    names = {"mongo": ["mongo"], "postgres": ["postgres"], "both": ["mongo", "postgres"]}
    for name in names[flow.choice]:
        counts = getattr(result.responses, name)
        assert counts.records_reencrypted > 0 and counts.records_readback_failed == 0
    if flow.choice == "both":  # the mirror holds the same ciphertext
        found = await stored_values("both")
        by_store = {}
        for (store, target, record, path), value in found.items():
            by_store.setdefault((target, record, path), set()).add(value)
        assert all(len(values) == 1 for values in by_store.values())

    # idempotent: a second run finds everything current and writes nothing
    again_params = flow.params(primary_id=new_id, stores=flow.choice)
    again_before = await stored_values(flow.choice)
    _, again = await flow.run("keyset.reencrypt", again_params)
    assert again["state"] == "succeeded", again
    for name in names[flow.choice]:
        counts = getattr(meta.ScanResult.model_validate(again["result"]).responses, name)
        assert counts.records_reencrypted == 0 and counts.values_reencrypted == 0
    assert await stored_values(flow.choice) == again_before

    # verify: read only, every value opens, counts per key id in the events
    verify_id, verified = await flow.run("keyset.verify", {"stores": flow.choice})
    assert verified["state"] == "succeeded", verified
    got = meta.ScanResult.model_validate(verified["result"])
    assert got.complete and got.values_unopenable == 0 and got.values_stale == 0
    events = await world.events(verify_id)
    assert {e["code"] for e in events} == {"verified"}
    assert any(f"kid_{new_id}" in e["counts"] for e in events), events

    # drop_old: only now
    drop_params = flow.params()
    _, dry = await flow.run("keyset.drop_old", drop_params, dry_run=True)
    assert dry["state"] == "succeeded" and dry["result"]["dropped_count"] == 1
    assert dry["result"]["changed"] is False and len(parse_keyset((await flow.stored()).value).key) == 2
    drop_id, dropped = await flow.run("keyset.drop_old", drop_params)
    assert dropped["state"] == "succeeded", dropped
    assert dropped["result"]["changed"] and dropped["result"]["key_count"] == 1
    final = await flow.stored()
    flow.versions.append(final.value)
    final_keyset = parse_keyset(final.value)
    assert key_ids(final_keyset) == [new_id] and final_keyset.primary_key_id == new_id
    assert await all_readable(flow, final.value) == {new_id}
    # the old key is gone: a keyset with only that key reads nothing
    with pytest.raises(Exception):
        await all_readable(flow, OLD)
    # the store verifier is content with every row, the manifest and the audit trail
    from tests.admin.tasks.keyset_support import settings_service

    assert await settings_service(world.admin).verify() == []
    # one audit row per keyset write: add, promote, drop; the system, with the requester
    rows = await world.audit_rows("settings.task_set")
    assert [r["detail"]["task"] for r in rows] == [
        "keyset.add_key", "keyset.promote", "keyset.drop_old",
    ]
    assert {r["actor_kind"] for r in rows} == {"system"}
    assert {r["detail"]["requested_by"] for r in rows} == {"ops@example.org"}

    # nothing secret anywhere: no keyset (any version), no record content
    recorded = await flow.recorded() + caplog.text
    for needle in fragments(*flow.versions) + list(PLAIN):
        assert needle not in recorded
    assert await world.locks() == []


async def test_a_real_run_needs_its_dry_run(world, flow):
    _, run = await flow.run("keyset.add_key")
    assert run["state"] == "refused" and run["refusal_code"] == "dry_run_required"
    assert (await flow.stored()).value == OLD


# ------------------------------------------------------------- add_key
async def test_add_key_refuses_while_a_rotation_is_under_way(world, flow):
    await flow.both("keyset.add_key")
    _, second = await flow.run("keyset.add_key", dry_run=True)
    assert second["state"] == "refused" and second["refusal_code"] == "rotation_in_progress"


async def test_the_task_keyset_comes_from_the_store_never_the_environment(world, stores):
    # the environment has a keyset (the suite's); with nothing imported, the
    # tasks that write or re-encrypt refuse, and verify (read-only) uses it
    data = Data()
    await seed(stores, data)
    flow = Flow(world, stores, data)
    for task, params in (
        ("keyset.add_key", {}),
        ("keyset.promote", flow.params(new_primary_id=1)),
        ("keyset.reencrypt", flow.params(primary_id=1)),
        ("keyset.drop_old", flow.params()),
    ):
        _, run = await flow.run(task, params, dry_run=True)
        assert run["state"] == "refused" and run["refusal_code"] == "keyset_not_in_store", task
    _, run = await flow.run("keyset.verify", {"stores": stores})
    assert run["state"] == "succeeded" and run["result"]["values_unopenable"] == 0


# ------------------------------------------------------------- promote
async def test_promote_refuses_a_key_that_is_not_in_the_keyset(world, flow):
    _, run = await flow.run("keyset.promote", flow.params(new_primary_id=12345), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "key_not_in_keyset"


async def test_promote_refuses_a_published_key(world, stores):
    data = Data()
    await seed(stores, data)
    # a keyset whose primary is new and which still holds the published key
    fresh = parse_keyset(generated_keyset())
    old = parse_keyset(OLD)
    mixed = parse_keyset(OLD)
    mixed.key.extend(fresh.key)
    mixed.primary_key_id = fresh.primary_key_id
    value = encode_keyset(mixed)
    await import_keyset(world.admin, value)
    flow = Flow(world, stores, data)
    await flow.beat()
    _, run = await flow.run(
        "keyset.promote", flow.params(new_primary_id=old.primary_key_id), dry_run=True
    )
    assert run["state"] == "refused" and run["refusal_code"] == "published_key_to_promote"


@pytest.mark.parametrize(
    "task, params",
    [
        ("keyset.promote", lambda f, nid: f.params(new_primary_id=nid)),
        ("keyset.reencrypt", lambda f, nid: f.params(primary_id=nid)),
        ("keyset.drop_old", lambda f, nid: f.params()),
    ],
)
async def test_every_consumer_must_confirm_before_a_step_that_depends_on_it(
    world, flow, task, params
):
    _, added = await flow.both("keyset.add_key")
    new_id = added["result"]["added_key_id"]
    if task != "keyset.promote":
        await flow.beat()
        _, promoted = await flow.both("keyset.promote", flow.params(new_primary_id=new_id))
        assert promoted["state"] == "succeeded"
    stored = await flow.stored()
    p = params(flow, new_id)

    async def expect(code):
        _, run = await flow.run(task, p, dry_run=True)
        assert run["state"] == "refused" and run["refusal_code"] == code, (code, run)

    # nobody reports
    async with world.owner.begin() as conn:
        await conn.execute(text("DELETE FROM settings.service_state"))
    await expect("consumer_not_reporting")
    # only the backend reports
    await heartbeat(world.owner, "backend", stored.value, revision=stored.revision)
    await expect("consumer_not_reporting")
    # a heartbeat older than two minutes (the service may still be running)
    await flow.beat(age_seconds=300)
    await expect("consumer_stale")
    # the keyset a service holds lacks a key
    await flow.beat(fp="ks-000000000000")
    await expect("consumer_missing_key")
    # it has not restarted since the keyset changed
    await flow.beat(restart_pending=True)
    await expect("consumer_restart_pending")
    await flow.beat(revision=stored.revision - 1)
    await expect("consumer_behind")
    # it overrides the keyset from its environment: the store write would not reach it
    await flow.beat(env=(KEY,))
    await expect("consumer_env_override")
    # all well: accepted
    await flow.beat()
    _, run = await flow.run(task, p, dry_run=True)
    assert run["state"] == "succeeded", run


async def test_google_need_not_report_when_it_is_not_in_use(world, flow):
    _, added = await flow.both("keyset.add_key")
    new_id = added["result"]["added_key_id"]
    async with world.owner.begin() as conn:
        await conn.execute(text("DELETE FROM settings.service_state WHERE service = 'google'"))
    await heartbeat(world.owner, "backend", (await flow.stored()).value, revision=(await flow.stored()).revision)
    _, run = await flow.run("keyset.promote", flow.params(new_primary_id=new_id), dry_run=True)
    assert run["refusal_code"] == "consumer_not_reporting"
    _, run = await flow.run(
        "keyset.promote", flow.params(new_primary_id=new_id, google_in_use=False), dry_run=True
    )
    assert run["state"] == "succeeded", run


@pytest.mark.parametrize(
    "task, params",
    [
        ("keyset.promote", {"new_primary_id": 1}),
        ("keyset.reencrypt", {"primary_id": 1}),
        ("keyset.drop_old", {}),
    ],
)
async def test_the_typeform_integration_must_be_acknowledged(world, flow, task, params):
    # it also receives the keyset, reports no heartbeat and what it stores cannot
    # be checked or re-encrypted from here
    _, run = await flow.run(task, params, dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "typeform_not_acknowledged"
    _, run = await flow.run(task, {**params, "typeform_acknowledged": False}, dry_run=True)
    assert run["refusal_code"] == "typeform_not_acknowledged"


# ------------------------------------------------------------- reencrypt
async def test_reencrypt_refuses_a_primary_other_than_the_stored_one(world, flow):
    new_id = await flow.rotate_to_new_primary()
    _, run = await flow.run(
        "keyset.reencrypt", flow.params(primary_id=new_id + 1, stores=flow.choice), dry_run=True
    )
    assert run["refusal_code"] == "primary_mismatch"
    old_id = parse_keyset(OLD).primary_key_id
    _, run = await flow.run(
        "keyset.reencrypt", flow.params(primary_id=old_id, stores=flow.choice), dry_run=True
    )
    assert run["refusal_code"] == "primary_mismatch"


async def test_reencrypt_never_writes_under_a_published_primary(world, flow):
    old_id = parse_keyset(OLD).primary_key_id
    params = flow.params(primary_id=old_id, stores=flow.choice)
    before = await stored_values(flow.choice)
    _, dry = await flow.run("keyset.reencrypt", params, dry_run=True)  # counting is allowed
    assert dry["state"] == "succeeded"
    _, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "refused" and run["refusal_code"] == "published_primary"
    assert await stored_values(flow.choice) == before


async def test_a_store_that_is_not_configured_refuses(world, flow, monkeypatch):
    new_id = await flow.rotate_to_new_primary()
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("MONGO_URI", "")
    _, run = await flow.run("keyset.reencrypt", flow.params(primary_id=new_id), dry_run=True)
    assert run["refusal_code"] == "store_not_configured"


@pytest.fixture
def tiny_batches(monkeypatch):
    real = core.reencrypt_store

    async def tiny(*args, **kw):
        kw["batch_size"] = 2
        return await real(*args, **kw)

    monkeypatch.setattr(core, "reencrypt_store", tiny)


async def cancel_after_first_batch(monkeypatch, world):
    real = core.reencrypt_store
    state_ = {"done": False}

    async def hooked(*args, on_batch=None, **kw):
        async def after(last, counts):
            if not state_["done"]:
                state_["done"] = True
                async with world.owner.begin() as conn:
                    await conn.execute(
                        text("UPDATE tasks.runs SET cancel_requested_at = now() WHERE state = 'running'")
                    )
            return await on_batch(last, counts)

        return await real(*args, on_batch=after, **kw)

    monkeypatch.setattr(core, "reencrypt_store", hooked)


async def test_an_interrupted_run_resumes_and_finishes(world, flow, monkeypatch, tiny_batches):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    real_walk = core.reencrypt_store
    await cancel_after_first_batch(monkeypatch, world)
    first_id, first = await flow.run("keyset.reencrypt", params)
    assert first["state"] == "cancelled", first  # cancel works between batches
    assert first["result"]["complete"] is False
    stored = await flow.stored()
    assert await all_readable(flow, stored.value) >= {new_id}  # never unreadable half way
    assert await world.locks() == []

    monkeypatch.setattr(core, "reencrypt_store", real_walk)
    second_id, second = await flow.run("keyset.reencrypt", params, resumes=first_id)
    assert second["state"] == "succeeded", second
    assert second["result"]["complete"] is True
    assert await all_readable(flow, stored.value) == {new_id}


async def test_a_resume_with_another_keyset_is_refused(world, flow, monkeypatch, tiny_batches):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    real_walk = core.reencrypt_store
    await cancel_after_first_batch(monkeypatch, world)
    first_id, first = await flow.run("keyset.reencrypt", params)
    assert first["state"] == "cancelled"
    monkeypatch.setattr(core, "reencrypt_store", real_walk)

    # the keyset changes between the runs (another secondary), the consumers follow
    from tests.admin.tasks.test_keyset_store import write

    stored = await flow.stored()
    changed = encode_keyset(add_secondary_key(parse_keyset(stored.value)))
    await write(world.tasks, changed)
    await flow.beat()
    second_id, second = await flow.run("keyset.reencrypt", params, resumes=first_id)
    assert second["state"] == "refused" and second["refusal_code"] == "resume_mismatch"


async def test_a_value_changed_mid_run_is_left_for_the_next_run_and_reported(
    world, flow, monkeypatch
):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    old_cipher = CryptoService(OLD)
    hits = {"n": 0}

    originals = {cls: cls.write for cls in (core.MongoStore, core.PostgresStore)}

    def hook(cls):
        real = cls.write

        async def write(self, record_id, updates):
            if hits["n"] == 0 and self.target.name == "responses":
                hits["n"] = 1
                # the application rewrites the value between our read and our write
                fresh = []
                for path, old, _new in updates:
                    context, plaintext = flow.data.expected[("responses", record_id, path)]
                    fresh.append((path, old, old_cipher.encrypt(*context, plaintext)))
                assert await real(self, record_id, fresh)
            return await real(self, record_id, updates)

        monkeypatch.setattr(cls, "write", write)

    hook(core.MongoStore)
    hook(core.PostgresStore)
    run_id, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded", run
    result = meta.ScanResult.model_validate(run["result"])
    primary = {"mongo": "mongo", "postgres": "postgres", "both": "mongo"}[flow.choice]
    assert getattr(result.responses, primary).records_changed_concurrently == 1
    events = await world.events(run_id)
    assert any(e["counts"].get("records_changed_concurrently") for e in events)
    stored = await flow.stored()
    assert hits["n"] == 1
    # that record still has a value on the old key (the one the app wrote)
    assert await all_readable(flow, stored.value) >= {new_id}

    for cls, original in originals.items():
        monkeypatch.setattr(cls, "write", original)
    _, again = await flow.run("keyset.reencrypt", params)
    assert again["state"] == "succeeded", again
    assert await all_readable(flow, stored.value) == {new_id}


async def test_a_record_that_does_not_read_back_is_not_counted(world, flow, monkeypatch):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    real = core._read_back
    seen = {"n": 0}

    async def once_wrong(store, record_id, updates):
        seen["n"] += 1
        return False if seen["n"] == 1 else await real(store, record_id, updates)

    monkeypatch.setattr(core, "_read_back", once_wrong)
    _, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded", run
    result = meta.ScanResult.model_validate(run["result"])
    primary = {"mongo": "mongo", "postgres": "postgres", "both": "mongo"}[flow.choice]
    counts = getattr(result.responses, primary)
    assert counts.records_readback_failed == 1
    # it was written, so a further run finds it current and counts nothing for it
    stored = await flow.stored()
    assert await all_readable(flow, stored.value) == {new_id}


async def test_values_no_context_opens_stay_and_are_reported(world, stores):
    data = Data(with_orphan=True)  # a response whose workspace nobody knows
    await seed(stores, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, stores, data)
    await flow.beat()
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=stores)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    _, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded", run
    assert run["result"]["values_unopenable"] >= 1
    # and drop_old refuses while any value stays on the old key
    _, dry = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert dry["state"] == "refused" and dry["refusal_code"] == "values_on_old_key"


# ------------------------------------------------------------- drop_old
async def test_drop_old_refuses_while_values_remain_on_an_old_key(world, flow):
    await flow.rotate_to_new_primary()  # promoted, nothing re-encrypted
    run_id, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "values_on_old_key"
    events = await world.events(run_id)
    assert events and all(e["code"] == "counted" for e in events)
    assert any(e["counts"].get("values_stale") for e in events)  # the counts are in the record
    assert len(parse_keyset((await flow.stored()).value).key) == 2


async def test_drop_old_refuses_a_published_primary(world, flow):
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "published_primary"


async def test_drop_old_refuses_when_the_scan_did_not_finish(world, flow, monkeypatch):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    _, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded"
    _, dry = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert dry["state"] == "succeeded"
    real = core.scan

    async def cancelling(store, target, rotation, batch_size, on_batch=None):
        async def after(records):
            async with world.owner.begin() as conn:
                await conn.execute(
                    text("UPDATE tasks.runs SET cancel_requested_at = now() WHERE state = 'running'")
                )
            return await on_batch(records)

        return await real(store, target, rotation, batch_size, after)

    monkeypatch.setattr(core, "scan", cancelling)
    _, run = await flow.run("keyset.drop_old", flow.params())
    # a partial scan is never enough to drop a key
    assert run["state"] == "refused" and run["refusal_code"] == "scan_incomplete", run
    assert len(parse_keyset((await flow.stored()).value).key) == 2


async def test_drop_old_refuses_an_empty_store(world, stores):
    data = Data()
    await seed(stores, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, stores, data)
    await flow.beat()
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=stores)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    await flow.run("keyset.reencrypt", params)
    # the responses store reads as empty (a wrong or empty database)
    from tests.conftest import _clear_mongo, TEST_MONGO_DB, _truncate_postgres
    from backend.app.container import container

    await _clear_mongo(container.database_client()[TEST_MONGO_DB])
    await _truncate_postgres()
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "store_empty"
    assert len(parse_keyset((await flow.stored()).value).key) == 2


async def test_an_empty_google_target_is_accepted_only_when_said_so(world, stores):
    data = Data(with_credentials=False)
    await seed(stores, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, stores, data)
    await flow.beat()
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=stores)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    await flow.run("keyset.reencrypt", params)
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["refusal_code"] == "store_empty"
    _, run = await flow.both("keyset.drop_old", flow.params(allow_empty_google=True))
    assert run["state"] == "succeeded", run
    assert len(parse_keyset((await flow.stored()).value).key) == 1


async def test_drop_old_with_one_key_has_nothing_to_drop(world, stores):
    data = Data()
    await seed(stores, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, stores, data)
    await flow.beat()
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=stores)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    await flow.run("keyset.reencrypt", params)
    await flow.both("keyset.drop_old", flow.params())
    await flow.beat()
    _, run = await flow.both("keyset.drop_old", flow.params())
    assert run["state"] == "succeeded" and run["result"]["nothing_to_drop"] is True
    assert run["result"]["changed"] is False


# -------------------------------------------------------------- verify
async def test_verify_reports_a_value_that_does_not_open(world, flow):
    await flow.beat()
    other = CryptoService(generated_keyset())
    # a value encrypted under a key the store's keyset does not have
    store = next(iter(store_objects(flow.choice)))
    batch = await store.batch(None, 10)
    record = next(r for r in batch if store.target.values(r))
    path, old = store.target.values(record)[0]
    bad = other.encrypt("x", "y", b"z")
    assert await store.write(record["id"], [(path, old, bad)])
    _, run = await flow.run("keyset.verify", {"stores": flow.choice})
    assert run["state"] == "succeeded"
    assert run["result"]["values_unopenable"] >= 1


async def test_verify_is_read_only(world, flow):
    before = await stored_values(flow.choice)
    _, run = await flow.run("keyset.verify", {"stores": flow.choice})
    assert run["state"] == "succeeded", run
    assert await stored_values(flow.choice) == before


def test_results_carry_ids_and_counters_only():
    from backend.admin.tasks.registry import check_result

    for task in meta.ALL:
        check_result(task.result)
