"""``postgres/ensure-jobs-exec-role.sh``: creates or repairs the executor's role on
a database that has the job queue but not the role (a stack whose volume predates
it, or one the role was never created on), and keeps it to the queue. Runs the real
script with psql against a throw-away database; the role's name is suffixed
because roles are server-global. Skipped without DATABASE_URL or psql."""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

from backend.jobs.app import libpq_url
from backend.jobs.schema import ensure_schema
from common.db.engine import normalise_url
from tests.app.db.test_auto_migrate import ROLES, _execute, _with_database, init_sql
from tests.app.jobs.test_executor_role import Db

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set"
    ),
    pytest.mark.skipif(shutil.which("psql") is None, reason="psql not installed"),
]

SCRIPT = Path(__file__).resolve().parents[4] / "postgres" / "ensure-jobs-exec-role.sh"


@pytest.fixture
async def db(tmp_path):
    """A database with the queue (applied by the backend's role) and every
    service role, but without the executor's role, as on a volume that predates it."""
    admin = normalise_url(os.environ["DATABASE_URL"])
    name = f"bc_jobsensure_test_{uuid.uuid4().hex[:10]}"
    suffix = f"t{uuid.uuid4().hex[:8]}"
    passwords = {role: secrets.token_hex(12) for role in ROLES}
    await _execute(_with_database(admin, "postgres"), f'CREATE DATABASE "{name}"')
    try:
        await _execute(_with_database(admin, name), init_sql(name, suffix, passwords))
        database = Db(admin, name, suffix, passwords)
        await _execute(
            database.url(),
            f'DROP OWNED BY "{database.exec_role}"; DROP ROLE "{database.exec_role}";'
            " CREATE TABLE app.canary (v text);",
        )
        await ensure_schema(database.queue_app("app"), role=database.exec_role)
        # the script with the role's name suffixed, like everything else here
        script = tmp_path / "ensure-jobs-exec-role.sh"
        script.write_text(
            re.sub(r"\bbc_jobs_exec\b", database.exec_role, SCRIPT.read_text())
        )
        database.script = script
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


def run_script(db, password=None):
    url = make_url(db.admin)
    env = {
        "PATH": os.environ["PATH"],
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGPASSWORD": url.password or "",
        "POSTGRES_USER": url.username,
        "POSTGRES_DB": db.name,
    }
    if password is not None:
        env["BC_JOBS_EXEC_PASSWORD"] = password
    return subprocess.run(
        ["bash", str(db.script)], env=env, capture_output=True, text=True, timeout=60
    )


async def _exec_connect(db, password):
    url = _with_database(db.admin, db.name, db.exec_role, password)
    return await psycopg.AsyncConnection.connect(libpq_url(url), autocommit=True)


async def test_it_creates_the_role_with_the_queue_and_nothing_else(db):
    password = secrets.token_hex(12)

    done = run_script(db, password)

    assert done.returncode == 0, done.stderr
    assert "login=true superuser=false password_set=true" in done.stdout
    assert (
        "queue_rw=true app_schema=false auth_schema=false google_schema=false"
        in done.stdout
    )
    assert password not in done.stdout + done.stderr
    conn = await _exec_connect(db, password)
    try:
        assert await (await conn.execute("SELECT count(*) FROM jobs.procrastinate_jobs")).fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("SELECT * FROM app.canary")
    finally:
        await conn.close()


async def test_it_says_when_the_row_restriction_is_not_applied_yet(db):
    first = run_script(db, secrets.token_hex(12))
    assert "queue_policy=MISSING" in first.stdout and "backend.jobs.schema" in first.stdout
    # the backend applies it now that the role exists
    await ensure_schema(db.queue_app("app"), role=db.exec_role)
    second = run_script(db)
    assert "queue_policy=present" in second.stdout


async def test_it_repairs_a_drifted_grant_and_keeps_the_password_when_unset(db):
    password = secrets.token_hex(12)
    assert run_script(db, password).returncode == 0
    await _execute(
        db.url(),
        f'GRANT USAGE ON SCHEMA app TO "{db.exec_role}";'
        f' GRANT SELECT ON app.canary TO "{db.exec_role}";',
    )

    done = run_script(db)  # no password given: the role keeps its own

    assert done.returncode == 0, done.stderr
    assert "app_schema=false" in done.stdout
    conn = await _exec_connect(db, password)  # still the same password
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("SELECT * FROM app.canary")
    finally:
        await conn.close()


async def test_it_gives_the_role_the_tables_a_later_migration_creates(db):
    password = secrets.token_hex(12)
    assert run_script(db, password).returncode == 0
    await _execute(
        _with_database(db.admin, db.name, f"bc_app_{db.suffix}", db.passwords["app"]),
        "CREATE TABLE jobs.created_later (v text);",
    )
    conn = await _exec_connect(db, password)
    try:
        await conn.execute("INSERT INTO jobs.created_later VALUES ('x')")
    finally:
        await conn.close()


@pytest.mark.parametrize("password", ["has space", "a'b", "p@ss/word", "x;y"])
async def test_it_refuses_a_password_that_would_break_a_database_url(db, password):
    done = run_script(db, password)
    assert done.returncode != 0
    assert password not in done.stdout + done.stderr


async def test_it_refuses_a_database_without_the_queue(db):
    await _execute(db.url(), "DROP SCHEMA jobs CASCADE")
    done = run_script(db, secrets.token_hex(12))
    assert done.returncode != 0 and "backend.jobs.schema" in done.stderr


async def test_it_keeps_the_role_from_writing_the_events_and_periodic_defers(db):
    password = secrets.token_hex(12)
    assert run_script(db, password).returncode == 0
    conn = await _exec_connect(db, password)
    try:
        for table in ("procrastinate_events", "procrastinate_periodic_defers"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute(f"DELETE FROM jobs.{table}")
    finally:
        await conn.close()
    owner = await psycopg.AsyncConnection.connect(
        libpq_url(db.url("app")), autocommit=True
    )
    try:
        row = await (
            await owner.execute(
                "SELECT bool_and(prosecdef) FROM pg_proc p JOIN pg_namespace n"
                " ON n.oid = p.pronamespace WHERE n.nspname = 'jobs' AND"
                " (starts_with(proname, 'procrastinate_trigger_function_')"
                " OR proname = 'procrastinate_unlink_periodic_defers_v1')"
            )
        ).fetchone()
        assert row == (True,)
    finally:
        await owner.close()
