"""The actions executor runs code that form creators wrote, as the ``bc_jobs_exec``
database role. Against a real, empty database laid out like production (the init
script's roles and schemas, procrastinate's tables applied as the backend's role):
the role reaches the queue's ``actions`` rows and nothing else. Not the other
services' schemas, and not the other queues' jobs (an account deletion, a response
deletion), which it could otherwise read, change, cancel or queue. Roles carry a
random suffix (they are server-global) and are dropped afterwards. Skipped when
DATABASE_URL is unset."""

from __future__ import annotations

import importlib.util
import os
import secrets
import uuid
from pathlib import Path

import psycopg
import pytest
from procrastinate import App

from backend.jobs.app import build_connector, libpq_url
from backend.jobs.schema import (
    EXECUTOR_POLICY,
    OPEN_POLICY,
    ensure_schema,
    isolate_executor_sql,
)
from common.db.engine import normalise_url
from tests.app.db.test_auto_migrate import ROLES, _execute, _with_database, init_sql

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)

ROOT = Path(__file__).resolve().parents[4]


def _executor_guard():
    """The executor's own startup check, loaded from its source (it has its own
    environment, no import path to the backend's)."""
    path = ROOT / "temporal" / "actions-executor" / "utilities" / "queue_isolation.py"
    spec = importlib.util.spec_from_file_location("queue_isolation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Db:
    def __init__(self, admin, name, suffix, passwords):
        self.admin, self.name, self.suffix, self.passwords = (
            admin,
            name,
            suffix,
            passwords,
        )

    def url(self, role=None):
        if role is None:
            return _with_database(self.admin, self.name)
        return _with_database(
            self.admin, self.name, f"bc_{role}_{self.suffix}", self.passwords[role]
        )

    @property
    def exec_role(self):
        return f"bc_jobs_exec_{self.suffix}"

    def queue_app(self, role):
        return App(connector=build_connector(self.url(role)))

    async def connect(self, role):
        return await psycopg.AsyncConnection.connect(
            libpq_url(self.url(role)), autocommit=True
        )


@pytest.fixture
async def db():
    admin = normalise_url(os.environ["DATABASE_URL"])
    name = f"bc_jobsrole_test_{uuid.uuid4().hex[:10]}"
    suffix = f"t{uuid.uuid4().hex[:8]}"
    passwords = {role: secrets.token_hex(12) for role in ROLES}
    await _execute(_with_database(admin, "postgres"), f'CREATE DATABASE "{name}"')
    try:
        await _execute(_with_database(admin, name), init_sql(name, suffix, passwords))
        # something of every other service for the role to be refused
        await _execute(
            _with_database(admin, name),
            "CREATE TABLE app.canary (v text); CREATE TABLE auth.canary (v text);"
            " CREATE TABLE google.canary (v text); CREATE TABLE public.canary (v text);"
            " INSERT INTO app.canary VALUES ('an answer');",
        )
        database = Db(admin, name, suffix, passwords)
        await ensure_schema(database.queue_app("app"), role=database.exec_role)
        yield database
    finally:
        await _execute(
            _with_database(admin, "postgres"),
            f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)',
        )
        for role in ROLES:
            await _execute(
                _with_database(admin, "postgres"),
                f'DROP ROLE IF EXISTS "bc_{role}_{suffix}"',
            )


async def _defer(database, name, queue, **args):
    backend = database.queue_app("app")
    async with backend.open_async():
        await backend.configure_task(name=name, queue=queue).defer_async(**args)


async def _statuses(database):
    conn = await database.connect("app")
    try:
        cur = await conn.execute(
            "SELECT task_name, queue_name, status FROM jobs.procrastinate_jobs"
            " ORDER BY id"
        )
        return await cur.fetchall()
    finally:
        await conn.close()


async def test_the_role_reaches_no_schema_of_another_service(db):
    conn = await db.connect("jobs_exec")
    try:
        for table in ("app.canary", "auth.canary", "google.canary", "public.canary"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute(f"SELECT * FROM {table}")
        for schema in ("app", "auth", "google"):
            row = await (
                await conn.execute(
                    "SELECT has_schema_privilege(current_user, %s, 'USAGE')", (schema,)
                )
            ).fetchone()
            assert row == (False,), schema
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("CREATE TABLE jobs.mine (v text)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("CREATE TABLE public.mine (v text)")
    finally:
        await conn.close()


async def test_the_role_is_not_a_superuser_and_cannot_change_roles(db):
    conn = await db.connect("jobs_exec")
    try:
        row = await (
            await conn.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication,"
                " rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        ).fetchone()
        assert row == (False, False, False, False, False)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(f"SET ROLE bc_app_{db.suffix}")
    finally:
        await conn.close()


async def test_the_executor_takes_its_job_and_leaves_the_other_queues_alone(db):
    await _defer(db, "delete_user", "default", encrypted_tokens="sealed", user_id="u1")
    await _defer(db, "delete_response", "default", response_id="r1")
    await _defer(
        db,
        "run_action",
        "actions",
        action_id="a",
        form_id="f",
        response_id="r",
        workspace_id="w",
    )
    ran = []
    executor = db.queue_app("jobs_exec")

    @executor.task(name="run_action", queue="actions")
    async def run_action(**kwargs):
        ran.append(kwargs)

    # tasks for the other queues are known to this worker, which listens on EVERY
    # queue: only the database's policy keeps it from running them
    @executor.task(name="delete_user", queue="default")
    async def delete_user(**kwargs):
        ran.append(("delete_user", kwargs))

    @executor.task(name="delete_response", queue="default")
    async def delete_response(**kwargs):
        ran.append(("delete_response", kwargs))

    async with executor.open_async():
        await executor.run_worker_async(
            wait=False, install_signal_handlers=False, queues=None
        )

    assert ran == [
        {"action_id": "a", "form_id": "f", "response_id": "r", "workspace_id": "w"}
    ]
    assert await _statuses(db) == [
        ("delete_user", "default", "todo"),
        ("delete_response", "default", "todo"),
        ("run_action", "actions", "succeeded"),
    ]


async def test_the_role_sees_and_changes_only_actions_rows(db):
    await _defer(db, "delete_user", "default", encrypted_tokens="sealed", user_id="u1")
    await _defer(db, "run_action", "actions", action_id="a")
    conn = await db.connect("jobs_exec")
    try:
        rows = await (
            await conn.execute("SELECT queue_name, args FROM jobs.procrastinate_jobs")
        ).fetchall()
        assert [queue for queue, _ in rows] == ["actions"]
        # an update or a delete of another queue's job finds no row
        changed = await conn.execute(
            "UPDATE jobs.procrastinate_jobs SET status = 'failed'"
            " WHERE queue_name = 'default'"
        )
        assert changed.rowcount == 0
        removed = await conn.execute(
            "DELETE FROM jobs.procrastinate_jobs WHERE queue_name = 'default'"
        )
        assert removed.rowcount == 0
        # an action job it may move to another queue is refused, and so is queueing there
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(
                "UPDATE jobs.procrastinate_jobs SET queue_name = 'default'"
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(
                "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
                " VALUES ('default', 'delete_user', '{}')"
            )
    finally:
        await conn.close()
    # queueing through procrastinate itself, as the executor's role, is refused too
    executor = db.queue_app("jobs_exec")
    async with executor.open_async():
        with pytest.raises(Exception) as refused:
            await executor.configure_task(
                name="delete_user", queue="default"
            ).defer_async(encrypted_tokens="forged", user_id="u2")
        assert "row-level security" in str(refused.value) or "row-level security" in str(
            refused.value.__cause__
        )
    assert [row[:2] for row in await _statuses(db)] == [
        ("delete_user", "default"),
        ("run_action", "actions"),
    ]
    assert [row[2] for row in await _statuses(db)] == ["todo", "todo"]


async def test_every_other_role_sees_the_whole_queue_as_before(db):
    """The backend's role owns the table; the admin portal's counting function
    reads it as another role. Neither is restricted."""
    await _defer(db, "delete_user", "default", encrypted_tokens="s", user_id="u1")
    await _defer(db, "run_action", "actions", action_id="a")
    reader = f"bc_count_{db.suffix}"
    await _execute(
        db.url(),
        f'CREATE ROLE "{reader}" LOGIN PASSWORD \'reader-pw\';'
        f' GRANT CONNECT ON DATABASE "{db.name}" TO "{reader}";'
        f' GRANT USAGE ON SCHEMA jobs TO "{reader}";'
        f' GRANT SELECT (id, queue_name, status) ON jobs.procrastinate_jobs'
        f' TO "{reader}";',
    )
    try:
        for url in (
            db.url("app"),
            _with_database(db.admin, db.name, reader, "reader-pw"),
        ):
            conn = await psycopg.AsyncConnection.connect(libpq_url(url))
            try:
                row = await (
                    await conn.execute("SELECT count(*) FROM jobs.procrastinate_jobs")
                ).fetchone()
                assert row == (2,)
            finally:
                await conn.close()
    finally:
        await _execute(db.url(), f'DROP OWNED BY "{reader}"; DROP ROLE "{reader}"')


async def test_the_restriction_is_asserted_again_and_only_for_an_existing_role(db):
    sql = isolate_executor_sql(db.exec_role)
    assert EXECUTOR_POLICY in sql and OPEN_POLICY in sql
    await ensure_schema(db.queue_app("app"), role=db.exec_role)  # idempotent
    await ensure_schema(db.queue_app("app"), role="bc_jobs_exec_never_created")
    with pytest.raises(ValueError):
        isolate_executor_sql("x'; DROP TABLE y; --")
    conn = await db.connect("app")
    try:
        row = await (
            await conn.execute(
                "SELECT count(*) FROM pg_policy WHERE polrelid ="
                " 'jobs.procrastinate_jobs'::regclass"
            )
        ).fetchone()
        assert row == (2,)
    finally:
        await conn.close()


async def test_the_executors_startup_check_follows_the_policy(db):
    guard = _executor_guard()
    assert guard.POLICY == EXECUTOR_POLICY  # the two sides name the same policy
    exec_conn = await db.connect("jobs_exec")
    try:
        assert await (await exec_conn.execute(guard.ISOLATION_SQL)).fetchone() == (
            True,
        )
        owner = await db.connect("app")
        try:
            await owner.execute(
                f"DROP POLICY {EXECUTOR_POLICY} ON jobs.procrastinate_jobs"
            )
        finally:
            await owner.close()
        assert await (await exec_conn.execute(guard.ISOLATION_SQL)).fetchone() == (
            False,
        )
    finally:
        await exec_conn.close()
