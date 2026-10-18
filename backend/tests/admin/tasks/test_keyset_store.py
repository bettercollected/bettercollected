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


async def write(engine, new_value, *, keys=None, task="keyset.add_key"):
    keys = keys or state.runner_keys()
    async with engine.begin() as conn:
        current = await state.read_stored(conn, keys)
        return await state.write_stored(
            conn,
            keys,
            current,
            new_value,
            requested_by=REQUESTER,
            run_id=str(uuid.uuid4()),
            task=task,
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
        "repeat('b', 64), CAST('{}' AS jsonb), repeat('c', 64))"
    )


NULL_CALL = call()


# --------------------------------------------------------------- happy path
async def test_a_task_write_is_signed_audited_and_verifies(world, store):
    value = parse_keyset(store)
    new = encode_keyset(add_secondary_key(value))
    before, rev_before = await entry(world)
    version, revision = await write(world.tasks, new)

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


async def test_the_history_keeps_the_previous_versions_sealed(world, store):
    value = parse_keyset(store)
    await write(world.tasks, encode_keyset(add_secondary_key(value)))
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
    code, _ = await sqlstate(world.tasks, "SELECT settings.task_write_keyset(NULL, 1, 1, 's', ARRAY['a'], 'v2:x', 'u', now(), 'x', 'a', 'b', '{}', 'c')")
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
    await write(world.tasks, first)  # someone else moved it on
    with pytest.raises(Refusal) as refused:
        async with world.tasks.begin() as conn:
            await state.write_stored(
                conn, keys, stale, encode_keyset(add_secondary_key(value)),
                requested_by=REQUESTER, run_id=str(uuid.uuid4()), task="keyset.add_key",
            )
    assert refused.value.code == "stale_version"
    async with world.tasks.connect() as conn:
        assert (await state.read_stored(conn, keys)).value == first
    # the failed attempt left no audit row behind (same transaction)
    assert len(await world.audit_rows("settings.task_set")) == 1


async def test_no_audit_row_no_write(world, store, monkeypatch):
    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr(audit, "write", nothing)
    row, revision = await entry(world)
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    with pytest.raises(DBAPIError) as caught:
        await write(world.tasks, new)
    assert "no audit row" in str(caught.value.orig)
    assert (await entry(world)) == (row, revision)


async def test_an_audit_row_of_another_transaction_does_not_count(world, store, monkeypatch):
    row, revision = await entry(world)
    # a perfect audit row, committed on its own earlier
    async with world.tasks.begin() as conn:
        await audit.write(
            conn, "settings.task_set", "setting", KEY, None,
            {"setting": KEY, "secret": "set", "version": row.version + 1, "digest": "d"},
            "success", actor_kind="system", detail={"revision": revision + 1},
        )

    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr(audit, "write", nothing)
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    with pytest.raises(DBAPIError) as caught:
        await write(world.tasks, new)
    assert "no audit row" in str(caught.value.orig)
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
        "TEMPORAL_API_KEY", "x" * 40, Actor("cli")
    )
    monkeypatch.setattr(state, "sign_manifest", tamper)
    row, revision = await entry(world)
    new = encode_keyset(add_secondary_key(parse_keyset(store)))
    with pytest.raises(DBAPIError) as caught:
        await write(world.tasks, new)
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
    await write(world.tasks, encode_keyset(add_secondary_key(parse_keyset(store))), keys=bad)
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
                    "text, text[], text, text, timestamptz, text, text, text, jsonb, text) "
                    f'TO "{server.reader_role("auth")}"'
                )
            )
        code, message = await sqlstate(auth, NULL_CALL, k=KEY)
        assert code == "42501" and "not the task runner" in message
    finally:
        await sup.dispose()
        await auth.dispose()


async def test_the_function_is_definer_with_a_pinned_search_path_and_not_public(world, store):
    async with world.owner.connect() as conn:
        definer, config, public = (
            await conn.execute(
                text(
                    "SELECT prosecdef, proconfig, has_function_privilege('public', oid, 'EXECUTE') "
                    "FROM pg_proc WHERE proname = 'task_write_keyset'"
                )
            )
        ).one()
    assert definer is True
    assert config and any(c.startswith("search_path=pg_catalog") for c in config)
    assert public is False


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
