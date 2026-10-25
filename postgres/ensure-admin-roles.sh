#!/bin/bash
# Creates (or repairs) the admin service's schemas and its roles. Idempotent:
# deploy.sh runs it as the database superuser on every deploy, before migrating.
#
#   bc_admin_mig  owns schema `admin` and its tables; used only to run the
#                 admin Alembic migrations (deploy time), never by the service.
#   bc_admin      the service's runtime role (ADMIN_DATABASE_URL). DML on the
#                 session, challenge, factor, recovery-code and attempt tables;
#                 INSERT and SELECT only on `audit_log` (plus USAGE on its
#                 sequence) so the log is append-only for the service. It has no
#                 access to the `app`, `auth`, `google` or `jobs` schemas.
#   bc_tasks      the data task runner's role (TASKS_DATABASE_URL). Column-level
#                 UPDATE on the runner-owned columns of tasks.runs, INSERT on
#                 tasks.run_events / checkpoints, INSERT/DELETE on tasks.locks;
#                 NO access to admin.audit_log: its audit rows are written by
#                 narrow SECURITY DEFINER functions (tasks.audit_append,
#                 settings.task_write_keyset) owned by bc_tasks_def. Nothing else
#                 in `admin` and nothing in the other services' schemas.
#   bc_tasks_def  NOLOGIN owner of the runner's definer functions. It holds what
#                 those functions need (INSERT on the audit log, the settings
#                 tables, the notification outbox) and nobody can log in as it.
#   admin.credential_purges_overdue()
#                 the integrity monitor's count of credential purges (and account
#                 deletions) still queued a day later or failed; read-only, owned
#                 by bc_count_app (the queue's `jobs` schema is the backend role's,
#                 like `app`), column SELECT on the queue tables, never job
#                 arguments; EXECUTE for bc_admin only.
#   admin.platform_counts_app(), admin.platform_counts_auth()
#                 the metrics page's counts, ONE read-only SECURITY DEFINER function
#                 per owning schema, each owned by a NOLOGIN role (bc_count_app,
#                 bc_count_auth) that holds column-level SELECT on that schema's
#                 tables only, i.e. nothing the schema's own owner role does not
#                 already hold; EXECUTE for bc_admin only. The admin combines the
#                 two results in Python and treats them as data. No definer
#                 function reads tables of more than one owning role.
#
#   bc_tasks_data_app, bc_tasks_data_google
#                 the task runner's DATA roles, ONE PER OWNING SCHEMA (the
#                 runner's DATABASE_URL and GOOGLE_DATABASE_URL; bc_tasks holds
#                 its own state and the settings store). They read and
#                 re-encrypt the stored responses and the Google credentials,
#                 and stamp responses with their workspace, and nothing else:
#                 column-level SELECT on exactly the columns the tasks read,
#                 column-level UPDATE on `doc` and `_bc_checksum`, no INSERT or
#                 DELETE, no TEMPORARY, search_path pg_catalog, no access to
#                 `admin`, `tasks`, `settings`, `auth` or `jobs`. Why two: an
#                 UPDATE runs the table owner's triggers and generated-column
#                 helpers with the UPDATER's privileges, so one role holding
#                 both bc_app's and bc_google's tables would let either owner
#                 plant code that runs with access to the other's table. Each
#                 role holds no more than the owner of its schema already has.
#                 Never use bc_app or bc_google for this. These grants live
#                 here, not in a migration: the tables belong to other roles,
#                 and only the superuser may grant on them. This script runs
#                 again after the other services' migrations (deploy.sh), so
#                 the grants reach tables created on first deploy.
#
# Schema `tasks` (the runner's state) is created here, owned by bc_admin_mig,
# like `admin`.
#
# The table grants are made by the migrations themselves (they know their
# tables); this script re-applies them for tables that already exist, so running
# it after a migration repairs drift. There are NO default privileges on
# purpose: they would hand UPDATE/DELETE on audit_log to the runtime role.
#
# Passwords come from BC_ADMIN_PASSWORD, BC_ADMIN_MIG_PASSWORD, BC_TASKS_PASSWORD and
# BC_TASKS_DATA_APP_PASSWORD and BC_TASKS_DATA_GOOGLE_PASSWORD and are never printed. Run inside the postgres container (it reads POSTGRES_USER/DB):
#   docker compose exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh
set -euo pipefail

: "${BC_ADMIN_PASSWORD:?BC_ADMIN_PASSWORD must be set}"
: "${BC_ADMIN_MIG_PASSWORD:?BC_ADMIN_MIG_PASSWORD must be set}"
: "${BC_TASKS_PASSWORD:?BC_TASKS_PASSWORD must be set}"
: "${BC_TASKS_DATA_APP_PASSWORD:?BC_TASKS_DATA_APP_PASSWORD must be set}"
: "${BC_TASKS_DATA_GOOGLE_PASSWORD:?BC_TASKS_DATA_GOOGLE_PASSWORD must be set}"
# the passwords are placed unencoded in database URLs by the compose file and
# deploy.sh: refuse characters that would break a URL (never print the value)
for name in BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD BC_TASKS_DATA_APP_PASSWORD BC_TASKS_DATA_GOOGLE_PASSWORD; do
    if ! printf '%s' "${!name}" | grep -Eq '^[A-Za-z0-9._~-]+$'; then
        echo "$name may only contain letters, digits, '.', '_', '~' and '-' (it is used unencoded in a database URL)." >&2
        exit 1
    fi
done
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"

# The passwords reach psql through its environment (\getenv below), never as
# `-v name=value` arguments, which any user of the host can read in the process
# list while the command runs. (\getenv needs psql 15 or newer; compose uses 16.)
export BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD BC_TASKS_DATA_APP_PASSWORD BC_TASKS_DATA_GOOGLE_PASSWORD

psql -v ON_ERROR_STOP=1 --quiet --output /dev/null --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv admin_pw BC_ADMIN_PASSWORD
\getenv mig_pw BC_ADMIN_MIG_PASSWORD
\getenv tasks_pw BC_TASKS_PASSWORD
\getenv tasks_data_app_pw BC_TASKS_DATA_APP_PASSWORD
\getenv tasks_data_google_pw BC_TASKS_DATA_GOOGLE_PASSWORD
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SELECT count(set_config('bc.admin_pw', :'admin_pw', false));
SELECT count(set_config('bc.mig_pw', :'mig_pw', false));
SELECT count(set_config('bc.tasks_pw', :'tasks_pw', false));
SELECT count(set_config('bc.tasks_data_app_pw', :'tasks_data_app_pw', false));
SELECT count(set_config('bc.tasks_data_google_pw', :'tasks_data_google_pw', false));

DO $do$
DECLARE
    -- To add a role (a task runner, a read-only reader, ...): add a {name, GUC}
    -- pair here, bind its password with another set_config line above and
    -- another -v option in the shell, then grant it what it needs in the
    -- revision that creates the tables (migration_support.grant(..., role=...)).
    -- Never add a role to `admin`'s default privileges.
    runtime_roles text[][] := ARRAY[
        ['bc_admin', 'bc.admin_pw'],
        ['bc_tasks', 'bc.tasks_pw']
    ];
    -- the data roles: one per owning schema, never one role over two owners' tables
    data_roles text[][] := ARRAY[
        ['bc_tasks_data_app', 'bc.tasks_data_app_pw'],
        ['bc_tasks_data_google', 'bc.tasks_data_google_pw']
    ];
    r text[];
    t text;
    s text;
    cols text;
BEGIN
    -- the migration role: owns schema `admin`; default search_path on purpose
    -- (every statement it runs is schema-qualified)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_admin_mig') THEN
        CREATE ROLE bc_admin_mig LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    EXECUTE format('ALTER ROLE bc_admin_mig PASSWORD %L', current_setting('bc.mig_pw'));
    ALTER ROLE bc_admin_mig RESET search_path;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO bc_admin_mig', current_database());

    -- schema owned by the migration role; invisible to everyone else
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'admin') THEN
        CREATE SCHEMA admin AUTHORIZATION bc_admin_mig;
    END IF;
    ALTER SCHEMA admin OWNER TO bc_admin_mig;
    REVOKE ALL ON SCHEMA admin FROM PUBLIC;

    -- the task runner's schema, same owner, invisible to everyone else
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'tasks') THEN
        CREATE SCHEMA tasks AUTHORIZATION bc_admin_mig;
    END IF;
    ALTER SCHEMA tasks OWNER TO bc_admin_mig;
    REVOKE ALL ON SCHEMA tasks FROM PUBLIC;

    -- schema `settings` (the settings store): same owner, invisible to everyone
    -- until a role is named below
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'settings') THEN
        CREATE SCHEMA settings AUTHORIZATION bc_admin_mig;
    END IF;
    ALTER SCHEMA settings OWNER TO bc_admin_mig;
    REVOKE ALL ON SCHEMA settings FROM PUBLIC;

    -- the owner of the runner's definer functions: cannot log in, owns no table;
    -- the migration role becomes a member so a revision can hand it a function
    -- it created (ALTER FUNCTION ... OWNER TO needs membership), nothing more
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_tasks_def') THEN
        CREATE ROLE bc_tasks_def NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE;
    END IF;
    ALTER ROLE bc_tasks_def NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ALTER ROLE bc_tasks_def SET search_path = pg_catalog;
    GRANT bc_tasks_def TO bc_admin_mig;
    GRANT USAGE ON SCHEMA admin, tasks, settings TO bc_tasks_def;

    -- login roles: created once, password re-synced on every run
    FOREACH r SLICE 1 IN ARRAY runtime_roles LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r[1]) THEN
            EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE', r[1]);
        END IF;
        EXECUTE format('ALTER ROLE %I PASSWORD %L', r[1], current_setting(r[2]));
        EXECUTE format('ALTER ROLE %I SET search_path = admin', r[1]);
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), r[1]);
        EXECUTE format('GRANT USAGE ON SCHEMA admin TO %I', r[1]);
        EXECUTE format('GRANT USAGE ON SCHEMA tasks TO %I', r[1]);
        EXECUTE format('GRANT USAGE ON SCHEMA settings TO %I', r[1]);
    END LOOP;

    -- the task runner's data roles: login roles of their own, search_path
    -- pg_catalog (nothing unqualified resolves into a schema), no USAGE on
    -- admin, tasks or settings
    FOREACH r SLICE 1 IN ARRAY data_roles LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r[1]) THEN
            EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE', r[1]);
        END IF;
        EXECUTE format('ALTER ROLE %I PASSWORD %L', r[1], current_setting(r[2]));
        EXECUTE format('ALTER ROLE %I SET search_path = pg_catalog', r[1]);
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), r[1]);
        EXECUTE format('REVOKE ALL ON SCHEMA admin, tasks, settings FROM %I', r[1]);
        IF to_regclass('admin.audit_log') IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA admin FROM %I', r[1]);
        END IF;
        IF to_regclass('tasks.runs') IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA tasks FROM %I', r[1]);
        END IF;
        IF to_regclass('settings.entries') IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA settings FROM %I', r[1]);
        END IF;
    END LOOP;

    -- no access to the other services' schemas, for any of them
    FOREACH s IN ARRAY ARRAY['app', 'auth', 'google', 'jobs'] LOOP
        IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = s) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA %I FROM bc_admin_mig', s);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM bc_admin_mig', s);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM bc_admin_mig', s);
            FOREACH r SLICE 1 IN ARRAY runtime_roles LOOP
                EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', s, r[1]);
                EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I', s, r[1]);
                EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM %I', s, r[1]);
            END LOOP;
            -- the data roles start from nothing as well; their grants follow below
            FOREACH r SLICE 1 IN ARRAY data_roles LOOP
                EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', s, r[1]);
                EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I', s, r[1]);
                EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM %I', s, r[1]);
            END LOOP;
        END IF;
    END LOOP;

    -- no TEMPORARY (temp tables) for the admin roles: it is granted to PUBLIC by
    -- default, so revoke it there and give it back by name to the existing
    -- service roles, whose access stays exactly as it was
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM bc_admin_mig', current_database());
    FOREACH r SLICE 1 IN ARRAY data_roles LOOP
        EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM %I', current_database(), r[1]);
    END LOOP;
    FOREACH r SLICE 1 IN ARRAY runtime_roles LOOP
        EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM %I', current_database(), r[1]);
    END LOOP;
    FOREACH s IN ARRAY ARRAY['bc_app', 'bc_auth', 'bc_google', 'bc_jobs_exec'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = s) THEN
            EXECUTE format('GRANT TEMPORARY ON DATABASE %I TO %I', current_database(), s);
        END IF;
    END LOOP;

    -- re-apply the table grants for tables the migrations already created
    IF to_regclass('admin.alembic_version') IS NOT NULL THEN
        GRANT SELECT ON admin.alembic_version TO bc_admin;
    END IF;
    FOREACH t IN ARRAY ARRAY['sessions', 'signin_challenges', 'attempts', 'factors', 'recovery_codes'] LOOP
        IF to_regclass('admin.' || t) IS NOT NULL THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON admin.%I TO bc_admin', t);
        END IF;
    END LOOP;
    IF to_regclass('admin.audit_log') IS NOT NULL THEN
        REVOKE ALL ON admin.audit_log FROM bc_admin;
        GRANT SELECT, INSERT ON admin.audit_log TO bc_admin;
        GRANT USAGE ON SEQUENCE admin.audit_log_seq_seq TO bc_admin;
        -- the runner has NO access to the log: its rows go through definer functions
        REVOKE ALL ON admin.audit_log FROM bc_tasks;
        REVOKE ALL ON SEQUENCE admin.audit_log_seq_seq FROM bc_tasks;
    END IF;

    -- the task runner's state (tables exist once the tasks revision has run)
    IF to_regclass('tasks.runs') IS NOT NULL THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA tasks FROM bc_admin, bc_tasks;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA tasks FROM bc_admin, bc_tasks;
        GRANT SELECT, INSERT ON tasks.runs TO bc_admin;
        GRANT UPDATE (cancel_requested_at) ON tasks.runs TO bc_admin;
        GRANT SELECT ON tasks.run_events, tasks.checkpoints, tasks.locks TO bc_admin;
        -- the retention loop (admin role): the runner itself can only append
        GRANT DELETE ON tasks.run_events, tasks.checkpoints TO bc_admin;
        GRANT SELECT ON tasks.runs TO bc_tasks;
        GRANT UPDATE (state, progress, heartbeat_at, result, refusal_code, runner_id,
                      started_at, finished_at) ON tasks.runs TO bc_tasks;
        GRANT SELECT, INSERT ON tasks.run_events, tasks.checkpoints TO bc_tasks;
        GRANT USAGE ON SEQUENCE tasks.run_events_id_seq, tasks.checkpoints_id_seq TO bc_tasks;
        GRANT SELECT, INSERT, DELETE ON tasks.locks TO bc_tasks;
    END IF;
    IF to_regclass('admin.notifications') IS NOT NULL THEN
        REVOKE ALL ON admin.notifications FROM bc_admin;
        GRANT SELECT, INSERT ON admin.notifications TO bc_admin;
        GRANT UPDATE (status, attempts, sent_at) ON admin.notifications TO bc_admin;
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'admin' AND table_name = 'notifications'
                     AND column_name = 'delivered_to') THEN
            GRANT UPDATE (next_attempt_at, last_error_code, delivered_to)
                ON admin.notifications TO bc_admin;
        END IF;
    END IF;

    -- The data task runner's grants: exactly the columns the responses and
    -- keyset tasks read and write, as column privileges, one role per owning
    -- schema. The generated columns (form_id, workspace_id, user_id, ...) are
    -- read-only for everyone; `doc` and `_bc_checksum` are what a re-encryption
    -- or a workspace stamp changes. USAGE on the schema also reaches the
    -- generated columns' helper functions there, nothing more.
    -- Only the columns that exist now are granted: this script runs BEFORE the
    -- application's migrations on an upgrade, and `workspace_id` of the response
    -- tables arrives with a later revision (app 0015). The run after the
    -- migrations (deploy.sh) grants it.
    FOREACH r SLICE 1 IN ARRAY ARRAY[
        ['form_responses', 'id,form_id,response_id,workspace_id,doc', 'doc,_bc_checksum'],
        ['responses_deletion_requests', 'id,form_id,response_id,workspace_id,doc', 'doc,_bc_checksum'],
        ['workspace_forms', 'id,form_id,workspace_id,doc', '']
    ] LOOP
        IF to_regclass('app.' || r[1]) IS NOT NULL THEN
            GRANT USAGE ON SCHEMA app TO bc_tasks_data_app;
            SELECT string_agg(quote_ident(c), ', ') INTO cols
              FROM unnest(string_to_array(r[2], ',')) AS c
             WHERE EXISTS (SELECT 1 FROM pg_attribute a
                            WHERE a.attrelid = to_regclass('app.' || r[1])
                              AND a.attname = c AND a.attnum > 0 AND NOT a.attisdropped);
            IF cols IS NOT NULL THEN
                EXECUTE format('GRANT SELECT (%s) ON app.%I TO bc_tasks_data_app', cols, r[1]);
            END IF;
            IF r[3] <> '' THEN
                SELECT string_agg(quote_ident(c), ', ') INTO cols
                  FROM unnest(string_to_array(r[3], ',')) AS c
                 WHERE EXISTS (SELECT 1 FROM pg_attribute a
                                WHERE a.attrelid = to_regclass('app.' || r[1])
                                  AND a.attname = c AND a.attnum > 0 AND NOT a.attisdropped);
                IF cols IS NOT NULL THEN
                    EXECUTE format('GRANT UPDATE (%s) ON app.%I TO bc_tasks_data_app', cols, r[1]);
                END IF;
            END IF;
        END IF;
    END LOOP;
    IF to_regclass('google.oauth_credentials') IS NOT NULL THEN
        GRANT USAGE ON SCHEMA google TO bc_tasks_data_google;
        GRANT SELECT (id, user_id, doc) ON google.oauth_credentials TO bc_tasks_data_google;
        GRANT UPDATE (doc, _bc_checksum) ON google.oauth_credentials TO bc_tasks_data_google;
    END IF;

    -- the settings store. The writer (bc_admin) holds exactly these; no DELETE
    -- on entries or manifest; service_state is written only through
    -- settings.report_state, and the admin's retention loop may delete stale rows.
    IF to_regclass('settings.entries') IS NOT NULL THEN
        REVOKE ALL ON settings.entries, settings.history, settings.manifest,
            settings.service_state FROM bc_admin;
        GRANT SELECT, INSERT, UPDATE ON settings.entries TO bc_admin;
        -- history rows are never changed by anyone: INSERT new versions, prune old
        -- ones; a master-key re-wrap is appended to history_wraps
        GRANT SELECT, INSERT, DELETE ON settings.history TO bc_admin;
        GRANT SELECT, INSERT, UPDATE ON settings.manifest TO bc_admin;
        GRANT SELECT, DELETE ON settings.service_state TO bc_admin;
    END IF;
    IF to_regclass('settings.history_wraps') IS NOT NULL THEN
        REVOKE ALL ON settings.history_wraps FROM bc_admin;
        GRANT SELECT, INSERT ON settings.history_wraps TO bc_admin;
        GRANT USAGE ON SEQUENCE settings.history_wraps_id_seq TO bc_admin;
    END IF;
    -- the portal's leases and the verification checkpoint (the lock rows have no
    -- grant at all: admin.take_lock, a definer function, is the only way in)
    IF to_regclass('admin.loop_leases') IS NOT NULL THEN
        REVOKE ALL ON admin.loop_leases FROM bc_admin;
        GRANT SELECT, INSERT ON admin.loop_leases TO bc_admin;
        GRANT UPDATE (holder, acquired_at, expires_at) ON admin.loop_leases TO bc_admin;
    END IF;
    IF to_regclass('admin.lock_rows') IS NOT NULL THEN
        REVOKE ALL ON admin.lock_rows FROM bc_admin, bc_tasks;
    END IF;
    -- Readers: their own two views and report_state, nothing else. Keep these
    -- {service, role} pairs equal to READER_SERVICES in
    -- backend/backend/admin/migration_support.py (a test compares them). A
    -- role that does not exist yet is skipped until it does.
    FOREACH r SLICE 1 IN ARRAY ARRAY[
        ['backend', 'bc_app'], ['auth', 'bc_auth'],
        ['google', 'bc_google'], ['tasks', 'bc_tasks']
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r[2]) THEN
            EXECUTE format('GRANT USAGE ON SCHEMA settings TO %I', r[2]);
            IF to_regclass('settings.v_' || r[1]) IS NOT NULL THEN
                EXECUTE format('GRANT SELECT ON settings.%I, settings.%I TO %I',
                               'v_' || r[1], 'v_' || r[1] || '_manifest', r[2]);
                EXECUTE format('GRANT EXECUTE ON FUNCTION settings.report_state'
                               || '(text, bigint, text[], text[], boolean, text) TO %I', r[2]);
            END IF;
        END IF;
    END LOOP;
END
$do$;

-- The runner's definer role and functions (they exist once the admin revisions
-- 0013-0017 have run; this block repairs drift and is a no-op before that): the
-- grants the functions need, the owner, and EXECUTE for the runner's role alone.
DO $defn$
DECLARE
    f record;
BEGIN
    IF to_regclass('admin.audit_log') IS NOT NULL THEN
        GRANT USAGE ON SCHEMA admin, tasks, settings TO bc_tasks_def;
        GRANT INSERT ON admin.audit_log TO bc_tasks_def;
        GRANT SELECT (seq, row_hash, request_id, action, actor_kind, target_type, target_id, detail)
            ON admin.audit_log TO bc_tasks_def;
        GRANT USAGE ON SEQUENCE admin.audit_log_seq_seq TO bc_tasks_def;
    END IF;
    IF to_regclass('tasks.runs') IS NOT NULL THEN
        GRANT SELECT ON tasks.runs TO bc_tasks_def;
    END IF;
    IF to_regclass('settings.entries') IS NOT NULL THEN
        GRANT SELECT ON settings.entries, settings.manifest, settings.reader_roles TO bc_tasks_def;
        GRANT UPDATE (readers, blob, version, source, updated_by, updated_at, sig)
            ON settings.entries TO bc_tasks_def;
        GRANT UPDATE (revision, digest, entries, sig) ON settings.manifest TO bc_tasks_def;
        GRANT SELECT, INSERT ON settings.history TO bc_tasks_def;
    END IF;
    IF to_regclass('admin.notifications') IS NOT NULL THEN
        GRANT SELECT, INSERT ON admin.notifications TO bc_tasks_def;
    END IF;
    IF to_regprocedure('admin.take_lock(text)') IS NOT NULL THEN
        REVOKE ALL ON FUNCTION admin.take_lock(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION admin.take_lock(text) TO bc_admin, bc_tasks_def;
    END IF;
    FOR f IN
        SELECT p.oid::regprocedure AS sig
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE (n.nspname, p.proname) IN (('tasks', 'begin_audit'), ('tasks', 'audit_append'),
                                         ('settings', 'task_write_keyset'),
                                         ('settings', 'task_notify_reencrypt'))
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO bc_tasks_def', f.sig);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', f.sig);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO bc_tasks', f.sig);
    END LOOP;
    IF to_regclass('admin.audit_verify_state') IS NOT NULL THEN
        REVOKE ALL ON admin.audit_verify_state FROM bc_admin;
        GRANT SELECT, INSERT ON admin.audit_verify_state TO bc_admin;
        GRANT UPDATE (verified_seq, verified_hash, rows_verified, verified_at)
            ON admin.audit_verify_state TO bc_admin;
    END IF;
END
$defn$;

-- Platform counts for the admin portal's metrics page: counts only, no
-- identifying value. The admin roles cannot read the `app` and `auth` schemas, so
-- the counts come from ONE read-only SECURITY DEFINER function PER OWNING SCHEMA,
-- each owned by a role that can log in nowhere and holds SELECT on that schema's
-- columns only: nothing the schema's own owner role (bc_app, bc_auth) does not
-- already hold. A table owner can replace a table with a view that runs its own
-- code as whoever reads it; here that reader is a role with nothing beyond the
-- owner's own rights, so there is nothing to steal. No definer function reads
-- tables of more than one owning role; the admin service adds the two results up
-- in Python and treats them as data. EXECUTE for bc_admin alone; the functions
-- never write, take no arguments and name their tables explicitly; until the
-- application migrations have run they fail and the page says so.
DO $drop$
BEGIN
    -- the single cross-schema function this replaces (and its owner role)
    IF to_regprocedure('admin.platform_counts()') IS NOT NULL THEN
        DROP FUNCTION admin.platform_counts();
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_admin_counts') THEN
        DROP OWNED BY bc_admin_counts;
        DROP ROLE bc_admin_counts;
    END IF;
EXCEPTION WHEN dependent_objects_still_exist THEN
    RAISE NOTICE 'bc_admin_counts still has dependencies elsewhere; it can log in nowhere and owns nothing here';
END
$drop$;

CREATE OR REPLACE FUNCTION admin.platform_counts_app() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER STABLE
SET search_path = pg_catalog, pg_temp
SET timezone = 'UTC' AS $fn$
DECLARE
    first_week timestamptz :=
        (date_trunc('week', now() AT TIME ZONE 'UTC') - interval '11 weeks') AT TIME ZONE 'UTC';
    since30 timestamptz := now() - interval '30 days';
    since7 timestamptz := now() - interval '7 days';
    id30 text := lpad(to_hex(floor(extract(epoch FROM now() - interval '30 days'))::bigint), 8, '0')
                 || '0000000000000000';
    weekly jsonb;
BEGIN
    SELECT jsonb_agg(jsonb_build_object(
        'week_start', (b.lo AT TIME ZONE 'UTC')::date,
        'new_organizations', (SELECT count(*) FROM app.workspaces w WHERE w.id >= b.lo_id AND w.id < b.hi_id),
        'new_forms', (SELECT count(*) FROM app.workspace_forms f WHERE f.id >= b.lo_id AND f.id < b.hi_id),
        'responses', (SELECT count(*) FROM app.form_responses r
                      WHERE r.doc ? 'answers' AND r.created_at >= b.lo AND r.created_at < b.hi)
    ) ORDER BY b.i)
    INTO weekly
    FROM (
        SELECT g.i, w.lo, w.hi,
               lpad(to_hex(floor(extract(epoch FROM w.lo))::bigint), 8, '0') || '0000000000000000' AS lo_id,
               lpad(to_hex(floor(extract(epoch FROM w.hi))::bigint), 8, '0') || '0000000000000000' AS hi_id
        FROM generate_series(0, 11) AS g(i),
             LATERAL (SELECT first_week + g.i * interval '1 week' AS lo,
                             first_week + (g.i + 1) * interval '1 week' AS hi) AS w
    ) AS b;

    RETURN jsonb_build_object(
        'organizations', jsonb_build_object(
            'total', (SELECT count(*) FROM app.workspaces),
            'new_last_30_days', (SELECT count(*) FROM app.workspaces WHERE id >= id30),
            'disabled', (SELECT count(*) FROM app.workspaces WHERE disabled IS TRUE)),
        'forms', jsonb_build_object(
            'total', (SELECT count(*) FROM app.workspace_forms),
            'published', (SELECT count(*) FROM app.workspace_forms f
                          WHERE EXISTS (SELECT 1 FROM app.form_versions v WHERE v.form_id = f.form_id)),
            'new_last_30_days', (SELECT count(*) FROM app.workspace_forms WHERE id >= id30),
            'by_provider', coalesce((
                SELECT jsonb_object_agg(p.name, p.n)
                FROM (SELECT left(coalesce(nullif(doc -> 'settings' ->> 'provider', ''), 'unknown'), 40) AS name,
                             count(*) AS n
                      FROM app.workspace_forms GROUP BY 1 ORDER BY 2 DESC LIMIT 20) AS p), '{}'::jsonb)),
        'form_creators', jsonb_build_object(
            'total', (SELECT count(DISTINCT user_id) FROM app.workspace_forms
                      WHERE user_id IS NOT NULL AND user_id <> ''),
            'active_last_30_days', (SELECT count(DISTINCT user_id) FROM app.workspace_forms
                                    WHERE user_id IS NOT NULL AND user_id <> '' AND id >= id30)),
        'responses', jsonb_build_object(
            'total', (SELECT count(*) FROM app.form_responses WHERE doc ? 'answers'),
            'last_7_days', (SELECT count(*) FROM app.form_responses
                            WHERE doc ? 'answers' AND created_at >= since7),
            'last_30_days', (SELECT count(*) FROM app.form_responses
                             WHERE doc ? 'answers' AND created_at >= since30)),
        'form_responders', jsonb_build_object(
            'identified_responses', (SELECT count(*) FROM app.form_responses
                                     WHERE doc ? 'answers' AND data_owner_identifier IS NOT NULL
                                           AND data_owner_identifier <> ''),
            'identified', (SELECT count(DISTINCT data_owner_identifier) FROM app.form_responses
                           WHERE doc ? 'answers' AND data_owner_identifier IS NOT NULL
                                 AND data_owner_identifier <> ''),
            'anonymous_responses', (SELECT count(*) FROM app.form_responses
                                    WHERE doc ? 'answers'
                                          AND (data_owner_identifier IS NULL OR data_owner_identifier = ''))),
        'weekly', coalesce(weekly, '[]'::jsonb));
END
$fn$;

CREATE OR REPLACE FUNCTION admin.platform_counts_auth() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER STABLE
SET search_path = pg_catalog, pg_temp
SET timezone = 'UTC' AS $fn$
DECLARE
    first_week timestamptz :=
        (date_trunc('week', now() AT TIME ZONE 'UTC') - interval '11 weeks') AT TIME ZONE 'UTC';
    since30 timestamptz := now() - interval '30 days';
    id30 text := lpad(to_hex(floor(extract(epoch FROM now() - interval '30 days'))::bigint), 8, '0')
                 || '0000000000000000';
    weekly jsonb;
    active_users bigint := 0;
    rec record;
BEGIN
    SELECT jsonb_agg(jsonb_build_object(
        'week_start', (b.lo AT TIME ZONE 'UTC')::date,
        'new_users', (SELECT count(*) FROM auth.users u WHERE u.id >= b.lo_id AND u.id < b.hi_id)
    ) ORDER BY b.i)
    INTO weekly
    FROM (
        SELECT g.i, w.lo, w.hi,
               lpad(to_hex(floor(extract(epoch FROM w.lo))::bigint), 8, '0') || '0000000000000000' AS lo_id,
               lpad(to_hex(floor(extract(epoch FROM w.hi))::bigint), 8, '0') || '0000000000000000' AS hi_id
        FROM generate_series(0, 11) AS g(i),
             LATERAL (SELECT first_week + g.i * interval '1 week' AS lo,
                             first_week + (g.i + 1) * interval '1 week' AS hi) AS w
    ) AS b;

    -- Users who signed in within 30 days. A malformed last_logged_in value must
    -- count as inactive, never break the page: try the set-based count first and,
    -- only when a value does not parse, count row by row with each cast guarded.
    BEGIN
        SELECT count(*) INTO active_users FROM auth.users u
        WHERE CASE
                WHEN jsonb_typeof(u.doc -> 'last_logged_in') = 'object'
                     AND jsonb_typeof(u.doc -> 'last_logged_in' -> '$date') = 'string'
                    THEN (u.doc -> 'last_logged_in' ->> '$date')::timestamptz
                WHEN jsonb_typeof(u.doc -> 'last_logged_in') = 'object'
                     AND jsonb_typeof(u.doc -> 'last_logged_in' -> '$date') = 'object'
                    THEN to_timestamp(((u.doc -> 'last_logged_in' -> '$date' ->> '$numberLong')::bigint) / 1000.0)
                WHEN jsonb_typeof(u.doc -> 'last_logged_in') = 'string'
                     AND (u.doc ->> 'last_logged_in') ~ '(Z|[+-][0-9][0-9]:?[0-9][0-9])$'
                    THEN (u.doc ->> 'last_logged_in')::timestamptz
            END >= since30;
    EXCEPTION WHEN others THEN
        active_users := 0;
        FOR rec IN SELECT doc FROM auth.users WHERE doc ? 'last_logged_in' LOOP
            BEGIN
                IF (SELECT CASE
                WHEN jsonb_typeof(u2.doc -> 'last_logged_in') = 'object'
                     AND jsonb_typeof(u2.doc -> 'last_logged_in' -> '$date') = 'string'
                    THEN (u2.doc -> 'last_logged_in' ->> '$date')::timestamptz
                WHEN jsonb_typeof(u2.doc -> 'last_logged_in') = 'object'
                     AND jsonb_typeof(u2.doc -> 'last_logged_in' -> '$date') = 'object'
                    THEN to_timestamp(((u2.doc -> 'last_logged_in' -> '$date' ->> '$numberLong')::bigint) / 1000.0)
                WHEN jsonb_typeof(u2.doc -> 'last_logged_in') = 'string'
                     AND (u2.doc ->> 'last_logged_in') ~ '(Z|[+-][0-9][0-9]:?[0-9][0-9])$'
                    THEN (u2.doc ->> 'last_logged_in')::timestamptz
            END >= since30
                    FROM (SELECT rec.doc AS doc) AS u2) THEN
                    active_users := active_users + 1;
                END IF;
            EXCEPTION WHEN others THEN
                NULL;
            END;
        END LOOP;
    END;

    RETURN jsonb_build_object(
        'users', jsonb_build_object(
            'total', (SELECT count(*) FROM auth.users),
            'new_last_30_days', (SELECT count(*) FROM auth.users WHERE id >= id30),
            'active_last_30_days', active_users,
            'by_plan', jsonb_build_object(
                'FREE', (SELECT count(*) FROM auth.users WHERE coalesce(plan, 'FREE') = 'FREE'),
                'PRO', (SELECT count(*) FROM auth.users WHERE plan = 'PRO'))),
        'weekly', coalesce(weekly, '[]'::jsonb));
END
$fn$;

-- Account deletion queues a purge of the user's stored provider credentials
-- (backend services/credential_purge.py); the integrity monitor reports one that
-- is still pending a day after it was queued, or failed, and a deletion job in the
-- same state. A count only, from the queue's own tables in `jobs` (owned by the
-- backend's role, like `app`, so the same NOLOGIN owner as platform_counts_app).
CREATE OR REPLACE FUNCTION admin.credential_purges_overdue() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER STABLE
SET search_path = pg_catalog, pg_temp AS $fn$
BEGIN
    IF to_regnamespace('jobs') IS NULL OR NOT has_schema_privilege('jobs', 'USAGE')
       OR to_regclass('jobs.procrastinate_jobs') IS NULL
       OR to_regclass('jobs.procrastinate_events') IS NULL THEN
        RETURN 0;
    END IF;
    RETURN (
        SELECT count(*)::integer
          FROM jobs.procrastinate_jobs j
         WHERE j.task_name IN ('purge_provider_credentials', 'delete_user')
           AND (j.status = 'failed'
                OR (j.status IN ('todo', 'doing')
                    AND EXISTS (SELECT 1 FROM jobs.procrastinate_events e
                                 WHERE e.job_id = j.id AND e.type = 'deferred'
                                   AND e.at < now() - interval '1 day')))
    );
END
$fn$;

-- The functions' owners: one role per schema, NOLOGIN, owning only its function
-- and holding column-level SELECT on that schema's tables. This block runs on
-- every deploy, so the grants are re-applied once the application migrations
-- have created the tables.
DO $own$
DECLARE
    r text[];
BEGIN
    FOREACH r SLICE 1 IN ARRAY ARRAY[['bc_count_app', 'app'], ['bc_count_auth', 'auth']] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r[1]) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE', r[1]);
        END IF;
        EXECUTE format('ALTER ROLE %I NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', r[1]);
        EXECUTE format('REVOKE ALL ON DATABASE %I FROM %I', current_database(), r[1]);
        IF to_regnamespace(r[2]) IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', r[2], r[1]);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I', r[2], r[1]);
            EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', r[2], r[1]);
        END IF;
    END LOOP;
    IF to_regclass('app.workspaces') IS NOT NULL THEN
        GRANT SELECT (id, disabled) ON app.workspaces TO bc_count_app;
    END IF;
    IF to_regclass('app.workspace_forms') IS NOT NULL THEN
        GRANT SELECT (id, doc, user_id, form_id) ON app.workspace_forms TO bc_count_app;
    END IF;
    IF to_regclass('app.form_versions') IS NOT NULL THEN
        GRANT SELECT (form_id) ON app.form_versions TO bc_count_app;
    END IF;
    IF to_regclass('app.form_responses') IS NOT NULL THEN
        GRANT SELECT (doc, created_at, data_owner_identifier) ON app.form_responses TO bc_count_app;
    END IF;
    IF to_regclass('auth.users') IS NOT NULL THEN
        GRANT SELECT (id, doc, plan) ON auth.users TO bc_count_auth;
    END IF;
    -- the job queue (schema `jobs`, also the backend role's): only the columns
    -- admin.credential_purges_overdue() reads, never the job arguments
    IF to_regnamespace('jobs') IS NOT NULL THEN
        GRANT USAGE ON SCHEMA jobs TO bc_count_app;
    END IF;
    IF to_regclass('jobs.procrastinate_jobs') IS NOT NULL THEN
        GRANT SELECT (id, task_name, status) ON jobs.procrastinate_jobs TO bc_count_app;
    END IF;
    IF to_regclass('jobs.procrastinate_events') IS NOT NULL THEN
        GRANT SELECT (job_id, type, at) ON jobs.procrastinate_events TO bc_count_app;
    END IF;
END
$own$;
ALTER FUNCTION admin.credential_purges_overdue() OWNER TO bc_count_app;
REVOKE ALL ON FUNCTION admin.credential_purges_overdue() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION admin.credential_purges_overdue() TO bc_admin;
ALTER FUNCTION admin.platform_counts_app() OWNER TO bc_count_app;
ALTER FUNCTION admin.platform_counts_auth() OWNER TO bc_count_auth;
REVOKE ALL ON FUNCTION admin.platform_counts_app() FROM PUBLIC;
REVOKE ALL ON FUNCTION admin.platform_counts_auth() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION admin.platform_counts_app() TO bc_admin;
GRANT EXECUTE ON FUNCTION admin.platform_counts_auth() TO bc_admin;

RESET bc.admin_pw;
RESET bc.mig_pw;
RESET bc.tasks_pw;
RESET bc.tasks_data_app_pw;
RESET bc.tasks_data_google_pw;
SQL
echo "admin roles and schema are in place."
