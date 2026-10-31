#!/bin/bash
# Creates (or repairs) the actions executor's database role. Idempotent: deploy.sh
# runs it as the database superuser on every deploy, after the job queue's tables
# exist; a stack without deploy.sh runs it once, by hand (see the line at the end).
#
#   bc_jobs_exec  the role the actions executor connects as. The executor runs
#                 code that form creators wrote, so the role is the job queue
#                 (schema `jobs`) and nothing else: USAGE on that schema and
#                 SELECT/INSERT/UPDATE/DELETE on its tables, USAGE on its
#                 sequences, EXECUTE on its functions, but no write on the events and
#                 periodic-defers tables (now, and on what a later
#                 procrastinate migration adds). It is not a superuser, cannot
#                 create roles, databases or objects, and holds no privilege in
#                 `app`, `auth`, `google`, `admin`, `tasks` or `settings`; those
#                 are revoked here, so a drifted grant is repaired.
#
# Which rows of the queue it may touch is not decided here but by a row-level
# policy on jobs.procrastinate_jobs that the backend applies (`python -m
# backend.jobs.schema`, also run by deploy.sh): the role sees and changes only the
# `actions` queue. The last line this script prints says whether that policy is there.
#
# The password comes from BC_JOBS_EXEC_PASSWORD when it is set (never printed;
# deploy.sh's compose service has it). Without it the role is created without one
# (it cannot log in) or keeps the one it has; set it with `\password bc_jobs_exec`
# in psql, which reads it without echo.
#
# Run inside the postgres container (it reads POSTGRES_USER/POSTGRES_DB):
#   docker compose exec -T app-postgres bash -s < postgres/ensure-jobs-exec-role.sh
#   docker exec -i "$(docker ps -q -f label=com.docker.swarm.service.name=<stack>_<postgres service> | head -n1)" bash -s < postgres/ensure-jobs-exec-role.sh
set -euo pipefail

: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
BC_JOBS_EXEC_PASSWORD="${BC_JOBS_EXEC_PASSWORD:-}"
# the password is placed unencoded in a database URL (the executor's DATABASE_URL):
# refuse characters that would break one (never print the value)
if [ -n "$BC_JOBS_EXEC_PASSWORD" ] && ! printf '%s' "$BC_JOBS_EXEC_PASSWORD" | grep -Eq '^[A-Za-z0-9._~-]+$'; then
    echo "BC_JOBS_EXEC_PASSWORD may only contain letters, digits, '.', '_', '~' and '-' (it is used unencoded in a database URL)." >&2
    exit 1
fi

# The password reaches psql through its environment (\getenv below), never as
# `-v name=value`, which any user of the host can read in the process list.
# (\getenv needs psql 15 or newer; compose uses 16.)
export BC_JOBS_EXEC_PASSWORD

psql -v ON_ERROR_STOP=1 --quiet --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv jobs_pw BC_JOBS_EXEC_PASSWORD
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SELECT count(set_config('bc.jobs_exec_pw', :'jobs_pw', false)) \gset

DO $do$
DECLARE
    owner_name text;
    s text;
BEGIN
    IF NOT (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user) THEN
        RAISE EXCEPTION 'run this as the database superuser';
    END IF;
    IF pg_catalog.pg_is_in_recovery() THEN
        RAISE EXCEPTION 'this is a replica: run it on the primary';
    END IF;
    IF to_regclass('jobs.procrastinate_jobs') IS NULL THEN
        RAISE EXCEPTION 'jobs.procrastinate_jobs is missing: the backend has not applied the job queue''s tables yet (python -m backend.jobs.schema)';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'bc_jobs_exec') THEN
        CREATE ROLE bc_jobs_exec LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    ALTER ROLE bc_jobs_exec LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    IF current_setting('bc.jobs_exec_pw') <> '' THEN
        EXECUTE format('ALTER ROLE bc_jobs_exec PASSWORD %L', current_setting('bc.jobs_exec_pw'));
    END IF;
    ALTER ROLE bc_jobs_exec SET search_path = jobs;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO bc_jobs_exec', current_database());

    -- nothing of the other services, whatever an earlier grant said
    FOREACH s IN ARRAY ARRAY['app', 'auth', 'google', 'admin', 'tasks', 'settings'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = s) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA %I FROM bc_jobs_exec', s);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM bc_jobs_exec', s);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM bc_jobs_exec', s);
            EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA %I FROM bc_jobs_exec', s);
        END IF;
    END LOOP;
    REVOKE CREATE ON SCHEMA public FROM bc_jobs_exec;

    -- the queue's objects that exist now
    GRANT USAGE ON SCHEMA jobs TO bc_jobs_exec;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA jobs TO bc_jobs_exec;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA jobs TO bc_jobs_exec;
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA jobs TO bc_jobs_exec;
    REVOKE CREATE ON SCHEMA jobs FROM bc_jobs_exec;

    -- except what only procrastinate's own triggers may write: the events and the
    -- periodic defers (the second would let the role suppress periodic jobs). The
    -- triggers write them as the table's owner for it (SECURITY DEFINER), the same
    -- as backend.jobs.schema asserts.
    FOR s IN
        SELECT p.proname FROM pg_catalog.pg_proc p
          JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'jobs'
           AND (starts_with(p.proname, 'procrastinate_trigger_function_')
                OR p.proname = 'procrastinate_unlink_periodic_defers_v1')
    LOOP
        EXECUTE 'ALTER FUNCTION jobs.' || quote_ident(s) || '() SECURITY DEFINER SET search_path = jobs, pg_catalog';
    END LOOP;
    REVOKE ALL ON jobs.procrastinate_events, jobs.procrastinate_periodic_defers FROM bc_jobs_exec;

    -- and those a later procrastinate migration creates, for every role that owns objects in `jobs`
    FOR owner_name IN
        SELECT DISTINCT pg_catalog.pg_get_userbyid(o) FROM (
            SELECT n.nspowner AS o FROM pg_catalog.pg_namespace n WHERE n.nspname = 'jobs'
            UNION SELECT c.relowner FROM pg_catalog.pg_class c
                   JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'jobs'
            UNION SELECT p.proowner FROM pg_catalog.pg_proc p
                   JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'jobs'
        ) owners
        WHERE NOT (SELECT rolsuper FROM pg_catalog.pg_roles WHERE oid = owners.o)
    LOOP
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA jobs GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bc_jobs_exec', owner_name);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA jobs GRANT USAGE, SELECT ON SEQUENCES TO bc_jobs_exec', owner_name);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA jobs GRANT EXECUTE ON FUNCTIONS TO bc_jobs_exec', owner_name);
    END LOOP;
END
$do$;

-- What it did: names and flags only, never a password.
\pset tuples_only on
\pset format unaligned
SELECT 'bc_jobs_exec: login=' || rolcanlogin || ' superuser=' || rolsuper
       || ' password_set=' || (rolpassword IS NOT NULL)
  FROM pg_catalog.pg_authid WHERE rolname = 'bc_jobs_exec';
SELECT 'queue_rw=' || has_table_privilege('bc_jobs_exec', 'jobs.procrastinate_jobs', 'UPDATE')
       || ' app_schema=' || has_schema_privilege('bc_jobs_exec', 'app', 'USAGE')
       || ' auth_schema=' || has_schema_privilege('bc_jobs_exec', 'auth', 'USAGE')
       || ' google_schema=' || has_schema_privilege('bc_jobs_exec', 'google', 'USAGE');
SELECT CASE WHEN EXISTS (
         SELECT 1 FROM pg_catalog.pg_policy
          WHERE polrelid = 'jobs.procrastinate_jobs'::regclass
            AND polname = 'bc_jobs_exec_actions_only')
       THEN 'queue_policy=present (the role sees the actions queue only)'
       ELSE 'queue_policy=MISSING: run python -m backend.jobs.schema with the backend''s configuration before starting the executor'
       END;
SQL
