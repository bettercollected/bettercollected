"""The executor refuses to start unless the database restricts its role to its
own queue.

The role it connects as may use the job queue, but its rows are visible and
writable only for the ``actions`` queue: a restrictive row-level policy on
``jobs.procrastinate_jobs`` (applied by the backend, ``python -m
backend.jobs.schema``). The executor runs code that form creators wrote, so a
database where that policy is missing is not a place for it to connect: without
it the role could read the other queues' jobs and queue or cancel an account or
response deletion. The catalog it asks is readable by every role.
"""

import logging

logger = logging.getLogger(__name__)

POLICY = "bc_jobs_exec_actions_only"

# What the policy must say, as the catalog prints it with spaces, parentheses
# and type casts removed, in lower case (the same normalisation is applied in the query). A stale
# or hand-made policy of the same name, whose expressions or command differ, fails.
EXPECTED_USING = "queue_name='actions'"
EXPECTED_CHECK = (
    "queue_name='actions'andtask_name='run_action'"
    "andlockisnullorstarts_withlock,'action_'"
    "andqueueing_lockisnullorstarts_withqueueing_lock,'action_'"
)


def _q(text: str) -> str:
    """``text`` inside an SQL string literal."""
    return text.replace("'", "''")


_NORMALISE = r"::(text|character varying)|[ ()\n]"

DEFINER_ROLE = "bc_jobs_def"
DEFINER_SEARCH_PATH = "search_path=jobs, pg_catalog, pg_temp"

# True when, for the role this connection is: row-level security is on for the
# queue table and a restrictive policy of that name, for all commands and with
# exactly the expressions above, applies to the role; the role is no superuser,
# bypasses no policy and does not own the table (an owner skips policies); it
# cannot write the events or periodic-defers tables; and every SECURITY DEFINER
# function of the queue's schema (the triggers that write those tables) belongs to
# the dedicated definer role (NOLOGIN, no superuser, no bypass) and has a search
# path that ends in pg_temp. Without pg_temp last the session's temporary schema is
# searched first: this role may create temp tables, shadow ``procrastinate_events``
# with one of its own, and have a trigger of its own run as the function's owner.
# A later ``CREATE OR REPLACE FUNCTION`` by procrastinate resets a function to
# SECURITY INVOKER with no path: this then fails closed until
# ``python -m backend.jobs.schema`` has run again.
def isolation_sql(definer: str = DEFINER_ROLE) -> str:
    return f"""
SELECT EXISTS (
    SELECT 1
      FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_policy p ON p.polrelid = c.oid
      JOIN pg_catalog.pg_roles r ON r.rolname = current_user
     WHERE c.oid = 'jobs.procrastinate_jobs'::regclass
       AND c.relrowsecurity
       AND p.polname = '{POLICY}'
       AND NOT p.polpermissive
       AND p.polcmd = '*'
       AND lower(regexp_replace(pg_catalog.pg_get_expr(p.polqual, p.polrelid),
                                '{_NORMALISE}', '', 'g')) = '{_q(EXPECTED_USING)}'
       AND lower(regexp_replace(pg_catalog.pg_get_expr(p.polwithcheck, p.polrelid),
                                '{_NORMALISE}', '', 'g')) = '{_q(EXPECTED_CHECK)}'
       AND r.oid = ANY (p.polroles)
       AND NOT r.rolsuper
       AND NOT r.rolbypassrls
       AND c.relowner <> r.oid
       AND NOT has_table_privilege(
               current_user, 'jobs.procrastinate_events', 'INSERT,UPDATE,DELETE')
       AND NOT has_table_privilege(
               current_user, 'jobs.procrastinate_periodic_defers', 'INSERT,UPDATE,DELETE')
       -- the trigger functions exist, are SECURITY DEFINER, and belong to the
       -- definer role
       AND EXISTS (
               SELECT 1 FROM pg_catalog.pg_proc f
                 JOIN pg_catalog.pg_namespace n ON n.oid = f.pronamespace
                WHERE n.nspname = 'jobs'
                  AND starts_with(f.proname, 'procrastinate_trigger_'))
       AND NOT EXISTS (
               SELECT 1 FROM pg_catalog.pg_proc f
                 JOIN pg_catalog.pg_namespace n ON n.oid = f.pronamespace
                WHERE n.nspname = 'jobs'
                  AND (starts_with(f.proname, 'procrastinate_trigger_')
                       OR f.proname = 'procrastinate_unlink_periodic_defers_v1'
                       OR f.prosecdef)
                  AND NOT (f.prosecdef
                           AND f.proconfig = ARRAY['{DEFINER_SEARCH_PATH}']::text[]
                           AND pg_catalog.pg_get_userbyid(f.proowner) = '{definer}'))
       AND EXISTS (
               SELECT 1 FROM pg_catalog.pg_roles d
                WHERE d.rolname = '{definer}' AND NOT d.rolcanlogin
                  AND NOT d.rolsuper AND NOT d.rolbypassrls AND NOT d.rolcreaterole)
)
"""


ISOLATION_SQL = isolation_sql()

REFUSAL = (
    "the job queue does not restrict this database role to running action jobs "
    f"(the '{POLICY}' policy on jobs.procrastinate_jobs, no write on the events and "
    "periodic-defers tables, or the role is more than a plain login role). Run "
    "`python -m backend.jobs.schema` with the backend's configuration (it is a "
    "no-op for the tables and applies the restriction), and "
    "postgres/ensure-jobs-exec-role.sh, then start the executor again."
)


async def require_isolated_queue(connector) -> None:
    """Exit with the reason, at start, when the restriction is not in place."""
    row = await connector.execute_query_one_async(ISOLATION_SQL)
    if not next(iter(row.values())):
        raise SystemExit(f"The actions executor will not start: {REFUSAL}")
