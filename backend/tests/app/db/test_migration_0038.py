"""Revision 0038 (audit log reader): three generated columns and four indexes on
``workspace_audit_events``, filled for the rows that exist, a downgrade that
removes exactly them, an upgrade again afterwards, and the page's queries using
the new indexes. Throw-away database, as ``test_migrations``."""

import asyncio
import datetime as dt

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.repositories.postgres.workspace_audit import (
    PostgresWorkspaceAuditRepository,
)
from tests.app.db.test_migrations import (  # noqa: F401 (scratch_url is a fixture)
    _config,
    _diff,
    _execute,
    scratch_url,
)

TABLE = "workspace_audit_events"
COLUMNS = ["form_id", "target_user_id", "user_id"]
INDEXES = [
    "ix_workspace_audit_events_actor",
    "ix_workspace_audit_events_form",
    "ix_workspace_audit_events_keyset",
    "ix_workspace_audit_events_target",
]
WS_A = "6ad000000000000000000001"
WS_B = "6ad000000000000000000002"


def _run(url, statement):
    return asyncio.run(_execute(url, statement))


async def _statement(url, statement):
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


def _insert(oid: str, workspace: str, at: str, event="access_grant_added", **ids) -> str:
    extra = "".join(f", '{k}', '{v}'" for k, v in ids.items())
    return (
        f"INSERT INTO app.{TABLE} (id, created_at, doc, _bc_checksum) VALUES ('{oid}', '{at}', "
        f"jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        f"'workspace_id', jsonb_build_object('$oid', '{workspace}'), "
        f"'event', '{event}'{extra}), 'x') RETURNING id"
    )


def _columns(url):
    return sorted(
        r[0]
        for r in _run(
            url,
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'app' "
            f"AND table_name = '{TABLE}' AND column_name IN ('form_id', 'user_id', 'target_user_id')",
        )
    )


def _indexes(url):
    return sorted(
        r[0]
        for r in _run(
            url,
            f"SELECT indexname FROM pg_indexes WHERE schemaname = 'app' AND tablename = '{TABLE}' "
            "AND indexname LIKE 'ix_workspace_audit_events_%'",
        )
        if r[0] in INDEXES
    )


def test_0038_follows_0037_on_the_one_chain():
    scripts = ScriptDirectory.from_config(_config("postgresql://unused"))
    revision = scripts.get_revision("0038")
    assert revision is not None and revision.down_revision == "0037"
    assert len(scripts.get_heads()) == 1


def test_upgrade_adds_the_columns_and_indexes_and_downgrade_removes_them(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "0037")
    assert _columns(scratch_url) == []
    # a row written before the revision: its ids are inside ``doc``
    _run(
        scratch_url,
        _insert(
            "6ad0000000000000000000a1",
            WS_A,
            "2026-10-01T10:00:00Z",
            form_id="form-1",
            user_id="user-1",
            target_user_id="user-2",
        ),
    )

    command.upgrade(config, "0038")
    assert _columns(scratch_url) == COLUMNS
    assert _indexes(scratch_url) == INDEXES
    # exactly what the models declare, but for what 0039, 0040 and 0041 add
    assert [
        d
        for d in asyncio.run(_diff(scratch_url))
        if "scim_group_team_links" not in repr(d)
        and "scim_users" not in repr(d)
        and "form_report_views" not in repr(d)
        and "captcha_daily_counts" not in repr(d)
    ] == []
    # the existing row has them filled, the indexes see it
    assert _run(
        scratch_url,
        f"SELECT form_id, user_id, target_user_id FROM app.{TABLE}",
    ) == [("form-1", "user-1", "user-2")]

    command.downgrade(config, "0037")
    assert _columns(scratch_url) == []
    assert _indexes(scratch_url) == []
    # the two indexes of revision 0030 and the row are untouched
    assert _run(scratch_url, f"SELECT count(*) FROM app.{TABLE}") == [(1,)]
    assert len(_run(
        scratch_url,
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'app' "
        f"AND tablename = '{TABLE}' AND indexname LIKE 'ix_app_{TABLE}_%'",
    )) == 2
    version = _run(scratch_url, "SELECT version_num FROM app.alembic_version")
    assert version == [("0037",)]

    command.upgrade(config, "0038")
    assert _columns(scratch_url) == COLUMNS
    assert _indexes(scratch_url) == INDEXES
    assert [
        d
        for d in asyncio.run(_diff(scratch_url))
        if "scim_group_team_links" not in repr(d)
        and "scim_users" not in repr(d)
        and "form_report_views" not in repr(d)
        and "captcha_daily_counts" not in repr(d)
    ] == []


def _plan(url, statement) -> str:
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    return "\n".join(r[0] for r in _run(url, "EXPLAIN " + sql))


def test_the_pages_queries_use_the_new_indexes(scratch_url):
    """A seeded table (200 workspaces of a few hundred entries each): the planner reaches the rows through the matching index, not a
    scan of the table."""
    config = _config(scratch_url)
    command.upgrade(config, "0038")
    _run(
        scratch_url,
        f"""
        INSERT INTO app.{TABLE} (id, created_at, doc, _bc_checksum)
        SELECT lpad(to_hex(n), 24, '0'),
               timestamptz '2026-01-01' + n * interval '1 minute',
               jsonb_build_object(
                 '_id', jsonb_build_object('$oid', lpad(to_hex(n), 24, '0')),
                 'workspace_id', jsonb_build_object('$oid', '6ad' || lpad(((n / 3) % 200)::text, 21, '0')),
                 'event', 'access_grant_added',
                 'user_id', 'user-' || (n % 13),
                 'form_id', 'form-' || (n % 17),
                 'target_user_id', 'person-' || (n % 11)),
               'x'
        FROM generate_series(1, 40000) AS n
        RETURNING 1
        """,
    )
    asyncio.run(_statement(scratch_url, f"ANALYZE app.{TABLE}"))
    workspace = "6ad000000000000000000007"
    some = ("access_grant_added", "access_grant_changed")
    statement = PostgresWorkspaceAuditRepository.page_statement
    when = dt.datetime(2026, 1, 20, tzinfo=dt.timezone.utc)

    cases = {
        "ix_workspace_audit_events_keyset": statement(workspace, 21, events=some),
        "ix_workspace_audit_events_form": statement(
            workspace, 21, events=some, form_id="form-3"
        ),
        "ix_workspace_audit_events_actor": statement(
            workspace, 21, events=some, actor="user-3"
        ),
        "ix_workspace_audit_events_target": statement(
            workspace, 21, events=some, target="person-3"
        ),
    }
    for index, query in cases.items():
        plan = _plan(scratch_url, query)
        assert index in plan, f"{index} not used:\n{plan}"
        assert "Seq Scan" not in plan, plan

    # the keyset continuation and a time range stay on the keyset index
    continued = statement(
        workspace, 21, before=(when, "ffffffffffffffffffffffff"), events=some,
        since=when - dt.timedelta(days=5), until=when,
    )
    plan = _plan(scratch_url, continued)
    assert "Seq Scan" not in plan, plan
