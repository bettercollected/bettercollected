"""The database privilege model, against hostile roles, on real Postgres.

Each test plays the attacker the privilege model has to stop and checks the
original exploit fails: a table owner planting code in front of a definer
function, the portal's role damaging sealed history or the keyset row, an outsider
holding the repository's old advisory-lock keys, the portal's role forging
notification progress, a stuck lock, a tampered audit chain, and an upgrade from
the previous head with data in every table.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.loops.base import Loop, LoopRunner
from backend.admin.loops.integrity import IntegrityMonitor
from backend.admin.loops.status import StatusBoard
from backend.admin.security.clock import FakeClock
from backend.admin.security.keys import admin_key
from backend.admin.services import audit
from backend.admin.services.settings_store import Actor, SettingsService, store_registry
from tests.admin.engines import fixture_engine
from tests.admin.conftest import _execute, needs_postgres, roles_sql
from tests.admin.tasks.keyset_support import KEY, generated_keyset, import_keyset
from tests.admin.test_host_settings import seed_stack
from tests.admin.test_migrations import _alembic
from tests.admin.test_settings_store import (  # noqa: F401 - fixtures
    CLI,
    PLANT,
    SECRET,
    T1,
    make_keys,
    put,
    scalar,
    superuser,
    svc,
)

pytestmark = needs_postgres

# the constant advisory-lock keys the repository used before revision 0013
OLD_CHAIN_KEY = -1909258384265368190
OLD_SETTINGS_KEY = 7310952481203619855
OLD_SETUP_KEY = 4099217756181324507
OLD_LOOP_CLASS = 0x42434144


@asynccontextmanager
async def as_role(server, database, role):
    engine = fixture_engine(server.url(database, role))
    try:
        yield engine
    finally:
        await engine.dispose()


async def refused(engine, sql, **params):
    """(sqlstate, message) of a statement that must fail."""
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    orig = caught.value.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None), str(orig)


# ================================================================== SEC-1
@pytest_asyncio.fixture(loop_scope="session")
async def stack(server, migrated, superuser):
    """The application tables as a deployment has them: owned by their services'
    roles (bc_app, bc_auth), which is what lets an owner plant code."""
    await seed_stack(server, migrated, superuser, users=2, responses=2)
    async with superuser.begin() as conn:
        for n in range(2):
            await conn.execute(
                text("INSERT INTO app.workspaces (id, doc, _bc_checksum) VALUES (:i, CAST('{}' AS jsonb), 'x')"),
                {"i": f"{0x5f000000 + n:08x}0000000000000000"},
            )
        for table in ("workspaces", "workspace_forms", "form_versions", "form_responses"):
            await conn.execute(text(f'ALTER TABLE app.{table} OWNER TO "{server.reader_role("app")}"'))
        await conn.execute(text(f'ALTER TABLE auth.users OWNER TO "{server.reader_role("auth")}"'))
    await _execute(
        server.url(migrated),
        roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw,
                  server.data_app_pw, server.data_google_pw),
    )


EVIL = """
CREATE FUNCTION {schema}.evil(x text) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO {schema}.loot VALUES (jsonb_build_object('ran_as', current_user));
    BEGIN
        INSERT INTO {schema}.loot SELECT {steal};
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('stole', 'other schema'));
    EXCEPTION WHEN others THEN
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    BEGIN
        INSERT INTO {schema}.loot SELECT to_jsonb(a) FROM admin.audit_log a;
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('stole', 'audit'));
    EXCEPTION WHEN others THEN
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    BEGIN
        INSERT INTO {schema}.loot SELECT to_jsonb(e) FROM settings.entries e;
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('stole', 'settings'));
    EXCEPTION WHEN others THEN
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    RETURN true;
END $$
"""


@pytest.mark.parametrize(
    "owner_logical,schema,table,columns,steal,counts_function",
    [
        # the backend's role owns app.*: it plants code in front of app.workspaces and
        # tries to reach auth.users through whoever runs the count
        ("app", "app", "workspaces", "id, disabled", "doc FROM auth.users", "platform_counts_app"),
        # the auth service's role owns auth.users: it tries the responses
        ("auth", "auth", "users", "id, doc, plan", "doc FROM app.form_responses", "platform_counts_auth"),
    ],
)
async def test_a_table_owner_cannot_use_a_counts_function_to_read_another_schema(
    server, migrated, stack, superuser, owner_logical, schema, table, columns, steal, counts_function
):
    """The original exploit: the owner swaps its table for a view that calls its own
    function; the function runs as whoever reads the view, i.e. the definer's owner.
    The owner of each count function now holds nothing beyond its own schema, so the
    planted code runs and gets nothing."""
    count_role = f"bc_count_{schema}_{server.suffix}"
    async with as_role(server, migrated, f"reader:{owner_logical}") as owner:
        async with owner.begin() as conn:
            await conn.execute(text(f"ALTER TABLE {schema}.{table} RENAME TO {table}_real"))
            await conn.execute(text(f"CREATE TABLE {schema}.loot (doc jsonb)"))
            await conn.execute(text(f"GRANT INSERT ON {schema}.loot TO {count_role}"))
            await conn.execute(text(EVIL.format(schema=schema, steal=steal)))
            await conn.execute(
                text(f"CREATE VIEW {schema}.{table} AS SELECT {columns} FROM {schema}.{table}_real "
                     f"WHERE {schema}.evil(id)")
            )
            await conn.execute(text(f"GRANT SELECT ON {schema}.{table} TO {count_role}"))
    # the portal's role asks for the counts, as the metrics page and bootstrap-keys do
    async with as_role(server, migrated, "runtime") as portal:
        async with portal.begin() as conn:  # committed: the planted function writes its loot
            answer = (await conn.execute(text(f"SELECT admin.{counts_function}()"))).scalar_one()
    assert isinstance(answer, (dict, str))
    async with as_role(server, migrated, f"reader:{owner_logical}") as owner:
        async with owner.connect() as conn:
            loot = [r[0] for r in (await conn.execute(text(f"SELECT doc FROM {schema}.loot"))).all()]
    assert loot, "the planted function did not run: the test proves nothing"
    # it ran as the count function's owner...
    assert {"ran_as": count_role} in loot
    # ...and every attempt to reach another schema, the audit log or the settings was refused
    assert not [row for row in loot if "stole" in row], loot
    denied = [row["denied"] for row in loot if "denied" in row]
    # (once per row the view looked at; each run tried the other schema, the log and the settings)
    assert denied and len(denied) % 3 == 0 and all("permission denied" in message for message in denied), denied
    # nothing from the other schema ended up in the table either
    assert all(set(row) <= {"ran_as", "denied"} for row in loot)


async def test_the_counts_come_from_two_functions_and_are_combined_as_data(server, migrated, stack):
    from backend.admin.repositories import views

    async with as_role(server, migrated, "runtime") as portal:
        async with portal.connect() as conn:
            counts = await views.platform_counts(conn)
    assert counts["users"]["total"] == 2 and counts["responses"]["total"] == 2
    assert len(counts["weekly"]) == 12
    # whatever a definer function answers, the combined result keeps only whole numbers
    # in the known fields
    hostile = {"organizations": {"total": "9" * 30, "disabled": -4, "extra": "<script>"},
               "forms": {"by_provider": {"x" * 100: 3, 5: 1}},
               "weekly": [{"week_start": "<b>", "responses": True, "new_forms": 2.9}]}
    combined = views.combine_counts(hostile, {"users": {"total": [1], "by_plan": {"PRO": 7}}})
    assert combined["organizations"] == {"total": 0, "new_last_30_days": 0, "disabled": 0}
    assert list(combined["forms"]["by_provider"]) == ["x" * 40]
    assert combined["weekly"] == [{"week_start": "", "new_users": 0, "new_organizations": 0, "new_forms": 2, "responses": 0}]
    assert combined["users"]["total"] == 0 and combined["users"]["by_plan"]["PRO"] == 7


# ================================================================== T-01
async def test_no_runtime_role_can_overwrite_a_sealed_history_blob(svc, server, migrated, superuser):
    await put(svc, SECRET, PLANT)
    await put(svc, SECRET, PLANT + "-b")
    original = await scalar(superuser, "SELECT blob FROM settings.history WHERE key = :k AND version = 1", k=SECRET)
    junk = "v2:" + "AAAA:" * 4 + "AAAA"
    # the portal's role: no UPDATE on the column any more
    async with as_role(server, migrated, "runtime") as portal:
        code, _ = await refused(portal, "UPDATE settings.history SET blob = :b WHERE key = :k AND version = 1",
                                b=junk, k=SECRET)
        assert code == "42501"
    # not even the owner: a version is never changed (its re-wrap is appended)
    async with as_role(server, migrated, "owner") as owner:
        code, message = await refused(owner, "UPDATE settings.history SET blob = :b WHERE key = :k AND version = 1",
                                      b=junk, k=SECRET)
        assert code == "42501" and "never changed" in message
    assert await scalar(superuser, "SELECT blob FROM settings.history WHERE key = :k AND version = 1", k=SECRET) == original
    assert await svc.verify() == []


async def test_a_wrap_may_only_re_key_never_replace_the_sealed_value(svc, server, migrated, superuser):
    await put(svc, SECRET, PLANT)
    await put(svc, SECRET, PLANT + "-b")
    original = await scalar(superuser, "SELECT blob FROM settings.history WHERE key = :k AND version = 1", k=SECRET)
    parts = original.split(":")
    insert = "INSERT INTO settings.history_wraps (key, version, blob) VALUES (:k, 1, :b)"
    async with as_role(server, migrated, "runtime") as portal:
        # a different sealed value (the envelope's own nonce and ciphertext): refused
        for index in (4, 5):
            changed = list(parts)
            changed[index] = "A" * len(parts[index])
            code, message = await refused(portal, insert, k=SECRET, b=":".join(changed))
            assert code == "23000" and "keeps the sealed value" in message
        # not an envelope, wrong shape, a version that has no history row: refused
        for blob in ("v2:x", "v2:a:b:c:d:e:f", original.replace("v2", "v1", 1)):
            code, _ = await refused(portal, insert, k=SECRET, b=blob)
            assert code in ("23000", "23514")
        code, _ = await refused(portal, insert.replace("version, blob) VALUES (:k, 1", "version, blob) VALUES (:k, 99"),
                                k=SECRET, b=original)
        assert code in ("23000", "23503")
        # a wrap is never changed or removed
        for sql in ("UPDATE settings.history_wraps SET blob = blob", "DELETE FROM settings.history_wraps"):
            code, _ = await refused(portal, sql)
            assert code == "42501"
        # a copy that only re-keys the data key is accepted... and cannot hurt: readers
        # fall back to the next copy, restoring the old version still works
        rekeyed = list(parts)
        rekeyed[3] = "B" * len(parts[3])
        async with portal.begin() as conn:
            await conn.execute(text(insert), {"k": SECRET, "b": ":".join(rekeyed)})
    versions = {h.version: h for h in await svc.history(SECRET)}
    assert versions[1].candidates[0] == ":".join(rekeyed) and versions[1].candidates[-1] == original
    change = await svc.restore(SECRET, 1, CLI, confirmation=SECRET)  # opens the original after the junk copy fails
    assert change.version == 3
    assert not [p for p in await svc.verify() if p.reason == "history_unreadable"]


async def test_verify_reports_a_version_with_no_usable_copy(svc, superuser):
    await put(svc, SECRET, PLANT)
    await put(svc, SECRET, PLANT + "-b")
    junk = "v2:" + "AAAA:" * 4 + "AAAA"
    # a database-level actor (here the superuser with the guards off) damages the only copy
    async with superuser.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(text("UPDATE settings.history SET blob = :b WHERE key = :k AND version = 1"),
                           {"b": junk, "k": SECRET})
    assert (SECRET, "history_unreadable") in {(p.key, p.reason) for p in await svc.verify()}


async def test_pruning_old_history_takes_its_wraps_along(svc, server, migrated, superuser):
    await put(svc, SECRET, PLANT)
    original = await scalar(superuser, "SELECT blob FROM settings.history WHERE key = :k AND version = 1", k=SECRET)
    parts = original.split(":")
    parts[3] = "C" * len(parts[3])
    async with as_role(server, migrated, "runtime") as portal:
        async with portal.begin() as conn:
            await conn.execute(text("INSERT INTO settings.history_wraps (key, version, blob) VALUES (:k, 1, :b)"),
                               {"k": SECRET, "b": ":".join(parts)})
    for n in range(7):  # more than the five versions a secret keeps
        await put(svc, SECRET, f"{PLANT}-{n}")
    assert await scalar(superuser, "SELECT count(*) FROM settings.history_wraps WHERE key = :k", k=SECRET) == 0
    assert await scalar(superuser, "SELECT count(*) FROM settings.history WHERE key = :k AND version = 1", k=SECRET) == 0


# ================================================================== T-03
async def test_the_portal_role_cannot_move_or_damage_the_keyset_row(svc, server, migrated, superuser):
    await import_keyset(svc._engine, generated_keyset())
    async with superuser.connect() as conn:
        stored = (await conn.execute(text("SELECT blob, version FROM settings.entries WHERE key = :k"), {"k": KEY})).one()
    parts = stored.blob.split(":")
    async with as_role(server, migrated, "runtime") as portal:
        # a new version: only the task runner's function may write one
        code, message = await refused(
            portal,
            "UPDATE settings.entries SET version = version + 1, blob = :b, source = 'portal' WHERE key = :k",
            b=stored.blob, k=KEY,
        )
        assert code == "42501" and "tasks only" in message
        # a same-version swap of the sealed value: refused
        swapped = list(parts)
        swapped[5] = "A" * len(parts[5])
        code, message = await refused(portal, "UPDATE settings.entries SET blob = :b WHERE key = :k",
                                      b=":".join(swapped), k=KEY)
        assert code == "23000" and "sealed value" in message
        # a re-key of the data key is the one thing left: it needs no master key, it
        # cannot produce a row that verifies, and verify() says so loudly
        rekeyed = list(parts)
        rekeyed[3] = "D" * len(parts[3])
        async with portal.begin() as conn:
            await conn.execute(text("UPDATE settings.entries SET blob = :b WHERE key = :k"),
                               {"b": ":".join(rekeyed), "k": KEY})
    assert (KEY, "bad_signature") in {(p.key, p.reason) for p in await svc.verify()}


# ================================================================== T-02 / SEC-2
async def test_an_outsider_holding_the_old_lock_keys_stalls_nothing(svc, server, migrated, runtime_engine):
    holders = []
    try:
        for logical in ("app",):  # any database login can: the backend's role stands for them all
            engine = create_async_engine(server.url(migrated, f"reader:{logical}"), poolclass=NullPool)
            conn = await engine.connect()
            holders.append((engine, conn))
            for key in (OLD_CHAIN_KEY, OLD_SETTINGS_KEY, OLD_SETUP_KEY):
                await conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": key})
            for number in (1, 2, 3):
                await conn.execute(text("SELECT pg_advisory_lock(:c, :n)"), {"c": OLD_LOOP_CLASS, "n": number})
        # the audit write, the settings write and the loops all still work, promptly
        async def work():
            async with runtime_engine.begin() as conn:
                await audit.write(conn, "outsider.test", None, None, None, None, "success", actor_kind="cli")
            await put(svc, T1, 7)
            ran = []

            class Counting(Loop):
                name = "integrity"
                lock_number = 3
                interval = 0.02

                async def run_once(self):
                    ran.append(1)
                    return "ran"

            runner = LoopRunner(runtime_engine, FakeClock(time.time()), [Counting()])
            await runner.start()
            for _ in range(100):
                if ran:
                    break
                await asyncio.sleep(0.05)
            await runner.stop()
            return ran

        assert await asyncio.wait_for(work(), 15)
        # and the outsider cannot take the real locks, nor see them
        conn = holders[0][1]
        for sql in ("SELECT admin.take_lock('audit_chain')", "SELECT 1 FROM admin.lock_rows FOR UPDATE",
                    "SELECT 1 FROM admin.loop_leases"):
            with pytest.raises(DBAPIError, match="permission denied"):
                await conn.execute(text(sql))
            await conn.rollback()
    finally:
        for engine, conn in holders:
            await conn.close()
            await engine.dispose()


async def _shorten_lock_timeouts(server, migrated, to: str) -> None:
    """The admin lock functions carry their own ``lock_timeout`` (5 s, revision
    0013). Check that, then shorten it in this test's database copy: what the
    test proves (a stuck holder makes the writer fail with lock_not_available
    within the lock timeout, and the monitor raises the alarm) does not depend
    on the length, and two 5 s waits made this the suite's slowest test."""
    functions = ("admin.take_lock(text)", "admin.audit_log_check_chain()")
    async with as_role(server, migrated, "superuser") as sup:
        async with sup.begin() as conn:
            for fn in functions:
                config = (
                    await conn.execute(
                        text("SELECT proconfig FROM pg_proc WHERE oid = CAST(:fn AS regprocedure)"),
                        {"fn": fn},
                    )
                ).scalar_one()
                assert "lock_timeout=5s" in (config or []), (fn, config)
                await conn.execute(text(f"ALTER FUNCTION {fn} SET lock_timeout = '{to}'"))


async def test_a_stuck_lock_fails_fast_and_raises_the_integrity_alarm(svc, server, migrated, runtime_engine):
    await _shorten_lock_timeouts(server, migrated, "300ms")
    clock = FakeClock(time.time())
    board = StatusBoard()
    monitor = IntegrityMonitor(runtime_engine, clock, svc.verify, board)
    holder = await runtime_engine.connect()  # an admin-role session that never lets go
    try:
        await holder.execute(text("SELECT admin.take_lock('audit_chain')"))
        started = time.monotonic()
        with pytest.raises(DBAPIError) as caught:
            async with runtime_engine.begin() as conn:
                await audit.write(conn, "blocked.test", None, None, None, None, "success", actor_kind="cli")
        # the function's lock timeout (300 ms here, 5 s as migrated), not a hang
        # or the 10 s statement timeout
        assert time.monotonic() - started < 3
        orig = caught.value.orig
        assert (getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)) == "55P03"
        # the monitor names it on the shell banner (its mail needs the audit log, so the
        # pass itself fails while the lock is held, the banner status is already set)
        with pytest.raises(DBAPIError):
            await monitor.run_once()
        assert board.integrity.ok is False and ("*", "lock_blocked") in board.integrity.problems
    finally:
        await holder.rollback()
        await holder.close()
    # released: the next pass is quiet again, the incident is over
    monitor_again = IntegrityMonitor(runtime_engine, clock, svc.verify, board)
    assert (await monitor_again.run_once()) == "ok"
    assert board.integrity.ok is True


# ================================================================== T-05
async def audit_rows(engine, n, action="chain.test"):
    for _ in range(n):
        async with engine.begin() as conn:
            await audit.write(conn, action, None, None, None, None, "success", actor_kind="cli")


def chain_monitor(engine, store, board, clock):
    async def step():
        async with engine.begin() as conn:
            return await audit.verify_step(conn, batch=4)

    return IntegrityMonitor(engine, clock, store.verify, board, audit_step=step, probe_locks=False)


async def test_the_integrity_loop_verifies_the_audit_chain_incrementally(svc, runtime_engine, superuser):
    board, clock = StatusBoard(), FakeClock(time.time())
    monitor = chain_monitor(runtime_engine, svc, board, clock)
    await audit_rows(runtime_engine, 6)
    assert await monitor.run_once() == "ok"
    first = await scalar(superuser, "SELECT verified_seq FROM admin.audit_verify_state")
    assert first == 4  # bounded per pass (batch 4): the checkpoint moved by four rows
    assert await monitor.run_once() == "ok"
    head = await scalar(superuser, "SELECT max(seq) FROM admin.audit_log")
    assert await scalar(superuser, "SELECT verified_seq FROM admin.audit_verify_state") == head
    await audit_rows(runtime_engine, 2)
    async with runtime_engine.begin() as conn:
        step = await audit.verify_step(conn, batch=4)
    assert step.ok and step.scanned == 2  # only what is new


async def test_a_broken_chain_is_an_integrity_problem_and_the_alarm_repeats(svc, runtime_engine, superuser):
    board, clock = StatusBoard(), FakeClock(time.time())
    monitor = chain_monitor(runtime_engine, svc, board, clock)
    await audit_rows(runtime_engine, 3)
    assert await monitor.run_once() == "ok"
    # a row that links to the chain head but whose hash nobody can recompute (what a
    # holder of an INSERT grant and no key can write; the old runner role could)
    async with runtime_engine.begin() as conn:
        head = (await conn.execute(text("SELECT row_hash FROM admin.audit_log ORDER BY seq DESC LIMIT 1"))).scalar_one()
        await conn.execute(
            text("INSERT INTO admin.audit_log (id, at, actor_kind, action, outcome, prev_hash, row_hash) "
                 "VALUES (gen_random_uuid(), now(), 'system', 'forged.junk', 'success', :p, :h)"),
            {"p": head, "h": secrets.token_bytes(32)},
        )
    await audit_rows(runtime_engine, 1)  # an honest write chains on top of it
    verified_before = await scalar(superuser, "SELECT verified_seq FROM admin.audit_verify_state")
    for _ in range(2):  # reported every pass, the checkpoint stays in front of the break
        assert (await monitor.run_once()).startswith("1 problem")
        assert ("*", "audit_chain_broken") in board.integrity.problems and board.integrity.ok is False
        assert await scalar(superuser, "SELECT verified_seq FROM admin.audit_verify_state") == verified_before
    assert len(await scalar(superuser, "SELECT array_agg(id) FROM admin.notifications WHERE kind = 'settings.integrity'")) == 1


async def test_a_tampered_checkpoint_is_reported(svc, runtime_engine, superuser):
    board, clock = StatusBoard(), FakeClock(time.time())
    monitor = chain_monitor(runtime_engine, svc, board, clock)
    await audit_rows(runtime_engine, 3)
    assert await monitor.run_once() == "ok"
    async with runtime_engine.begin() as conn:  # the portal's role may write the checkpoint row...
        await conn.execute(text("UPDATE admin.audit_verify_state SET verified_hash = :h"), {"h": secrets.token_bytes(32)})
        # ...but it only ever moves forward
        code = None
        try:
            async with conn.begin_nested():
                await conn.execute(text("UPDATE admin.audit_verify_state SET verified_seq = verified_seq - 1"))
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        assert code == "23000"
    assert (await monitor.run_once()).startswith("1 problem")
    assert ("*", "audit_checkpoint_bad") in board.integrity.problems


# ================================================================== T-07
async def test_the_portal_role_cannot_reset_or_edit_delivered_notices(server, migrated, superuser):
    async with as_role(server, migrated, "runtime") as portal:
        async with portal.begin() as conn:
            ids = [
                (await conn.execute(text(
                    "INSERT INTO admin.notifications (kind, payload) VALUES ('settings.changed', '{}') RETURNING id"
                ))).scalar_one()
                for _ in range(2)
            ]
        first, second = ids
        # a legitimate delivery step: an attempt counted, a recipient recorded, then sent
        async with portal.begin() as conn:
            await conn.execute(text(
                "UPDATE admin.notifications SET status = 'sent', sent_at = now(), attempts = attempts + 1, "
                "delivered_to = ARRAY['ab12cd'] WHERE id = :i"), {"i": first})
        # a sent notice is final: not reset to pending for a replay, nothing else changes
        for sql in (
            "UPDATE admin.notifications SET status = 'pending', sent_at = NULL WHERE id = :i",
            "UPDATE admin.notifications SET attempts = 0 WHERE id = :i",
            "UPDATE admin.notifications SET delivered_to = '{}' WHERE id = :i",
        ):
            code, message = await refused(portal, sql, i=first)
            assert code == "42501" and "final" in message, sql
        # a pending one cannot jump to sent without the delivery record, nor be put off for good,
        # nor have its attempts reset, nor lose recipients
        for sql in (
            "UPDATE admin.notifications SET status = 'sent', sent_at = now() WHERE id = :i",
            "UPDATE admin.notifications SET status = 'sent', sent_at = now(), delivered_to = ARRAY['x'] WHERE id = :i",
            "UPDATE admin.notifications SET next_attempt_at = now() + interval '30 days' WHERE id = :i",
            "UPDATE admin.notifications SET attempts = attempts + 5 WHERE id = :i",
            "UPDATE admin.notifications SET sent_at = now() WHERE id = :i",
        ):
            code, _ = await refused(portal, sql, i=second)
            assert code == "23000", sql
        # the content columns are not writable at all
        for column in ("payload = '{}'", "kind = 'x'", "dedupe_key = 'x'", "audit_seq = 1"):
            code, _ = await refused(portal, f"UPDATE admin.notifications SET {column} WHERE id = :i", i=second)
            assert code == "42501", column
    assert await scalar(superuser, "SELECT status FROM admin.notifications WHERE id = :i", i=second) == "pending"


# ================================================================== upgrade
async def test_the_upgrade_from_the_previous_head_keeps_every_table_and_works(server, unmigrated):
    owner_url = server.url(unmigrated, "owner")
    done = _alembic(owner_url, "upgrade", "0012_setup_state")
    assert done.returncode == 0, done.stderr[-2000:]
    sup = create_async_engine(server.url(unmigrated), poolclass=NullPool)
    key = admin_key("audit", 1)
    prev = audit.GENESIS_HASH
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    try:
        async with sup.begin() as conn:
            for i in range(3):  # a chain written by the previous release's code
                row = {
                    "id": uuid.uuid4(), "at": at + timedelta(minutes=i), "actor_kind": "cli", "actor_email": None,
                    "session_id": None, "ip": None, "ua": None, "action": "old.row", "target_type": None,
                    "target_id": None, "outcome": "success", "before": None, "after": None, "detail": None,
                    "request_id": None, "key_version": 1,
                }
                digest = audit.compute_row_hash(key, prev, row)
                await conn.execute(
                    text("INSERT INTO admin.audit_log (id, at, actor_kind, action, outcome, key_version, prev_hash, row_hash) "
                         "VALUES (:id, :at, 'cli', 'old.row', 'success', 1, :p, :h)"),
                    {"id": row["id"], "at": row["at"], "p": prev, "h": digest},
                )
                prev = digest
            sig = "a" * 64
            await conn.execute(text(
                "INSERT INTO settings.entries (key, section, readers, is_secret, reload_class, tier, value, "
                "version, source, updated_by, updated_at, sig) VALUES ('API_FLOW_EVENTS_PER_WINDOW', 'api', "
                "ARRAY['backend'], false, 'H', 'T1', '5'::jsonb, 1, 'cli', 'cli', now(), :s)"), {"s": sig})
            await conn.execute(text(
                "INSERT INTO settings.history (key, version, section, is_secret, value, action, source, actor, at) "
                "VALUES ('API_FLOW_EVENTS_PER_WINDOW', 1, 'api', false, '5'::jsonb, 'import', 'cli', 'cli', now())"))
            await conn.execute(text("INSERT INTO admin.notifications (kind, payload) VALUES ('settings.changed', '{}')"))
            await conn.execute(text(
                "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, requested_by, requested_at, "
                "nonce, request_sig, sig_version) VALUES (gen_random_uuid(), 'selftest', 1, '{}'::jsonb, repeat('0', 64), "
                "false, 'x', now(), 'n', decode(repeat('00', 32), 'hex'), 1)"))
        done = _alembic(owner_url, "upgrade", "head")
        assert done.returncode == 0, done.stderr[-2000:]
        # the roles script runs again after the migrations, as deploy.sh does
        await _execute(
            server.url(unmigrated),
            roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw,
                      server.data_app_pw, server.data_google_pw),
        )
        counts = {}
        async with sup.connect() as conn:
            for table in ("admin.audit_log", "settings.entries", "settings.history", "admin.notifications", "tasks.runs"):
                counts[table] = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            attempts = (await conn.execute(text("SELECT claim_attempts FROM tasks.runs"))).scalar_one()
        assert counts == {"admin.audit_log": 3, "settings.entries": 1, "settings.history": 1,
                          "admin.notifications": 1, "tasks.runs": 1}
        assert attempts == 0
        # the new code writes on top of the old chain and verifies the whole of it
        portal = create_async_engine(server.url(unmigrated, "runtime"), poolclass=NullPool)
        try:
            async with portal.begin() as conn:
                await audit.write(conn, "new.row", None, None, None, None, "success", actor_kind="cli")
            async with portal.begin() as conn:
                step = await audit.verify_step(conn)
            assert step.ok and step.scanned == 4
            # the notice written before the upgrade can still be delivered
            async with portal.begin() as conn:
                await conn.execute(text(
                    "UPDATE admin.notifications SET status = 'sent', sent_at = now(), attempts = attempts + 1, "
                    "delivered_to = ARRAY['ab'] WHERE status = 'pending'"))
            code, _ = await refused(portal, "UPDATE settings.history SET blob = NULL")
            assert code == "42501"
        finally:
            await portal.dispose()
        # the runner's role lost the log and gained its functions
        async with sup.connect() as conn:
            tasks_role = server.tasks_role
            assert not (await conn.execute(text("SELECT has_table_privilege(:r, 'admin.audit_log', 'INSERT')"), {"r": tasks_role})).scalar_one()
            assert not (await conn.execute(text("SELECT has_table_privilege(:r, 'admin.audit_log', 'SELECT')"), {"r": tasks_role})).scalar_one()
            assert (await conn.execute(text(
                "SELECT has_function_privilege(:r, 'tasks.audit_append(text, text, text, text, jsonb, jsonb, jsonb, text, uuid, timestamptz, bytea, bytea, integer)', 'EXECUTE')"),
                {"r": tasks_role})).scalar_one()
    finally:
        await sup.dispose()


# ================================================================== small hardening items
def test_notice_fields_do_not_accept_a_trailing_newline():
    from backend.admin.loops.notifications import BadPayload, render

    good = {"setting": "API_TRUST_CLOUDFLARE", "tier": "T3", "action": "set", "version": 2, "actor": "ops@example.org"}
    assert render("settings.changed", good)
    for field in ("setting", "action"):
        with pytest.raises(BadPayload):
            render("settings.changed", {**good, field: good[field] + "\n"})
    with pytest.raises(BadPayload):
        render("settings.integrity", {"count": 1, "problems": [{"key": "*", "reason": "bad_signature\n"}]})


def test_the_roles_script_never_puts_a_password_on_a_command_line(tmp_path):
    """The passwords reach psql through its environment (\\getenv); a fake psql records
    its arguments and stdin, and no password appears in the arguments."""
    import stat
    import subprocess

    from tests.admin.conftest import ROLES_SCRIPT

    passwords = {
        "BC_ADMIN_PASSWORD": "pw-admin-Zk3q",
        "BC_ADMIN_MIG_PASSWORD": "pw-mig-Zk3q",
        "BC_TASKS_PASSWORD": "pw-tasks-Zk3q",
        "BC_TASKS_DATA_APP_PASSWORD": "pw-dataapp-Zk3q",
        "BC_TASKS_DATA_GOOGLE_PASSWORD": "pw-datagoogle-Zk3q",
    }
    fake = tmp_path / "psql"
    fake.write_text(
        "#!/bin/bash\n"
        f"printf '%s\\n' \"$@\" > {tmp_path}/argv\n"
        f"cat > {tmp_path}/stdin\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {"PATH": f"{tmp_path}:{os.environ['PATH']}", "POSTGRES_USER": "u", "POSTGRES_DB": "d", **passwords}
    done = subprocess.run(["bash", str(ROLES_SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    argv = (tmp_path / "argv").read_text()
    stdin = (tmp_path / "stdin").read_text()
    for value in passwords.values():
        assert value not in argv and value not in stdin and value not in done.stdout + done.stderr
    assert "ON_ERROR_STOP=1" in argv and "_pw=" not in argv
    assert "\\getenv admin_pw BC_ADMIN_PASSWORD" in stdin
