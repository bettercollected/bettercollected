"""The Health page's job queue line: ``admin.queue_counts_app()`` and its page.

The function counts the queue's jobs by state and reports how long the longest
waiting job has been due. It reads four columns of the queue's two tables and never a
job's arguments; only the portal's role may execute it; its answer is data.
"""

from __future__ import annotations

import json
import re

import pytest
from sqlalchemy import text

from backend.admin.repositories import views
from backend.admin.services import pages as pg
from tests.admin.conftest import _execute, needs_postgres
from tests.admin.engines import fixture_engine
from tests.admin.test_loops import QUEUE_TABLES
from tests.admin.test_portal_health import refused, rerun_roles
from tests.admin.test_portal_pages import signed_in, superuser  # noqa: F401 - fixture

pytestmark = needs_postgres

SEALED = "sealed-argument-never-shown"


async def lay_out_queue(server, database):
    """The queue's tables, made by the backend's role (python -m backend.jobs.schema),
    then the roles script again, as every deploy runs it."""
    await _execute(server.url(database, "reader:app"), QUEUE_TABLES)
    await rerun_roles(server, database)


async def enqueue(superuser, status="todo", deferred_minutes_ago=1.0, scheduled_minutes_ago=None,
                  task="delete_user"):
    """A job deferred ``deferred_minutes_ago`` minutes ago; ``scheduled_minutes_ago``
    negative means scheduled for later."""
    async with superuser.begin() as conn:
        job_id = (await conn.execute(
            text("INSERT INTO jobs.procrastinate_jobs (task_name, status, args, scheduled_at) "
                 "VALUES (:t, CAST(:s AS jobs.procrastinate_job_status), "
                 "jsonb_build_object('sealed', CAST(:a AS text)), "
                 "CASE WHEN CAST(:m AS float8) IS NULL THEN NULL "
                 "ELSE now() - make_interval(secs => CAST(:m AS float8) * 60) END) RETURNING id"),
            {"t": task, "s": status, "a": SEALED, "m": scheduled_minutes_ago})).scalar_one()
        await conn.execute(
            text("INSERT INTO jobs.procrastinate_events (job_id, type, at) VALUES "
                 "(:j, 'deferred', now() - make_interval(secs => CAST(:d AS float8) * 60))"),
            {"j": job_id, "d": deferred_minutes_ago})
    return job_id


async def counts(runtime_engine):
    async with runtime_engine.connect() as conn:
        return await views.queue_counts(conn)


async def test_before_the_queue_exists_the_function_answers_null(runtime_engine):
    async with runtime_engine.connect() as conn:
        assert (await conn.execute(text("SELECT admin.queue_counts_app()"))).scalar_one() is None
    assert await counts(runtime_engine) is None


async def test_an_empty_queue_counts_zero_and_nothing_waits(server, migrated, superuser, runtime_engine):  # noqa: F811
    await lay_out_queue(server, migrated)
    assert await counts(runtime_engine) == {
        "todo": 0, "scheduled": 0, "doing": 0, "failed": 0, "oldest_todo_seconds": None}


async def test_counts_by_state_and_the_age_of_the_oldest_waiting_job(server, migrated, superuser, runtime_engine):  # noqa: F811
    await lay_out_queue(server, migrated)
    await enqueue(superuser, "todo", deferred_minutes_ago=5)
    await enqueue(superuser, "todo", deferred_minutes_ago=120, task="delete_response")
    await enqueue(superuser, "todo", deferred_minutes_ago=30)
    await enqueue(superuser, "doing", deferred_minutes_ago=500)
    await enqueue(superuser, "failed", deferred_minutes_ago=500)
    await enqueue(superuser, "failed", deferred_minutes_ago=500)
    await enqueue(superuser, "succeeded", deferred_minutes_ago=500)
    await enqueue(superuser, "cancelled", deferred_minutes_ago=500)
    result = await counts(runtime_engine)
    assert {k: v for k, v in result.items() if k != "oldest_todo_seconds"} == {
        "todo": 3, "scheduled": 0, "doing": 1, "failed": 2}
    assert 7200 <= result["oldest_todo_seconds"] <= 7210


async def test_a_job_scheduled_for_later_or_retrying_does_not_look_stuck(server, migrated, superuser, runtime_engine):  # noqa: F811
    await lay_out_queue(server, migrated)
    # a response deletion set for its expiry, deferred long ago
    await enqueue(superuser, "todo", deferred_minutes_ago=60 * 24 * 90, scheduled_minutes_ago=-60 * 24 * 30)
    # a retry whose back-off ended two minutes ago, first deferred three hours ago
    await enqueue(superuser, "todo", deferred_minutes_ago=180, scheduled_minutes_ago=2)
    result = await counts(runtime_engine)
    assert (result["todo"], result["scheduled"]) == (1, 1)
    assert 120 <= result["oldest_todo_seconds"] <= 130


async def test_the_function_reads_no_job_argument_and_only_the_portal_role_may_ask(server, migrated, superuser):  # noqa: F811
    await lay_out_queue(server, migrated)
    owner = f"bc_count_app_{server.suffix}"
    async with superuser.connect() as conn:
        async def column(table, name):
            return (await conn.execute(text("SELECT has_column_privilege(:r, :t, :c, 'SELECT')"),
                                       {"r": owner, "t": table, "c": name})).scalar_one()

        for name in ("id", "task_name", "status", "scheduled_at"):
            assert await column("jobs.procrastinate_jobs", name)
        for name in ("args", "queue_name", "attempts"):
            assert not await column("jobs.procrastinate_jobs", name), name
        fn = (await conn.execute(text(
            "SELECT r.rolname, p.prosecdef, p.provolatile, p.proconfig, p.pronargs, p.proacl::text AS acl, "
            "pg_get_functiondef(p.oid) AS definition FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_roles r ON r.oid = p.proowner "
            "WHERE n.nspname = 'admin' AND p.proname = 'queue_counts_app'"))).one()
    assert fn.rolname == owner and fn.prosecdef and fn.provolatile in ("s", b"s") and fn.pronargs == 0
    assert "search_path=pg_catalog, pg_temp" in fn.proconfig
    grantees = {g.split("=")[0] for g in re.findall(r"[^{},]+=[A-Za-z]*/[^,}]+", fn.acl)}
    assert grantees == {server.runtime_role, owner}, fn.acl  # not PUBLIC
    body = fn.definition.split("$function$")[1]
    assert re.search(r"\b(INSERT|UPDATE|DELETE|EXECUTE)\b", body, re.I) is None
    assert "args" not in body and "admin." not in body
    # every table reference names its schema
    assert not re.search(r"\b(FROM|JOIN)\s+(?!jobs\.|pg_catalog\.)", body)
    for role in ("reader:app", "reader:auth", "reader:google", "reader:tasks", "owner"):
        engine = fixture_engine(server.url(migrated, role))
        try:
            assert "permission denied" in await refused(engine, "SELECT admin.queue_counts_app()"), role
        finally:
            await engine.dispose()


async def test_the_roles_script_is_idempotent_for_the_function(server, migrated, superuser):  # noqa: F811
    await lay_out_queue(server, migrated)

    async def state():
        async with superuser.connect() as conn:
            return (await conn.execute(text(
                "SELECT p.proowner::regrole::text, p.proacl::text, md5(pg_get_functiondef(p.oid)) "
                "FROM pg_proc p WHERE p.oid = 'admin.queue_counts_app()'::regprocedure"))).one()

    first = await state()
    await rerun_roles(server, migrated)
    await rerun_roles(server, migrated)
    assert await state() == first


async def test_a_caller_cannot_steer_the_function_through_its_search_path(server, migrated, superuser):  # noqa: F811
    await lay_out_queue(server, migrated)
    await enqueue(superuser, "todo", deferred_minutes_ago=3)
    # the portal's role holds no TEMP right at all; a superuser stands in for any caller
    # that can plant temporary objects
    engine = fixture_engine(server.url(migrated))
    try:
        async with engine.connect() as conn:
            assert not (await conn.execute(text(
                f"SELECT has_database_privilege('{server.runtime_role}', current_database(), 'TEMP')"))).scalar_one()
            # the caller's own temp objects come first on ITS path; the definer's pinned
            # path (pg_catalog, then pg_temp last) must still pick the real ones
            await conn.execute(text("SET search_path TO pg_temp, public"))
            await conn.execute(text(
                "CREATE FUNCTION pg_temp.now() RETURNS timestamptz LANGUAGE sql "
                "AS $$ SELECT '2000-01-01'::timestamptz $$"))
            await conn.execute(text(
                "CREATE FUNCTION pg_temp.to_regclass(text) RETURNS regclass LANGUAGE sql "
                "AS $$ SELECT NULL::regclass $$"))
            await conn.execute(text(
                "CREATE FUNCTION pg_temp.has_schema_privilege(name, text) RETURNS boolean LANGUAGE sql "
                "AS $$ SELECT false $$"))
            await conn.execute(text("CREATE TEMP TABLE procrastinate_jobs (id int, status text)"))
            await conn.execute(text("CREATE TEMP TABLE procrastinate_events (job_id int)"))
            raw = (await conn.execute(text("SELECT admin.queue_counts_app()"))).scalar_one()
            answer = json.loads(raw) if isinstance(raw, str) else raw
    finally:
        await engine.dispose()
    assert answer["todo"] == 1 and 175 <= answer["oldest_todo_seconds"] <= 190


EVIL = """
CREATE FUNCTION jobs.evil(x bigint) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO jobs.loot VALUES (jsonb_build_object('ran_as', current_user));
    BEGIN
        INSERT INTO jobs.loot SELECT to_jsonb(a) FROM admin.audit_log a;
        INSERT INTO jobs.loot VALUES (jsonb_build_object('stole', 'audit'));
    EXCEPTION WHEN others THEN
        INSERT INTO jobs.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    BEGIN
        INSERT INTO jobs.loot SELECT to_jsonb(j) FROM jobs.procrastinate_jobs_real j;
        INSERT INTO jobs.loot VALUES (jsonb_build_object('stole', 'arguments'));
    EXCEPTION WHEN others THEN
        INSERT INTO jobs.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    RETURN true;
END $$
"""


async def test_a_hostile_queue_owner_gets_nothing_from_planting_code(server, migrated, superuser):  # noqa: F811
    """The jobs schema's owner swaps the queue table for a view that calls its own
    function: it runs as the count role, which holds four columns and nothing else."""
    await lay_out_queue(server, migrated)
    await enqueue(superuser, "todo", deferred_minutes_ago=1)
    count_role = f"bc_count_app_{server.suffix}"
    owner = fixture_engine(server.url(migrated, "reader:app"))
    try:
        async with owner.begin() as conn:
            await conn.execute(text("ALTER TABLE jobs.procrastinate_jobs RENAME TO procrastinate_jobs_real"))
            await conn.execute(text("CREATE TABLE jobs.loot (doc jsonb)"))
            await conn.execute(text(f"GRANT INSERT ON jobs.loot TO {count_role}"))
            await conn.execute(text(EVIL))
            await conn.execute(text(
                "CREATE VIEW jobs.procrastinate_jobs AS SELECT id, task_name, status, scheduled_at "
                "FROM jobs.procrastinate_jobs_real WHERE jobs.evil(id)"))
            await conn.execute(text(f"GRANT SELECT ON jobs.procrastinate_jobs TO {count_role}"))
        for statement in (
            "ALTER FUNCTION admin.queue_counts_app() SECURITY INVOKER",
            "ALTER FUNCTION admin.queue_counts_app() OWNER TO CURRENT_USER",
            "DROP FUNCTION admin.queue_counts_app()",
            "CREATE OR REPLACE FUNCTION admin.queue_counts_app() RETURNS jsonb LANGUAGE sql "
            "AS $$ SELECT '{}'::jsonb $$",
        ):
            assert await refused(owner, statement)
    finally:
        await owner.dispose()
    portal_engine = fixture_engine(server.url(migrated, "runtime"))
    try:
        async with portal_engine.begin() as conn:  # committed: the planted function writes its loot
            result = await views.queue_counts(conn)
    finally:
        await portal_engine.dispose()
    assert result is not None and result["todo"] == 1
    owner = fixture_engine(server.url(migrated, "reader:app"))
    try:
        async with owner.connect() as conn:
            loot = [r[0] for r in (await conn.execute(text("SELECT doc FROM jobs.loot"))).all()]
    finally:
        await owner.dispose()
    assert {"ran_as": count_role} in loot, "the planted code did not run: the test proves nothing"
    assert not [row for row in loot if "stole" in row], loot
    denied = [row["denied"] for row in loot if "denied" in row]
    assert denied and all("permission denied" in d for d in denied), denied


async def test_a_hostile_answer_is_kept_to_whole_numbers(runtime_engine, monkeypatch):
    class Conn:
        async def execute(self, statement):
            class Result:
                def scalar_one(self):
                    return {"todo": "<b>7</b>", "scheduled": -4, "doing": True, "failed": 2.0,
                            "oldest_todo_seconds": "9", "extra": "x"}
            return Result()

    assert await views.queue_counts(Conn()) == {
        "todo": 0, "scheduled": 0, "doing": 0, "failed": 2, "oldest_todo_seconds": 0}


# -- the page -------------------------------------------------------------------------
def _queue_section(html):
    return html.split("<h2>Job queue</h2>", 1)[1].split("<h2>", 1)[0]


async def test_the_health_page_shows_a_healthy_queue(server, migrated, superuser, portal, app):  # noqa: F811
    await lay_out_queue(server, migrated)
    await enqueue(superuser, "todo", deferred_minutes_ago=2)
    await enqueue(superuser, "doing")
    await enqueue(superuser, "todo", deferred_minutes_ago=60 * 24, scheduled_minutes_ago=-600)
    await enqueue(superuser, "succeeded", deferred_minutes_ago=999)
    health = await portal.pages.health()
    assert health.queue.state == "ok"
    assert (health.queue.todo, health.queue.scheduled, health.queue.doing, health.queue.failed) == (1, 1, 1, 0)
    b = await signed_in(portal, app)
    html = (await b.get("/health")).text
    section = _queue_section(html)
    assert '<span class="ok">healthy</span>' in section and "warn" not in section.replace("Needs attention when", "")
    assert re.search(r"<td>1</td>\s*<td>1[12]\d s</td>\s*<td>1</td>\s*<td>1</td>\s*<td>0</td>", section), section
    assert SEALED not in html and "delete_user" not in html
    assert "The job queue needs attention" not in (await b.get("/")).text
    await b.aclose()


async def test_a_failed_job_turns_the_line_amber(server, migrated, superuser, portal, app):  # noqa: F811
    await lay_out_queue(server, migrated)
    await enqueue(superuser, "failed")
    health = await portal.pages.health()
    assert health.queue.state == "warning" and health.queue.failed == 1
    b = await signed_in(portal, app)
    section = _queue_section((await b.get("/health")).text)
    assert '<span class="warn">needs attention</span>' in section
    assert '<span class="warn">1</span>' in section
    assert "The job queue needs attention." in (await b.get("/")).text
    await b.aclose()


@pytest.mark.parametrize("minutes,warn", [(14, False), (16, True)])
async def test_a_job_waiting_over_fifteen_minutes_turns_the_line_amber(
        server, migrated, superuser, portal, app, minutes, warn):  # noqa: F811
    assert pg.QUEUE_WAIT_WARN_SECONDS == 900
    await lay_out_queue(server, migrated)
    await enqueue(superuser, "todo", deferred_minutes_ago=minutes)
    health = await portal.pages.health()
    assert (health.queue.state == "warning") is warn and health.queue.stale is warn
    b = await signed_in(portal, app)
    section = _queue_section((await b.get("/health")).text)
    assert (re.search(r'<span class="warn">\d+ s</span>', section) is not None) is warn
    await b.aclose()


async def test_before_the_queue_exists_the_page_says_so(server, migrated, portal, app):
    health = await portal.pages.health()
    assert health.queue.state == "missing"
    b = await signed_in(portal, app)
    section = _queue_section((await b.get("/health")).text)
    assert "no job queue in the database yet" in section and "<table" not in section
    await b.aclose()


async def test_without_the_function_the_page_names_the_roles_script(server, migrated, portal, app, superuser):  # noqa: F811
    async with superuser.begin() as conn:
        await conn.execute(text("DROP FUNCTION admin.queue_counts_app()"))
    health = await portal.pages.health()
    assert health.queue == pg.QueueStatus("unavailable")
    b = await signed_in(portal, app)
    section = _queue_section((await b.get("/health")).text)
    assert '<span class="bad">not available</span>' in section
    assert "run postgres/ensure-admin-roles.sh" in section and "<table" not in section
    await b.aclose()
