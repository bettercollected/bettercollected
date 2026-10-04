#!/bin/bash

user_preference="$1"

# Array to hold selected services
services_to_start=("mongodb" "mongo-seed" "webapp" "nginx" "backend" "auth" "postgresql" "temporal" "worker" "umami-postgresql" "umami")

# Determine the appropriate Docker Compose command
if command -v docker-compose &>/dev/null; then
  docker_compose_cmd="docker-compose"
elif command -v docker &>/dev/null; then
  # Check if 'docker compose' is available
  if docker compose --help &>/dev/null; then
    docker_compose_cmd="docker compose"
  else
    echo "Neither 'docker-compose' nor 'docker compose' is available. Please install Docker Compose."
    exit 1
  fi
else
  echo "Docker is not installed. Please install Docker and Docker Compose."
  exit 1
fi

# docker-compose.deployment.yml substitutes ${UMAMI_APP_SECRET} itself (it's not
# read from .env.deployment, which only supplies container env, not compose
# variable substitution) — generate one on first run and persist it to a root
# .env so `docker compose` picks it up automatically on every subsequent run.
if [ ! -f .env ] || ! grep -q "^UMAMI_APP_SECRET=" .env 2>/dev/null; then
  echo "UMAMI_APP_SECRET=$(openssl rand -hex 32)" >> .env
  echo "Generated a new UMAMI_APP_SECRET in .env (first run)."
fi

# Same mechanism for the application Postgres (plans/postgres-consolidation.md):
# docker-compose.deployment.yml substitutes the superuser password and the four
# per-service role passwords, and postgres/init/01-roles-schemas.sh reads them on
# the volume's first start. Hex only, so they are safe inside DATABASE_URL.
# AUTH_INTERNAL_NOTIFY_KEY: shared by backend, auth and integrations-googleform;
# the auth service's API refuses every request without it (sign-in, users,
# billing, notification mails), so only those services can call it.
# TEMPORAL_API_KEY: shared by the backend (TEMPORAL_API_KEY) and the Temporal
# worker / actions-executor (API_KEY); the backend's internal job routes refuse
# requests without it and answer 503 while it is unset.
for var in APP_POSTGRES_PASSWORD BC_APP_PASSWORD BC_AUTH_PASSWORD BC_GOOGLE_PASSWORD BC_JOBS_EXEC_PASSWORD AUTH_INTERNAL_NOTIFY_KEY TEMPORAL_API_KEY; do
  if ! grep -q "^${var}=" .env 2>/dev/null; then
    echo "${var}=$(openssl rand -hex 24)" >> .env
    echo "Generated a new ${var} in .env (first run)."
  fi
done

# Single sign-on (docs/sso.md): off unless the root .env has SSO_ENABLED=true.
# Then Polis runs (compose profile `sso`) with generated secrets and its own
# database and role in app-postgres. The operator sets SSO_POLIS_URL,
# SSO_REDIRECT_URI and SSO_SAML_AUDIENCE in the root .env (see the doc).
sso_enabled=false
if grep -q "^SSO_ENABLED=true" .env 2>/dev/null; then
  sso_enabled=true
  for var in SSO_POLIS_URL SSO_REDIRECT_URI SSO_SAML_AUDIENCE; do
    if ! grep -q "^${var}=." .env; then
      echo "SSO_ENABLED=true needs ${var} in .env (see docs/sso.md)." >&2
      exit 1
    fi
  done
  # hex only: safe inside Polis's DB_URL. DB_ENCRYPTION_KEY must be 32 chars.
  for var in BC_POLIS_PASSWORD SSO_POLIS_API_KEY POLIS_CLIENT_SECRET_VERIFIER POLIS_NEXTAUTH_SECRET; do
    if ! grep -q "^${var}=" .env; then
      echo "${var}=$(openssl rand -hex 24)" >> .env
      echo "Generated a new ${var} in .env (first run with SSO)."
    fi
  done
  if ! grep -q "^POLIS_DB_ENCRYPTION_KEY=" .env; then
    echo "POLIS_DB_ENCRYPTION_KEY=$(openssl rand -hex 16)" >> .env
    echo "Generated a new POLIS_DB_ENCRYPTION_KEY in .env (first run with SSO)."
  fi
  services_to_start+=("polis")
fi

compose_files=(-f "docker-compose.deployment.yml")
if [ "$sso_enabled" = true ]; then
  compose_files+=(--profile sso)
fi

# Polis's own database and role, created once (idempotent). The password is
# re-applied on every run, so it always matches BC_POLIS_PASSWORD in .env.
function ensure_polis_database() {
  local password
  password=$(grep "^BC_POLIS_PASSWORD=" .env | cut -d= -f2-)
  "$docker_compose_cmd" "${compose_files[@]}" exec -T app-postgres \
    psql -v ON_ERROR_STOP=1 -U bettercollected -d postgres -v pw="$password" <<'SQL'
SELECT 'CREATE ROLE bc_polis LOGIN' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_polis')\gexec
ALTER ROLE bc_polis WITH LOGIN PASSWORD :'pw';
SELECT 'CREATE DATABASE polis OWNER bc_polis' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'polis')\gexec
REVOKE CONNECT ON DATABASE polis FROM PUBLIC;
GRANT CONNECT ON DATABASE polis TO bc_polis;
SQL
}

# Common docker function
function dockerup() {
  typeform_flag=false
  googleform_flag=false

  # Loop through the arguments in "$@"
  for arg in "$@"; do
    # Check if the current argument is equal to "integrations-typeform"
    if [ "$arg" == "integrations-typeform" ]; then
      typeform_flag=true
    fi

    # Check if the current argument is equal to "integrations-googleform"
    if [ "$arg" == "integrations-googleform" ]; then
      googleform_flag=true
    fi
  done

  # Schema migrations run once, here, before the services roll
  # (plans/postgres-consolidation.md). Each service owns one schema and its own
  # Alembic history; `run --rm --no-deps` executes inside the freshly pulled
  # image with the same DATABASE_URL the service will use. Services check the
  # revision at startup and refuse to serve on a stale schema; with
  # DB_AUTO_MIGRATE=true they would migrate themselves (advisory-locked), which
  # finds nothing left to do after this step.
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" pull -q backend auth $([ "$googleform_flag" = true ] && echo integrations-googleform)
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" up -d --wait app-postgres
  if [ "$sso_enabled" = true ]; then
    ensure_polis_database
  fi
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps backend /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini upgrade head
  # procrastinate's queue tables (jobs schema), applied once; a no-op afterwards
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps backend /api/backend/.venv/bin/python -m backend.jobs.schema
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps auth /api/auth/.venv/bin/alembic -c /api/auth/alembic.ini upgrade head
  if [ "$googleform_flag" = true ]; then
    "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps integrations-googleform alembic -c /api/integrations/google/alembic.ini upgrade head
  fi
  GOOGLE_ENABLED="$googleform_flag" TYPEFORM_ENABLED="$typeform_flag" "$docker_compose_cmd" "${compose_files[@]}" up --build -d "$@"
}

function dockerdown() {
  "$docker_compose_cmd" "${compose_files[@]}" down
}

if [ "$user_preference" == both ]; then
  services=("integrations-typeform" "integrations-googleform")
  for service in "${services[@]}"; do
    services_to_start+=("$service")
  done
  dockerup "${services_to_start[@]}"
elif [ "$user_preference" == googleform ]; then
  services_to_start+=("integrations-googleform")
  dockerup "${services_to_start[@]}"
elif [ "$user_preference" == typeform ]; then
  services_to_start+=("integrations-typeform")
  dockerup "${services_to_start[@]}"
elif [ "$user_preference" == down ]; then
  dockerdown
else
  dockerup "${services_to_start[@]}"
fi
