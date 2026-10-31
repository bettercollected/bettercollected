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
from procrastinate.exceptions import ConnectorException

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

    @property
    def definer_role(self):
        return f"bc_jobs_def_{self.suffix}"

    async def ensure(self):
        """The backend's schema step, with this database's role names."""
        await ensure_schema(
            self.queue_app("app"), role=self.exec_role, definer=self.definer_role
        )

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
            " INSERT INTO app.canary VALUES ('an answer');"
            # the backend's role reads application data; that is what the trigger
            # functions' owner must never be
            f' GRANT SELECT ON app.canary TO "bc_app_{suffix}";',
        )
        database = Db(admin, name, suffix, passwords)
        await database.ensure()
        yield database
    finally:
        await _execute(
            _with_database(admin, "postgres"),
            f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)',
        )
        for role in (*ROLES, "jobs_def"):
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


async def _as_backend(db, sql, *args):
    conn = await db.connect("app")
    try:
        return await (await conn.execute(sql, args)).fetchall()
    finally:
        await conn.close()


async def test_the_role_cannot_take_a_lock_that_blocks_another_job(db):
    """procrastinate's unique indexes on ``queueing_lock`` (waiting jobs) and
    ``lock`` (running jobs) are shared by every queue: an actions row named
    ``delete_response:<id>`` would make the backend skip that response's deletion
    (it reads a taken lock as already queued). The role may only write
    ``run_action`` rows whose locks start with ``action_``."""
    conn = await db.connect("jobs_exec")
    try:
        for column in ("queueing_lock", "lock"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute(
                    f"INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, {column}, args)"
                    " VALUES ('actions', 'run_action', 'delete_response:r1', '{}')"
                )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(
                "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
                " VALUES ('actions', 'delete_response', '{}')"
            )
        # its own kind of job and lock is fine, and so is no lock
        await conn.execute(
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, queueing_lock, args)"
            " VALUES ('actions', 'run_action', 'action_a1f1r1', '{}')"
        )
        await conn.execute(
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
            " VALUES ('actions', 'run_action', '{}')"
        )
        # nor can it rename a lock or a task afterwards
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(
                "UPDATE jobs.procrastinate_jobs SET queueing_lock = 'delete_user:u1'"
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(
                "UPDATE jobs.procrastinate_jobs SET task_name = 'delete_user'"
            )
    finally:
        await conn.close()
    # the backend still queues the deletion: nothing took its lock
    await _defer_with_lock(db, "delete_response", "delete_response:r1")
    assert ("delete_response", "default") in [
        row[:2] for row in await _statuses(db)
    ]


async def _defer_with_lock(db, name, lock):
    backend = db.queue_app("app")
    async with backend.open_async():
        await backend.configure_task(
            name=name, queue="default", queueing_lock=lock
        ).defer_async(response_id="r1")


async def test_the_role_cannot_write_the_events_or_the_periodic_defers(db):
    await _defer(db, "run_action", "actions", action_id="a")
    conn = await db.connect("jobs_exec")
    try:
        for table in ("procrastinate_events", "procrastinate_periodic_defers"):
            for statement in (
                f"INSERT INTO jobs.{table} DEFAULT VALUES",
                f"UPDATE jobs.{table} SET job_id = NULL",
                f"DELETE FROM jobs.{table}",
                f"SELECT * FROM jobs.{table}",
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    await conn.execute(statement)
    finally:
        await conn.close()
    # a periodic job can still be deferred by the backend after the role tried
    assert await _as_backend(db, "SELECT count(*) FROM jobs.procrastinate_periodic_defers") == [(0,)]


async def test_a_run_still_goes_through_with_the_events_written_for_it(db):
    """The role cannot write the events, procrastinate's triggers do, as the
    owner: a run is started, finished and deleted with its events intact."""
    await _defer(db, "run_action", "actions", action_id="a")
    executor = db.queue_app("jobs_exec")

    @executor.task(name="run_action", queue="actions")
    async def run_action(**kwargs):
        return None

    async with executor.open_async():
        await executor.run_worker_async(wait=False, install_signal_handlers=False)
    events = await _as_backend(
        db, "SELECT type FROM jobs.procrastinate_events ORDER BY id"
    )
    assert [e[0] for e in events] == ["deferred", "started", "succeeded"]
    conn = await db.connect("jobs_exec")
    try:
        removed = await conn.execute("DELETE FROM jobs.procrastinate_jobs")
        assert removed.rowcount == 1  # the unlink trigger runs as the owner too
    finally:
        await conn.close()


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
    sql = isolate_executor_sql(db.exec_role, db.definer_role)
    assert EXECUTOR_POLICY in sql and OPEN_POLICY in sql
    await db.ensure()  # idempotent
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
    isolation_sql = guard.isolation_sql(db.definer_role)
    assert guard.POLICY == EXECUTOR_POLICY  # the two sides name the same policy
    exec_conn = await db.connect("jobs_exec")
    try:
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
            True,
        )
        # a stale or hand-made policy of the same name fails it, whatever its name
        owner = await db.connect("app")
        for statement in (
            # the first version of the policy: the queue only
            f"CREATE POLICY {EXECUTOR_POLICY} ON jobs.procrastinate_jobs AS RESTRICTIVE"
            f" FOR ALL TO {db.exec_role} USING (queue_name = 'actions')"
            " WITH CHECK (queue_name = 'actions')",
            # a policy for reads only
            f"CREATE POLICY {EXECUTOR_POLICY} ON jobs.procrastinate_jobs AS RESTRICTIVE"
            f" FOR SELECT TO {db.exec_role} USING (queue_name = 'actions')",
        ):
            await owner.execute(f"DROP POLICY {EXECUTOR_POLICY} ON jobs.procrastinate_jobs")
            await owner.execute(statement)
            assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
                False,
            ), statement
        await db.ensure()  # the real one
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
            True,
        )
        # a grant on the events table, or a trigger that runs as the role, fails it
        await owner.execute(
            f"GRANT INSERT ON jobs.procrastinate_events TO {db.exec_role}"
        )
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
            False,
        )
        await owner.execute(
            f"REVOKE INSERT ON jobs.procrastinate_events FROM {db.exec_role}"
        )
        await owner.execute(
            "ALTER FUNCTION jobs.procrastinate_trigger_function_status_events_insert_v1()"
            " SECURITY INVOKER"
        )
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
            False,
        )
        fn = "jobs.procrastinate_trigger_function_status_events_insert_v1()"
        # no pg_temp at the end of the path, or an owner that is not the definer role
        await owner.execute(
            f"ALTER FUNCTION {fn} SECURITY DEFINER SET search_path = jobs, pg_catalog"
        )
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (False,)
        await owner.execute(
            f"ALTER FUNCTION {fn} SET search_path = pg_temp, jobs, pg_catalog"
        )
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (False,)
        await owner.execute(
            f"ALTER FUNCTION {fn} SET search_path = jobs, pg_catalog, pg_temp"
        )
        await owner.execute(f'ALTER FUNCTION {fn} OWNER TO "bc_app_{db.suffix}"')
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (False,)
        await owner.close()
        await db.ensure()  # repaired
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
            True,
        )
        owner = await db.connect("app")
        try:
            await owner.execute(
                f"DROP POLICY {EXECUTOR_POLICY} ON jobs.procrastinate_jobs"
            )
        finally:
            await owner.close()
        assert await (await exec_conn.execute(isolation_sql)).fetchone() == (
            False,
        )
    finally:
        await exec_conn.close()


async def test_the_purge_deletes_only_old_finished_actions_rows(db):
    """The real purge, on the real queue: finished ``actions`` rows go after their
    retention (a week; a month when failed), and nothing else does."""
    from backend.jobs import tasks

    async def insert(queue, status):
        conn = await db.connect("app")
        try:
            row = await (
                await conn.execute(
                    "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
                    " VALUES (%s, 'run_action', '{}') RETURNING id",
                    (queue,),
                )
            ).fetchone()
            # through the states a job goes through, so its events are written
            # (the purge dates a job by its latest event)
            for step in ("doing", status):
                if step != "todo":
                    await conn.execute(
                        "UPDATE jobs.procrastinate_jobs SET status ="
                        " %s::jobs.procrastinate_job_status WHERE id = %s",
                        (step, row[0]),
                    )
            return row[0]
        finally:
            await conn.close()

    async def age(job_id, days):
        conn = await db.connect("app")
        try:
            await conn.execute(
                "UPDATE jobs.procrastinate_events SET at = now() - make_interval(days => %s)"
                " WHERE job_id = %s",
                (days, job_id),
            )
        finally:
            await conn.close()

    gone, kept = {}, {}
    cases = [
        # (queue, status, age in days, is deleted)
        ("actions", "succeeded", 8, True),
        ("actions", "succeeded", 2, False),
        ("actions", "failed", 31, True),
        ("actions", "failed", 10, False),
        ("actions", "cancelled", 31, True),
        ("actions", "aborted", 31, True),
        ("actions", "todo", 60, False),
        ("actions", "doing", 60, False),
        ("default", "succeeded", 60, False),
        ("default", "failed", 60, False),
    ]
    for n, (queue, status, days, deleted) in enumerate(cases):
        job_id = await insert(queue, status)
        await age(job_id, days)
        (gone if deleted else kept)[job_id] = (queue, status, days)

    backend = db.queue_app("app")
    with tasks.app.replace_connector(backend.connector):
        async with tasks.app.open_async():
            assert await tasks.purge_finished_action_jobs.func(0) == "purged"

    remaining = {row[0] for row in await _as_backend(db, "SELECT id FROM jobs.procrastinate_jobs")}
    assert remaining == set(kept), (remaining, gone, kept)


TRIGGER_FUNCTIONS = (
    "procrastinate_trigger_function_status_events_insert_v1",
    "procrastinate_trigger_function_status_events_update_v1",
    "procrastinate_trigger_function_scheduled_events_v1",
    "procrastinate_trigger_abort_requested_events_procedure_v1",
    "procrastinate_unlink_periodic_defers_v1",
)


async def _definer_functions(db):
    return await _as_backend(
        db,
        "SELECT p.proname, p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner)::text"
        " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE n.nspname = 'jobs' AND (p.proname LIKE 'procrastinate\\_trigger\\_%%'"
        " OR p.proname = 'procrastinate_unlink_periodic_defers_v1') ORDER BY 1",
    )


async def test_the_trigger_functions_belong_to_the_definer_role_and_end_in_pg_temp(db):
    rows = await _definer_functions(db)
    assert {row[0] for row in rows} == set(TRIGGER_FUNCTIONS)
    for name, secdef, config, owner in rows:
        assert secdef, name
        assert config == ["search_path=jobs, pg_catalog, pg_temp"], name
        assert owner == db.definer_role, name
    # and the owner holds only what the triggers need
    held = await _as_backend(
        db,
        "SELECT has_table_privilege(%s, 'jobs.procrastinate_events', 'INSERT'),"
        " has_table_privilege(%s, 'jobs.procrastinate_jobs', 'SELECT'),"
        " has_schema_privilege(%s, 'app', 'USAGE'),"
        " has_schema_privilege(%s, 'auth', 'USAGE'),"
        " has_schema_privilege(%s, 'google', 'USAGE'),"
        " has_schema_privilege(%s, 'jobs', 'CREATE')",
        *([db.definer_role] * 6),
    )
    assert held == [(True, False, False, False, False, False)]
    login = await _as_backend(
        db, "SELECT rolcanlogin, rolsuper FROM pg_roles WHERE rolname = %s", db.definer_role
    )
    assert login == [(False, False)]


LEAK = "an answer"


async def _run_the_temp_table_exploit(db):
    """The executor's role, which may create temporary tables, shadows the table
    the definer trigger functions write with one of its own, puts a trigger on it,
    and queues a job: if the function resolves its table through the session's
    temporary schema, the trigger runs as the function's owner. Returns the error
    the trigger raises, with whatever the owner could read."""
    conn = await db.connect("jobs_exec")
    try:
        await conn.execute(
            "CREATE TEMP TABLE procrastinate_events"
            " (id bigserial, job_id bigint, type text, at timestamptz DEFAULT now())"
        )
        owners = await (
            await conn.execute(
                "SELECT DISTINCT pg_get_userbyid(p.proowner)::text FROM pg_proc p"
                " JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'jobs'"
                " AND p.proname = 'procrastinate_trigger_function_status_events_insert_v1'"
            )
        ).fetchall()
        (owner,) = owners[0]
        await conn.execute(f'GRANT ALL ON procrastinate_events TO "{owner}"')
        await conn.execute(
            f'GRANT ALL ON SEQUENCE pg_temp.procrastinate_events_id_seq TO "{owner}"'
        )
        await conn.execute(
            "CREATE FUNCTION pg_temp.steal() RETURNS trigger LANGUAGE plpgsql AS $f$"
            " BEGIN RAISE EXCEPTION 'owner % read: %', current_user,"
            " (SELECT string_agg(v, ',') FROM app.canary); END $f$"
        )
        await conn.execute(
            "CREATE TRIGGER steal BEFORE INSERT ON pg_temp.procrastinate_events"
            " FOR EACH ROW EXECUTE FUNCTION pg_temp.steal()"
        )
        try:
            await conn.execute(
                "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
                " VALUES ('actions', 'run_action', '{}')"
            )
        except psycopg.Error as error:
            return str(error)
        return ""
    finally:
        await conn.close()


async def test_the_executor_cannot_run_code_as_the_trigger_functions_owner(db):
    """Regression: the functions' path was ``jobs, pg_catalog`` with no ``pg_temp``,
    so the temporary schema was searched first and the exploit below ran as the
    owner (then the backend's role) and read the answers."""
    message = await _run_the_temp_table_exploit(db)

    assert LEAK not in message
    # the real events table got the job's event: the function did not use the temp one
    events = await _as_backend(db, "SELECT count(*) FROM jobs.procrastinate_events")
    assert events == [(1,)]


async def test_the_probe_does_leak_with_the_search_path_and_owner_the_review_found(db):
    """The probe is real: with the functions as they were (owned by the backend's
    role, ``search_path = jobs, pg_catalog``) it reads the answers."""
    backend_role = f"bc_app_{db.suffix}"
    conn = await db.connect("app")
    try:
        await _execute(db.url(), f'GRANT SELECT ON app.canary TO "{backend_role}"')
        for row in await _definer_functions(db):
            signature = (
                f"jobs.{row[0]}()"
            )
            await conn.execute(f"ALTER FUNCTION {signature} OWNER TO \"{backend_role}\"")
            await conn.execute(
                f"ALTER FUNCTION {signature} SET search_path = jobs, pg_catalog"
            )
    finally:
        await conn.close()

    message = await _run_the_temp_table_exploit(db)

    assert LEAK in message


async def test_the_role_cannot_see_read_change_cancel_or_queue_webhook_jobs(db):
    """Webhook deliveries run in the backend's own worker on the ``webhooks``
    queue (no creator code). The executor's role, which runs creator code, must
    not see them (a job's args name a delivery), take their place in the queue,
    queue one of its own (a delivery to an address it chose, signed for a
    workspace it does not own, or one that makes the backend skip a real
    delivery through the queue's unique indexes) or touch them in any way."""
    await _defer(db, "deliver_webhook", "webhooks", log_id="l1")
    await _defer(db, "purge_action_logs", "webhooks")
    await _defer(db, "run_action", "actions", action_id="a")
    assert await _as_backend(
        db, "SELECT count(*) FROM jobs.procrastinate_jobs WHERE queue_name = 'webhooks'"
    ) == [(2,)]
    conn = await db.connect("jobs_exec")
    try:
        # invisible: not by queue, not by task, not by id, not in a count
        for sql in (
            "SELECT count(*) FROM jobs.procrastinate_jobs WHERE queue_name = 'webhooks'",
            "SELECT count(*) FROM jobs.procrastinate_jobs WHERE task_name = 'deliver_webhook'",
            "SELECT count(*) FROM jobs.procrastinate_jobs WHERE args ? 'log_id'",
        ):
            assert await (await conn.execute(sql)).fetchone() == (0,), sql
        assert await (
            await conn.execute("SELECT count(*) FROM jobs.procrastinate_jobs")
        ).fetchone() == (1,)  # the one actions row
        # not changeable, not cancellable, not removable
        for sql in (
            "UPDATE jobs.procrastinate_jobs SET status = 'failed' WHERE queue_name = 'webhooks'",
            "UPDATE jobs.procrastinate_jobs SET args = '{}' WHERE task_name = 'deliver_webhook'",
            "DELETE FROM jobs.procrastinate_jobs WHERE queue_name = 'webhooks'",
        ):
            assert (await conn.execute(sql)).rowcount == 0, sql
        # not queueable: the webhooks queue, the webhook task, or a lock that would
        # make the backend skip a delivery (``deliver_webhook:<log id>``)
        for sql in (
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
            " VALUES ('webhooks', 'deliver_webhook', '{\"log_id\": \"x\"}')",
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
            " VALUES ('webhooks', 'run_action', '{}')",
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args)"
            " VALUES ('actions', 'deliver_webhook', '{\"log_id\": \"x\"}')",
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, queueing_lock, args)"
            " VALUES ('actions', 'run_action', 'deliver_webhook:l1', '{}')",
            "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, lock, args)"
            " VALUES ('actions', 'run_action', 'deliver_webhook:l1', '{}')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute(sql)
        # moving an actions row onto the webhooks queue is refused as well
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(
                "UPDATE jobs.procrastinate_jobs SET queue_name = 'webhooks'"
            )
    finally:
        await conn.close()
    # procrastinate's own deferral, through the role, is refused too
    executor = db.queue_app("jobs_exec")
    async with executor.open_async():
        with pytest.raises(ConnectorException) as refused:
            await executor.configure_task(
                name="deliver_webhook", queue="webhooks"
            ).defer_async(log_id="x")
    assert isinstance(
        refused.value.__cause__, psycopg.errors.InsufficientPrivilege
    ), repr(refused.value.__cause__)
    # the backend's rows are untouched, and its own delivery can still be queued
    # with the lock the role tried to take
    assert await _as_backend(
        db,
        "SELECT task_name, status FROM jobs.procrastinate_jobs"
        " WHERE queue_name = 'webhooks' ORDER BY id",
    ) == [("deliver_webhook", "todo"), ("purge_action_logs", "todo")]
    backend = db.queue_app("app")
    async with backend.open_async():
        await backend.configure_task(
            name="deliver_webhook", queue="webhooks", queueing_lock="deliver_webhook:l2"
        ).defer_async(log_id="l2")


async def test_a_worker_of_the_role_never_runs_a_webhook_job(db):
    await _defer(db, "deliver_webhook", "webhooks", log_id="l1")
    ran = []
    executor = db.queue_app("jobs_exec")

    # a worker of the executor that even knows the task, on every queue
    @executor.task(name="deliver_webhook", queue="webhooks")
    async def deliver_webhook(**kwargs):
        ran.append(kwargs)

    async with executor.open_async():
        await executor.run_worker_async(
            wait=False, install_signal_handlers=False, queues=None
        )
    assert ran == []
    assert await _statuses(db) == [("deliver_webhook", "webhooks", "todo")]
