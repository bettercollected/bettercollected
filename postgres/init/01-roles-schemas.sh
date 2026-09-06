#!/bin/bash
# Creates the application database's schemas and least-privilege roles.
#
# One schema per service, one role per service that owns its schema:
#   app    <- bc_app        (backend; also owns `jobs`, the queue's tables)
#   auth   <- bc_auth       (auth service)
#   google <- bc_google     (integrations/google)
#   jobs   <- bc_app        (procrastinate; the actions-executor connects as
#                            bc_jobs_exec and can reach this schema and nothing
#                            else — it runs user-authored code)
#
# Runs once, on the first start of an empty volume (docker-entrypoint-initdb.d).
# Passwords come from the environment; the local compose stack leaves them at
# their role-name defaults, deploy.sh generates real ones on first run.
# See plans/postgres-consolidation.md, decision D3.
set -euo pipefail

: "${BC_APP_PASSWORD:=bc_app}"
: "${BC_AUTH_PASSWORD:=bc_auth}"
: "${BC_GOOGLE_PASSWORD:=bc_google}"
: "${BC_JOBS_EXEC_PASSWORD:=bc_jobs_exec}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v app_pw="$BC_APP_PASSWORD" \
    -v auth_pw="$BC_AUTH_PASSWORD" \
    -v google_pw="$BC_GOOGLE_PASSWORD" \
    -v jobs_pw="$BC_JOBS_EXEC_PASSWORD" <<'SQL'
CREATE ROLE bc_app       LOGIN PASSWORD :'app_pw';
CREATE ROLE bc_auth      LOGIN PASSWORD :'auth_pw';
CREATE ROLE bc_google    LOGIN PASSWORD :'google_pw';
CREATE ROLE bc_jobs_exec LOGIN PASSWORD :'jobs_pw';

CREATE SCHEMA app    AUTHORIZATION bc_app;
CREATE SCHEMA auth   AUTHORIZATION bc_auth;
CREATE SCHEMA google AUTHORIZATION bc_google;
CREATE SCHEMA jobs   AUTHORIZATION bc_app;

-- Nothing lands in `public` by accident, and only our roles may connect.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CONNECT ON DATABASE :"DBNAME" FROM PUBLIC;
GRANT  CONNECT ON DATABASE :"DBNAME" TO bc_app, bc_auth, bc_google, bc_jobs_exec;

-- Each service sees its own schema first. The backend also sees `jobs`
-- (it enqueues); the executor sees only `jobs`.
ALTER ROLE bc_app       SET search_path = app, jobs, public;
ALTER ROLE bc_auth      SET search_path = auth, public;
ALTER ROLE bc_google    SET search_path = google, public;
ALTER ROLE bc_jobs_exec SET search_path = jobs;

-- The executor may use the queue's tables, sequences and functions that the
-- backend creates in `jobs` (now and in the future) — and nothing in `app`.
GRANT USAGE ON SCHEMA jobs TO bc_jobs_exec;
ALTER DEFAULT PRIVILEGES FOR ROLE bc_app IN SCHEMA jobs
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bc_jobs_exec;
ALTER DEFAULT PRIVILEGES FOR ROLE bc_app IN SCHEMA jobs
    GRANT USAGE, SELECT ON SEQUENCES TO bc_jobs_exec;
ALTER DEFAULT PRIVILEGES FOR ROLE bc_app IN SCHEMA jobs
    GRANT EXECUTE ON FUNCTIONS TO bc_jobs_exec;
SQL
