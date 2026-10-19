"""The runner's only way to change the keyset in the settings store:
``settings.task_write_keyset`` (migration 0009) and the code that uses it.

Everything against a real Postgres, as the real roles: the admin role imports
the keyset (the one first write), the runner role (``bc_tasks``) reads it
through its view and writes new versions through the function, and the
portal's own verifier (``SettingsService.verify``) must find every row,
signature, the manifest and the audit trail consistent afterwards.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.config import parse_master_key
from backend.admin.services import audit
from backend.admin.services.settings_store import Actor, SettingsError
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.spec import Refusal
from common.services.keyset import (
    add_secondary_key,
    encode_keyset,
    parse_keyset,
)
from common.settings.keys import SectionKeys, SectionNotAllowed
from tests.admin.conftest import needs_postgres
from tests.admin.tasks.keyset_support import (
    KEY,
    generated_keyset,
    import_keyset,
    settings_service,
)

pytestmark = needs_postgres

REQUESTER = "ops@example.org"


@pytest_asyncio.fixture(loop_scope="session")
async def store(world):
    keyset = generated_keyset()
    await import_keyset(world.admin, keyset)
    return keyset


async def start_run(world, task="keyset.add_key", params=None, *, dry_run=False):
    """A signed run enqueued by the portal's role and claimed by the runner, which
    records its start through ``tasks.audit_append``: what a keyset write needs."""
    run_id = await world.enqueue(
        task, params if params is not None else {}, dry_run=dry_run, requested_by=REQUESTER
    )
    claimed = await world.runner().claim()
    assert claimed is not None and claimed[0]["id"] == run_id
    return str(run_id)


async def write(world, new_value, *, keys=None, task="keyset.add_key", action="add_key",
                extra=None, run_id=None):
    """One ``write_stored`` as the runner, for a freshly started run unless ``run_id`` is given."""
    keys = keys or state.runner_keys()
    run_id = run_id or await start_run(world, task)
    async with world.tasks.begin() as conn:
        current = await state.read_stored(conn, keys)
        return await state.write_stored(
            conn,
            keys,
            current,
            new_value,
            requested_by=REQUESTER,
            run_id=run_id,
            task=task,
            action=action,
            extra=extra,
        )


async def sqlstate(engine, sql, **params):
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    orig = caught.value.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None), str(orig)


async def entry(world):
    async with world.owner.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT version, source, updated_by, readers FROM settings.entries WHERE key = :k"),
                {"k": KEY},
            )
        ).one()
        revision = (await conn.execute(text("SELECT revision FROM settings.manifest"))).scalar_one()
    return row, revision


def call(version: int = 1, revision: int = 1) -> str:
    """A call with well-formed but meaningless arguments (``:k`` is the key)."""
    return (
        f"SELECT settings.task_write_keyset(CAST(:k AS text), {version}, {revision}, "
        "'auth_keys', ARRAY['backend'], 'v2:x', 'u', now(), repeat('a', 64), 'a', "
        "repeat('b', 64), CAST('{}' AS jsonb), repeat('c', 64), 'promote', 'r', CAST('{}' AS jsonb), "
        "gen_random_uuid(), now(), decode(repeat('00', 32), 'hex'), decode(repeat('01', 32), 'hex'), 1, "
        "CAST('{}' AS jsonb), CAST('{}' AS jsonb), CAST('{}' AS jsonb))"
    )


NULL_CALL = call()


# --------------------------------------------------------------- happy path
async def test_a_task_write_is_signed_audited_and_verifies(world, store):
    value = parse_keyset(store)
    new = encode_keyset(add_secondary_key(value))
    before, rev_before = await entry(world)
    run_id = await start_run(world)
    version, revision = await write(world, new, extra={"added_key_id": 77}, run_id=run_id)

    assert (version, revision) == (before.version + 1, rev_before + 1)
    after, rev_after = await entry(world)
    assert after.version == version and rev_after == revision
    assert after.source == "task" and after.updated_by == "task:keyset.add_key"
    assert list(after.readers) == ["backend", "google", "tasks"]

    # the portal's verifier finds the row, the manifest and the audit trail consistent
    assert await settings_service(world.admin).verify() == []
    # the runner reads back exactly what it wrote
    async with world.tasks.connect() as conn:
        stored = await state.read_stored(conn, state.runner_keys())
    assert stored.value == new and stored.version == version

    # every admin is told in the same transaction: names and versions, never a value
    async with world.owner.connect() as conn:
        notices = (
            await conn.execute(
                text("SELECT kind, payload, audit_seq, status FROM admin.notifications "
                     "WHERE kind = 'settings.keyset_changed'")
            )
        ).all()
    assert len(notices) == 1
    assert notices[0].status == "pending" and notices[0].audit_seq is not None
    assert notices[0].payload == {
        "setting": KEY, "tier": "T4", "action": "add_key", "version": version,
        "actor": REQUESTER, "run_id": run_id, "added_key_id": 77,
    }
    assert new not in json.dumps(notices[0].payload)

    rows = await world.audit_rows("settings.task_set")
    assert len(rows) == 1
    row = rows[0]
    assert row["actor_kind"] == "system" and row["target_id"] == KEY
    assert row["detail"]["requested_by"] == REQUESTER
    assert row["detail"]["task"] == "keyset.add_key"
    assert row["detail"]["revision"] == revision
    assert row["after"]["version"] == version
    assert row["after"]["secret"] == "set"
    # no keyset material anywhere the audit or the store keeps in the clear
    everything = json.dumps(await world.audit_rows(), default=str)
    async with world.owner.connect() as conn:
        everything += json.dumps(
            [dict(r) for r in (await conn.execute(text("SELECT * FROM settings.history"))).mappings()],
            default=str,
        )
        everything += json.dumps(
            [dict(r) for r in (await conn.execute(text("SELECT * FROM settings.entries"))).mappings()],
            default=str,
        )
    for fragment in (new, store, new[:40], store[:40]):
        assert fragment not in everything


async def test_the_history_of_the_keyset_is_never_pruned(world, store, server, migrated):
    """A key dropped from the keyset stays openable through the history, so a
    database backup from before the re-encryption can still be read."""
    value = parse_keyset(store)
    for _ in range(7):  # more than the five versions other secrets keep
        await write(world, encode_keyset(add_secondary_key(value)))
    async with world.owner.connect() as conn:
        versions = (
            await conn.execute(
                text("SELECT version FROM settings.history WHERE key = :k ORDER BY version"),
                {"k": KEY},
            )
        ).scalars().all()
    assert versions == list(range(1, 9))
    # no role can prune it: not the migration role, not the portal's writer
    for engine in (world.owner, world.admin):
        code, message = await sqlstate(
            engine, "DELETE FROM settings.history WHERE key = :k AND version = 1", k=KEY
        )
        assert code == "42501" and "never pruned" in message
    # and the portal's own prune of other secrets still works
    await settings_service(world.admin).import_once("TEMPORAL_API_KEY", "3f9a1c7e5b2d48a6c0e1f7d3b9a5c2e84d6f1a0b7c3e9d5f2a8b4c6e0d1f3a79", Actor("cli"))


async def test_the_runner_cannot_widen_who_reads_the_keyset(world, store, monkeypatch):
    from dataclasses import replace

    import backend.admin.services.settings_store as module

    real = module.store_registry()

    class Wider:
        def get(self, key):
            spec = real.get(key)
            return replace(spec, readers=(*spec.readers, "auth"))

    monkeypatch.setattr(module, "store_registry", lambda: Wider())
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    before = await entry(world)
    with pytest.raises(DBAPIError) as caught:
        await write(world, new)
    assert "invalid row" in str(caught.value.orig)
    assert await entry(world) == before


async def test_the_reencrypt_notice_only_for_a_recorded_apply_run(world, store):
    async def notices():
        async with world.owner.connect() as conn:
            return (
                await conn.execute(
                    text("SELECT payload FROM admin.notifications WHERE kind = 'settings.keyset_reencrypt'")
                )
            ).scalars().all()

    async def ask(run_id):
        async with world.tasks.begin() as conn:
            await conn.execute(text("SELECT settings.task_notify_reencrypt(:r, 1)"), {"r": run_id})

    # no such run, a dry run, another task's run: refused, nothing enqueued
    dry = await start_run(world, "keyset.reencrypt", {"primary_id": 1}, dry_run=True)
    other = await start_run(world, "keyset.promote", {"new_primary_id": 5})
    for run_id in (str(uuid.uuid4()), dry, other):
        with pytest.raises(DBAPIError) as caught:
            await ask(run_id)
        assert caught.value.orig.sqlstate == "42501"
    assert await notices() == []
    # an apply run: the runner's claim announces it; asking again adds nothing
    run_id = await start_run(world, "keyset.reencrypt", {"primary_id": 1})
    await ask(run_id)
    await ask(run_id)
    assert await notices() == [
        {"setting": KEY, "tier": "T4", "action": "reencrypt", "run_id": run_id,
         "primary_id": 1, "actor": REQUESTER}
    ]
    # a run row the runner role itself moved to running, with no recorded start: refused
    forged = await world.enqueue("keyset.reencrypt", {"primary_id": 2}, requested_by=REQUESTER)
    async with world.tasks.begin() as conn:
        await conn.execute(
            text("UPDATE tasks.runs SET state = 'running', runner_id = 'me' WHERE id = :i"), {"i": forged}
        )
    with pytest.raises(DBAPIError) as caught:
        await ask(str(forged))
    assert caught.value.orig.sqlstate == "42501" and "start of the run" in str(caught.value.orig)
    # no other role may call it
    code, _ = await sqlstate(world.admin, "SELECT settings.task_notify_reencrypt('x', 1)")
    assert code == "42501"


async def test_the_history_keeps_the_previous_versions_sealed(world, store):
    value = parse_keyset(store)
    await write(world, encode_keyset(add_secondary_key(value)))
    async with world.owner.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT version, action, source, blob IS NOT NULL AS sealed FROM settings.history "
                     "WHERE key = :k ORDER BY version"),
                {"k": KEY},
            )
        ).all()
    assert [(r.version, r.action, r.source, r.sealed) for r in rows] == [
        (1, "import", "import", True),
        (2, "set", "task", True),
    ]


# ------------------------------------------------------------------ guards
async def test_the_runner_can_write_no_other_key(world, store):
    code, message = await sqlstate(world.tasks, NULL_CALL, k="AUTH_JWT_SECRET")
    assert code == "42501" and "not task-writable" in message
    code, _ = await sqlstate(world.tasks, NULL_CALL, k="AI_DEFAULT_PROVIDER")
    assert code == "42501"
    code, _ = await sqlstate(world.tasks, call().replace("CAST(:k AS text)", "NULL"))
    assert code == "42501"


async def test_the_runner_cannot_skip_a_version_or_a_revision(world, store):
    row, revision = await entry(world)
    code, message = await sqlstate(world.tasks, call(row.version + 4, revision), k=KEY)
    assert code == "40001" and "stale version" in message
    code, message = await sqlstate(world.tasks, call(row.version, revision + 7), k=KEY)
    assert code == "40001" and "stale revision" in message
    # nothing changed
    assert (await entry(world)) == (row, revision)


async def test_a_stale_read_is_a_refusal_not_an_overwrite(world, store):
    keys = state.runner_keys()
    value = parse_keyset(store)
    first = encode_keyset(add_secondary_key(value))
    async with world.tasks.connect() as conn:
        stale = await state.read_stored(conn, keys)
    await write(world, first)  # someone else moved it on
    with pytest.raises(Refusal) as refused:
        async with world.tasks.begin() as conn:
            await state.write_stored(
                conn, keys, stale, encode_keyset(add_secondary_key(value)),
                requested_by=REQUESTER, run_id=await start_run(world), task="keyset.add_key", action="add_key",
            )
    assert refused.value.code == "stale_version"
    async with world.tasks.connect() as conn:
        assert (await state.read_stored(conn, keys)).value == first
    # the failed attempt left no audit row and no notification behind (same transaction)
    assert len(await world.audit_rows("settings.task_set")) == 1
    async with world.owner.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM admin.notifications WHERE kind = 'settings.keyset_changed'"))).scalar_one() == 1


async def test_the_runner_role_alone_cannot_forge_a_keyset_write(world, store):
    """The old attack: the runner's credential inserts its own matching audit row and
    calls the function. It can do neither any more, and the function wants a run."""
    row, revision = await entry(world)
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    # (1) it cannot insert the audit row (nor read the log)
    code, _ = await sqlstate(
        world.tasks,
        "INSERT INTO admin.audit_log (id, at, actor_kind, action, target_type, target_id, outcome, "
        "after, detail, prev_hash, row_hash) VALUES (gen_random_uuid(), now(), 'system', "
        "'settings.task_set', 'setting', :k, 'success', "
        "CAST('{\"version\": 2}' AS jsonb), CAST('{\"revision\": 2}' AS jsonb), "
        "decode(repeat('00', 32), 'hex'), decode(repeat('01', 32), 'hex'))",
        k=KEY,
    )
    assert code == "42501"
    # (2) the function refuses a write for a run that does not exist...
    with pytest.raises(DBAPIError) as caught:
        await write(world, new, run_id=str(uuid.uuid4()))
    assert "no running apply run" in str(caught.value.orig)
    # (3) ...for a run that is only queued, even if its own role marks it running (no
    # recorded start: the start is written by tasks.audit_append, which checks the
    # transition it saw)
    queued = await world.enqueue("keyset.add_key", {}, requested_by=REQUESTER)
    with pytest.raises(DBAPIError) as caught:
        await write(world, new, run_id=str(queued))
    assert "no running apply run" in str(caught.value.orig)
    async with world.tasks.begin() as conn:
        await conn.execute(
            text("UPDATE tasks.runs SET state = 'running', runner_id = 'me' WHERE id = :i"), {"i": queued}
        )
    with pytest.raises(DBAPIError) as caught:
        await write(world, new, run_id=str(queued))
    assert "start of the run was not recorded" in str(caught.value.orig)
    assert (await entry(world)) == (row, revision)


async def test_a_keyset_write_is_bound_to_an_apply_run_of_the_matching_task_once(world, store):
    row, revision = await entry(world)
    value = parse_keyset(store)
    new = encode_keyset(add_secondary_key(value))
    # a dry run may not write
    dry = await start_run(world, dry_run=True)
    with pytest.raises(DBAPIError) as caught:
        await write(world, new, run_id=dry)
    assert "no running apply run" in str(caught.value.orig)
    # a run of another task may not write under this action
    promote = await start_run(world, "keyset.promote", {"new_primary_id": 5})
    with pytest.raises(DBAPIError) as caught:
        await write(world, new, run_id=promote)
    assert "no running apply run" in str(caught.value.orig)
    assert (await entry(world)) == (row, revision)
    # the right run writes, once
    run_id = await start_run(world)
    await write(world, new, run_id=run_id)
    with pytest.raises(DBAPIError) as caught:
        await write(world, encode_keyset(add_secondary_key(parse_keyset(new))), run_id=run_id)
    assert "already wrote" in str(caught.value.orig)


async def test_the_audit_row_of_a_keyset_write_is_checked_by_the_function(world, store, monkeypatch):
    """Whatever the caller computes, the function refuses an audit row that does not
    describe this write (another version, a smuggled field, a nested value)."""
    real = audit.prepare_runner_row

    def with_changes(**changes):
        async def prepare(conn, action, target_type, target_id, before, after, outcome, **kw):
            after = {**after, **changes.get("after", {})}
            detail = {**kw["detail"], **changes.get("detail", {})}
            return await real(conn, action, target_type, target_id, before, after, outcome,
                              detail=detail, request_id=kw["request_id"])
        return prepare

    row, revision = await entry(world)
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    for changes in (
        {"after": {"version": row.version + 5}},
        {"after": {"smuggled": "x"}},
        {"detail": {"revision": revision + 9}},
        {"detail": {"task": "keyset.promote"}},
        {"detail": {"nested": {"a": 1}}},
    ):
        monkeypatch.setattr(audit, "prepare_runner_row", with_changes(**changes))
        with pytest.raises(DBAPIError) as caught:
            await write(world, new)
        assert "invalid audit row" in str(caught.value.orig), changes
    assert (await entry(world)) == (row, revision)


async def test_the_manifest_may_differ_in_this_key_only(world, store, monkeypatch):
    real = state.sign_manifest

    def tamper(revision, entries, signing_key):
        entries = dict(entries)
        other = next(k for k in entries if k != KEY)
        version, sig, readers = entries[other]
        entries[other] = (version + 1, sig, readers)  # claim another key moved
        return real(revision, entries, signing_key)

    # a second row so there is another key to tamper with
    await settings_service(world.admin).import_once(
        "TEMPORAL_API_KEY", "3f9a1c7e5b2d48a6c0e1f7d3b9a5c2e84d6f1a0b7c3e9d5f2a8b4c6e0d1f3a79", Actor("cli")
    )
    monkeypatch.setattr(state, "sign_manifest", tamper)
    row, revision = await entry(world)
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    with pytest.raises(DBAPIError) as caught:
        await write(world, new)
    assert "manifest does not match" in str(caught.value.orig)


async def test_a_wrongly_signed_row_is_written_but_nothing_accepts_it(world, store):
    """The database cannot check an HMAC (the keys are not there); what it
    guarantees is that a bad signature is refused by every reader and found
    by the verifier."""

    class BadSigner(SectionKeys):
        def sign_row(self, row):
            return row.with_sig("f" * 64)

    bad = BadSigner(
        parse_master_key(os.environ["SETTINGS_MASTER_KEY"]), sections={state.SECTION}
    )
    await write(world, encode_keyset(add_secondary_key(parse_keyset(store))), keys=bad)
    problems = await settings_service(world.admin).verify()
    assert any(p.key == KEY and p.reason == "bad_signature" for p in problems)
    async with world.tasks.connect() as conn:
        with pytest.raises(Refusal) as refused:
            await state.read_stored(conn, state.runner_keys())
    assert refused.value.code == "keyset_unverified"


# ----------------------------------------------------------- privileges
async def test_the_runner_has_no_direct_write_or_read_on_the_store(world, store):
    for sql in (
        "SELECT * FROM settings.entries",
        "SELECT * FROM settings.history",
        "SELECT * FROM settings.manifest",
        "UPDATE settings.entries SET version = version",
        "UPDATE settings.entries SET blob = 'v2:x' WHERE key = 'MASTER_ENCRYPTION_KEYSET'",
        "INSERT INTO settings.entries (key) VALUES ('X')",
        "DELETE FROM settings.entries",
        "UPDATE settings.manifest SET revision = revision + 1",
        "INSERT INTO settings.history (key) VALUES ('X')",
        "DELETE FROM settings.history",
        # the outbox: only the function writes it for the runner
        "INSERT INTO admin.notifications (kind, payload) VALUES ('x', '{}')",
        "SELECT * FROM admin.notifications",
        "SELECT * FROM settings.v_backend",
        "SELECT * FROM settings.v_google",
    ):
        code, _ = await sqlstate(world.tasks, sql)
        assert code == "42501", sql
    async with world.tasks.connect() as conn:
        # what it may read: its own view and the heartbeats
        assert (await conn.execute(text("SELECT count(*) FROM settings.v_tasks"))).scalar_one() >= 1
        await conn.execute(text("SELECT count(*) FROM settings.service_state"))


async def test_no_other_role_can_call_the_function(world, store, server, migrated):
    for logical in ("app", "auth", "google"):
        engine = create_async_engine(server.url(migrated, f"reader:{logical}"), poolclass=NullPool)
        try:
            code, message = await sqlstate(engine, NULL_CALL, k=KEY)
            assert code == "42501" and "permission denied for function" in message
        finally:
            await engine.dispose()
    code, message = await sqlstate(world.admin, NULL_CALL, k=KEY)  # the portal's writer
    assert code == "42501" and "permission denied for function" in message


async def test_the_function_checks_who_calls_even_if_granted_wrongly(world, store, server, migrated):
    sup = create_async_engine(server.url(migrated), poolclass=NullPool)
    auth = create_async_engine(server.url(migrated, "reader:auth"), poolclass=NullPool)
    try:
        async with sup.begin() as conn:
            await conn.execute(
                text(
                    "GRANT EXECUTE ON FUNCTION settings.task_write_keyset(text, integer, bigint, "
                    "text, text[], text, text, timestamptz, text, text, text, jsonb, text, text, text, jsonb, "
                    "uuid, timestamptz, bytea, bytea, integer, jsonb, jsonb, jsonb) "
                    f'TO "{server.reader_role("auth")}"'
                )
            )
        code, message = await sqlstate(auth, NULL_CALL, k=KEY)
        assert code == "42501" and "not the task runner" in message
    finally:
        await sup.dispose()
        await auth.dispose()


async def test_an_unknown_action_is_refused(world, store):
    row, revision = await entry(world)
    sql = call(row.version, revision).replace("'promote', 'r'", "'delete_everything', 'r'")
    code, _ = await sqlstate(world.tasks, sql, k=KEY)
    assert code in ("22023", "42501")


async def test_the_function_is_definer_with_a_pinned_search_path_and_not_public(world, store, server):
    async with world.owner.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT p.proname, p.prosecdef, p.proconfig, has_function_privilege('public', p.oid, 'EXECUTE'), "
                    "r.rolname, r.rolcanlogin, r.rolsuper FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner "
                    "WHERE p.proname IN ('task_write_keyset', 'task_notify_reencrypt', 'audit_append', 'begin_audit')"
                )
            )
        ).all()
    assert {r.proname for r in rows} == {"task_write_keyset", "task_notify_reencrypt", "audit_append", "begin_audit"}
    for name, definer, config, public, owner, can_login, is_super in rows:
        assert definer is True and public is False, name
        assert config and any(c.startswith("search_path=pg_catalog") for c in config), name
        assert "pg_temp" in "".join(config), name
        # owned by the dedicated definer role: no login, no superuser
        assert owner == server.definer_role and not can_login and not is_super, name


async def test_the_portal_writer_still_refuses_the_keyset(world, store):
    with pytest.raises(SettingsError) as refused:
        await settings_service(world.admin).set(
            KEY, generated_keyset(), Actor("admin", REQUESTER), expected_version=1
        )
    assert refused.value.code == "managed_by_task"


def test_the_runner_can_seal_and_open_only_the_keysets_section():
    keys = state.runner_keys()
    assert keys.sections == frozenset({"auth_keys"})
    with pytest.raises(SectionNotAllowed):
        keys.seal("mail", "MAIL_PASSWORD", 1, "x")
