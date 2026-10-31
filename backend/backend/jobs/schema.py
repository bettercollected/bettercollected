"""Apply procrastinate's schema into the ``jobs`` schema, once.

``python -m backend.jobs.schema`` — run at deploy after Alembic (deploy.sh),
as the backend's role (bc_app owns ``jobs``). Idempotent: a no-op when the
queue table already exists, so it cannot hang or half-apply a second time.
With ``DB_AUTO_MIGRATE=true`` the backend applies it itself at startup under an
advisory lock (:data:`JOBS_SCHEMA`, wired in ``backend.db.startup``).
"""

from __future__ import annotations

import asyncio
import re
import sys

from procrastinate import App
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.jobs.app import app, build_connector, postgres_jobs_enabled
from common.db import AuxiliarySchema

QUEUE_TABLE = "jobs.procrastinate_jobs"

# The actions executor runs code that form creators wrote and connects as this
# role. It may use the queue (grants in postgres/init and
# postgres/ensure-jobs-exec-role.sh), but only as far as running action jobs needs:
#
# * only the ``actions`` queue's rows are visible, and only ``run_action`` jobs
#   with no lock or an ``action_`` one can be written. Without that it could read
#   the other queues' jobs, queue, change or cancel an account or response
#   deletion, or take a lock name (``delete_response:<id>``) that makes the backend
#   skip that deletion through the queue's unique indexes.
# * it cannot write the events table or the periodic-defers table (the second
#   would let it suppress periodic jobs). procrastinate's triggers write them as
#   the table owner for it: they are SECURITY DEFINER.
#
# Row-level security on the queue's table does the first: a restrictive policy
# for this role, next to a policy that leaves every other role (the backend's owner
# role bypasses policies anyway; the admin portal's counting function reads as
# another role) exactly as before.
EXECUTOR_ROLE = "bc_jobs_exec"
EXECUTOR_QUEUE = "actions"
EXECUTOR_TASK = "run_action"
EXECUTOR_LOCK_PREFIX = "action_"
OPEN_POLICY = "bc_queue_open"
EXECUTOR_POLICY = "bc_jobs_exec_actions_only"
# tables the role may only read through procrastinate's own functions
NO_WRITE_TABLES = ("procrastinate_events", "procrastinate_periodic_defers")
_ROLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def isolate_executor_sql(role: str = EXECUTOR_ROLE) -> str:
    """One DO block (idempotent; a no-op while the role does not exist yet, as
    on a stack whose role is created later: run this again then). It makes no
    use of ``%`` (procrastinate's connector reads it as a placeholder)."""
    if not _ROLE_NAME.match(role):
        raise ValueError("not a role name")
    tables = ", ".join(f"jobs.{t}" for t in NO_WRITE_TABLES)
    lock_ok = lambda column: (  # noqa: E731
        f"({column} IS NULL OR starts_with({column}, '{EXECUTOR_LOCK_PREFIX}'))"
    )
    return f"""
DO $isolate$
DECLARE
    f record;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '{role}') THEN
        ALTER TABLE {QUEUE_TABLE} ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS {OPEN_POLICY} ON {QUEUE_TABLE};
        CREATE POLICY {OPEN_POLICY} ON {QUEUE_TABLE}
            FOR ALL USING (true) WITH CHECK (true);
        DROP POLICY IF EXISTS {EXECUTOR_POLICY} ON {QUEUE_TABLE};
        CREATE POLICY {EXECUTOR_POLICY} ON {QUEUE_TABLE} AS RESTRICTIVE
            FOR ALL TO {role}
            USING (queue_name = '{EXECUTOR_QUEUE}')
            WITH CHECK (queue_name = '{EXECUTOR_QUEUE}'
                AND task_name = '{EXECUTOR_TASK}'
                AND {lock_ok("lock")} AND {lock_ok("queueing_lock")});
        -- the triggers that write the events and unlink periodic defers run as
        -- the owner, then the role needs no write on those tables
        FOR f IN
            SELECT p.proname FROM pg_catalog.pg_proc p
              JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'jobs'
               AND (starts_with(p.proname, 'procrastinate_trigger_function_')
                    OR p.proname = 'procrastinate_unlink_periodic_defers_v1')
        LOOP
            EXECUTE 'ALTER FUNCTION jobs.' || quote_ident(f.proname)
                || '() SECURITY DEFINER SET search_path = jobs, pg_catalog';
        END LOOP;
        REVOKE ALL ON {tables} FROM {role};
    END IF;
END
$isolate$
"""


async def isolate_executor(jobs_app: App, role: str = EXECUTOR_ROLE) -> None:
    await jobs_app.connector.execute_query_async(isolate_executor_sql(role))


async def ensure_schema(jobs_app: App = app, role: str = EXECUTOR_ROLE) -> bool:
    """Returns True when the schema was applied, False when it was present.
    Either way the executor role's row restriction is (re)asserted."""
    async with jobs_app.open_async():
        row = await jobs_app.connector.execute_query_one_async(
            f"SELECT to_regclass('{QUEUE_TABLE}') AS queue_table"
        )
        applied = row["queue_table"] is None
        if applied:
            await jobs_app.schema_manager.apply_schema_async()
        await isolate_executor(jobs_app, role)
        return applied


async def queue_table_present(conn: AsyncConnection) -> bool:
    found = await conn.scalar(text("SELECT to_regclass(:t)"), {"t": QUEUE_TABLE})
    return found is not None


async def apply_schema(database_url: str) -> bool:
    """On a connector of its own: the process-wide app is opened separately."""
    return await ensure_schema(App(connector=build_connector(database_url)))


JOBS_SCHEMA = AuxiliarySchema(
    name="jobs",
    needed=postgres_jobs_enabled,
    present=queue_table_present,
    apply=apply_schema,
    fix="Apply procrastinate's schema (`python -m backend.jobs.schema`, as deploy.sh does).",
)


async def scrub() -> dict:
    """Remove the response data that 4.1.x left in the actions queue (counts)."""
    from backend.jobs.legacy import run

    async with app.open_async():
        return await run(app)


if __name__ == "__main__":
    applied = asyncio.run(ensure_schema())
    print("procrastinate schema applied" if applied else "procrastinate schema present")
    found = asyncio.run(scrub())
    print(
        "legacy action jobs: {deleted} deleted, {rewritten} rewritten, {left} left".format(
            **found
        )
    )
    sys.exit(0)
