"""DB_AUTO_MIGRATE against a real, empty database laid out like production.

Each test creates a throw-away database (its name contains "test") on the
server DATABASE_URL points at, runs postgres/init/01-roles-schemas.sh's SQL in
it — with uniquely suffixed role names, since roles are server-global and the
local server already has bc_app & co. — and then lets the startup guard
migrate as the backend's own least-privilege role. Database and roles are
dropped afterwards. Skipped when DATABASE_URL is unset.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import backend.db.models  # noqa: F401 — registers every table on Base.metadata
from backend.db.base import SCHEMA, Base
from backend.db.startup import MIGRATIONS
from backend.jobs.schema import JOBS_SCHEMA
from common.db import AUTO_MIGRATE_KEY, SchemaNotReady, ensure_schema_ready, load_flags
from common.db.engine import normalise_url

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)

INIT_SCRIPT = (
    Path(__file__).resolve().parents[4] / "postgres" / "init" / "01-roles-schemas.sh"
)
ROLES = ("app", "auth", "google", "jobs_exec")
FLAGS = load_flags({"DB_WRITE_MODE": "dual", "JOBS_BACKEND": "postgres"})
AUTO = {AUTO_MIGRATE_KEY: "true"}


def _with_database(
    url: str, database: str, user: str | None = None, pw: str = ""
) -> str:
    base, _, _ = url.rpartition("/")
    if user is not None:
        scheme, _, rest = base.partition("://")
        host = rest.rpartition("@")[2]
        base = f"{scheme}://{user}:{pw}@{host}"
    return f"{base}/{database}"


def init_sql(database: str, suffix: str, passwords: dict[str, str]) -> str:
    """The init script's SQL with psql variables bound and role names suffixed."""
    script = INIT_SCRIPT.read_text()
    sql = script.split("<<'SQL'\n", 1)[1].rsplit("\nSQL", 1)[0]
    sql = re.sub(r"\bbc_(app|auth|google|jobs_exec)\b", rf"bc_\1_{suffix}", sql)
    for role, var in zip(ROLES, ("app_pw", "auth_pw", "google_pw", "jobs_pw")):
        sql = sql.replace(f":'{var}'", f"'{passwords[role]}'")
    return sql.replace(':"DBNAME"', f'"{database}"')


async def _execute(url: str, statement: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(statement)  # multi-statement script
    finally:
        await engine.dispose()


@pytest.fixture
async def app_role_url():
    """An empty database initialised like app-postgres; yields bc_app's URL."""
    admin = normalise_url(os.environ["DATABASE_URL"])
    name = f"bc_automigrate_test_{uuid.uuid4().hex[:10]}"
    suffix = f"t{uuid.uuid4().hex[:8]}"
    passwords = {role: secrets.token_hex(12) for role in ROLES}
    await _execute(_with_database(admin, "postgres"), f'CREATE DATABASE "{name}"')
    try:
        await _execute(_with_database(admin, name), init_sql(name, suffix, passwords))
        yield _with_database(admin, name, f"bc_app_{suffix}", passwords["app"])
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


async def _state(url: str) -> dict:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            tables = (
                (
                    await conn.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = :s ORDER BY 1"
                        ),
                        {"s": SCHEMA},
                    )
                )
                .scalars()
                .all()
            )
            revision = (
                (
                    await conn.execute(
                        text(f'SELECT version_num FROM "{SCHEMA}".alembic_version')
                    )
                )
                .scalars()
                .all()
            )
            queue = await conn.scalar(
                text("SELECT to_regclass('jobs.procrastinate_jobs')")
            )
            owner = await conn.scalar(
                text(
                    "SELECT tableowner FROM pg_tables "
                    "WHERE schemaname = :s AND tablename = 'alembic_version'"
                ),
                {"s": SCHEMA},
            )
            return {
                "tables": list(tables),
                "revision": list(revision),
                "queue": queue,
                "owner": owner,
                "user": await conn.scalar(text("SELECT current_user")),
            }
    finally:
        await engine.dispose()


async def _guard(url: str, env: dict) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        await ensure_schema_ready(FLAGS, engine, MIGRATIONS, (JOBS_SCHEMA,), env=env)
    finally:
        await engine.dispose()


def _expected_tables() -> list[str]:
    return sorted([t.name for t in Base.metadata.sorted_tables] + ["alembic_version"])


async def test_unmigrated_database_refuses_to_start(app_role_url):
    with pytest.raises(SchemaNotReady) as raised:
        await _guard(app_role_url, env={})
    message = str(raised.value)
    assert "schema 'app' has no Alembic revision" in message
    assert "schema 'jobs' is missing its tables" in message
    assert f"{AUTO_MIGRATE_KEY}=true" in message


async def test_auto_migrate_brings_an_empty_database_to_head(app_role_url):
    await _guard(app_role_url, env=AUTO)

    state = await _state(app_role_url)
    heads, _ = MIGRATIONS.code_revisions()
    assert state["tables"] == _expected_tables()
    assert state["revision"] == list(heads)
    assert state["queue"] is not None
    assert state["owner"] == state["user"]  # migrated as bc_app, not a superuser

    await _guard(app_role_url, env={})  # the check alone now passes
    await _guard(app_role_url, env=AUTO)  # and a second migration is a no-op


async def test_concurrent_auto_migrations_serialise(app_role_url, caplog):
    """Replicas starting together: all succeed, the schema ends at head once."""
    caplog.set_level(logging.INFO, logger="common.db.schema_guard")
    await asyncio.gather(*(_guard(app_role_url, env=AUTO) for _ in range(3)))

    messages = [r.getMessage() for r in caplog.records]
    assert any("another instance is migrating it; waiting" in m for m in messages)
    assert sum("schema 'app' migrated, applied" in m for m in messages) == 1
    assert sum("schema 'app' already at head" in m for m in messages) == 2

    state = await _state(app_role_url)
    heads, _ = MIGRATIONS.code_revisions()
    assert state["tables"] == _expected_tables()
    assert state["revision"] == list(heads)
    assert state["queue"] is not None


async def test_failed_migration_refuses_to_start(app_role_url):
    """A migration that cannot run (here: the role may not use the schema) is fatal."""
    admin = normalise_url(os.environ["DATABASE_URL"])
    database = app_role_url.rsplit("/", 1)[1]
    await _execute(
        _with_database(admin, database), "ALTER SCHEMA app OWNER TO CURRENT_USER"
    )
    with pytest.raises(SchemaNotReady) as raised:
        await _guard(app_role_url, env=AUTO)
    assert f"{AUTO_MIGRATE_KEY}: migrating schema(s) app, jobs failed" in str(
        raised.value
    )
