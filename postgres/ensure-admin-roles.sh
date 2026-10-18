#!/bin/bash
# Creates (or repairs) the admin service's schema and its two roles. Idempotent:
# deploy.sh runs it as the database superuser on every deploy, before migrating.
#
#   bc_admin_mig  owns schema `admin` and its tables; used only to run the
#                 admin Alembic migrations (deploy time), never by the service.
#   bc_admin      the service's runtime role (ADMIN_DATABASE_URL). DML on the
#                 session, challenge, factor, recovery-code and attempt tables;
#                 INSERT and SELECT only on `audit_log` (plus USAGE on its
#                 sequence) so the log is append-only for the service. It has no
#                 access to the `app`, `auth`, `google` or `jobs` schemas.
#
# The table grants are made by the migrations themselves (they know their
# tables); this script re-applies them for tables that already exist, so running
# it after a migration repairs drift. There are NO default privileges on
# purpose: they would hand UPDATE/DELETE on audit_log to the runtime role.
#
# Passwords come from BC_ADMIN_PASSWORD and BC_ADMIN_MIG_PASSWORD and are never
# printed. Run inside the postgres container (it reads POSTGRES_USER/DB):
#   docker compose exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh
set -euo pipefail

: "${BC_ADMIN_PASSWORD:?BC_ADMIN_PASSWORD must be set}"
: "${BC_ADMIN_MIG_PASSWORD:?BC_ADMIN_MIG_PASSWORD must be set}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"

psql -v ON_ERROR_STOP=1 --quiet --output /dev/null --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v admin_pw="$BC_ADMIN_PASSWORD" \
    -v mig_pw="$BC_ADMIN_MIG_PASSWORD" <<'SQL'
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SELECT count(set_config('bc.admin_pw', :'admin_pw', false));
SELECT count(set_config('bc.mig_pw', :'mig_pw', false));

DO $do$
DECLARE
    -- To add a role (a task runner, a read-only reader, ...): add a {name, GUC}
    -- pair here, bind its password with another set_config line above and
    -- another -v option in the shell, then grant it what it needs in the
    -- revision that creates the tables (migration_support.grant(..., role=...)).
    -- Never add a role to `admin`'s default privileges.
    runtime_roles text[][] := ARRAY[
        ['bc_admin', 'bc.admin_pw']
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

    -- login roles: created once, password re-synced on every run
    FOREACH r SLICE 1 IN ARRAY runtime_roles LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r[1]) THEN
            EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE', r[1]);
        END IF;
        EXECUTE format('ALTER ROLE %I PASSWORD %L', r[1], current_setting(r[2]));
        EXECUTE format('ALTER ROLE %I SET search_path = admin', r[1]);
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), r[1]);
        EXECUTE format('GRANT USAGE ON SCHEMA admin TO %I', r[1]);
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
    END IF;
END
$do$;

RESET bc.admin_pw;
RESET bc.mig_pw;
SQL
echo "admin roles and schema are in place."
