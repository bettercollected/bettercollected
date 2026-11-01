"""The auth key rotation tasks end to end, through the real runner: the runner role
on its own database (the settings store, the heartbeats, the audit trail), the
backend's Postgres (the app test setup) seeded with every kind of value sealed
with the encryption key, and both key rings in the settings store.

``authkeys.add_key -> promote -> reencrypt -> verify -> drop_old`` runs for the
encryption key (``which: aes``) and for the signing secret (``which: jwt``); every
guard has its refusal test; each of the eight sealed value types proves the round
trip old key -> new key (opened with the new key ALONE, through the helper that
sealed it) and that the old key is not needed once it is dropped. Throwaway keys
only: the tests never print or compare a real secret.
"""

from __future__ import annotations

import json
import secrets as stdlib_secrets
from dataclasses import replace

import pytest
from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.services.settings_store import Actor, SettingsService, store_registry
from backend.admin.tasks import catalog
from backend.admin.tasks.catalog import authkeys as meta
from backend.admin.tasks.impl import authkeys_core as core
from backend.admin.tasks.impl import authkeys_state as ring_state
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.registry import check_meta
from backend.admin.tasks.runner.runner import lock_names
from backend.app.services.registration import secrets as registration_secrets
from backend.app.services.webhooks import sealing as webhook_sealing
from common.configs.crypto import Crypto
from common.db.canonical import canonical_document, checksum
from common.settings.key_ring import REPORT_MARK
from tests.admin.conftest import needs_postgres
from tests.admin.tasks.keyset_support import admin_keys, generated_keyset, heartbeat
from tests.conftest import TEST_DATABASE_URL

pytestmark = needs_postgres

OLD_F = Fernet.generate_key().decode()
OLD_J = stdlib_secrets.token_hex(32)
FOREIGN = Fernet.generate_key().decode()  # a key that is in no ring
WS = "65e5501d00000000000000a1"
FORM = "65e5501d00000000000000f1"
ACTION = "65e5501d00000000000000c1"
SERVICE = "65e5501d00000000000000d1"
HOOK = "65e5501d00000000000000e1"
CREDENTIAL = json.dumps({"token": "access-1", "refresh_token": "refresh-1", "scopes": "x"})
PLAINS = ("access-1", "refresh-1", "whsec-scim", "reg-secret-1", "https://hook.example/h?k=1", "hook-secret-1", "token-plain-1")
KEYSET = generated_keyset()  # the heartbeats' keyset value (unused by the ring checks)


@pytest.fixture(autouse=True)
def data_env(monkeypatch, _initialized_app):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("GOOGLE_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("MONGO_URI", "")


@pytest.fixture(autouse=True)
async def _clean_data(data_env):
    from tests.conftest import _postgres_configured, _truncate_postgres

    async def clean():
        if _postgres_configured():
            await _truncate_postgres()

    await clean()
    yield
    await clean()


@pytest.fixture
def no_queue(monkeypatch):
    """The counts the rotation gates on come from definer functions over tables the
    admin test database does not have (tested for real in test_authkeys_counts)."""
    counts = {"jobs": 0, "sessions": 0, "drafts": 0, "cutoffs": []}

    async def jobs(conn):
        return counts["jobs"]

    async def sessions(conn, at):
        counts["cutoffs"].append(at)
        return counts["sessions"]

    async def drafts(conn, at):
        return counts["drafts"]

    monkeypatch.setattr(ring_state, "jobs_pending", jobs)
    monkeypatch.setattr(ring_state, "sessions_on_previous", sessions)
    monkeypatch.setattr(ring_state, "drafts_on_previous", drafts)
    return counts


class Run(dict):
    def __repr__(self):
        keep = ("task", "state", "refusal_code", "dry_run", "error_class", "error_code", "result")
        return "Run(" + ", ".join(f"{k}={self.get(k)!r}" for k in keep if k in self) + ")"


async def app_engine():
    return create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)


async def insert(table: str, **fields) -> str:
    oid = ObjectId()
    doc = canonical_document({"_id": oid, **fields})
    engine = await app_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO app.{table} (id, doc, _bc_checksum) "
                    "VALUES (:id, CAST(:doc AS jsonb), :c)"
                ),
                {"id": str(oid), "doc": json.dumps(doc), "c": checksum(doc)},
            )
    finally:
        await engine.dispose()
    return str(oid)


async def doc_of(table: str, record_id: str) -> dict:
    engine = await app_engine()
    try:
        async with engine.connect() as conn:
            value = (
                await conn.execute(text(f"SELECT doc FROM app.{table} WHERE id = :i"), {"i": record_id})
            ).scalar_one()
    finally:
        await engine.dispose()
    return json.loads(value) if isinstance(value, str) else value


async def checksum_ok(table: str, record_id: str) -> bool:
    engine = await app_engine()
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(f"SELECT doc, _bc_checksum FROM app.{table} WHERE id = :i"), {"i": record_id}
                )
            ).one()
    finally:
        await engine.dispose()
    doc = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    return checksum(doc) == row[1]


class Seeded:
    """The rows holding one value of every kind sealed with the encryption key."""

    def __init__(self):
        self.ids: dict = {}


async def seed(key: str = OLD_F) -> Seeded:
    crypto = Crypto(key)
    seeded = Seeded()
    bag = lambda: {  # noqa: E731 - one bag per row
        ACTION: [
            {"name": "Credentials", "value": crypto.encrypt(CREDENTIAL), "required": False},
            {"name": "Token", "value": crypto.encrypt("token-plain-1"), "required": False},
            {"name": "Empty", "value": "", "required": False},
            {"name": "Plain", "value": "plain-text-not-sealed", "required": False},
        ]
    }
    seeded.ids["forms"] = await insert("forms", form_id=FORM, secrets=bag())
    seeded.ids["form_versions"] = await insert("form_versions", form_id=FORM, version=1, secrets=bag())
    seeded.ids["actions"] = await insert(
        "actions", name="sheets", secrets=[{"name": "Token", "value": crypto.encrypt("token-plain-1")}]
    )
    seeded.ids["workspace_actions"] = await insert(
        "workspace_actions",
        workspace_id=WS,
        action_id=ACTION,
        secrets=[{"name": "Credentials", "value": crypto.encrypt(CREDENTIAL)}],
    )
    seeded.ids["scim_directories"] = await insert(
        "scim_directories",
        workspace_id=WS,
        polis_directory_id="dir-1",
        webhook_secret=crypto.encrypt("whsec-scim"),
    )
    seeded.ids["registration_services"] = await insert(
        "registration_services",
        workspace_id=WS,
        name="crm",
        kind="http",
        secret_sealed=registration_secrets.seal(crypto, WS, SERVICE, "reg-secret-1"),
    )
    seeded.ids["form_webhooks"] = await insert(
        "form_webhooks",
        workspace_id=WS,
        form_id=FORM,
        url_sealed=webhook_sealing.seal_url(crypto, WS, HOOK, "https://hook.example/h?k=1"),
        secret_sealed=registration_secrets.seal(crypto, WS, HOOK, "hook-secret-1"),
    )
    return seeded


def check_round_trip(docs: dict, crypto: Crypto) -> None:
    """Every sealed value opens with ``crypto`` and means what it meant: through
    the very helper that sealed it, so the envelope (workspace, row, purpose)
    survived the re-encryption."""
    for table in ("forms", "form_versions"):
        items = docs[table]["secrets"][ACTION]
        assert json.loads(crypto.decrypt(items[0]["value"])) == json.loads(CREDENTIAL)
        assert crypto.decrypt(items[1]["value"]) == "token-plain-1"
        assert items[2]["value"] == ""  # an empty value is left alone
        assert items[3]["value"] == "plain-text-not-sealed"  # so is one that is not a token
    assert crypto.decrypt(docs["actions"]["secrets"][0]["value"]) == "token-plain-1"
    assert json.loads(crypto.decrypt(docs["workspace_actions"]["secrets"][0]["value"])) == json.loads(CREDENTIAL)
    assert crypto.decrypt(docs["scim_directories"]["webhook_secret"]) == "whsec-scim"
    assert (
        registration_secrets.unseal(crypto, WS, SERVICE, docs["registration_services"]["secret_sealed"])
        == "reg-secret-1"
    )
    hook = docs["form_webhooks"]
    assert webhook_sealing.unseal_url(crypto, WS, HOOK, hook["url_sealed"]) == "https://hook.example/h?k=1"
    assert registration_secrets.unseal(crypto, WS, HOOK, hook["secret_sealed"]) == "hook-secret-1"


async def all_docs(seeded: Seeded) -> dict:
    return {table: await doc_of(table, record_id) for table, record_id in seeded.ids.items()}


def values_of(docs: dict) -> list:
    out = []
    for table, doc in docs.items():
        out += [v for _, v in core.TARGETS[table].values(doc)]
    return out


class Flow:
    def __init__(self, world):
        self.world = world
        self.members: list = []  # every ring text the store held (never printed)

    async def run(self, task, params=None, *, dry_run=False, resumes=None):
        self.world.clock.advance(1)
        run_id = await self.world.enqueue(
            task, dict(params or {}), dry_run=dry_run, resumes=resumes,
            requested_at=self.world.clock.now(),
        )
        await self.world.drain()
        return run_id, Run(await self.world.run(run_id))

    async def both(self, task, params=None, **kw):
        _, dry = await self.run(task, params, dry_run=True, **kw)
        assert dry["state"] == "succeeded", dry
        return await self.run(task, params, **kw)

    async def stored(self, which):
        async with self.world.tasks.connect() as conn:
            return await state.read_stored(
                conn, state.runner_keys(), ring_state.SETTING[meta.Which(which)]
            )

    async def ring(self, which):
        stored = await self.stored(which)
        self.members.append(stored.value)
        return stored, ring_state.parse_ring(meta.Which(which), stored.value)

    async def beat(self, which="aes", *, google=True, **kw):
        """Every service restarted onto the store's current revision."""
        stored = await self.stored(which)
        kw.setdefault("revision", stored.revision)
        kw.setdefault("fp", "ks-000000000000" + REPORT_MARK)  # a build with ring support
        await heartbeat(self.world.owner, "backend", KEYSET, **kw)
        await heartbeat(self.world.owner, "backend", KEYSET, instance="i2", **kw)
        await heartbeat(self.world.owner, "auth", KEYSET, **kw)
        if google:
            await heartbeat(self.world.owner, "google", KEYSET, **kw)
        return stored

    async def recorded(self) -> str:
        parts = [json.dumps(await self.world.audit_rows(), default=str)]
        async with self.world.owner.connect() as conn:
            for table in ("runs", "run_events", "checkpoints"):
                rows = await conn.execute(text(f"SELECT * FROM tasks.{table}"))
                parts.append(json.dumps([dict(r) for r in rows.mappings()], default=str))
            rows = await conn.execute(text("SELECT payload FROM admin.notifications"))
            parts.append(json.dumps([dict(r) for r in rows.mappings()], default=str))
        return "\n".join(parts)


async def import_ring(engine, key: str, value: str):
    change = await SettingsService(engine, store_registry(), admin_keys()).import_once(
        key, value, Actor("cli")
    )
    assert change is not None
    return change


async def make_flow(world) -> Flow:
    await import_ring(world.admin, "AUTH_AES_HEX_KEY", OLD_F)
    await import_ring(world.admin, "AUTH_JWT_SECRET", OLD_J)
    flow = Flow(world)
    flow.members = [OLD_F, OLD_J]
    await flow.beat("aes")
    return flow


@pytest.fixture
async def flow(world, no_queue):
    return await make_flow(world)


def add(which, **extra):
    return {"which": which, "ring_build_deployed": True, **extra}


# ------------------------------------------------------------- the catalog
def test_the_five_tasks_meet_the_registry_rules():
    for task in meta.ALL:
        check_meta(task)
    names = [t.name for t in meta.ALL]
    assert names == [
        "authkeys.add_key", "authkeys.promote", "authkeys.reencrypt",
        "authkeys.verify", "authkeys.drop_old",
    ]
    assert [t.name for t in catalog.all_meta({}) if t.name.startswith("authkeys.")] == names


def test_flags_resources_and_locks():
    for task in meta.ALL:
        # exclusive with the keyset family: both write the one settings manifest
        assert task.resources == ("authkeys", "keyset")
        assert {"authkeys", "keyset"} <= set(lock_names(task))
        assert task.requires_prior_dry_run == task.mutating
    assert {t.name for t in meta.ALL if t.mutating} == {
        "authkeys.add_key", "authkeys.promote", "authkeys.reencrypt", "authkeys.drop_old",
    }
    assert [t.name for t in meta.ALL if t.resumable] == ["authkeys.reencrypt"]
    assert not meta.VERIFY.mutating


def test_no_parameter_or_result_can_carry_a_key():
    for task in meta.ALL:
        for name in task.params.model_fields:
            assert name in {
                "which", "ring_build_deployed", "google_in_use", "new_primary_id",
                "external_consumers_updated", "primary_id", "targets", "batch_size",
                "keep_id", "accept_sign_out", "accept_draft_link_loss", "allow_empty",
                "jobs_on_postgres",
            }, name
    for extra in ({"ring": "x"}, {"secret": "x"}, {"member": "x"}):
        with pytest.raises(Exception):
            meta.AddKeyParams.model_validate({"which": "aes", **extra})


# ------------------------------------------- the encryption key, whole sequence
async def test_the_whole_aes_rotation_moves_every_value_and_the_old_key_is_not_needed_after(
    world, flow, caplog
):
    seeded = await seed()
    before = await all_docs(seeded)
    check_round_trip(before, Crypto(OLD_F))
    old_ring = ring_state.parse_ring(meta.Which.aes, OLD_F)

    # add_key: the new key is the SECOND member; the dry run changes nothing
    _, dry = await flow.run("authkeys.add_key", add("aes"), dry_run=True)
    assert dry["state"] == "succeeded" and dry["result"]["changed"] is False
    assert (await flow.stored("aes")).value == OLD_F
    _, added = await flow.both("authkeys.add_key", add("aes"))
    assert added["state"] == "succeeded", added
    stored, ring = await flow.ring("aes")
    new_id = added["result"]["added_key_id"]
    assert len(ring.members) == 2 and ring.primary == OLD_F and ring.ids[1] == new_id
    assert added["result"]["primary_id"] == old_ring.primary_id
    NEW_F = ring.members[1]
    assert Crypto(OLD_F).member_count == 1 and Crypto(stored.value).member_count == 2
    assert await all_docs(seeded) == before  # nothing re-encrypted yet

    # promote: the new key signs/encrypts; the old one still reads
    await flow.beat("aes")
    _, promoted = await flow.both(
        "authkeys.promote", {"which": "aes", "new_primary_id": new_id, "external_consumers_updated": True}
    )
    assert promoted["state"] == "succeeded", promoted
    assert promoted["result"]["changed"] and promoted["result"]["previous_primary_id"] == old_ring.primary_id
    stored, ring = await flow.ring("aes")
    assert ring.members == (NEW_F, OLD_F) and ring.primary_id == new_id
    assert Crypto(stored.value).decrypt(before["scim_directories"]["webhook_secret"]) == "whsec-scim"

    # reencrypt: a dry run counts and changes nothing; the real run moves everything
    await flow.beat("aes")
    params = {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
    _, counted = await flow.run("authkeys.reencrypt", params, dry_run=True)
    assert counted["state"] == "succeeded", counted
    assert counted["result"]["values_stale"] == 10  # 2+2 form secrets, 1+1 actions, 1 directory, 1 service, 2 webhook
    assert await all_docs(seeded) == before
    _, run = await flow.both("authkeys.reencrypt", params)
    assert run["state"] == "succeeded", run
    result = meta.ScanResult.model_validate(run["result"])
    assert result.complete and result.primary_id == new_id and result.values_unopenable == 0
    assert result.forms.records_reencrypted == 1 and result.forms.values_reencrypted == 2
    assert result.forms.records_readback_failed == 0 and result.forms.values_plain == 1
    after = await all_docs(seeded)
    assert after != before
    # every value now opens with the NEW key alone, through the helper that sealed it
    check_round_trip(after, Crypto(NEW_F))
    for value in values_of(after):
        with pytest.raises(InvalidToken):
            Crypto(OLD_F).decrypt(value)  # and the old key alone opens none of them
    for table, record_id in seeded.ids.items():
        assert await checksum_ok(table, record_id), table  # the row checksum follows the document

    # idempotent: a second run finds everything current and writes nothing
    _, again = await flow.run("authkeys.reencrypt", params)
    assert again["state"] == "succeeded", again
    again_result = meta.ScanResult.model_validate(again["result"])
    assert all(
        getattr(again_result, name).records_reencrypted == 0 for name in core.TARGETS
    )
    assert await all_docs(seeded) == after

    # verify: read only; everything is on the first key
    verify_id, verified = await flow.run("authkeys.verify", {"which": "aes"})
    assert verified["state"] == "succeeded", verified
    got = meta.ScanResult.model_validate(verified["result"])
    assert got.complete and got.values_stale == 0 and got.values_unopenable == 0
    assert got.gates.checked and got.gates.jobs_pending == 0
    events = await world.events(verify_id)
    assert {e["code"] for e in events} <= {"verified", "counted"}

    # drop_old: only now, with the kept key named
    drop = {"which": "aes", "keep_id": new_id, "external_consumers_updated": True}
    _, unconfirmed = await flow.run("authkeys.drop_old", drop, dry_run=True)
    assert unconfirmed["refusal_code"] == "jobs_routing_unconfirmed"  # Temporal-routed jobs are not counted
    drop = {**drop, "jobs_on_postgres": True}
    _, dry = await flow.run("authkeys.drop_old", drop, dry_run=True)
    assert dry["state"] == "succeeded" and dry["result"]["dropped_count"] == 1
    assert dry["result"]["changed"] is False and dry["result"]["ready"] is True
    assert (await flow.stored("aes")).value == stored.value
    _, dropped = await flow.run("authkeys.drop_old", drop)
    assert dropped["state"] == "succeeded", dropped
    assert dropped["result"]["changed"] and dropped["result"]["key_count"] == 1
    final, final_ring = await flow.ring("aes")
    assert final.value == NEW_F and final_ring.ids == [new_id]
    # the old key is gone from the ring: the stored value alone reads everything
    check_round_trip(await all_docs(seeded), Crypto(final.value))
    for value in (v for v in values_of(await all_docs(seeded)) if core.is_fernet_token(v)):
        assert Crypto(final.value).opening_position(value) == 0  # the only member opens each
        assert Crypto(OLD_F).opening_position(value) is None  # the old key opens none
    # dropping again changes nothing
    _, nothing = await flow.both("authkeys.drop_old", drop)
    assert nothing["state"] == "succeeded" and nothing["result"]["nothing_to_drop"] is True

    # the store verifier is content with every row, the manifest and the audit trail
    from tests.admin.tasks.keyset_support import settings_service

    assert await settings_service(world.admin).verify() == []
    rows = await world.audit_rows("settings.task_set")
    assert [r["detail"]["task"] for r in rows] == [
        "authkeys.add_key", "authkeys.promote", "authkeys.drop_old",
    ]
    assert {r["actor_kind"] for r in rows} == {"system"}
    assert {r["target_id"] for r in rows} == {"AUTH_AES_HEX_KEY"}
    async with world.owner.connect() as conn:
        notices = (
            await conn.execute(
                text("SELECT payload FROM admin.notifications "
                     "WHERE kind = 'settings.keyset_changed' ORDER BY created_at")
            )
        ).scalars().all()
    assert [(n["setting"], n["action"]) for n in notices] == [
        ("AUTH_AES_HEX_KEY", "add_key"), ("AUTH_AES_HEX_KEY", "promote"), ("AUTH_AES_HEX_KEY", "drop_old"),
    ]
    # nothing secret anywhere: no ring member, no plaintext
    recorded = await flow.recorded() + caplog.text
    for member in {m for text_ in flow.members for m in text_.split(",")}:
        assert member not in recorded
    for needle in PLAINS:
        assert needle not in recorded
    assert await world.locks() == []


async def test_the_dry_run_reports_what_will_move(world, flow):
    await seed()
    await flow.both("authkeys.add_key", add("aes"))
    stored, ring = await flow.ring("aes")
    await flow.beat("aes")
    await flow.both(
        "authkeys.promote",
        {"which": "aes", "new_primary_id": ring.ids[1], "external_consumers_updated": True},
    )
    await flow.beat("aes")
    _, counted = await flow.run(
        "authkeys.reencrypt",
        {"which": "aes", "primary_id": ring.ids[1]},
        dry_run=True,
    )
    result = meta.ScanResult.model_validate(counted["result"])
    # forms and versions: 2 sealed + 1 empty each; actions 1; workspace actions 1; scim 1;
    # registration 1; webhooks 2
    assert (result.forms.values, result.forms.values_stale, result.forms.values_plain) == (2, 2, 1)
    assert result.form_versions.values_stale == 2 and result.actions.values_stale == 1
    assert result.workspace_actions.values_stale == 1 and result.scim_directories.values_stale == 1
    assert result.registration_services.values_stale == 1 and result.form_webhooks.values_stale == 2
    assert result.values_stale == 10 and result.values_unopenable == 0


# --------------------------------------------------- the signing secret, whole
async def test_the_whole_jwt_rotation_with_the_signing_counts(world, flow, no_queue):
    await flow.beat("jwt")
    old_ring = ring_state.parse_ring(meta.Which.jwt, OLD_J)
    _, added = await flow.both("authkeys.add_key", add("jwt"))
    assert added["state"] == "succeeded", added
    stored, ring = await flow.ring("jwt")
    new_id = added["result"]["added_key_id"]
    assert ring.primary == OLD_J and len(ring.members) == 2 and ring.ids[1] == new_id
    assert ring.members[1] != OLD_J and len(ring.members[1]) == 64

    # a drop before the promote is refused: the kept key must be the first member
    await flow.beat("jwt")
    _, early = await flow.run(
        "authkeys.drop_old", {"which": "jwt", "keep_id": new_id}, dry_run=True
    )
    assert early["state"] == "refused" and early["refusal_code"] == "primary_mismatch"

    _, promoted = await flow.both("authkeys.promote", {"which": "jwt", "new_primary_id": new_id})
    assert promoted["state"] == "succeeded", promoted
    stored, ring = await flow.ring("jwt")
    assert ring.primary_id == new_id and ring.members[1] == OLD_J
    await flow.beat("jwt")

    # nothing to re-encrypt for a signing secret
    _, none = await flow.run(
        "authkeys.reencrypt", {"which": "jwt", "primary_id": new_id}, dry_run=True
    )
    assert none["state"] == "refused" and none["refusal_code"] == "nothing_to_reencrypt"

    # the drop counts from a verify made after the promote: without one it is refused
    drop = {"which": "jwt", "keep_id": new_id}
    await refused(flow, "authkeys.drop_old", drop, "promotion_not_verified")
    # sessions made before the promote are counted; the drop needs the statement
    no_queue["sessions"], no_queue["drafts"] = 4, 2
    _, verified = await flow.run("authkeys.verify", {"which": "jwt"})
    gates = meta.ScanResult.model_validate(verified["result"]).gates
    assert (gates.sessions_on_previous, gates.drafts_on_previous) == (4, 2)
    # the count runs from when every service was proven to sign with the new key (this
    # verify), never from the promote's own write: until the last service restarted it
    # still signed with the previous key
    async with world.owner.connect() as conn:
        started = (
            await conn.execute(
                text("SELECT min(started_at) FROM tasks.runs WHERE task = 'authkeys.verify' "
                     "AND state = 'succeeded' AND params ->> 'which' = 'jwt'")
            )
        ).scalar_one()
        promote_started = (
            await conn.execute(
                text("SELECT max(started_at) FROM tasks.runs WHERE task = 'authkeys.promote' AND NOT dry_run")
            )
        ).scalar_one()
    assert promote_started < started
    _, dry = await flow.run("authkeys.drop_old", drop, dry_run=True)
    assert dry["state"] == "succeeded" and dry["result"]["ready"] is False
    assert dry["result"]["gates"]["sessions_on_previous"] == 4
    _, undried = await flow.run("authkeys.drop_old", drop)  # needs a succeeded dry run first
    assert undried["state"] == "refused"
    accepted = {**drop, "accept_sign_out": True}
    await flow.run("authkeys.drop_old", accepted, dry_run=True)
    _, still = await flow.run("authkeys.drop_old", accepted)
    assert still["state"] == "refused" and still["refusal_code"] == "draft_links_not_accepted"
    both = {**accepted, "accept_draft_link_loss": True}
    _, dry = await flow.run("authkeys.drop_old", both, dry_run=True)
    assert dry["result"]["ready"] is True
    _, dropped = await flow.run("authkeys.drop_old", both)
    assert dropped["state"] == "succeeded", dropped
    assert dropped["result"]["changed"] and dropped["result"]["dropped_count"] == 1
    final, final_ring = await flow.ring("jwt")
    assert final_ring.members == (ring.members[0],) and final_ring.ids == [new_id]
    assert old_ring.primary not in final.value
    recorded = await flow.recorded()
    for member in {m for text_ in flow.members for m in text_.split(",")}:
        assert member not in recorded
    # the other ring was never touched
    assert (await flow.stored("aes")).value == OLD_F


async def test_a_jwt_drop_with_nothing_on_the_old_key_needs_no_statement(world, flow, no_queue):
    _, added = await flow.both("authkeys.add_key", add("jwt"))
    new_id = added["result"]["added_key_id"]
    await flow.beat("jwt")
    await flow.both("authkeys.promote", {"which": "jwt", "new_primary_id": new_id})
    await flow.beat("jwt")
    _, verified = await flow.run("authkeys.verify", {"which": "jwt"})
    assert verified["state"] == "succeeded", verified
    _, dropped = await flow.both("authkeys.drop_old", {"which": "jwt", "keep_id": new_id})
    assert dropped["state"] == "succeeded" and dropped["result"]["changed"], dropped


async def test_a_real_run_needs_its_dry_run(world, flow):
    _, run = await flow.run("authkeys.add_key", add("aes"))
    assert run["state"] == "refused" and run["refusal_code"] == "dry_run_required"
    assert (await flow.stored("aes")).value == OLD_F


# -------------------------------------------------------------- the refusals
async def refused(flow, task, params, code):
    _, run = await flow.run(task, params, dry_run=True)
    assert run["state"] == "refused" and run["refusal_code"] == code, (code, run)


async def test_add_key_refusals(world, flow):
    await refused(flow, "authkeys.add_key", {"which": "aes"}, "ring_build_unconfirmed")
    await flow.both("authkeys.add_key", add("aes"))
    await flow.beat("aes")
    await refused(flow, "authkeys.add_key", add("aes"), "rotation_in_progress")
    # the other ring is independent
    _, jwt_run = await flow.run("authkeys.add_key", add("jwt"), dry_run=True)
    assert jwt_run["state"] == "succeeded"


async def test_a_jwt_secret_with_a_comma_cannot_be_extended(world, no_queue):
    comma = "short-part,another-short-part-of-a-hand-made-secret-1234"
    await import_ring(world.admin, "AUTH_JWT_SECRET", comma)
    flow = Flow(world)
    await flow.beat("jwt")
    await refused(flow, "authkeys.add_key", add("jwt"), "secret_has_separator")


async def test_the_ring_comes_from_the_store_never_the_environment(world, no_queue, monkeypatch):
    monkeypatch.setenv("AUTH_AES_HEX_KEY", OLD_F)
    flow = Flow(world)
    for task, params in (
        ("authkeys.add_key", add("aes")),
        ("authkeys.promote", {"which": "aes", "new_primary_id": 1}),
        ("authkeys.reencrypt", {"which": "aes", "primary_id": 1}),
        ("authkeys.verify", {"which": "aes"}),
        ("authkeys.drop_old", {"which": "aes", "keep_id": 1}),
    ):
        await refused(flow, task, params, "key_not_in_store")


async def test_a_ring_the_runner_may_not_read_is_named_and_the_host_command_fixes_it(world, no_queue):
    """A row written before the runner was a reader hides from it; the signed
    manifest still lists it. ``regrant_readers`` re-seals the same value."""
    registry = store_registry()
    spec = registry.get("AUTH_AES_HEX_KEY")
    legacy = replace(spec, readers=tuple(r for r in spec.readers if r != "tasks"))
    service = SettingsService(world.admin, registry, admin_keys())
    from backend.admin.repositories import settings as repo

    async with world.admin.begin() as conn:
        revision = await repo.lock(conn)
        await service._write(conn, legacy, None, OLD_F, Actor("cli"), "import", revision)
    flow = Flow(world)
    await refused(flow, "authkeys.add_key", add("aes"), "key_not_readable_by_runner")
    # dry run of the host command: reports, writes nothing
    assert (await service.regrant_readers("AUTH_AES_HEX_KEY", Actor("cli"), apply=False)).changed is False
    await refused(flow, "authkeys.add_key", add("aes"), "key_not_readable_by_runner")
    change = await service.regrant_readers("AUTH_AES_HEX_KEY", Actor("cli"))
    assert change.changed and change.version == 2
    assert await service.regrant_readers("AUTH_AES_HEX_KEY", Actor("cli")) is None  # nothing left to do
    stored = await flow.stored("aes")
    assert stored.value == OLD_F and stored.version == 2
    rows = await world.audit_rows("settings.grant_readers")
    assert len(rows) == 1 and rows[0]["actor_kind"] == "cli"
    with pytest.raises(Exception):
        await service.regrant_readers("AUTH_AES_HEX_KEY", Actor("admin"))
    with pytest.raises(Exception):
        await service.regrant_readers("API_ALLOWED_WORKSPACES", Actor("cli"))


async def test_promote_refusals(world, flow):
    await refused(flow, "authkeys.promote", {"which": "aes", "new_primary_id": 1}, "no_rotation_in_progress")
    _, added = await flow.both("authkeys.add_key", add("aes"))
    new_id = added["result"]["added_key_id"]
    await refused(flow, "authkeys.promote", {"which": "aes", "new_primary_id": 12345}, "member_not_in_ring")
    await flow.beat("aes")
    await refused(
        flow, "authkeys.promote", {"which": "aes", "new_primary_id": new_id}, "external_consumers_unconfirmed"
    )
    # promoting the key that is already first changes nothing and needs nothing
    _, same = await flow.run(
        "authkeys.promote",
        {"which": "aes", "new_primary_id": ring_state.parse_ring(meta.Which.aes, OLD_F).primary_id},
        dry_run=True,
    )
    assert same["state"] == "succeeded" and same["result"]["changed"] is False


@pytest.mark.parametrize("task", ["authkeys.promote", "authkeys.reencrypt", "authkeys.drop_old"])
async def test_every_service_must_confirm_before_a_step_that_depends_on_it(world, flow, task):
    await seed()
    _, added = await flow.both("authkeys.add_key", add("aes"))
    new_id = added["result"]["added_key_id"]
    if task != "authkeys.promote":
        await flow.beat("aes")
        _, promoted = await flow.both(
            "authkeys.promote", {"which": "aes", "new_primary_id": new_id, "external_consumers_updated": True}
        )
        assert promoted["state"] == "succeeded", promoted
    if task == "authkeys.drop_old":
        await flow.beat("aes")
        _, moved = await flow.both(
            "authkeys.reencrypt", {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
        )
        assert moved["state"] == "succeeded", moved
    stored = await flow.stored("aes")
    params = {
        "authkeys.promote": {"which": "aes", "new_primary_id": new_id, "external_consumers_updated": True},
        "authkeys.reencrypt": {"which": "aes", "primary_id": new_id, "external_consumers_updated": True},
        "authkeys.drop_old": {
            "which": "aes", "keep_id": new_id, "external_consumers_updated": True,
            "jobs_on_postgres": True,
        },
    }[task]

    async def expect(code):
        await refused(flow, task, params, code)

    async with world.owner.begin() as conn:
        await conn.execute(text("DELETE FROM settings.service_state"))
    await expect("consumer_not_reporting")
    await heartbeat(world.owner, "backend", KEYSET, revision=stored.revision)
    await expect("consumer_not_reporting")  # auth and google are missing
    await heartbeat(world.owner, "auth", KEYSET, revision=stored.revision)
    await expect("consumer_not_reporting")  # google is missing
    await flow.beat("aes", age_seconds=300)
    await expect("consumer_stale")
    await flow.beat("aes", restart_pending=True)
    await expect("consumer_restart_pending")
    await flow.beat("aes", revision=stored.revision - 1)
    await expect("consumer_behind")
    await flow.beat("aes", env=("AUTH_AES_HEX_KEY",))
    await expect("consumer_env_override")
    # an override of the OTHER ring does not matter
    await flow.beat("aes", env=("AUTH_JWT_SECRET",))
    _, run = await flow.run(task, params, dry_run=True)
    assert run["state"] == "succeeded", run
    # google may be left out when it is not in use
    async with world.owner.begin() as conn:
        await conn.execute(text("DELETE FROM settings.service_state WHERE service = 'google'"))
    await refused(flow, task, params, "consumer_not_reporting")
    _, run = await flow.run(task, {**params, "google_in_use": False}, dry_run=True)
    assert run["state"] == "succeeded", run


async def test_reencrypt_refusals(world, flow):
    seeded = await seed()
    _, added = await flow.both("authkeys.add_key", add("aes"))
    new_id = added["result"]["added_key_id"]
    await flow.beat("aes")
    await flow.both(
        "authkeys.promote", {"which": "aes", "new_primary_id": new_id, "external_consumers_updated": True}
    )
    await flow.beat("aes")
    await refused(
        flow, "authkeys.reencrypt", {"which": "aes", "primary_id": new_id + 1}, "primary_mismatch"
    )
    # the workers' statement is demanded of the real run, not of the count
    _, dry = await flow.run("authkeys.reencrypt", {"which": "aes", "primary_id": new_id}, dry_run=True)
    assert dry["state"] == "succeeded"
    _, real = await flow.run("authkeys.reencrypt", {"which": "aes", "primary_id": new_id})
    assert real["state"] == "refused" and real["refusal_code"] == "external_consumers_unconfirmed"
    assert values_of(await all_docs(seeded))  # nothing was touched


async def test_reencrypt_needs_the_data_store(world, flow, monkeypatch):
    _, added = await flow.both("authkeys.add_key", add("aes"))
    await flow.beat("aes")
    monkeypatch.setenv("DATABASE_URL", "")
    await refused(
        flow, "authkeys.reencrypt",
        {"which": "aes", "primary_id": ring_state.parse_ring(meta.Which.aes, OLD_F).primary_id},
        "store_not_configured",
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://nobody:x@127.0.0.1:1/none")
    await refused(
        flow, "authkeys.reencrypt",
        {"which": "aes", "primary_id": ring_state.parse_ring(meta.Which.aes, OLD_F).primary_id},
        "store_unreachable",
    )


async def promoted_flow(flow):
    """add_key and promote done, consumers following."""
    _, added = await flow.both("authkeys.add_key", add("aes"))
    new_id = added["result"]["added_key_id"]
    await flow.beat("aes")
    await flow.both(
        "authkeys.promote", {"which": "aes", "new_primary_id": new_id, "external_consumers_updated": True}
    )
    await flow.beat("aes")
    return new_id


DROP = lambda new_id, **extra: {  # noqa: E731
    "which": "aes", "keep_id": new_id, "external_consumers_updated": True,
    "jobs_on_postgres": True, **extra
}


async def test_drop_old_refuses_while_a_value_is_on_the_old_key(world, flow):
    await seed()
    new_id = await promoted_flow(flow)
    await refused(flow, "authkeys.drop_old", DROP(new_id), "values_on_previous")
    stored, ring = await flow.ring("aes")
    assert len(ring.members) == 2  # nothing was dropped


async def test_drop_old_refuses_a_value_no_key_opens(world, flow):
    seeded = await seed()
    foreign = Crypto(FOREIGN).encrypt("sealed under a key that is in no ring")
    await insert("scim_directories", workspace_id="65e5501d00000000000000a2", polis_directory_id="dir-2", webhook_secret=foreign)
    new_id = await promoted_flow(flow)
    params = {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
    _, run = await flow.both("authkeys.reencrypt", params)
    result = meta.ScanResult.model_validate(run["result"])
    assert run["state"] == "succeeded" and result.values_unopenable == 1
    assert result.scim_directories.values_unopenable == 1 and result.scim_directories.records_reencrypted == 1
    # everything else moved; the foreign value is still the foreign value
    await refused(flow, "authkeys.drop_old", DROP(new_id), "values_not_readable")
    check_round_trip(await all_docs(seeded), Crypto((await flow.stored("aes")).value.split(",")[0]))


async def test_drop_old_refuses_an_empty_store_unless_told(world, flow):
    new_id = await promoted_flow(flow)  # nothing seeded at all: a wrong database looks like this
    await refused(flow, "authkeys.drop_old", DROP(new_id), "store_empty")
    _, run = await flow.both("authkeys.drop_old", DROP(new_id, allow_empty=True))
    assert run["state"] == "succeeded" and run["result"]["changed"], run


async def test_drop_old_refuses_while_a_sealed_job_is_pending(world, flow, no_queue):
    await seed()
    new_id = await promoted_flow(flow)
    await flow.both(
        "authkeys.reencrypt", {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
    )
    no_queue["jobs"] = 2
    await refused(flow, "authkeys.drop_old", DROP(new_id), "jobs_pending")
    no_queue["jobs"] = 0
    _, run = await flow.both("authkeys.drop_old", DROP(new_id))
    assert run["state"] == "succeeded" and run["result"]["changed"], run


async def test_an_unavailable_count_refuses_instead_of_reading_as_zero(world):
    """The admin test database has no job queue, sessions or drafts: the count
    functions answer NULL and the task refuses (``counts_unavailable``). Nothing
    is stubbed here."""
    flow = await make_flow(world)
    await flow.beat("jwt")
    _, added = await flow.both("authkeys.add_key", add("jwt"))
    new_id = added["result"]["added_key_id"]
    await flow.beat("jwt")
    await flow.both("authkeys.promote", {"which": "jwt", "new_primary_id": new_id})
    await flow.beat("jwt")
    # the verify itself counts, so it is the one that is refused; with no verify
    # on record the drop is refused too
    await refused(flow, "authkeys.verify", {"which": "jwt"}, "counts_unavailable")
    await refused(flow, "authkeys.drop_old", {"which": "jwt", "keep_id": new_id}, "promotion_not_verified")


async def test_resume_continues_after_the_walked_records(world, flow, monkeypatch):
    await seed()
    for index in range(4):
        await insert(
            "scim_directories",
            workspace_id=f"65e5501d000000000000{index:04x}",
            polis_directory_id=f"dir-x{index}",
            webhook_secret=Crypto(OLD_F).encrypt(f"whsec-{index}"),
        )
    new_id = await promoted_flow(flow)
    params = {"which": "aes", "primary_id": new_id, "external_consumers_updated": True, "batch_size": 50}
    await flow.run("authkeys.reencrypt", params, dry_run=True)
    _, run = await flow.run("authkeys.reencrypt", params)
    assert run["state"] == "succeeded"
    # a second, resumed run with the same parameters finds nothing left to do
    _, resumed = await flow.run("authkeys.reencrypt", params)
    assert resumed["state"] == "succeeded"
    assert meta.ScanResult.model_validate(resumed["result"]).scim_directories.records_reencrypted == 0


# --------------------------- the database ties each key to its own task family
async def test_a_keyset_run_cannot_write_a_ring_and_an_authkeys_run_cannot_write_the_keyset(
    world, flow, monkeypatch
):
    """``settings.task_write_keyset`` binds ``keyset.<action>`` runs to the keyset
    and ``authkeys.<action>`` runs to the two rings (migration 0020)."""
    from backend.admin.tasks.impl import keyset_tasks
    from tests.admin.tasks.keyset_support import import_keyset

    await import_keyset(world.admin, generated_keyset())
    real = state.write_stored

    async def into_ring(conn, keys, current, new_value, **kw):
        kw["name"] = "AUTH_AES_HEX_KEY"
        return await real(conn, keys, current, new_value, **kw)

    await flow.beat("aes")
    # a keyset task asked to write a ring is refused by the database
    with monkeypatch.context() as patched:
        patched.setattr(keyset_tasks.state, "write_stored", into_ring)
        _, dry = await flow.run("keyset.add_key", {}, dry_run=True)
        assert dry["state"] == "succeeded", dry
        _, run = await flow.run("keyset.add_key", {})
        assert run["state"] == "failed", run  # insufficient_privilege from the definer function
    assert (await flow.stored("aes")).value == OLD_F and (await flow.stored("aes")).version == 1

    # an authkeys task asked to write the keyset is refused the same way
    async def into_keyset(conn, keys, current, new_value, **kw):
        kw["name"] = "MASTER_ENCRYPTION_KEYSET"
        return await real(conn, keys, current, new_value, **kw)

    await flow.beat("aes")
    with monkeypatch.context() as patched:
        patched.setattr(ring_state.state, "write_stored", into_keyset)
        _, dry = await flow.run("authkeys.add_key", add("aes"), dry_run=True)
        assert dry["state"] == "succeeded", dry
        _, run = await flow.run("authkeys.add_key", add("aes"))
        assert run["state"] == "failed", run
    assert (await flow.stored("aes")).version == 1
    assert await world.audit_rows("settings.task_set") == []


async def test_the_signing_counts_run_from_the_verify_not_from_the_promote(world, flow, no_queue):
    await flow.beat("jwt")
    _, added = await flow.both("authkeys.add_key", add("jwt"))
    new_id = added["result"]["added_key_id"]
    await flow.beat("jwt")
    # a verify made before the promote proves nothing about it
    await flow.run("authkeys.verify", {"which": "jwt"})
    await flow.both("authkeys.promote", {"which": "jwt", "new_primary_id": new_id})
    drop = {"which": "jwt", "keep_id": new_id}
    # restarted? not yet: the verify refuses, and no drop can count from it
    await flow.beat("jwt", restart_pending=True)
    await refused(flow, "authkeys.verify", {"which": "jwt"}, "consumer_restart_pending")
    await flow.beat("jwt")
    await refused(flow, "authkeys.drop_old", drop, "promotion_not_verified")
    _, first = await flow.run("authkeys.verify", {"which": "jwt"})
    assert first["state"] == "succeeded"
    _, later = await flow.run("authkeys.verify", {"which": "jwt"})  # a later verify does not move it
    assert later["state"] == "succeeded"
    async with world.owner.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT id, started_at FROM tasks.runs WHERE task = 'authkeys.verify' "
                     "AND state = 'succeeded' ORDER BY started_at")
            )
        ).all()
    assert len(rows) == 3  # the pre-promote one, the first and the later
    _, dry = await flow.run("authkeys.drop_old", drop, dry_run=True)
    assert dry["state"] == "succeeded"
    # the count was asked from the first verify after the promote (not the pre-promote one)
    assert no_queue["cutoffs"][-1] == rows[1].started_at
    assert rows[0].started_at < rows[1].started_at < rows[2].started_at


async def test_add_key_refuses_while_a_service_runs_a_build_without_ring_support(world, flow):
    await flow.beat("aes", fp="ks-000000000000")  # no mark: a build from before key rings
    await refused(flow, "authkeys.add_key", add("aes"), "consumer_old_build")
    await flow.beat("aes")
    _, ok = await flow.run("authkeys.add_key", add("aes"), dry_run=True)
    assert ok["state"] == "succeeded", ok


# ------------------------------ a re-encryption that left records behind is not a success
async def _promoted_with_data(flow):
    seeded = await seed()
    new_id = await promoted_flow(flow)
    return seeded, new_id


async def test_a_record_changed_under_the_walk_fails_the_run_and_the_rerun_finishes(world, flow, monkeypatch):
    seeded, new_id = await _promoted_with_data(flow)
    params = {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
    await flow.run("authkeys.reencrypt", params, dry_run=True)
    real = core.PostgresStore.write
    changed = []

    async def interleaved(self, record_id, updates):
        if not changed and self.target.name == "scim_directories":
            changed.append(record_id)
            # the application changes the sealed value between the read and the write
            fresh = Crypto(OLD_F).encrypt("whsec-rewritten-by-the-application")
            engine = await app_engine()
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text("UPDATE app.scim_directories SET doc = jsonb_set(doc, '{webhook_secret}', "
                             "to_jsonb(CAST(:v AS text))) WHERE id = :i"),
                        {"v": fresh, "i": record_id},
                    )
            finally:
                await engine.dispose()
        return await real(self, record_id, updates)

    with monkeypatch.context() as patched:
        patched.setattr(core.PostgresStore, "write", interleaved)
        run_id, failed = await flow.run("authkeys.reencrypt", params)
    assert changed and failed["state"] == "failed" and failed["refusal_code"] == "records_left_behind", failed
    events = await world.events(run_id)
    assert any(e["counts"].get("records_changed_concurrently") == 1 for e in events), events
    # the rewritten value is still on the previous key; a rerun moves it
    doc = await doc_of("scim_directories", seeded.ids["scim_directories"])
    assert Crypto(OLD_F).opening_position(doc["webhook_secret"]) == 0  # still on the previous key
    _, again = await flow.run("authkeys.reencrypt", params)
    assert again["state"] == "succeeded", again
    doc = await doc_of("scim_directories", seeded.ids["scim_directories"])
    new_ring = (await flow.stored("aes")).value
    assert Crypto(new_ring.split(",")[0]).decrypt(doc["webhook_secret"]) == "whsec-rewritten-by-the-application"


async def test_a_record_that_does_not_read_back_fails_the_run(world, flow, monkeypatch):
    await _promoted_with_data(flow)
    new_id = ring_state.parse_ring(meta.Which.aes, (await flow.stored("aes")).value).primary_id
    params = {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
    await flow.run("authkeys.reencrypt", params, dry_run=True)

    async def never(store, record_id, updates):
        return False

    with monkeypatch.context() as patched:
        patched.setattr(core, "_read_back", never)
        _, failed = await flow.run("authkeys.reencrypt", params)
    assert failed["state"] == "failed" and failed["refusal_code"] == "records_left_behind", failed
    _, again = await flow.run("authkeys.reencrypt", params)
    assert again["state"] == "succeeded", again


# ----------------------- an authkeys run writes only the ring its signed parameter names
async def test_a_run_for_one_ring_cannot_write_the_other(world, flow, monkeypatch):
    real = state.write_stored

    def into(other):
        async def write(conn, keys, current, new_value, **kw):
            kw["name"] = other
            return await real(conn, keys, current, new_value, **kw)

        return write

    for which, other in (("aes", "AUTH_JWT_SECRET"), ("jwt", "AUTH_AES_HEX_KEY")):
        await flow.beat(which)
        with monkeypatch.context() as patched:
            patched.setattr(ring_state.state, "write_stored", into(other))
            _, dry = await flow.run("authkeys.add_key", add(which), dry_run=True)
            assert dry["state"] == "succeeded", dry
            _, run = await flow.run("authkeys.add_key", add(which))
        assert run["state"] == "failed", (which, run)
    assert (await flow.stored("aes")).version == 1 and (await flow.stored("jwt")).version == 1
    assert await world.audit_rows("settings.task_set") == []


# ------------------------------- only the sealed values change, not the rest of a document
async def test_the_rest_of_a_document_is_left_exactly_as_stored(world, flow):
    crypto = Crypto(OLD_F)
    engine = await app_engine()
    raw = (
        '{"_id": {"$oid": "65e5501d00000000000000c9"}, "form_id": "f-precision", '
        '"price": 1.10, "huge": 12345678901234567890123, "tiny": 1e-7, "name": "x", '
        '"secrets": {"a1": [{"name": "Token", "value": "%s"}]}}' % crypto.encrypt("token-plain-1")
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO app.forms (id, doc, _bc_checksum) VALUES ('65e5501d00000000000000c9', "
                     "CAST(:d AS jsonb), 'c')"),
                {"d": raw},
            )
    finally:
        await engine.dispose()
    new_id = await promoted_flow(flow)
    params = {"which": "aes", "primary_id": new_id, "external_consumers_updated": True}
    await flow.both("authkeys.reencrypt", params)
    engine = await app_engine()
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT doc ->> 'price', doc ->> 'huge', doc ->> 'tiny', "
                         "doc #>> '{secrets,a1,0,value}' FROM app.forms WHERE id = '65e5501d00000000000000c9'")
                )
            ).one()
    finally:
        await engine.dispose()
    assert str(row[0]) == "1.10" and str(row[1]) == "12345678901234567890123"
    assert str(row[2]) in ("0.0000001", "1e-7")
    ring_head = (await flow.stored("aes")).value.split(",")[0]
    assert Crypto(ring_head).decrypt(row[3]) == "token-plain-1"
