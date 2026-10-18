"""The ``tasks`` schema: who may do what, the triggers, the size CHECKs."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.services import audit
from backend.admin.tasks.tables import SCHEMA, metadata
from common.db.alembic_support import metadata_diff
from tests.admin.conftest import _execute, needs_postgres, roles_sql

pytestmark = needs_postgres


async def run_sql(engine, sql, **params):
    async with engine.begin() as conn:
        return await conn.execute(text(sql), params)


async def scalar(engine, sql, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar()


async def refused(engine, sql, **params) -> str:
    with pytest.raises(DBAPIError) as raised:
        await run_sql(engine, sql, **params)
    return str(raised.value.orig)


def test_the_migration_matches_the_table_definitions_marker():
    assert SCHEMA == "tasks"
    assert {t.name for t in metadata.sorted_tables} == {
        "runs",
        "run_events",
        "checkpoints",
        "locks",
    }


async def test_migrated_tasks_schema_matches_the_definitions(owner_engine):
    async with owner_engine.connect() as conn:
        diff = await conn.run_sync(lambda c: metadata_diff(c, metadata, SCHEMA))
    assert diff == []


# -- runs: the admin side ------------------------------------------------------------
async def test_admin_inserts_queued_runs_only(world):
    await world.enqueue("selftest", {})  # fine
    base = (
        "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, "
        "requested_by, requested_at, nonce, request_sig, {extra}) "
        "VALUES (:id, 'selftest', 1, '{{}}'::jsonb, :h, false, 'a', now(), 'n', :sig, {value})"
    )
    for extra, value in (
        ("state", "'running'"),
        ("state", "'succeeded'"),
        ("started_at", "now()"),
        ("finished_at", "now()"),
        ("heartbeat_at", "now()"),
        ("runner_id", "'x'"),
        ("result", "'{}'::jsonb"),
        ("refusal_code", "'declined'"),
        ("progress", "'{}'::jsonb"),
        ("cancel_requested_at", "now()"),
    ):
        message = await refused(
            world.admin,
            base.format(extra=extra, value=value),
            id=uuid.uuid4(),
            h="0" * 64,
            sig=b"0" * 32,
        )
        assert "inserted queued" in message, (extra, message)


async def test_the_guard_binds_the_owner_too(world):
    message = await refused(
        world.owner,
        "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, "
        "requested_by, requested_at, nonce, request_sig, state) "
        "VALUES (:id, 't', 1, '{}'::jsonb, :h, false, 'a', now(), 'n', :sig, 'running')",
        id=uuid.uuid4(),
        h="0" * 64,
        sig=b"0" * 32,
    )
    assert "inserted queued" in message


async def test_admin_may_only_request_cancel_once(world):
    run_id = await world.enqueue("selftest", {})
    await world.cancel(run_id)
    message = await refused(
        world.admin,
        "UPDATE tasks.runs SET cancel_requested_at = NULL WHERE id = :id",
        id=run_id,
    )
    assert "set once" in message
    for column, value in (
        ("state", "'succeeded'"),
        ("result", "'{}'::jsonb"),
        ("runner_id", "'x'"),
        ("params", "'{\"rounds\": 99}'::jsonb"),
        ("request_sig", "decode('00', 'hex')"),
        ("finished_at", "now()"),
    ):
        assert "permission denied" in await refused(
            world.admin, f"UPDATE tasks.runs SET {column} = {value} WHERE id = :id", id=run_id
        ), column
    assert "permission denied" in await refused(
        world.admin, "DELETE FROM tasks.runs WHERE id = :id", id=run_id
    )


async def test_admin_can_read_but_not_write_the_other_tables(world):
    for table in ("run_events", "checkpoints", "locks"):
        await scalar(world.admin, f"SELECT count(*) FROM tasks.{table}")
    assert "permission denied" in await refused(
        world.admin,
        "INSERT INTO tasks.locks (name, run_id, runner_id) VALUES ('x', :id, 'r')",
        id=uuid.uuid4(),
    )
    assert "permission denied" in await refused(
        world.admin, "INSERT INTO tasks.run_events (run_id, seq, code) VALUES (:id, 1, 'x')", id=uuid.uuid4()
    )


# -- the runner role -----------------------------------------------------------------
async def test_the_runner_role_cannot_create_or_rewrite_requests(world):
    run_id = await world.enqueue("selftest", {})
    assert "permission denied" in await refused(
        world.tasks,
        "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, "
        "requested_by, requested_at, nonce, request_sig) "
        "VALUES (:id, 't', 1, '{}'::jsonb, :h, false, 'a', now(), 'n', :sig)",
        id=uuid.uuid4(),
        h="0" * 64,
        sig=b"0" * 32,
    )
    for column, value in (
        ("task", "'other'"),
        ("params", "'{}'::jsonb"),
        ("params_hash", "repeat('0', 64)"),
        ("requested_by", "'someone'"),
        ("request_sig", "decode(repeat('00', 32), 'hex')"),
        ("cancel_requested_at", "now()"),
        ("dry_run", "true"),
    ):
        assert "permission denied" in await refused(
            world.tasks, f"UPDATE tasks.runs SET {column} = {value} WHERE id = :id", id=run_id
        ), column
    assert "permission denied" in await refused(
        world.tasks, "DELETE FROM tasks.runs WHERE id = :id", id=run_id
    )


async def test_the_runner_role_cannot_change_request_columns_even_via_owner_triggers(world):
    run_id = await world.enqueue("selftest", {})
    message = await refused(
        world.owner, "UPDATE tasks.runs SET task = 'x' WHERE id = :id", id=run_id
    )
    assert "immutable" in message


async def test_state_only_moves_forward(world):
    run_id = await world.enqueue("selftest", {})
    await run_sql(world.tasks, "UPDATE tasks.runs SET state = 'running' WHERE id = :id", id=run_id)
    await run_sql(world.tasks, "UPDATE tasks.runs SET state = 'succeeded' WHERE id = :id", id=run_id)
    for state in ("running", "queued", "failed", "interrupted"):
        assert "illegal state change" in await refused(
            world.tasks, f"UPDATE tasks.runs SET state = '{state}' WHERE id = :id", id=run_id
        )
    other = await world.enqueue("selftest", {})
    assert "illegal state change" in await refused(
        world.tasks, "UPDATE tasks.runs SET state = 'succeeded' WHERE id = :id", id=other
    )  # queued -> succeeded skips running


async def test_the_runner_role_touches_nothing_else_in_admin(world):
    for table in (
        "sessions",
        "signin_challenges",
        "attempts",
        "factors",
        "recovery_codes",
        "alembic_version",
    ):
        assert "permission denied" in await refused(world.tasks, f"SELECT 1 FROM admin.{table}")
    for sql in (
        "UPDATE admin.audit_log SET outcome = 'x'",
        "DELETE FROM admin.audit_log",
        "TRUNCATE admin.audit_log",
    ):
        assert "permission denied" in await refused(world.tasks, sql)
    async with world.tasks.begin() as conn:  # the chain it may extend
        entry = await audit.write(
            conn, "task.run.started", "task_run", "x", None, None, "success", actor_kind="system"
        )
    assert entry.seq >= 1
    assert await scalar(world.tasks, "SELECT count(*) FROM admin.audit_log") >= 1


async def test_history_is_append_only(world):
    run_id = await world.enqueue("selftest", {})
    await run_sql(world.tasks, "UPDATE tasks.runs SET state = 'running' WHERE id = :id", id=run_id)
    await run_sql(
        world.tasks,
        "INSERT INTO tasks.run_events (run_id, seq, code) VALUES (:id, 1, 'step')",
        id=run_id,
    )
    await run_sql(
        world.tasks,
        "INSERT INTO tasks.checkpoints (run_id, cursor) VALUES (:id, '{\"n\": 1}'::jsonb)",
        id=run_id,
    )
    for sql in (
        "UPDATE tasks.run_events SET code = 'other'",
        "DELETE FROM tasks.run_events",
        "UPDATE tasks.checkpoints SET cursor = '{}'::jsonb",
        "DELETE FROM tasks.checkpoints",
    ):
        await refused(world.tasks, sql)
        await refused(world.owner if sql.startswith("UPDATE") else world.tasks, sql)
    # locks: insert and delete are the runner's
    await run_sql(
        world.tasks,
        "INSERT INTO tasks.locks (name, run_id, runner_id) VALUES ('task:x', :id, 'r')",
        id=run_id,
    )
    assert "permission denied" in await refused(
        world.tasks, "UPDATE tasks.locks SET runner_id = 'z'"
    )
    await run_sql(world.tasks, "DELETE FROM tasks.locks WHERE run_id = :id", id=run_id)


async def test_size_checks(world):
    run_id = await world.enqueue("selftest", {})
    await run_sql(world.tasks, "UPDATE tasks.runs SET state = 'running' WHERE id = :id", id=run_id)
    big = json.dumps({f"c{i}": "x" * 300 for i in range(10)})
    assert "ck_run_events_row_size" in await refused(
        world.tasks,
        "INSERT INTO tasks.run_events (run_id, seq, code, counts) "
        "VALUES (:id, 1, 'step', CAST(:c AS jsonb))",
        id=run_id,
        c=big,
    )
    assert "ck_run_events_row_size" in await refused(
        world.tasks,
        "INSERT INTO tasks.run_events (run_id, seq, code, ids) "
        "VALUES (:id, 2, 'step', CAST(:c AS jsonb))",
        id=run_id,
        c=json.dumps(["i" * 60] * 40),
    )
    assert "ck_run_events_code" in await refused(
        world.tasks,
        "INSERT INTO tasks.run_events (run_id, seq, code) VALUES (:id, 3, 'Free text here')",
        id=run_id,
    )
    assert "ck_checkpoints_cursor_size" in await refused(
        world.tasks,
        "INSERT INTO tasks.checkpoints (run_id, cursor) VALUES (:id, CAST(:c AS jsonb))",
        id=run_id,
        c=json.dumps({"k": "x" * 2100}),
    )
    assert "ck_runs_result_size" in await refused(
        world.tasks,
        "UPDATE tasks.runs SET result = CAST(:c AS jsonb) WHERE id = :id",
        id=run_id,
        c=json.dumps({"k": "x" * 8300}),
    )
    assert "ck_runs_refusal_code" in await refused(
        world.tasks,
        "UPDATE tasks.runs SET refusal_code = 'Not a code!' WHERE id = :id",
        id=run_id,
    )
    # at the limit is fine
    await run_sql(
        world.tasks,
        "UPDATE tasks.runs SET result = CAST(:c AS jsonb) WHERE id = :id",
        id=run_id,
        c=json.dumps({"k": "x" * 8000}),
    )


async def test_other_roles_have_no_access_to_tasks(server, migrated):
    roles = [f"bc_{r}_{server.suffix}" for r in ("app", "auth", "google", "jobs_exec")]
    async with create_async_engine(server.url(migrated), poolclass=NullPool).connect() as conn:
        for role in roles:
            assert not (
                await conn.execute(
                    text("SELECT has_schema_privilege(:r, 'tasks', 'USAGE')"), {"r": role}
                )
            ).scalar(), role
            for table in ("runs", "run_events", "checkpoints", "locks"):
                for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    assert not (
                        await conn.execute(
                            text("SELECT has_table_privilege(:r, :t, :p)"),
                            {"r": role, "t": f"tasks.{table}", "p": priv},
                        )
                    ).scalar(), (role, table, priv)


async def test_roles_script_is_idempotent_and_repairs_grants(server, migrated):
    url = server.url(migrated)
    runner_sql = (
        "SELECT has_column_privilege(:r, 'tasks.runs', :c, 'UPDATE')"
    )

    async def snapshot():
        out = {}
        async with create_async_engine(url, poolclass=NullPool).connect() as conn:
            for c in ("state", "heartbeat_at", "result", "params", "request_sig", "cancel_requested_at"):
                out[c] = (await conn.execute(text(runner_sql), {"r": server.tasks_role, "c": c})).scalar()
            out["admin_cancel"] = (
                await conn.execute(
                    text(runner_sql), {"r": server.runtime_role, "c": "cancel_requested_at"}
                )
            ).scalar()
            out["admin_state"] = (
                await conn.execute(text(runner_sql), {"r": server.runtime_role, "c": "state"})
            ).scalar()
        return out

    before = await snapshot()
    assert before["state"] and before["heartbeat_at"] and before["result"]
    assert not before["params"] and not before["request_sig"] and not before["cancel_requested_at"]
    assert before["admin_cancel"] and not before["admin_state"]
    # drift: hand out a broad grant, let the script repair it
    await _execute(url, f'GRANT UPDATE ON tasks.runs TO "{server.tasks_role}"')
    assert (await snapshot())["params"] is True
    sql = roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw)
    await _execute(url, sql)
    await _execute(url, sql)
    assert await snapshot() == before


async def test_the_runner_may_only_write_audit_rows_as_system(world):
    for kind in ("admin", "cli", "anonymous"):
        with pytest.raises(DBAPIError) as raised:
            async with world.tasks.begin() as conn:
                await audit.write(
                    conn, "task.run.started", "task_run", "x", None, None, "success",
                    actor_kind=kind, actor_email="ops@example.org",
                )
        assert "as system only" in str(raised.value.orig)
    async with world.tasks.begin() as conn:
        await audit.write(
            conn, "task.run.started", "task_run", "x", None, None, "success", actor_kind="system"
        )
    # the admin role is unaffected
    async with world.admin.begin() as conn:
        await audit.write(
            conn, "setting.update", "setting", "x", None, None, "success",
            actor_kind="admin", actor_email="ops@example.org",
        )
