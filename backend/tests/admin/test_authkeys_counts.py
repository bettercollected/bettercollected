"""The counts the auth key rotation tasks gate a drop of the previous key on
(``postgres/ensure-admin-roles.sh``): ``admin.sealed_jobs_pending()``,
``admin.sessions_on_old_key(ts)`` and ``admin.drafts_on_old_key(ts)``.

A number each (NULL when the tables cannot be seen, so the task refuses rather
than read it as zero), executable by the task runner's role alone, owned by the
counts role that reads columns and never writes. Run against a database laid
out like production: the admin chain, the backend's real migrations, the job
queue's tables, then the roles script.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest_asyncio
from bson import ObjectId
from sqlalchemy import text

from backend.db.startup import MIGRATIONS as APP_MIGRATIONS
from common.db.canonical import canonical_document, checksum
from common.db.schema_guard import upgrade_schema
from tests.admin.conftest import _execute, needs_postgres
from tests.admin.engines import fixture_engine
from tests.admin.test_loops import QUEUE_TABLES
from tests.admin.test_portal_health import refused, rerun_roles
from tests.admin.test_portal_pages import superuser  # noqa: F401 - fixture

pytestmark = needs_postgres

NOW = dt.datetime.now(dt.timezone.utc)
PROMOTED = NOW - dt.timedelta(days=2)
TASKS = ("purge_provider_credentials", "revoke_google_grant", "delete_user")


@pytest_asyncio.fixture(loop_scope="session")
async def tasks(server, migrated):
    engine = fixture_engine(server.url(migrated, "reader:tasks"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def laid_out(server, migrated, superuser):
    await upgrade_schema(server.url(migrated, "reader:app"), APP_MIGRATIONS)
    await _execute(server.url(migrated, "reader:app"), QUEUE_TABLES)
    await rerun_roles(server, migrated)
    yield migrated


async def one(engine, sql, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def insert(superuser, table: str, **fields):
    oid = ObjectId()
    doc = canonical_document({"_id": oid, **fields})
    async with superuser.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO app.{table} (id, doc, _bc_checksum) VALUES (:i, CAST(:d AS jsonb), :c)"),
            {"i": str(oid), "d": json.dumps(doc), "c": checksum(doc)},
        )


async def job(superuser, task: str, status: str):
    async with superuser.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO jobs.procrastinate_jobs (task_name, status, args) VALUES "
                "(:t, CAST(:s AS jobs.procrastinate_job_status), "
                "jsonb_build_object('sealed', 'never-read'))"
            ),
            {"t": task, "s": status},
        )


async def test_before_the_tables_exist_every_count_is_null_not_zero(migrated, tasks):
    assert await one(tasks, "SELECT admin.sealed_jobs_pending()") is None
    assert await one(tasks, "SELECT admin.sessions_on_old_key(:t)", t=PROMOTED) is None
    assert await one(tasks, "SELECT admin.drafts_on_old_key(:t)", t=PROMOTED) is None


async def test_pending_jobs_are_the_three_sealed_tasks_in_flight(laid_out, tasks, superuser):
    assert await one(tasks, "SELECT admin.sealed_jobs_pending()") == 0
    for task in TASKS:
        await job(superuser, task, "todo")
    await job(superuser, "delete_user", "doing")
    await job(superuser, "delete_user", "succeeded")  # done
    await job(superuser, "delete_user", "failed")  # not retried by the queue
    await job(superuser, "run_action", "todo")  # carries ids and a run token only
    await job(superuser, "delete_response", "todo")
    assert await one(tasks, "SELECT admin.sealed_jobs_pending()") == 4


async def test_sessions_on_the_old_key_are_the_live_ones_not_re_issued_since(laid_out, tasks, superuser):
    day = dt.timedelta(days=1)
    base = {"user_id": "u1", "refresh_jti": "j", "expires_at": NOW + 10 * day}
    # signed with the old key: created or last rotated before the promotion
    await insert(superuser, "sessions", **base, created_at=NOW - 5 * day)
    await insert(superuser, "sessions", **base, created_at=NOW - 9 * day, rotated_at=NOW - 3 * day)
    # re-issued after the promotion: new key (created before, rotated after; or created after)
    await insert(superuser, "sessions", **base, created_at=NOW - 9 * day, rotated_at=NOW - day)
    await insert(superuser, "sessions", **base, created_at=NOW - day)
    # not live: revoked, or expired
    await insert(superuser, "sessions", **base, created_at=NOW - 5 * day, revoked_at=NOW - day)
    await insert(
        superuser, "sessions", user_id="u1", refresh_jti="j", created_at=NOW - 5 * day,
        expires_at=NOW - dt.timedelta(minutes=1),
    )
    assert await one(tasks, "SELECT admin.sessions_on_old_key(:t)", t=PROMOTED) == 2
    assert await one(tasks, "SELECT admin.sessions_on_old_key(:t)", t=NOW - 20 * day) == 0
    assert await one(tasks, "SELECT admin.sessions_on_old_key(:t)", t=NOW + day) == 4


async def test_drafts_on_the_old_key_are_the_unexpired_ones_with_a_link_or_edit_key(laid_out, tasks, superuser):
    day = dt.timedelta(days=1)
    live = {"form_id": "f1", "payload": "p", "expires_at": NOW + 5 * day}
    await insert(superuser, "form_drafts", **live, workspace_id="65e5501d00000000000000a1",
                 token_hash="a" * 64, created_at=NOW - 4 * day)
    await insert(superuser, "form_drafts", **live, workspace_id="65e5501d00000000000000a1",
                 edit_key_hash="b" * 64, created_at=NOW - 3 * day)
    # made after the promotion: the new key
    await insert(superuser, "form_drafts", **live, workspace_id="65e5501d00000000000000a1",
                 token_hash="c" * 64, created_at=NOW - dt.timedelta(hours=1))
    # a signed-in respondent's draft has no link or edit key; an expired one does not count
    await insert(superuser, "form_drafts", **live, workspace_id="65e5501d00000000000000a1",
                 owner_id="u1", created_at=NOW - 4 * day)
    await insert(superuser, "form_drafts", form_id="f1", payload="p", expires_at=NOW - day,
                 workspace_id="65e5501d00000000000000a1", token_hash="d" * 64, created_at=NOW - 4 * day)
    assert await one(tasks, "SELECT admin.drafts_on_old_key(:t)", t=PROMOTED) == 2


async def test_only_the_task_runner_may_ask_and_a_null_time_is_not_a_count(laid_out, server, tasks, superuser):
    for sql in (
        "SELECT admin.sealed_jobs_pending()",
        "SELECT admin.sessions_on_old_key(now())",
        "SELECT admin.drafts_on_old_key(now())",
    ):
        for role in ("runtime", "reader:app", "reader:auth", "reader:google"):
            engine = fixture_engine(server.url(laid_out, role))
            try:
                assert "permission denied" in await refused(engine, sql), (role, sql)
            finally:
                await engine.dispose()
    assert await one(tasks, "SELECT admin.sessions_on_old_key(NULL)") is None
    assert await one(tasks, "SELECT admin.drafts_on_old_key(NULL)") is None


async def test_the_counts_role_reads_columns_and_writes_nothing(laid_out, server, superuser):
    owner = f"bc_count_app_{server.suffix}"
    async with superuser.connect() as conn:
        async def can(table, column, privilege="SELECT"):
            return (
                await conn.execute(
                    text("SELECT has_column_privilege(:r, :t, :c, :p)"),
                    {"r": owner, "t": table, "c": column, "p": privilege},
                )
            ).scalar_one()

        for column in ("id", "revoked_at", "expires_at", "doc"):
            assert await can("app.sessions", column)
        for column in ("id", "expires_at", "doc"):
            assert await can("app.form_drafts", column)
        assert not await can("app.sessions", "user_id")
        assert not await can("app.form_drafts", "owner_id")
        for table in ("app.sessions", "app.form_drafts"):
            assert not (
                await conn.execute(
                    text("SELECT has_table_privilege(:r, :t, 'UPDATE') OR has_table_privilege(:r, :t, 'INSERT') "
                         "OR has_table_privilege(:r, :t, 'DELETE')"),
                    {"r": owner, "t": table},
                )
            ).scalar_one()
        # the queue's arguments stay unread
        assert not await can("jobs.procrastinate_jobs", "args")
