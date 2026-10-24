"""Shared fixtures: Postgres for the google suite (plans/postgres-consolidation.md).

Postgres is taken from DATABASE_URL when it names a *test* database, migrated
once per session with Alembic and emptied before each test that asks for it.
"""

import os
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import googleform.db.models  # noqa: F401 — registers the rows on the metadata
from googleform.db.base import SCHEMA, Base

TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")
SERVICE_DIR = Path(__file__).resolve().parents[1]

#: Test files that drive a Mongo server themselves, whatever the flags (store
#: parity, the migration CLI). They get the ``mongo`` marker: CI runs the
#: Postgres mode without Mongo and ``-m "not mongo"`` (docs/ci.md).
MONGO_DRIVEN = (
    "tests/integration/app/repository/test_postgres_parity.py",
    "tests/integration/test_migrate_marker.py",
    "tests/integration/test_migrate_tombstones.py",
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "mongo: the test drives a Mongo server itself, whatever the flags"
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.nodeid.partition("::")[0] in MONGO_DRIVEN:
            item.add_marker(pytest.mark.mongo)


def _postgres_configured() -> bool:
    if not TEST_DATABASE_URL:
        return False
    name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
    return "test" in name


def _alembic_upgrade_head() -> None:
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")


async def _truncate_postgres() -> None:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                await conn.execute(text(f'DELETE FROM "{SCHEMA}"."{table.name}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def _postgres_schema():
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    _alembic_upgrade_head()


@pytest.fixture(scope="session", autouse=True)
def _schema_when_served_from_postgres():
    """When the flags put a repository group on Postgres the app refuses to start
    on an unmigrated schema. Migrate up front instead of relying on an earlier
    test, or an earlier run against the same database, to have done it: each
    persistence mode can then run alone on a fresh database (CI runs them as
    parallel jobs)."""
    from common.db.flags import load_flags

    if _postgres_configured() and load_flags().requires_postgres():
        _alembic_upgrade_head()


@pytest_asyncio.fixture
async def clean_postgres(_postgres_schema):
    """For tests that drive the Postgres repositories directly."""
    await _truncate_postgres()
    yield
