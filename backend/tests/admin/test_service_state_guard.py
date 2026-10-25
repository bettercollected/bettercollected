"""The portal's role can delete from ``settings.service_state`` only what the
retention loop removes: rows older than 7 days of a service with nothing newer
(admin revision 0019). The table's owner (``settings.report_state`` runs as it)
and a superuser are not narrowed."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.admin.conftest import needs_postgres
from tests.admin.engines import fixture_engine
from tests.admin.test_settings_store import as_superuser_raw, scalar

pytestmark = needs_postgres

ROWS = (  # service, instance, age in days
    ("svc_live", "fresh", 0),
    ("svc_live", "old", 20),  # a live service: report_state's job, not the portal's
    ("svc_gone", "gone1", 30),
    ("svc_gone", "gone2", 9),
    ("svc_young", "recent", 3),  # not stale yet
)


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, migrated):
    engine = fixture_engine(server.url(migrated))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def seeded(superuser):
    await as_superuser_raw(superuser, "DELETE FROM settings.service_state")
    for service, instance, age in ROWS:
        await as_superuser_raw(
            superuser,
            "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
            "VALUES (:s, :i, now() - make_interval(days => :d), 1)",
            s=service, i=instance, d=age,
        )
    yield
    await as_superuser_raw(superuser, "DELETE FROM settings.service_state")


async def left(superuser):
    return await scalar(
        superuser, "SELECT array_agg(instance ORDER BY instance) FROM settings.service_state"
    )


async def delete_as(engine, where):
    async with engine.begin() as conn:
        return (await conn.execute(text(f"DELETE FROM settings.service_state WHERE {where}"))).rowcount


@pytest.mark.parametrize(
    "where",
    [
        "true",  # the whole table
        "instance = 'fresh'",  # a live heartbeat
        "instance = 'old'",  # stale, but its service still reports
        "instance = 'recent'",  # younger than 7 days
        "service IN ('svc_gone', 'svc_young')",  # one row that may not go refuses the whole statement
    ],
)
async def test_the_portals_role_cannot_delete_a_live_or_young_heartbeat(runtime_engine, superuser, seeded, where):
    before = await left(superuser)
    with pytest.raises(DBAPIError) as err:
        await delete_as(runtime_engine, where)
    assert "stopped reporting" in str(err.value)
    assert await left(superuser) == before  # the statement is atomic


async def test_a_service_that_stopped_reporting_can_be_pruned(runtime_engine, superuser, seeded):
    assert await delete_as(runtime_engine, "service = 'svc_gone'") == 2
    assert await left(superuser) == ["fresh", "old", "recent"]


async def test_the_portal_can_delete_exactly_the_rows_the_retention_loop_does(runtime_engine, superuser, seeded):
    removed = await delete_as(
        runtime_engine,
        "ctid IN (SELECT s.ctid FROM settings.service_state s WHERE s.reported_at < now() - interval '7 days' "
        "AND NOT EXISTS (SELECT 1 FROM settings.service_state f WHERE f.service = s.service "
        "AND f.reported_at >= now() - interval '7 days'))",
    )
    assert removed == 2
    assert await left(superuser) == ["fresh", "old", "recent"]


async def test_the_owner_and_a_superuser_are_not_narrowed(server, migrated, superuser, seeded):
    owner = fixture_engine(server.url(migrated, "owner"))
    try:
        assert await delete_as(owner, "instance = 'fresh'") == 1  # report_state runs as the owner
    finally:
        await owner.dispose()
    assert await delete_as(superuser, "instance = 'old'") == 1
    assert await left(superuser) == ["gone1", "gone2", "recent"]


async def test_report_state_still_prunes_and_reports_through_the_guard(server, migrated, superuser, seeded):
    """A service whose only rows are stale reports again: its stale rows are pruned by
    ``settings.report_state`` (owner-run) and the new row lands."""
    await as_superuser_raw(superuser, "DELETE FROM settings.service_state")
    await as_superuser_raw(
        superuser,
        "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
        "VALUES ('backend', 'dead-1', now() - interval '10 days', 1)",
    )
    engine = fixture_engine(server.url(migrated, "reader:app"))
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "SELECT settings.report_state('alive-1', 1, CAST('{}' AS text[]), CAST('{}' AS text[]), false, '')"))
    finally:
        await engine.dispose()
    assert await left(superuser) == ["alive-1"]


async def test_the_guard_is_in_place_and_the_portal_cannot_remove_it(runtime_engine, superuser):
    assert await scalar(
        superuser,
        "SELECT count(*) FROM pg_trigger WHERE tgrelid = 'settings.service_state'::regclass "
        "AND tgname = 'service_state_delete_guard' AND tgenabled = 'O'",
    ) == 1
    for statement in (
        "ALTER TABLE settings.service_state DISABLE TRIGGER service_state_delete_guard",
        "DROP TRIGGER service_state_delete_guard ON settings.service_state",
        "CREATE OR REPLACE FUNCTION settings.service_state_delete_guard() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RETURN OLD; END $$",
    ):
        with pytest.raises(DBAPIError):
            async with runtime_engine.begin() as conn:
                await conn.execute(text(statement))
