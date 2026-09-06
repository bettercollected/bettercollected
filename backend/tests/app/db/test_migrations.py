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

import backend.db.models  # noqa: F401
from backend.db.base import SCHEMA, Base
from common.db.alembic_support import metadata_diff
from common.db.engine import normalise_url

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)
SERVICE_DIR = Path(__file__).resolve().parents[3]  # .../backend


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
    config.set_main_option(
        "script_location", str(SERVICE_DIR / "backend" / "migrations")
    )
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
