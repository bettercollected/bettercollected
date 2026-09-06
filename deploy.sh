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
for var in APP_POSTGRES_PASSWORD BC_APP_PASSWORD BC_AUTH_PASSWORD BC_GOOGLE_PASSWORD BC_JOBS_EXEC_PASSWORD; do
  if ! grep -q "^${var}=" .env 2>/dev/null; then
    echo "${var}=$(openssl rand -hex 24)" >> .env
    echo "Generated a new ${var} in .env (first run)."
  fi
done

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

  # Schema migrations run once, here, before the services roll — never from
  # application startup, where several replicas would race each other
  # (plans/postgres-consolidation.md). Each service owns one schema and its own
  # Alembic history; `run --rm --no-deps` executes inside the freshly pulled
  # image with the same DATABASE_URL the service will use.
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" pull -q backend auth $([ "$googleform_flag" = true ] && echo integrations-googleform)
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" up -d --wait app-postgres
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps backend /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini upgrade head
  # procrastinate's queue tables (jobs schema), applied once; a no-op afterwards
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps backend /api/backend/.venv/bin/python -m backend.jobs.schema
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps auth /api/auth/.venv/bin/alembic -c /api/auth/alembic.ini upgrade head
  if [ "$googleform_flag" = true ]; then
    "$docker_compose_cmd" -f "docker-compose.deployment.yml" run --rm --no-deps integrations-googleform alembic -c /api/integrations/google/alembic.ini upgrade head
  fi
  GOOGLE_ENABLED="$googleform_flag" TYPEFORM_ENABLED="$typeform_flag" "$docker_compose_cmd" -f "docker-compose.deployment.yml" up --build -d "$@"
}

function dockerdown() {
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" down
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
