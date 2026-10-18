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
#                 tasks.run_events / checkpoints, INSERT/DELETE on tasks.locks,
#                 INSERT and SELECT on admin.audit_log; nothing else in `admin`
#                 and nothing in the other services' schemas.
#   admin.platform_counts()  one read-only SECURITY DEFINER function for the metrics
#                 page, owned by bc_admin_counts (NOLOGIN, column-level SELECT on the
#                 counted tables only); EXECUTE for bc_admin only.
#
# Schema `tasks` (the runner's state) is created here, owned by bc_admin_mig,
# like `admin`.
#
# The table grants are made by the migrations themselves (they know their
# tables); this script re-applies them for tables that already exist, so running
# it after a migration repairs drift. There are NO default privileges on
# purpose: they would hand UPDATE/DELETE on audit_log to the runtime role.
#
# Passwords come from BC_ADMIN_PASSWORD, BC_ADMIN_MIG_PASSWORD and BC_TASKS_PASSWORD and are never
# printed. Run inside the postgres container (it reads POSTGRES_USER/DB):
#   docker compose exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh
set -euo pipefail

: "${BC_ADMIN_PASSWORD:?BC_ADMIN_PASSWORD must be set}"
: "${BC_ADMIN_MIG_PASSWORD:?BC_ADMIN_MIG_PASSWORD must be set}"
: "${BC_TASKS_PASSWORD:?BC_TASKS_PASSWORD must be set}"
# the passwords are placed unencoded in database URLs by the compose file and
# deploy.sh: refuse characters that would break a URL (never print the value)
for name in BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD; do
    if ! printf '%s' "${!name}" | grep -Eq '^[A-Za-z0-9._~-]+$'; then
        echo "$name may only contain letters, digits, '.', '_', '~' and '-' (it is used unencoded in a database URL)." >&2
        exit 1
    fi
done
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"

psql -v ON_ERROR_STOP=1 --quiet --output /dev/null --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v admin_pw="$BC_ADMIN_PASSWORD" \
    -v mig_pw="$BC_ADMIN_MIG_PASSWORD" \
    -v tasks_pw="$BC_TASKS_PASSWORD" <<'SQL'
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SELECT count(set_config('bc.admin_pw', :'admin_pw', false));
SELECT count(set_config('bc.mig_pw', :'mig_pw', false));
SELECT count(set_config('bc.tasks_pw', :'tasks_pw', false));

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
    r text[];
    t text;
    s text;
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
        END IF;
    END LOOP;

    -- no TEMPORARY (temp tables) for the admin roles: it is granted to PUBLIC by
    -- default, so revoke it there and give it back by name to the existing
    -- service roles, whose access stays exactly as it was
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM bc_admin_mig', current_database());
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
        REVOKE ALL ON admin.audit_log FROM bc_tasks;
        GRANT SELECT, INSERT ON admin.audit_log TO bc_tasks;
        GRANT USAGE ON SEQUENCE admin.audit_log_seq_seq TO bc_tasks;
    END IF;

    -- the task runner's state (tables exist once the tasks revision has run)
    IF to_regclass('tasks.runs') IS NOT NULL THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA tasks FROM bc_admin, bc_tasks;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA tasks FROM bc_admin, bc_tasks;
        GRANT SELECT, INSERT ON tasks.runs TO bc_admin;
        GRANT UPDATE (cancel_requested_at) ON tasks.runs TO bc_admin;
        GRANT SELECT ON tasks.run_events, tasks.checkpoints, tasks.locks TO bc_admin;
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
    END IF;

    -- the settings store. The writer (bc_admin) holds exactly these; no DELETE
    -- on entries or manifest, and service_state is written
    -- only through settings.report_state.
    IF to_regclass('settings.entries') IS NOT NULL THEN
        REVOKE ALL ON settings.entries, settings.history, settings.manifest,
            settings.service_state FROM bc_admin;
        GRANT SELECT, INSERT, UPDATE ON settings.entries TO bc_admin;
        GRANT SELECT, INSERT, DELETE ON settings.history TO bc_admin;
        GRANT UPDATE (blob) ON settings.history TO bc_admin;
        GRANT SELECT, INSERT, UPDATE ON settings.manifest TO bc_admin;
        GRANT SELECT ON settings.service_state TO bc_admin;
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

-- Platform counts for the admin portal's metrics page: counts only, no
-- identifying value. The admin roles cannot read the `app` and `auth` schemas,
-- so this one read-only function is a SECURITY DEFINER owned by bc_admin_counts,
-- a role with SELECT on only the columns it reads (never a superuser), and is
-- executable by bc_admin alone. It never writes, takes no arguments and names its tables explicitly;
-- until the application migrations have run it fails and the page says so.
CREATE OR REPLACE FUNCTION admin.platform_counts() RETURNS jsonb
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
    result jsonb;
BEGIN
    SELECT jsonb_agg(jsonb_build_object(
        'week_start', (b.lo AT TIME ZONE 'UTC')::date,
        'new_users', (SELECT count(*) FROM auth.users u WHERE u.id >= b.lo_id AND u.id < b.hi_id),
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

    SELECT jsonb_build_object(
        'generated_at', now(),
        'organizations', jsonb_build_object(
            'total', (SELECT count(*) FROM app.workspaces),
            'new_last_30_days', (SELECT count(*) FROM app.workspaces WHERE id >= id30),
            'disabled', (SELECT count(*) FROM app.workspaces WHERE disabled IS TRUE)),
        'users', jsonb_build_object(
            'total', (SELECT count(*) FROM auth.users),
            'new_last_30_days', (SELECT count(*) FROM auth.users WHERE id >= id30),
            'active_last_30_days', (SELECT count(*) FROM auth.users u
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
                                    END >= since30),
            'by_plan', jsonb_build_object(
                'FREE', (SELECT count(*) FROM auth.users WHERE coalesce(plan, 'FREE') = 'FREE'),
                'PRO', (SELECT count(*) FROM auth.users WHERE plan = 'PRO'))),
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
            'identified', (SELECT count(DISTINCT data_owner_identifier) FROM app.form_responses
                           WHERE doc ? 'answers' AND data_owner_identifier IS NOT NULL
                                 AND data_owner_identifier <> ''),
            'anonymous_responses', (SELECT count(*) FROM app.form_responses
                                    WHERE doc ? 'answers'
                                          AND (data_owner_identifier IS NULL OR data_owner_identifier = ''))),
        'weekly', coalesce(weekly, '[]'::jsonb)
    ) INTO result;
    RETURN result;
END
$fn$;

-- The function's owner: a role that cannot log in, owns nothing and can create
-- nothing, and may read only the columns the function reads. The function must
-- not be owned by a superuser: it reads tables owned by other services' roles,
-- and an owner with more rights than that would run whatever those roles put in
-- front of it. This block runs on every deploy, so the grants are re-applied
-- once the application migrations have created the tables.
DO $own$
DECLARE
    g text[];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_admin_counts') THEN
        CREATE ROLE bc_admin_counts NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE;
    END IF;
    ALTER ROLE bc_admin_counts NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM bc_admin_counts', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO bc_admin_counts', current_database());
    FOREACH g SLICE 1 IN ARRAY ARRAY[['app'], ['auth']] LOOP
        IF to_regnamespace(g[1]) IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON SCHEMA %I FROM bc_admin_counts', g[1]);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM bc_admin_counts', g[1]);
            EXECUTE format('GRANT USAGE ON SCHEMA %I TO bc_admin_counts', g[1]);
        END IF;
    END LOOP;
    IF to_regclass('app.workspaces') IS NOT NULL THEN
        GRANT SELECT (id, disabled) ON app.workspaces TO bc_admin_counts;
    END IF;
    IF to_regclass('app.workspace_forms') IS NOT NULL THEN
        GRANT SELECT (id, doc, user_id, form_id) ON app.workspace_forms TO bc_admin_counts;
    END IF;
    IF to_regclass('app.form_versions') IS NOT NULL THEN
        GRANT SELECT (form_id) ON app.form_versions TO bc_admin_counts;
    END IF;
    IF to_regclass('app.form_responses') IS NOT NULL THEN
        GRANT SELECT (doc, created_at, data_owner_identifier) ON app.form_responses TO bc_admin_counts;
    END IF;
    IF to_regclass('auth.users') IS NOT NULL THEN
        GRANT SELECT (id, doc, plan) ON auth.users TO bc_admin_counts;
    END IF;
END
$own$;
ALTER FUNCTION admin.platform_counts() OWNER TO bc_admin_counts;
REVOKE ALL ON FUNCTION admin.platform_counts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION admin.platform_counts() TO bc_admin;

RESET bc.admin_pw;
RESET bc.mig_pw;
RESET bc.tasks_pw;
SQL
echo "admin roles and schema are in place."
