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

# The stack's own signing and encryption keys (AUTH_JWT_SECRET,
# AUTH_AES_HEX_KEY, MASTER_ENCRYPTION_KEYSET) also live in the root .env:
# generated once, never overwritten, and refused by the services when empty or
# a value published in the repository (deploy/generate-secrets.sh). It needs to
# know whether this stack already holds data: an earlier deploy.sh run left its
# generated values behind, or the data volumes exist.
existing_stack=false
if grep -qE "^(UMAMI_APP_SECRET|APP_POSTGRES_PASSWORD|AUTH_INTERNAL_NOTIFY_KEY|TEMPORAL_API_KEY)=" .env 2>/dev/null; then
  existing_stack=true
fi
compose_project=$(printf '%s' "${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')
for volume in mongo-data app-postgres-data; do
  if docker volume inspect "${compose_project}_${volume}" &>/dev/null; then
    existing_stack=true
  fi
done
BC_EXISTING_STACK="$existing_stack" bash deploy/generate-secrets.sh .env .env.deployment || exit 1

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
for var in APP_POSTGRES_PASSWORD BC_APP_PASSWORD BC_AUTH_PASSWORD BC_GOOGLE_PASSWORD BC_JOBS_EXEC_PASSWORD BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD AUTH_INTERNAL_NOTIFY_KEY TEMPORAL_API_KEY; do
  if ! grep -q "^${var}=" .env 2>/dev/null; then
    echo "${var}=$(openssl rand -hex 24)" >> .env
    echo "Generated a new ${var} in .env (first run)."
  fi
done

# The internal admin service (database foundations only so far): BC_ADMIN_PASSWORD
# is its runtime role, BC_ADMIN_MIG_PASSWORD the migration role that owns schema
# `admin` (generated above; postgres/ensure-admin-roles.sh applies them).
# SETTINGS_MASTER_KEY (base64, 48 random bytes) is generated once and never
# overwritten: it encrypts the admin second-factor secrets and keys the audit
# log's hash chain.
if ! grep -q "^SETTINGS_MASTER_KEY=." .env 2>/dev/null; then
  echo "SETTINGS_MASTER_KEY=$(openssl rand -base64 48 | tr -d '\n')" >> .env
  echo "Generated a new SETTINGS_MASTER_KEY in .env (first run)."
fi
# .env holds every generated secret: owner-only, whatever the umask was
[ -f .env ] && chmod 600 .env
echo "IMPORTANT: back up SETTINGS_MASTER_KEY from .env. If it is lost, the admin service's"
echo "second-factor (TOTP) secrets cannot be decrypted and the audit log can no longer be"
echo "verified; neither is recoverable. Never change or regenerate it on a stack that has"
echo "admin data."
# The portal starts only when PLATFORM_ADMIN_EMAILS (the super admin list) is set
# in the root .env, next to the keys above. Never written here: it is the
# operator's decision who may sign in.
if ! grep -q "^PLATFORM_ADMIN_EMAILS=." .env 2>/dev/null; then
  echo ""
  echo "ADMIN PORTAL IS OFF: PLATFORM_ADMIN_EMAILS is not set in .env."
  echo "Add the super admins' email addresses (comma-separated) to enable it:"
  echo "  PLATFORM_ADMIN_EMAILS=you@example.com"
  echo "Sign-in codes are mailed, so set MAIL_SMTP_SERVER and MAIL_SENDER (and"
  echo "MAIL_USER / MAIL_PASSWORD if your server needs them) in .env as well."
  echo "See docs/admin-service.md."
  echo ""
fi

# Single sign-on (docs/sso.md): off unless the root .env has SSO_ENABLED=true.
# Then Polis and its own Postgres run from the overlay
# docker-compose.sso-deployment.yml, with secrets generated here (once; hex
# only, DB_ENCRYPTION_KEY must be 32 characters). The operator sets
# SSO_POLIS_URL, SSO_REDIRECT_URI and SSO_SAML_AUDIENCE in the root .env.
# Without SSO nothing here is needed or generated.
sso_enabled=false
compose_files=(-f "docker-compose.deployment.yml")
if grep -q "^SSO_ENABLED=true" .env 2>/dev/null; then
  sso_enabled=true
  for var in SSO_POLIS_URL SSO_REDIRECT_URI SSO_SAML_AUDIENCE; do
    if ! grep -q "^${var}=." .env; then
      echo "SSO_ENABLED=true needs ${var} in .env (see docs/sso.md)." >&2
      exit 1
    fi
  done
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
  compose_files+=(-f "docker-compose.sso-deployment.yml")
  services_to_start+=("polis-postgres" "polis")
fi

[ -f .env ] && chmod 600 .env

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
  # The admin service's schema and roles (idempotent), as the database superuser
  # inside the container, which already holds BC_ADMIN_*_PASSWORD. Then its own
  # migration chain as the migration role; the password goes in through the
  # environment, not the command line.
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh || exit 1
  admin_mig_password=$(grep -E "^BC_ADMIN_MIG_PASSWORD=" .env | tail -n 1 | cut -d= -f2-)
  DATABASE_URL="postgresql+asyncpg://bc_admin_mig:${admin_mig_password}@app-postgres:5432/bettercollected" \
    "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps -e DATABASE_URL backend /api/backend/.venv/bin/alembic -c /api/backend/backend/admin/alembic.ini upgrade head || exit 1
  unset admin_mig_password
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
