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

# True when row-level security is on for the queue table and a restrictive
# policy of that name applies to the role this connection is.
ISOLATION_SQL = f"""
SELECT EXISTS (
    SELECT 1
      FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_policy p ON p.polrelid = c.oid
     WHERE c.oid = 'jobs.procrastinate_jobs'::regclass
       AND c.relrowsecurity
       AND p.polname = '{POLICY}'
       AND NOT p.polpermissive
       AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = current_user)
           = ANY (p.polroles)
)
"""

REFUSAL = (
    "the job queue does not restrict this database role to its own queue (no "
    f"'{POLICY}' policy on jobs.procrastinate_jobs). Run `python -m "
    "backend.jobs.schema` with the backend's configuration (it is a no-op for "
    "the tables and applies the policy), then start the executor again."
)


async def require_isolated_queue(connector) -> None:
    """Exit with the reason, at start, when the restriction is not in place."""
    row = await connector.execute_query_one_async(ISOLATION_SQL)
    if not next(iter(row.values())):
        raise SystemExit(f"The actions executor will not start: {REFUSAL}")
