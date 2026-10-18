"""The admin Alembic chain, the schema guard and the roles script, on real Postgres."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import backend.admin as admin_package
from backend.admin.db import MIGRATIONS, ensure_schema
from backend.admin.repositories import audit as audit_repo
from backend.admin.repositories.tables import SCHEMA, metadata
from backend.admin.services import audit
from common.db import SchemaNotReady
from common.db.alembic_support import metadata_diff
from common.db.schema_guard import upgrade_schema
from tests.admin.conftest import _execute, needs_postgres, roles_sql

pytestmark = needs_postgres

BACKEND_ROOT = Path(admin_package.__file__).resolve().parents[2]
INI = Path(admin_package.__file__).resolve().parent / "alembic.ini"
HEAD = "0004_tasks_schema"
TABLES = sorted([t.name for t in metadata.sorted_tables] + ["alembic_version"])


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(INI), *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


async def _scalar(url: str, sql: str, **params):
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).scalar()
    finally:
        await engine.dispose()


async def _tables(url: str) -> list[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'admin' ORDER BY 1"
                )
            )
            return list(rows.scalars())
    finally:
        await engine.dispose()


def test_the_chain_is_linear_with_hand_named_revisions():
    heads, known = MIGRATIONS.code_revisions()
    assert heads == (HEAD,)
    assert sorted(known) == [
        "0001_sessions_and_attempts",
        "0002_factors_and_recovery_codes",
        "0003_audit_log",
        "0004_tasks_schema",
    ]


def test_migration_constants_match_the_service():
    path = (
        Path(admin_package.__file__).parent
        / "migrations"
        / "versions"
        / "0003_audit_log.py"
    )
    spec = importlib.util.spec_from_file_location("rev0003", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert bytes.fromhex(module.GENESIS_HASH_HEX) == audit.GENESIS_HASH
    assert module.CHAIN_LOCK_KEY == audit_repo.CHAIN_LOCK_KEY


async def test_migrations_apply_from_empty_and_are_idempotent(server, unmigrated):
    owner = server.url(unmigrated, "owner")
    applied = await upgrade_schema(owner, MIGRATIONS)
    assert applied == [
        "0001_sessions_and_attempts",
        "0002_factors_and_recovery_codes",
        "0003_audit_log",
        "0004_tasks_schema",
    ]
    assert await _tables(owner) == TABLES
    assert await upgrade_schema(owner, MIGRATIONS) == []
    assert await _tables(owner) == TABLES
    version = await _scalar(owner, 'SELECT version_num FROM "admin".alembic_version')
    assert version == HEAD


async def test_the_alembic_cli_applies_and_repeats(server, unmigrated):
    owner = server.url(unmigrated, "owner")
    for _ in range(2):
        done = _alembic(owner, "upgrade", "head")
        assert done.returncode == 0, done.stderr[-2000:]
    assert await _tables(owner) == TABLES


async def test_migrated_schema_matches_the_table_definitions(server, migrated):
    engine = create_async_engine(server.url(migrated, "owner"), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            diff = await conn.run_sync(lambda c: metadata_diff(c, metadata, SCHEMA))
    finally:
        await engine.dispose()
    assert diff == []


async def test_schema_guard_refuses_unmigrated_and_old_schemas(server, unmigrated):
    runtime = create_async_engine(server.url(unmigrated, "runtime"), poolclass=NullPool)
    try:
        with pytest.raises(SchemaNotReady) as raised:
            await ensure_schema(runtime)
        assert "no Alembic revision" in str(raised.value)

        done = _alembic(
            server.url(unmigrated, "owner"), "upgrade", "0001_sessions_and_attempts"
        )
        assert done.returncode == 0, done.stderr[-2000:]
        with pytest.raises(SchemaNotReady) as raised:
            await ensure_schema(runtime)
        assert "behind" in str(raised.value) and "refusing to start" in str(
            raised.value
        )

        await upgrade_schema(server.url(unmigrated, "owner"), MIGRATIONS)
        await ensure_schema(runtime)  # at head, read as the runtime role
    finally:
        await runtime.dispose()


async def test_runtime_role_privileges(server, migrated):
    url = server.url(migrated)
    role = server.runtime_role

    async def can(table: str, privilege: str) -> bool:
        return await _scalar(
            url, "SELECT has_table_privilege(:r, :t, :p)", r=role, t=table, p=privilege
        )

    for table in (
        "sessions",
        "signin_challenges",
        "attempts",
        "factors",
        "recovery_codes",
    ):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert await can(f"admin.{table}", privilege), (table, privilege)
        assert not await can(f"admin.{table}", "TRUNCATE")
    assert await can("admin.audit_log", "SELECT")
    assert await can("admin.audit_log", "INSERT")
    for privilege in ("UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
        assert not await can("admin.audit_log", privilege), privilege
    assert await _scalar(
        url,
        "SELECT has_sequence_privilege(:r, 'admin.audit_log_seq_seq', 'USAGE')",
        r=role,
    )
    assert await can("admin.alembic_version", "SELECT")
    assert not await can("admin.alembic_version", "UPDATE")
    # no default privileges that could hand later tables (or audit_log) more
    assert (
        await _scalar(
            url,
            "SELECT count(*) FROM pg_default_acl WHERE defaclrole::regrole::text IN (:a, :b)",
            a=role,
            b=server.owner_role,
        )
        == 0
    )
    # the runtime role does not own anything and cannot create tables
    assert not await _scalar(
        url, "SELECT has_schema_privilege(:r, 'admin', 'CREATE')", r=role
    )


async def test_neither_role_reaches_the_other_services_schemas(server, migrated):
    url = server.url(migrated)
    for role in (server.runtime_role, server.owner_role):
        for schema in ("app", "auth", "google", "jobs"):
            assert not await _scalar(
                url,
                "SELECT has_schema_privilege(:r, :s, 'USAGE') "
                "OR has_schema_privilege(:r, :s, 'CREATE')",
                r=role,
                s=schema,
            ), (role, schema)
            reachable = await _scalar(
                url,
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = :s AND c.relkind IN ('r', 'v', 'S') "
                "AND (has_table_privilege(:r, c.oid, 'SELECT') "
                "OR has_table_privilege(:r, c.oid, 'INSERT'))",
                r=role,
                s=schema,
            )
            assert reachable == 0, (role, schema)


async def test_runtime_role_cannot_run_ddl(server, migrated):
    engine = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            with pytest.raises(DBAPIError, match="permission denied"):
                await conn.execute(text("CREATE TABLE admin.sneaky (x int)"))
    finally:
        await engine.dispose()


async def test_the_roles_script_is_idempotent(server, migrated):
    url = server.url(migrated)
    sql = roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw)
    for _ in range(2):
        await _execute(url, sql)
    # still works as the runtime role, still no UPDATE on the log
    runtime = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    try:
        await ensure_schema(runtime)
    finally:
        await runtime.dispose()
    assert not await _scalar(
        url,
        "SELECT has_table_privilege(:r, 'admin.audit_log', 'UPDATE')",
        r=server.runtime_role,
    )
    assert await _scalar(
        url,
        "SELECT has_table_privilege(:r, 'admin.audit_log', 'INSERT')",
        r=server.runtime_role,
    )
    assert (
        await _scalar(
            url,
            "SELECT count(*) FROM pg_roles WHERE rolname IN (:a, :b) "
            "AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole",
            a=server.runtime_role,
            b=server.owner_role,
        )
        == 2
    )
    assert (
        await _scalar(
            url,
            "SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'admin'",
        )
        == server.owner_role
    )


def test_named_roles_resolve_with_overrides(monkeypatch):
    from backend.admin.migration_support import role_name

    monkeypatch.delenv("ADMIN_DB_RUNTIME_ROLE", raising=False)
    monkeypatch.delenv("ADMIN_DB_ROLE_TASKS", raising=False)
    assert role_name() == "bc_admin"
    assert role_name("tasks") == "bc_tasks"
    monkeypatch.setenv("ADMIN_DB_ROLE_TASKS", "bc_tasks_x1")
    assert role_name("tasks") == "bc_tasks_x1"
    monkeypatch.setenv("ADMIN_DB_ROLE_TASKS", "x; DROP")
    with pytest.raises(ValueError):
        role_name("tasks")
    with pytest.raises(ValueError):
        role_name("Bad Name")
