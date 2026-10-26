"""The keyset rotation tasks end to end, through the real runner: the runner role
on its own database (the settings store, the heartbeats, the audit trail), the
data store (Postgres of the app's test setup, the only one since 4.1) seeded with
the dataset the rotation script's tests use, and the keyset in the settings store.
Mongo is refused (``store_retired``) and never connected to.

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
    monkeypatch.setenv("GOOGLE_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("MONGO_URI", "")  # tests that need one set it


@pytest.fixture(autouse=True)
async def _clean_data(data_env):
    """The suite's cleaning is switched off for tests/admin: start (and leave)
    every test with empty data stores."""
    from backend.app.container import container
    from tests.conftest import _postgres_configured, _truncate_postgres

    async def clean():
        if _postgres_configured():
            await _truncate_postgres()

    await clean()
    yield
    await clean()


class Run(dict):
    """A run row that prints briefly in assertion messages."""

    def __repr__(self):
        keep = ("task", "state", "refusal_code", "dry_run", "error_class", "error_code", "result")
        return "Run(" + ", ".join(f"{k}={self.get(k)!r}" for k in keep if k in self) + ")"


class Flow:
    """One rotation on one store choice."""

    def __init__(self, world, choice, data):
        self.world, self.choice, self.data = world, choice, data
        self.versions = [OLD]  # every keyset the store has held

    async def run(self, task, params=None, *, dry_run=False, resumes=None, ack=True):
        """``keyset.drop_old`` carries ``mongo_retired`` (required since 4.1)
        unless ``ack`` is false."""
        params = dict(params or {})
        if task == "keyset.drop_old" and ack:
            params.setdefault("mongo_retired", True)
        self.world.clock.advance(1)
        run_id = await self.world.enqueue(
            task, params, dry_run=dry_run, resumes=resumes, requested_at=self.world.clock.now()
        )
        await self.world.drain()
        return run_id, Run(await self.world.run(run_id))

    async def both(self, task, params=None, **kw):
        """The dry run, then the real run (the runner demands the dry run)."""
        _, dry = await self.run(task, params, dry_run=True, **kw)
        assert dry["state"] == "succeeded", dry
        run_id, run = await self.run(task, params, **kw)
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
        return dict(extra)

    @property
    def store_choice(self):
        """The tasks' ``stores``: Postgres, the only store."""
        return self.choice

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
        "mongo_retired", "google_in_use", "allow_empty_google", "batch_size",
    }
    for extra in ({"targets": ["responses"]}, {"stores": "mongo"}, {"target": "responses"}):
        with pytest.raises(Exception):
            meta.DropOldParams.model_validate(extra)


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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
    _, counted = await flow.run("keyset.reencrypt", params, dry_run=True)
    assert counted["state"] == "succeeded", counted
    assert counted["result"]["values_stale"] > 0
    assert await stored_values(flow.choice) == before
    run_id, run = await flow.both("keyset.reencrypt", params)
    assert run["state"] == "succeeded", run
    result = meta.ScanResult.model_validate(run["result"])
    assert result.complete and result.primary_id == new_id and result.values_unopenable == 0
    assert result.responses.mongo is None  # Mongo is never covered
    assert await all_readable(flow, stored.value) == {new_id}
    counts = result.responses.postgres
    assert counts.records_readback_failed == 0 and counts.records_reencrypted > 0

    # idempotent: a second run finds everything current and writes nothing
    again_params = flow.params(primary_id=new_id, stores=flow.store_choice)
    again_before = await stored_values(flow.choice)
    _, again = await flow.run("keyset.reencrypt", again_params)
    assert again["state"] == "succeeded", again
    counts = meta.ScanResult.model_validate(again["result"]).responses.postgres
    assert counts.records_reencrypted == 0 and counts.values_reencrypted == 0
    assert await stored_values(flow.choice) == again_before

    # verify: read only, every value opens, counts per key id in the events
    verify_id, verified = await flow.run("keyset.verify", {"stores": flow.store_choice})
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
    async with world.owner.connect() as conn:
        notices = (
            await conn.execute(
                text("SELECT payload FROM admin.notifications "
                     "WHERE kind = 'settings.keyset_changed' ORDER BY created_at")
            )
        ).scalars().all()
    assert [n["action"] for n in notices] == ["add_key", "promote", "drop_old"]
    assert {n["actor"] for n in notices} == {"ops@example.org"}
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
    assert run["state"] == "succeeded", run
    assert run["result"]["values_unopenable"] == 0


async def test_a_keyset_the_runner_may_not_read_is_named_not_called_absent(world, flow):
    """Written before the runner was a reader: the view hides it, the signed
    manifest still lists it."""
    async with world.owner.begin() as conn:
        await conn.execute(text("ALTER TABLE settings.entries DISABLE TRIGGER entries_guard"))
        await conn.execute(
            text("UPDATE settings.entries SET readers = ARRAY['backend', 'google'] WHERE key = :k"),
            {"k": KEY},
        )
        await conn.execute(text("ALTER TABLE settings.entries ENABLE TRIGGER entries_guard"))
    _, run = await flow.run("keyset.add_key", dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "keyset_not_readable_by_runner"


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
    if task == "keyset.drop_old":  # it needs the values moved first
        await flow.beat()
        rp = flow.params(primary_id=new_id, stores=flow.store_choice)
        _, moved = await flow.both("keyset.reencrypt", rp)
        assert moved["state"] == "succeeded", moved
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
        await conn.execute(text("DELETE FROM settings.service_state"))
    await heartbeat(world.owner, "backend", (await flow.stored()).value, revision=(await flow.stored()).revision)
    _, run = await flow.run("keyset.promote", flow.params(new_primary_id=new_id), dry_run=True)
    assert run["refusal_code"] == "consumer_not_reporting"
    _, run = await flow.run(
        "keyset.promote", flow.params(new_primary_id=new_id, google_in_use=False), dry_run=True
    )
    assert run["state"] == "succeeded", run
    # but a google instance that DOES report is always checked
    await heartbeat(
        world.owner, "google", (await flow.stored()).value,
        revision=(await flow.stored()).revision, fp="ks-000000000000",
    )
    _, run = await flow.run(
        "keyset.promote", flow.params(new_primary_id=new_id, google_in_use=False), dry_run=True
    )
    assert run["refusal_code"] == "consumer_missing_key"


@pytest.mark.parametrize(
    "cls, params",
    [
        (meta.PromoteParams, {"new_primary_id": 1}),
        (meta.ReencryptParams, {"primary_id": 1}),
        (meta.DropOldParams, {}),
    ],
)
def test_typeform_acknowledged_is_accepted_and_ignored(cls, params):
    """The Typeform integration is gone: its acknowledgement no longer gates a
    step, and requests that still send it keep validating."""
    plain = cls.model_validate(params)
    for ack in (True, False, "on"):
        parsed = cls.model_validate({**params, "typeform_acknowledged": ack})
        assert parsed == plain and "typeform_acknowledged" not in parsed.model_dump()
    assert "typeform_acknowledged" not in cls.model_json_schema()["properties"]
    with pytest.raises(Exception):
        cls.model_validate({**params, "typeform_reporting": True})  # other names stay refused


# ------------------------------------------------------------- reencrypt
async def test_reencrypt_refuses_a_primary_other_than_the_stored_one(world, flow):
    new_id = await flow.rotate_to_new_primary()
    _, run = await flow.run(
        "keyset.reencrypt", flow.params(primary_id=new_id + 1, stores=flow.store_choice), dry_run=True
    )
    assert run["refusal_code"] == "primary_mismatch"
    old_id = parse_keyset(OLD).primary_key_id
    _, run = await flow.run(
        "keyset.reencrypt", flow.params(primary_id=old_id, stores=flow.store_choice), dry_run=True
    )
    assert run["refusal_code"] == "primary_mismatch"


async def test_reencrypt_never_writes_under_a_published_primary(world, flow):
    old_id = parse_keyset(OLD).primary_key_id
    params = flow.params(primary_id=old_id, stores=flow.store_choice)
    before = await stored_values(flow.choice)
    _, dry = await flow.run("keyset.reencrypt", params, dry_run=True)  # counting is allowed
    assert dry["state"] == "succeeded"
    _, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "refused" and run["refusal_code"] == "published_primary"
    assert await stored_values(flow.choice) == before


async def test_a_store_that_is_not_configured_refuses(world, flow, monkeypatch):
    new_id = await flow.rotate_to_new_primary()
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo-not-used.invalid/")  # does not stand in
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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
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
    await write(world, changed)
    await flow.beat()
    second_id, second = await flow.run("keyset.reencrypt", params, resumes=first_id)
    assert second["state"] == "refused" and second["refusal_code"] == "resume_mismatch"


async def test_a_value_changed_mid_run_is_left_for_the_next_run_and_reported(
    world, flow, monkeypatch
):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    old_cipher = CryptoService(OLD)
    hits = {"n": 0}

    originals = {cls: cls.write for cls in (core.PostgresStore,)}

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

    hook(core.PostgresStore)
    run_id, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded", run
    result = meta.ScanResult.model_validate(run["result"])
    assert result.responses.postgres.records_changed_concurrently == 1
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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
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
    counts = result.responses.postgres
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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    _, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded"
    _, dry = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert dry["state"] == "succeeded"
    real = core.verify_store

    async def cancelling(store, target, rotation, batch_size, on_batch=None):
        async def after(records):
            async with world.owner.begin() as conn:
                await conn.execute(
                    text("UPDATE tasks.runs SET cancel_requested_at = now() WHERE state = 'running'")
                )
            return await on_batch(records)

        return await real(store, target, rotation, batch_size, after)

    monkeypatch.setattr(core, "verify_store", cancelling)
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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    await flow.run("keyset.reencrypt", params)
    # the responses store reads as empty (a wrong or empty database)
    from tests.conftest import _truncate_postgres

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
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
    await flow.run("keyset.reencrypt", params, dry_run=True)
    await flow.run("keyset.reencrypt", params)
    _, run = await flow.run("keyset.drop_old", flow.params(google_in_use=False), dry_run=True)
    assert run["refusal_code"] == "store_empty"
    # "empty because never used" contradicts "in use"
    _, run = await flow.run(
        "keyset.drop_old", flow.params(allow_empty_google=True), dry_run=True
    )
    assert run["refusal_code"] == "google_flags_conflict"
    async with world.owner.begin() as conn:
        await conn.execute(text("DELETE FROM settings.service_state WHERE service = 'google'"))
    _, run = await flow.both(
        "keyset.drop_old", flow.params(allow_empty_google=True, google_in_use=False)
    )
    assert run["state"] == "succeeded", run
    assert len(parse_keyset((await flow.stored()).value).key) == 1


async def test_drop_old_with_one_key_has_nothing_to_drop(world, stores):
    data = Data()
    await seed(stores, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, stores, data)
    await flow.beat()
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.store_choice)
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
    _, run = await flow.run("keyset.verify", {"stores": flow.store_choice})
    assert run["state"] == "succeeded"
    assert run["result"]["values_unopenable"] >= 1


async def test_verify_is_read_only(world, flow):
    before = await stored_values(flow.choice)
    _, run = await flow.run("keyset.verify", {"stores": flow.store_choice})
    assert run["state"] == "succeeded", run
    assert await stored_values(flow.choice) == before


def test_results_carry_ids_and_counters_only():
    from backend.admin.tasks.registry import check_result

    for task in meta.ALL:
        check_result(task.result)


# ------------------------------------------------------ Postgres is the only store
async def prepare(world, choice, **kw):
    """Promoted, consumers on it; the data in Postgres."""
    data = Data(**kw)
    await seed(choice, data)
    await import_keyset(world.admin, OLD)
    flow = Flow(world, choice, data)
    await flow.beat()
    new_id = await flow.rotate_to_new_primary()
    return flow, new_id


@pytest.fixture(autouse=True)
def no_mongo_client(monkeypatch):
    """No task opens a Mongo client, whatever it is asked for."""
    import pymongo

    def refuse(*args, **kwargs):
        raise AssertionError("a Mongo client was created")

    monkeypatch.setattr(pymongo.AsyncMongoClient, "__init__", refuse)


@pytest.mark.parametrize("choice", ["mongo", "both"])
@pytest.mark.parametrize("task", ["keyset.reencrypt", "keyset.verify"])
async def test_mongo_and_both_are_refused_and_nothing_connects(
    world, stores, monkeypatch, task, choice
):
    """``store_retired`` before anything connects, even with a Mongo URI
    configured: nothing is read, written or re-encrypted."""
    flow, new_id = await prepare(world, stores)
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo-not-used.invalid/")
    before = await stored_values(stores)
    params = {"keyset.reencrypt": flow.params(primary_id=new_id), "keyset.verify": {}}[task]
    _, run = await flow.run(task, {**params, "stores": choice}, dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "store_retired", run
    assert await stored_values(stores) == before


@pytest.mark.parametrize("task", ["keyset.reencrypt", "keyset.verify"])
@pytest.mark.parametrize("choice", ["auto", "postgres"])
async def test_auto_and_postgres_cover_postgres_whatever_the_runners_write_mode(
    world, stores, monkeypatch, task, choice
):
    """No write mode is read (an unset, unknown or Mongo-writing one changes
    nothing), and a leftover Mongo URI is not used: both choices cover Postgres
    alone (``auto`` is kept for parameters saved before 4.1)."""
    flow, new_id = await prepare(world, stores)
    for mode in (None, "mongo", "dual", "nonsense"):
        if mode is None:
            monkeypatch.delenv("DB_WRITE_MODE", raising=False)
        else:
            monkeypatch.setenv("DB_WRITE_MODE", mode)
        monkeypatch.setenv("MONGO_URI", "mongodb://mongo-not-used.invalid/")
        params = {"keyset.reencrypt": flow.params(primary_id=new_id), "keyset.verify": {}}[task]
        _, run = await flow.run(task, {**params, "stores": choice}, dry_run=True)
        assert run["state"] == "succeeded", (mode, run)
        assert run["result"]["responses"].get("mongo") is None
        assert run["result"]["responses"]["postgres"]["records"] > 0
    _, run = await flow.both("keyset.reencrypt", flow.params(primary_id=new_id, stores=choice))
    assert run["state"] == "succeeded", run


def test_the_store_rule_plans_postgres_alone():
    from backend.admin.tasks.catalog.responses_common import StoreChoice

    both_urls = {
        "DATABASE_URL": "postgresql+asyncpg://h/app",
        "GOOGLE_DATABASE_URL": "postgresql+asyncpg://h/google",
        "MONGO_URI": "mongodb://h",
    }
    for env in (both_urls, {**both_urls, "DB_WRITE_MODE": "dual"}):
        config = state.DataConfig.from_env(env)
        for target in (core.RESPONSES, core.GOOGLE_CREDENTIALS):
            for choice in (StoreChoice.auto, StoreChoice.postgres):
                assert config.stores_for(target, choice) == ["postgres"]
            for choice in (StoreChoice.mongo, StoreChoice.both):
                assert _refusal(lambda: config.stores_for(target, choice)) == "store_retired"
            assert config.drop_old_stores(target) == ["postgres"]
    # Postgres of the target not configured: refused (a Mongo URI does not stand in)
    no_responses = state.DataConfig.from_env({**both_urls, "DATABASE_URL": ""})
    assert _refusal(lambda: no_responses.drop_old_stores(core.RESPONSES)) == "store_not_configured"
    assert no_responses.drop_old_stores(core.GOOGLE_CREDENTIALS) == ["postgres"]
    no_google = state.DataConfig.from_env({**both_urls, "GOOGLE_DATABASE_URL": ""})
    assert _refusal(lambda: no_google.drop_old_stores(core.GOOGLE_CREDENTIALS)) == (
        "store_not_configured"
    )


def _refusal(call):
    from backend.admin.tasks.spec import Refusal

    with pytest.raises(Refusal) as caught:
        call()
    return caught.value.code


def test_the_config_never_shows_a_connection_string():
    config = state.DataConfig.from_env(
        {
            "DATABASE_URL": "postgresql+asyncpg://user:pw-never-shown@h/app",
            "GOOGLE_DATABASE_URL": "postgresql+asyncpg://user:pw-never-shown@h/g",
            "MONGO_URI": "mongodb://user:pw-never-shown@h",
        }
    )
    assert "pw-never-shown" not in repr(config) and config.mongo_configured is True


def test_mongo_retired_is_a_documented_parameter_off_by_default():
    params = meta.DropOldParams.model_validate({"typeform_acknowledged": True})
    assert params.mongo_retired is False
    schema = meta.DropOldParams.model_json_schema()["properties"]["mongo_retired"]
    assert schema["type"] == "boolean" and "retired" in schema["description"]
    assert {"store_retired", "consumer_writes_mongo"} <= {r.value for r in meta.Refusals}
    assert "mongo_not_retired" not in {r.value for r in meta.Refusals}


async def test_drop_old_needs_the_retirement_confirmed(world, stores):
    """Mongo is not scanned: without ``mongo_retired`` the drop refuses
    (``store_retired``) rather than drop a key that values in Mongo may still
    use; with it, Postgres alone is scanned and the old key goes."""
    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True, ack=False)
    assert run["refusal_code"] == "store_retired", run
    assert len(parse_keyset((await flow.stored()).value).key) == 2
    _, run = await flow.both("keyset.drop_old", flow.params())
    assert run["state"] == "succeeded", run
    assert run["params"]["mongo_retired"] is True
    assert run["result"]["responses"].get("mongo") is None
    assert run["result"]["responses"]["postgres"]["records"] > 0
    assert len(parse_keyset((await flow.stored()).value).key) == 1


async def _record_backfill(collection, *, state, skipped=0):
    from sqlalchemy import insert

    from backend.app.container import container
    from backend.db.models import MigrationProgress

    table = MigrationProgress.__table__
    async with container.pg_engine().begin() as conn:
        await conn.execute(
            insert(table).values(
                collection=collection,
                count=4,
                skipped=skipped,
                batch_size=200,
                state=state,
                last_id=None,
            )
        )


async def test_drop_old_waits_for_the_import_from_4_0(world, stores, monkeypatch):
    """The retirement statement does not prove that the import is over: a later
    backfill could bring in a value on the key that was dropped. The drop
    refuses (``import_incomplete``) while the runner has a Mongo connection, or
    while ``migration_progress`` records an unfinished backfill of the
    responses (or of the forms' links their contexts come from)."""
    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))

    async def drop():
        _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
        return run

    monkeypatch.setenv("MONGO_URI", "mongodb://mongo-not-used.invalid/")
    run = await drop()
    assert run["state"] == "refused" and run["refusal_code"] == "import_incomplete", run
    monkeypatch.setenv("MONGO_URI", "")
    assert (await drop())["state"] == "succeeded"  # nothing recorded: a stack never imported

    await _record_backfill("form_responses", state="running")
    run = await drop()
    assert run["state"] == "refused" and run["refusal_code"] == "import_incomplete", run
    from backend.app.container import container
    from sqlalchemy import text

    async def progress(**values):
        async with container.pg_engine().begin() as conn:
            await conn.execute(text("DELETE FROM app.migration_progress"))
        await _record_backfill(**values)

    await progress(collection="form_responses", state="done", skipped=1)
    assert (await drop())["refusal_code"] == "import_incomplete"
    await progress(collection="workspace_forms", state="paused")
    assert (await drop())["refusal_code"] == "import_incomplete"
    await progress(collection="form_responses", state="done")
    assert (await drop())["state"] == "succeeded"
    assert len(parse_keyset((await flow.stored()).value).key) == 2  # a dry run
    _, run = await flow.both("keyset.drop_old", flow.params())
    assert run["state"] == "succeeded", run
    assert len(parse_keyset((await flow.stored()).value).key) == 1


async def test_drop_old_checks_the_import_again_right_before_the_write(
    world, stores, monkeypatch
):
    """A backfill that starts during a long scan is caught by the check made
    right before the key write: the key is kept."""
    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))
    await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    real = core.verify_store
    started = []

    async def then_a_backfill_starts(*args, **kw):
        result = await real(*args, **kw)
        if not started:  # after the first target's scan
            started.append(True)
            await _record_backfill("form_responses", state="running")
        return result

    monkeypatch.setattr(core, "verify_store", then_a_backfill_starts)
    _, run = await flow.run("keyset.drop_old", flow.params())
    assert run["state"] == "refused" and run["refusal_code"] == "import_incomplete", run
    assert len(parse_keyset((await flow.stored()).value).key) == 2


def _failing_store(sqlstate):
    from sqlalchemy.exc import DBAPIError

    class Orig(Exception):
        pass

    orig = Orig("boom")
    orig.sqlstate = sqlstate

    class Connection:
        async def __aenter__(self):
            raise DBAPIError("SELECT", {}, orig)

        async def __aexit__(self, *exc):
            return False

    class Engine:
        def connect(self):
            return Connection()

    return core.PostgresStore(Engine(), core.RESPONSES)


async def test_the_import_record_is_read_fail_closed():
    """Permission denied refuses; an absent table is "nothing recorded"; any
    other database error fails the task instead of passing the guard."""
    from sqlalchemy.exc import DBAPIError

    from backend.admin.tasks.spec import Refusal

    with pytest.raises(Refusal) as refused:
        await state.check_import_finished(_failing_store("42501"), False)
    assert refused.value.code == "import_state_unreadable"
    await state.check_import_finished(_failing_store("42P01"), False)  # passes
    with pytest.raises(DBAPIError):
        await state.check_import_finished(_failing_store("57014"), False)


async def test_drop_old_still_refuses_old_values_in_postgres(world, stores):
    flow, _new_id = await prepare(world, stores)  # nothing re-encrypted yet
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "values_on_old_key", run


async def test_a_mongo_retired_added_after_signing_is_refused(world, stores):
    """The statement is bound into the signed request: a row whose stored params
    gained mongo_retired after signing never runs."""
    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))
    world.clock.advance(1)
    signed = flow.params()
    run_id = await world.enqueue(
        "keyset.drop_old",
        {**signed, "mongo_retired": True},
        sign_params=signed,
        dry_run=True,
        requested_at=world.clock.now(),
    )
    await world.drain()
    run = await world.run(run_id)
    assert run["state"] == "refused" and run["refusal_code"] == "bad_signature", run
    assert len(parse_keyset((await flow.stored()).value).key) == 2


@pytest.mark.parametrize("missing", ["DATABASE_URL", "GOOGLE_DATABASE_URL"])
async def test_drop_old_needs_postgres_configured_for_every_target(
    world, stores, monkeypatch, missing
):
    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "succeeded", run
    monkeypatch.setenv(missing, "")
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "store_not_configured"


@pytest.mark.parametrize(
    "service, reported, code",
    [
        ("backend", "mongo,postgres", "consumer_writes_mongo"),
        ("backend", "mongo", "consumer_writes_mongo"),
        ("google", "mongo,postgres", "consumer_writes_mongo"),
        ("backend", "", "consumer_write_stores_unknown"),
        ("google", "", "consumer_write_stores_unknown"),
    ],
)
async def test_drop_old_refuses_while_a_service_reports_writing_mongo(
    world, stores, service, reported, code
):
    """A running service says (in its heartbeat) that it still writes Mongo, or
    does not say: the drop is refused, before and right before the key write."""
    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))
    stored = await flow.stored()
    await heartbeat(
        world.owner, service, stored.value, instance="other",
        revision=stored.revision, write_stores=reported,
    )
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == code, run
    assert len(parse_keyset((await flow.stored()).value).key) == 2


@pytest.mark.parametrize("service", ["backend", "google"])
@pytest.mark.parametrize(
    "env",
    [{}, {"DB_WRITE_MODE": "dual"}, {"DB_WRITE_MODE": "mongo", "DB_READ_SOURCE": "mongo"}],
    ids=["unset", "stale-dual", "stale-mongo"],
)
async def test_a_41_service_is_not_taken_for_one_writing_mongo(world, stores, service, env):
    """What a running 4.1 service reports comes from its own environment
    (``write_stores_report``). With ``DB_WRITE_MODE`` unset, or a service-wide
    ``dual`` the backend ignores, it used to say mongo and so refused the drop."""
    from common.settings.write_stores import write_stores_report

    flow, new_id = await prepare(world, stores)
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id))
    stored = await flow.stored()
    await heartbeat(
        world.owner, service, stored.value, instance="other",
        revision=stored.revision, write_stores=write_stores_report(env),
    )
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "succeeded", run


# ------------------------------------------------------- the other drop guards
async def test_drop_old_no_longer_waits_for_typeform(world, flow):
    """Neither an unticked acknowledgement nor a leftover instance of the
    removed Typeform integration reporting in stops the drop any more."""
    new_id = await flow.rotate_to_new_primary()
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id, stores=flow.store_choice))
    stored = await flow.stored()
    await heartbeat(world.owner, "typeform", stored.value, instance="t1", revision=stored.revision)
    _, run = await flow.run(
        "keyset.drop_old", flow.params(typeform_acknowledged=False), dry_run=True
    )
    assert run["state"] == "succeeded", run


async def test_drop_old_reads_with_the_primary_alone(world, flow):
    """A value the primary key alone cannot open stops the drop, even though
    the full keyset opens it."""
    new_id = await flow.rotate_to_new_primary()
    await flow.both("keyset.reencrypt", flow.params(primary_id=new_id, stores=flow.store_choice))
    stored = await flow.stored()
    # on the primary key, but not for the context the record needs
    wrong = CryptoService(stored.value).encrypt("x", "y", b"z")
    assert ciphertext_key_id(wrong) == new_id
    store = next(iter(store_objects(flow.choice)))
    record = next(r for r in await store.batch(None, 10) if store.target.values(r))
    path, old = store.target.values(record)[0]
    assert await store.write(record["id"], [(path, old, wrong)])
    _, run = await flow.run("keyset.drop_old", flow.params(), dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == "values_not_readable", run


async def test_the_reencrypt_apply_run_tells_the_admins_once_and_a_dry_run_no_one(world, flow):
    new_id = await flow.rotate_to_new_primary()
    params = flow.params(primary_id=new_id, stores=flow.store_choice)

    async def notices():
        async with world.owner.connect() as conn:
            return (
                await conn.execute(
                    text("SELECT payload FROM admin.notifications "
                         "WHERE kind = 'settings.keyset_reencrypt'")
                )
            ).scalars().all()

    await flow.run("keyset.reencrypt", params, dry_run=True)
    assert await notices() == []
    run_id, run = await flow.run("keyset.reencrypt", params)
    assert run["state"] == "succeeded"
    found = await notices()
    assert found == [
        {"setting": KEY, "tier": "T4", "action": "reencrypt", "run_id": str(run_id),
         "primary_id": new_id, "actor": "ops@example.org"}
    ]
    # a resume of the same work is a new run: its start tells them again
    _, again = await flow.run("keyset.reencrypt", params)
    assert len(await notices()) == 2
