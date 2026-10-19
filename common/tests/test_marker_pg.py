"""``migration_verified`` reads the latest service-wide marker, on a live Postgres."""

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from common.db import DatabaseSettings, make_base, make_engine
from common.db.marker import (
    SCOPE_GROUP,
    SCOPE_SERVICE,
    StoreMigrationMixin,
    migration_verified,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)
SCHEMA = "common_marker_test"
Base = make_base(SCHEMA)


class StoreMigration(Base, StoreMigrationMixin):
    __tablename__ = "store_migration"


@pytest.fixture
async def engine():
    engine = make_engine(DatabaseSettings.from_env(), application_name="marker-tests")
    async with engine.begin() as c:
        await c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await c.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    yield engine
    async with engine.begin() as c:
        await c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    await engine.dispose()


def _row(scope, at, run_id, collections, based_on=None, service="backend"):
    return {
        "service": service,
        "scope": scope,
        "groups": ["forms"],
        "collections": collections,
        "verified_at": at,
        "code_version": "0.1.0+schema.0017",
        "run_id": run_id,
        "based_on": based_on,
    }


async def test_no_table_or_no_marker_reads_as_not_verified(engine):
    async with engine.connect() as conn:
        assert await migration_verified(conn, "backend", schema=SCHEMA) is None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # a group row alone is not the marker
        now = datetime.now(timezone.utc)
        await conn.execute(
            StoreMigration.__table__.insert(),
            [_row(SCOPE_GROUP, now, "g1", {"forms": {"mongo": 1, "postgres": 1}})],
        )
    async with engine.connect() as conn:
        assert await migration_verified(conn, "backend", schema=SCHEMA) is None


async def test_the_latest_service_row_is_the_marker(engine):
    earlier = datetime.now(timezone.utc) - timedelta(days=1)
    later = earlier + timedelta(hours=2)
    counts = {"forms": {"group": "forms", "mongo": 2, "postgres": 2}}
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            StoreMigration.__table__.insert(),
            [
                _row(SCOPE_SERVICE, earlier, "old", counts),
                _row(
                    SCOPE_SERVICE,
                    later,
                    "new",
                    counts,
                    based_on=[{"group": "forms", "run_id": "g"}],
                ),
                _row(SCOPE_SERVICE, later, "other", counts, service="auth"),
            ],
        )
    async with engine.connect() as conn:
        marker = await migration_verified(conn, "backend", schema=SCHEMA)
        assert marker is not None
        assert (marker.run_id, marker.verified_at) == ("new", later)
        assert marker.combined and marker.groups == ("forms",)
        assert marker.counts() == {"forms": {"mongo": 2, "postgres": 2}}
        assert marker.as_dict()["code_version"] == "0.1.0+schema.0017"
        # a startup guard can require that today's collections are all covered
        assert await migration_verified(
            conn, "backend", schema=SCHEMA, collections=["forms"]
        )
        assert (
            await migration_verified(
                conn, "backend", schema=SCHEMA, collections=["forms", "new_table"]
            )
            is None
        )
