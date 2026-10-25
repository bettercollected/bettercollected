"""The Alembic revisions must create exactly the tables the models declare, and roll back clean.

Runs against a throw-away database created for the test (so the local
app-postgres roles and the CI service database are never touched), skipped
when DATABASE_URL is unset. Synchronous on purpose: Alembic's env.py drives its
own event loop.
"""

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import auth.db.models  # noqa: F401
from auth.db.base import SCHEMA, Base
from common.db.alembic_support import metadata_diff
from common.db.engine import normalise_url

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)
SERVICE_DIR = Path(__file__).resolve().parents[2]  # .../auth


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


async def _admin(url: str, statement: str) -> None:
    engine = create_async_engine(
        _with_database(url, "postgres"),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


async def _diff(url: str) -> list:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(metadata_diff, Base.metadata, SCHEMA)
    finally:
        await engine.dispose()


async def _tables(url: str) -> list[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = :s ORDER BY 1"
                ),
                {"s": SCHEMA},
            )
            return [r[0] for r in rows]
    finally:
        await engine.dispose()


@pytest.fixture
def scratch_url():
    base_url = normalise_url(os.environ["DATABASE_URL"])
    name = f"bc_migtest_{uuid.uuid4().hex[:10]}"
    asyncio.run(_admin(base_url, f'CREATE DATABASE "{name}"'))
    try:
        yield _with_database(base_url, name)
    finally:
        asyncio.run(_admin(base_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def _config(url: str) -> Config:
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_DIR / "auth" / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_upgrade_head_matches_the_models_and_downgrade_base_is_clean(scratch_url):
    config = _config(scratch_url)

    command.upgrade(config, "head")
    diffs = asyncio.run(_diff(scratch_url))
    assert diffs == [], f"models and migrations have drifted: {diffs}"
    created = asyncio.run(_tables(scratch_url))
    expected = sorted(t.name for t in Base.metadata.sorted_tables) + ["alembic_version"]
    assert created == sorted(expected)

    command.downgrade(config, "base")
    assert asyncio.run(_tables(scratch_url)) == ["alembic_version"]


def test_upgrade_is_idempotent(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # nothing to do, must not fail
    assert asyncio.run(_diff(scratch_url)) == []


async def _execute(url: str, statement: str) -> list:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(statement))
            return [tuple(r) for r in result] if result.returns_rows else []
    finally:
        await engine.dispose()


def _account(oid: str, email: str) -> str:
    return (
        "INSERT INTO auth.users (id, doc, _bc_checksum) VALUES "
        f"('{oid}', jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        f"'email', '{email}'), 'x') RETURNING id"
    )


def test_case_variant_accounts_stop_0005_before_it_changes_anything(scratch_url):
    """Revision 0005's unique lower(email) index refuses, with counts only and
    before any change, while two accounts' emails differ only in case; no
    account is merged or deleted."""
    config = _config(scratch_url)
    command.upgrade(config, "0004")
    asyncio.run(_execute(scratch_url, _account("a" * 24, "Jane@Example.com")))
    asyncio.run(_execute(scratch_url, _account("b" * 24, "jane@example.com")))
    asyncio.run(_execute(scratch_url, _account("c" * 24, "other@example.com")))

    with pytest.raises(RuntimeError) as refused:
        command.upgrade(config, "head")
    message = str(refused.value)
    assert "1 email addresses held by 2 accounts" in message
    assert "HAVING count(*) > 1" in message  # the read-only query to find them
    assert "jane" not in message.lower() and "a" * 24 not in message

    rows = asyncio.run(_execute(scratch_url, "SELECT id, email FROM auth.users"))
    assert len(rows) == 3 and ("a" * 24, "Jane@Example.com") in rows
    version = asyncio.run(
        _execute(scratch_url, "SELECT version_num FROM auth.alembic_version")
    )
    assert version == [("0004",)]

    # resolved by hand: it goes through, and the index holds from then on
    asyncio.run(
        _execute(
            scratch_url, f"DELETE FROM auth.users WHERE id = '{'b' * 24}' RETURNING id"
        )
    )
    command.upgrade(config, "head")
    with pytest.raises(Exception, match="uq_users_email_lower"):
        asyncio.run(_execute(scratch_url, _account("d" * 24, "JANE@example.com")))
    # downgrade restores the exact constraint and keeps the accounts
    command.downgrade(config, "0004")
    asyncio.run(_execute(scratch_url, _account("d" * 24, "JANE@example.com")))
    with pytest.raises(Exception, match="uq_users_email"):
        asyncio.run(_execute(scratch_url, _account("e" * 24, "JANE@example.com")))
