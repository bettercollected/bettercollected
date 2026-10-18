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

# Extra precaution (docs/admin-service.md): create containers one at a time. The
# compose file's explicit network priorities are what fix the occasional
# one-network attach of containers on two networks (app-postgres, admin).
# Note this also serialises `pull` and `up --build` for the whole stack, so a
# deploy can take longer; set COMPOSE_PARALLEL_LIMIT yourself to change it.
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"

# What deploy.sh needs from the operator (docs/admin-service.md): in a fresh
# bundled install only PLATFORM_ADMIN_EMAILS (who may sign in to the admin
# portal) and, if the portal is reached from another address than the host
# itself, ADMIN_ALLOWED_IPS. Everything else is generated here, once, and never
# overwritten:
#   .env                     SETTINGS_MASTER_KEY, the database passwords, the
#                            Umami secret, the Temporal worker's two keys
#   the settings store       AUTH_JWT_SECRET, AUTH_AES_HEX_KEY,
#                            AUTH_INTERNAL_NOTIFY_KEY, TEMPORAL_API_KEY and the
#                            response keyset (`bootstrap-keys`; nothing printed)
# An upgrade from a release that kept those keys in .env imports them into the
# store instead (never overwriting), and checks the result against the files.
# Secrets are never printed: only names and counts.

compose_project=$(printf '%s' "${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')
compose_files=(-f "docker-compose.deployment.yml")
sso_enabled=false
if grep -q "^SSO_ENABLED=true" .env 2>/dev/null; then
  sso_enabled=true
  compose_files+=(-f "docker-compose.sso-deployment.yml")
fi

# The settings keys the stack's own files (the root .env, .env.deployment) can
# still carry, and the ones something outside the settings store reads:
#  - the Typeform service (a separate image) reads three keys from its
#    environment, so they stay in the files while it runs;
#  - deploy.sh itself reads the SSO values from the root .env to add the Polis
#    overlay (single sign-on stays environment-driven in this release);
#  - the admin service mails sign-in codes with MAIL_* from the environment
#    (until the admin mail settings are set up in the portal).
typeform_keys=(AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET)
env_driven_keys=(SSO_ENABLED SSO_POLIS_URL SSO_POLIS_API_KEY SSO_REDIRECT_URI SSO_SAML_AUDIENCE MAIL_USER MAIL_PASSWORD MAIL_SMTP_SERVER MAIL_SMTP_PORT MAIL_SENDER MAIL_STARTTLS MAIL_SSL_TLS MAIL_USE_CREDENTIALS MAIL_VALIDATE_CERTS)

# --- helpers ---------------------------------------------------------------------------

# True when FILE has a non-empty VAR assignment.
file_has() {
  grep -qE "^${2}=." "$1" 2>/dev/null
}

# Appends VAR=VALUE to the root .env (dropping an empty assignment of VAR first).
env_put() {
  local var=$1 value=$2 tmp
  if [ -f .env ] && grep -qE "^${var}=" .env; then
    tmp=$(mktemp .env.XXXXXX)
    grep -vE "^${var}=" .env > "$tmp" || true
    mv "$tmp" .env
  fi
  printf '%s=%s\n' "$var" "$value" >> .env
}

# Runs `python -m backend.admin ARGS` in a one-off admin container: it has the
# admin database role and the master key and nothing else (never a generated
# key: `bootstrap-keys` refuses an environment that carries one). Extra
# `docker compose run` options go in the admin_cli_opts array.
admin_cli_opts=()
admin_cli() {
  "$docker_compose_cmd" "${compose_files[@]}" run --rm --no-deps -T "${admin_cli_opts[@]}" admin /api/backend/.venv/bin/python -m backend.admin "$@"
}

compose_config_json() {
  "$docker_compose_cmd" "${compose_files[@]}" config --format json
}

# A private directory the one-off container (running as the calling user) can
# write files into; removed by the caller.
private_dir() {
  local dir
  dir=$(mktemp -d) || return 1
  chmod 700 "$dir"
  printf '%s' "$dir"
}

# Number of kept versions the store holds for KEY (0 when none), "" on error.
store_versions() {
  local out
  out=$(admin_cli settings-history "$1" 2>/dev/null) || return 1
  printf '%s\n' "$out" | sed -n 's/^versions=\([0-9][0-9]*\)$/\1/p' | tail -n 1
}

# complete: the three data keys are in the store; none: none of them; partial.
store_keys_state() {
  local key count have=0 want=0
  for key in AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET; do
    count=$(store_versions "$key") || { echo error; return 1; }
    [ -n "$count" ] || { echo error; return 1; }
    want=$((want + 1))
    [ "$count" -gt 0 ] && have=$((have + 1))
  done
  if [ "$have" -eq "$want" ]; then echo complete
  elif [ "$have" -eq 0 ]; then echo none
  else echo partial; fi
}

# Sets KEY to VALUE only when the store has never held a value for it.
seed_setting() {
  local key=$1 value=$2 count
  count=$(store_versions "$key") || return 1
  if [ "${count:-0}" -eq 0 ]; then
    printf '%s' "$value" | admin_cli settings-set "$key" --stdin --confirm "$key" --yes >/dev/null || return 1
  fi
}

# API_KEY and AES_HEX_KEY: the Temporal worker's copies of TEMPORAL_API_KEY and
# AUTH_AES_HEX_KEY. The worker is not on the settings store and never gets the
# master key, so the two values live in the root .env. Copies the legacy values
# when .env still has them, otherwise exports them from the store.
copy_legacy_worker_keys() {
  if ! file_has .env API_KEY && file_has .env TEMPORAL_API_KEY; then
    env_put API_KEY "$(grep -E '^TEMPORAL_API_KEY=' .env | tail -n 1 | cut -d= -f2-)"
  fi
  if ! file_has .env AES_HEX_KEY && file_has .env AUTH_AES_HEX_KEY; then
    env_put AES_HEX_KEY "$(grep -E '^AUTH_AES_HEX_KEY=' .env | tail -n 1 | cut -d= -f2-)"
  fi
}

ensure_worker_keys() {
  local dir out
  copy_legacy_worker_keys
  if file_has .env API_KEY && file_has .env AES_HEX_KEY; then
    return 0
  fi
  dir=$(private_dir) || return 1
  admin_cli_opts=(--user "$(id -u):$(id -g)" -v "$dir:/out")
  admin_cli bootstrap-keys --export-worker-only --export-worker /out/worker.env >/dev/null
  out=$?
  admin_cli_opts=()
  if [ "$out" -eq 0 ]; then merge_worker_env "$dir/worker.env"; out=$?; fi
  rm -rf "$dir"
  return "$out"
}

# Appends API_KEY / AES_HEX_KEY from FILE to .env when .env has no value for them.
merge_worker_env() {
  local var line
  for var in API_KEY AES_HEX_KEY; do
    line=$(grep -E "^${var}=." "$1" | tail -n 1)
    if [ -z "$line" ]; then
      echo "The worker key ${var} is missing from the bootstrap output." >&2
      return 1
    fi
    if ! file_has .env "$var"; then
      env_put "$var" "${line#*=}"
    fi
  done
}

# Prints how many settings the store holds against the files. Names only.
settings_drift() {
  ( set -o pipefail; compose_config_json | admin_cli settings-drift --from-compose-config "$@" )
}

# The root .env aliases that expand into a stored setting: a value here is an
# environment value and wins over the store, and prune cannot remove it because
# the name is not a setting.
warn_env_aliases() {
  local name
  for name in TRUSTED_PROXIES STRIPE_REDIRECT_URL; do
    if file_has .env "$name"; then
      echo "NOTE: ${name} is set in .env. It is passed to the services as an environment value, which wins over"
      echo "      the settings store. Once the stack runs, remove it from .env to manage it in the portal."
    fi
  done
}

# Replaces Umami's built-in admin/umami login (its port has to be reachable by
# respondents' browsers) with a generated password, stored as the backend's
# UMAMI_PASSWORD setting. Safe to repeat: it does nothing once the built-in
# login no longer works.
umami_credentials() {
  local state password stamp tmp
  local js="deploy/umami-rotate.js"
  local i
  for i in $(seq 1 30); do
    state=$("$docker_compose_cmd" "${compose_files[@]}" exec -T umami node - < "$js" 2>/dev/null)
    case "$state" in default_login=*) break ;; esac
    sleep 2
  done
  case "$state" in
    default_login=yes) ;;
    default_login=no) return 0 ;;
    *) echo "WARNING: could not check Umami's admin login (is the umami service healthy?). Re-run deploy.sh." >&2; return 0 ;;
  esac
  password=$(openssl rand -hex 24)
  seed_setting UMAMI_USERNAME admin || { echo "WARNING: could not store the Umami user name; Umami's login was not changed." >&2; return 0; }
  # the store first: a failure leaves Umami untouched. A failure after it is
  # repaired by the next run, which still finds the built-in login and stores
  # a new password.
  if ! printf '%s' "$password" | admin_cli settings-set UMAMI_PASSWORD --stdin --yes >/dev/null; then
    echo "WARNING: could not store the Umami password; Umami's login was not changed." >&2
    return 0
  fi
  if ! UMAMI_NEW_PASSWORD="$password" "$docker_compose_cmd" "${compose_files[@]}" exec -T -e UMAMI_NEW_PASSWORD umami node - < "$js" >/dev/null 2>&1; then
    echo "WARNING: Umami's built-in admin/umami login could not be replaced. Re-run deploy.sh; until then anyone" >&2
    echo "         who can reach port 3003 can sign in to Umami." >&2
    return 0
  fi
  unset password
  # an old UMAMI_PASSWORD in .env.deployment is an environment value that would win
  # over the store: blank it (a private backup of the file is kept)
  if [ -f .env.deployment ] && file_has .env.deployment UMAMI_PASSWORD; then
    stamp=$(date +%Y%m%d%H%M%S)
    cp -p .env.deployment ".env.deployment.pre-umami.${stamp}" && chmod 600 ".env.deployment.pre-umami.${stamp}"
    tmp=$(mktemp .env.deployment.XXXXXX)
    sed 's/^UMAMI_PASSWORD=.*/UMAMI_PASSWORD=/' .env.deployment > "$tmp" && cat "$tmp" > .env.deployment
    rm -f "$tmp"
    echo "Blanked UMAMI_PASSWORD in .env.deployment (backup: .env.deployment.pre-umami.${stamp}, holds the old value)."
  fi
  echo "Replaced Umami's built-in admin/umami login with a generated password (the UMAMI_PASSWORD setting; not shown)."
  echo "To sign in to Umami yourself: ./deploy.sh settings-env-export --keys UMAMI_USERNAME,UMAMI_PASSWORD --out FILE"
  "$docker_compose_cmd" "${compose_files[@]}" up -d --force-recreate --no-deps backend jobs-worker >/dev/null
}

# ./deploy.sh settings-prune [--apply] [--swap] [--typeform | --no-typeform]
# Removes from .env and .env.deployment the settings the store already holds
# with the same value (docs/admin-service.md). Without --apply it only reports.
settings_prune() {
  local args=() typeform=auto arg keep=() dir rc stamp
  for arg in "$@"; do
    case "$arg" in
      --typeform) typeform=yes ;;
      --no-typeform) typeform=no ;;
      *) args+=("$arg") ;;
    esac
  done
  if [ "$typeform" = auto ]; then
    typeform=no
    if [ -n "$("$docker_compose_cmd" "${compose_files[@]}" ps -aq integrations-typeform 2>/dev/null)" ]; then
      typeform=yes
    fi
  fi
  local name
  for name in "${env_driven_keys[@]}"; do keep+=(--keep "$name"); done
  if [ "$typeform" = yes ]; then
    for name in "${typeform_keys[@]}"; do keep+=(--keep "$name"); done
    echo "integrations-typeform is deployed: its three keys (${typeform_keys[*]}) are kept in the files."
  fi
  dir=$(private_dir) || return 1
  cp -p .env "$dir/.env" 2>/dev/null
  cp -p .env.deployment "$dir/.env.deployment" 2>/dev/null
  chmod 600 "$dir"/.env* 2>/dev/null
  admin_cli_opts=(--user "$(id -u):$(id -g)" -v "$dir:/work")
  admin_cli settings-prune --env-file /work/.env --env-file /work/.env.deployment "${keep[@]}" "${args[@]}"
  rc=$?
  admin_cli_opts=()
  if printf '%s\n' "${args[@]}" | grep -qx -- '--swap' && printf '%s\n' "${args[@]}" | grep -qx -- '--apply'; then
    [ -f "$dir/.env" ] && cat "$dir/.env" > .env
    [ -f "$dir/.env.deployment" ] && cat "$dir/.env.deployment" > .env.deployment
  fi
  for stamp in "$dir"/.env.pre-v4.* "$dir"/.env.deployment.pre-v4.* "$dir"/.env.pruned "$dir"/.env.deployment.pruned; do
    [ -e "$stamp" ] || continue
    if [ -e "./$(basename "$stamp")" ]; then
      echo "not overwriting existing $(basename "$stamp")" >&2
    else
      mv "$stamp" "./$(basename "$stamp")"
      chmod 600 "./$(basename "$stamp")"
    fi
  done
  rm -rf "$dir"
  chmod 600 .env 2>/dev/null
  return "$rc"
}

# ./deploy.sh settings-env-export --keys A,B --out FILE (break-glass)
settings_env_export() {
  local keys="" out="" dir rc
  while [ $# -gt 0 ]; do
    case "$1" in
      --keys) keys="$2"; shift 2 ;;
      --out) out="$2"; shift 2 ;;
      *) echo "usage: ./deploy.sh settings-env-export --keys A,B --out FILE" >&2; return 2 ;;
    esac
  done
  if [ -z "$keys" ] || [ -z "$out" ]; then
    echo "usage: ./deploy.sh settings-env-export --keys A,B --out FILE" >&2
    return 2
  fi
  if [ -e "$out" ]; then
    echo "refused: $out exists" >&2
    return 1
  fi
  dir=$(private_dir) || return 1
  admin_cli_opts=(--user "$(id -u):$(id -g)" -v "$dir:/out")
  admin_cli settings-env-export --keys "$keys" --out /out/export.env
  rc=$?
  admin_cli_opts=()
  if [ "$rc" -eq 0 ]; then
    ( umask 077; cat "$dir/export.env" > "$out" ) && chmod 600 "$out"
    echo "written: $out (mode 600; delete it when done)"
  fi
  rm -rf "$dir"
  return "$rc"
}

# Prints the one-time setup token on the console only: it is shown once, it is
# in no log and no file, and the one-off container (and with it the container's
# log) is removed when the command ends.
setup_token() {
  if [ ! -t 0 ] || [ ! -t 1 ]; then
    echo "The setup token is shown on a terminal only. Run ./deploy.sh setup-token from one." >&2
    return 1
  fi
  "$docker_compose_cmd" "${compose_files[@]}" run --rm --no-deps admin /api/backend/.venv/bin/python -m backend.admin setup-token "$@"
}

# --- host commands on the settings store ------------------------------------------------
# These need the stack's database up and the root .env of this stack.
case "$user_preference" in
  settings-import)
    shift
    ( set -o pipefail; compose_config_json | admin_cli settings-import --from-compose-config "$@" )
    exit $?
    ;;
  settings-drift)
    shift
    settings_drift "$@"
    exit $?
    ;;
  settings-prune)
    shift
    settings_prune "$@"
    exit $?
    ;;
  settings-env-export)
    shift
    settings_env_export "$@"
    exit $?
    ;;
  setup-token)
    shift
    setup_token "$@"
    exit $?
    ;;
  settings-set|settings-restore|settings-history|settings-verify|master-key-fingerprint)
    shift
    admin_cli "$user_preference" "$@"
    exit $?
    ;;
esac

# --- generated secrets ------------------------------------------------------------------

# Does the stack already hold data? Its data volumes outlive a failed first run
# only for Postgres, so the Mongo volume (created by the first complete start)
# is the sign of a stack that ran.
existing_stack=false
if docker volume inspect "${compose_project}_mongo-data" &>/dev/null; then
  existing_stack=true
fi
fresh_temporal_db=true
docker volume inspect "${compose_project}_temporal-postgres-data" &>/dev/null && fresh_temporal_db=false
fresh_umami_db=true
docker volume inspect "${compose_project}_umami-db-data" &>/dev/null && fresh_umami_db=false

# A release that kept its keys in the root .env or .env.deployment (before the
# settings store): they are imported, not generated.
legacy_keys=false
for key_file in .env .env.deployment; do
  for key in AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET; do
    if file_has "$key_file" "$key"; then legacy_keys=true; fi
  done
done

# docker-compose.deployment.yml substitutes ${UMAMI_APP_SECRET} itself (it's not
# read from .env.deployment, which only supplies container env, not compose
# variable substitution) — generate one on first run and persist it to a root
# .env so `docker compose` picks it up automatically on every subsequent run.
if [ ! -f .env ]; then
  ( umask 077; : > .env )
fi
if ! grep -q "^UMAMI_APP_SECRET=" .env 2>/dev/null; then
  echo "UMAMI_APP_SECRET=$(openssl rand -hex 32)" >> .env
  echo "Generated a new UMAMI_APP_SECRET in .env (first run)."
fi

# Same mechanism for the application Postgres (plans/postgres-consolidation.md):
# docker-compose.deployment.yml substitutes the superuser password and the
# per-service role passwords, and postgres/init/01-roles-schemas.sh reads them on
# the volume's first start. Hex only, so they are safe inside DATABASE_URL.
for var in APP_POSTGRES_PASSWORD BC_APP_PASSWORD BC_AUTH_PASSWORD BC_GOOGLE_PASSWORD BC_JOBS_EXEC_PASSWORD BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD BC_TASKS_DATA_APP_PASSWORD BC_TASKS_DATA_GOOGLE_PASSWORD; do
  if ! grep -q "^${var}=" .env 2>/dev/null; then
    echo "${var}=$(openssl rand -hex 24)" >> .env
    echo "Generated a new ${var} in .env (first run)."
  fi
done

# The Temporal and Umami databases are internal only, but no longer use the
# well-known password on a new volume. A volume created by an earlier release
# keeps the password it was created with, which is what compose uses when the
# variable is unset (docs/admin-service.md, "Internal credentials and ports").
if [ "$fresh_temporal_db" = true ] && ! grep -q "^BC_TEMPORAL_DB_PASSWORD=" .env 2>/dev/null; then
  echo "BC_TEMPORAL_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
  echo "Generated a new BC_TEMPORAL_DB_PASSWORD in .env (first run)."
fi
if [ "$fresh_umami_db" = true ] && ! grep -q "^BC_UMAMI_DB_PASSWORD=" .env 2>/dev/null; then
  echo "BC_UMAMI_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
  echo "Generated a new BC_UMAMI_DB_PASSWORD in .env (first run)."
fi

# BC_ADMIN_PASSWORD and BC_ADMIN_MIG_PASSWORD go unencoded into database URLs
# (compose ADMIN_DATABASE_URL, the migration URL below): only URL-safe characters
# are accepted, because "@", "/", "#" or "?" would break the URL or point it
# elsewhere. Generated values are hex; this guards values set by hand.
for var in BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD BC_TASKS_DATA_APP_PASSWORD BC_TASKS_DATA_GOOGLE_PASSWORD; do
  value=$(grep -E "^${var}=" .env | tail -n 1 | cut -d= -f2-)
  if ! printf '%s' "$value" | grep -Eq '^[A-Za-z0-9._~-]+$'; then
    echo "${var} in .env must be non-empty and use only letters, digits, '.', '_', '~' and '-'" >&2
    echo "(it is placed unencoded in a database URL). Remove the line to have a new one generated." >&2
    exit 1
  fi
done
unset value

# The internal admin service: BC_ADMIN_PASSWORD is its runtime role,
# BC_ADMIN_MIG_PASSWORD the migration role that owns schema `admin` (generated
# above; postgres/ensure-admin-roles.sh applies them). BC_TASKS_PASSWORD is the
# task runner's own role and BC_TASKS_DATA_APP_PASSWORD /
# BC_TASKS_DATA_GOOGLE_PASSWORD its two narrow data roles, one per owning schema.
# SETTINGS_MASTER_KEY (base64, 48 random bytes) is generated once and never
# overwritten: it encrypts the settings store and the admin second-factor
# secrets and keys the audit log's hash chain.
if ! grep -q "^SETTINGS_MASTER_KEY=." .env 2>/dev/null; then
  if [ "$existing_stack" = true ] && [ "$legacy_keys" = false ]; then
    echo "SETTINGS_MASTER_KEY is not set in .env, but this stack has run before. If the settings store holds data," >&2
    echo "restore the key you backed up (a new one cannot open it); otherwise add SETTINGS_MASTER_KEY to .env." >&2
    exit 1
  fi
  echo "SETTINGS_MASTER_KEY=$(openssl rand -base64 48 | tr -d '\n')" >> .env
  echo "Generated a new SETTINGS_MASTER_KEY in .env (first run)."
fi
# .env holds every generated secret: owner-only, whatever the umask was
chmod 600 .env
echo "IMPORTANT: back up SETTINGS_MASTER_KEY from .env. If it is lost, every secret in the settings"
echo "store (including the response encryption keyset), the admin second-factor secrets and the audit"
echo "log's verification are not recoverable. Never change or regenerate it on a stack that has data."
# The portal starts only when PLATFORM_ADMIN_EMAILS (the super admin list) is set
# in the root .env, next to the keys above. Never written here: it is the
# operator's decision who may sign in.
if ! grep -q "^PLATFORM_ADMIN_EMAILS=." .env 2>/dev/null; then
  echo ""
  echo "ADMIN PORTAL IS OFF: PLATFORM_ADMIN_EMAILS is not set in .env."
  echo "Add the super admins' email addresses (comma-separated) to enable it:"
  echo "  PLATFORM_ADMIN_EMAILS=you@example.com"
  echo "If you reach the portal from another address than this host, also set"
  echo "ADMIN_ALLOWED_IPS (default 127.0.0.1/32). Sign-in codes are mailed, so set"
  echo "MAIL_SMTP_SERVER and MAIL_SENDER (and MAIL_USER / MAIL_PASSWORD if your server"
  echo "needs them) in .env as well. See docs/admin-service.md."
  echo ""
fi

# Single sign-on (docs/sso.md): off unless the root .env has SSO_ENABLED=true.
# Then Polis and its own Postgres run from the overlay
# docker-compose.sso-deployment.yml, with secrets generated here (once; hex
# only, DB_ENCRYPTION_KEY must be 32 characters). The operator sets
# SSO_POLIS_URL, SSO_REDIRECT_URI and SSO_SAML_AUDIENCE in the root .env.
# Without SSO nothing here is needed or generated.
if [ "$sso_enabled" = true ]; then
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
  services_to_start+=("polis-postgres" "polis")
fi

chmod 600 .env

# The stack's keys (AUTH_JWT_SECRET, AUTH_AES_HEX_KEY, AUTH_INTERNAL_NOTIFY_KEY,
# TEMPORAL_API_KEY, MASTER_ENCRYPTION_KEYSET) live in the settings store. Runs
# after the database and its migrations are in place and before any service
# starts, because the services refuse to start without them.
function stack_keys() {
  local state rc dir
  state=$(store_keys_state) || {
    echo "Could not read the settings store (see the message above). Is SETTINGS_MASTER_KEY the key this stack has used?" >&2
    return 1
  }

  if [ "$state" != complete ] && { [ "$legacy_keys" = true ] || [ "$existing_stack" = true ]; }; then
    # An upgrade: the keys are in the old files. Copy values still in
    # .env.deployment into the root .env and refuse published ones
    # (deploy/generate-secrets.sh), then import everything the services read.
    BC_EXISTING_STACK=true bash deploy/generate-secrets.sh .env .env.deployment || return 1
    for var in AUTH_INTERNAL_NOTIFY_KEY TEMPORAL_API_KEY; do
      if [ "$(store_versions "$var")" = 0 ] && ! file_has .env "$var"; then
        env_put "$var" "$(openssl rand -hex 24)"
        echo "Generated a new ${var} in .env (it is imported into the settings store below)."
      fi
    done
    copy_legacy_worker_keys
    echo "Importing the settings found in the compose configuration into the settings store (names and counts only):"
    import_out=$( ( set -o pipefail; compose_config_json | admin_cli settings-import --from-compose-config ) 2>&1 )
    rc=$?
    printf '%s\n' "$import_out"
    if [ "$rc" -ne 0 ]; then
      # A value the registry refuses (a URL without https, say) is not imported
      # and stays an environment value, which is how it has been read so far:
      # that is a warning. A conflict, a published or weak key, a refused key
      # of the stack, or anything unexpected stops the deploy.
      if printf '%s\n' "$import_out" | grep -qE '^conflict |Traceback| weak_secret$| no_secret_check$|^refused (AUTH_JWT_SECRET|AUTH_AES_HEX_KEY|AUTH_INTERNAL_NOTIFY_KEY|TEMPORAL_API_KEY|MASTER_ENCRYPTION_KEYSET) ' \
        || ! printf '%s\n' "$import_out" | grep -q '^refused '; then
        echo "The import stopped: nothing was overwritten. Review it with ./deploy.sh settings-import --dry-run;" >&2
        echo "values the services disagree on need --prefer SERVICE (docs/admin-service.md)." >&2
        return 1
      fi
      echo "NOTE: the settings listed as refused are not imported; they stay environment values (which win over the store)."
      echo "      Fix them in .env / .env.deployment and run ./deploy.sh settings-import to import them."
    fi
    echo "Comparing the store with the files:"
    settings_drift || {
      echo "The store and the files differ (see above). An environment value wins over the store in this release:" >&2
      echo "fix the differing values, then run ./deploy.sh again." >&2
      return 1
    }
    warn_env_aliases
    echo "The old values are still in .env / .env.deployment, and a value there wins over the store. Once the"
    echo "stack runs, remove them with: ./deploy.sh settings-prune --apply --swap   (before rotating any key)"
  elif [ "$state" != complete ]; then
    # A new stack: generate the keys straight into the store; nothing is printed
    # except the master key's short fingerprint.
    dir=$(private_dir) || return 1
    admin_cli_opts=(--user "$(id -u):$(id -g)" -v "$dir:/out")
    admin_cli bootstrap-keys $([ "$state" = partial ] && echo --fill-missing) --export-worker /out/worker.env
    rc=$?
    admin_cli_opts=()
    if [ "$rc" -eq 0 ]; then merge_worker_env "$dir/worker.env"; rc=$?; fi
    rm -rf "$dir"
    if [ "$rc" -ne 0 ]; then
      echo "Generating the stack's keys failed (see above). Fix the cause and run ./deploy.sh again: it continues where it stopped." >&2
      return 1
    fi
    fresh_install=true
  fi

  ensure_worker_keys || {
    echo "Could not set up the Temporal worker's keys (API_KEY, AES_HEX_KEY) in .env." >&2
    return 1
  }
  chmod 600 .env
  # Values the services used to get pinned by the compose file, now plain settings
  seed_setting UMAMI_URL "http://umami:3000" || {
    echo "Could not seed the UMAMI_URL setting." >&2
    return 1
  }
}

fresh_install=false

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
  # again, now that the other services' tables exist: the task runner's data
  # role is granted on them (a no-op when nothing changed)
  "$docker_compose_cmd" -f "docker-compose.deployment.yml" exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh || exit 1

  # The settings store exists now: the stack's keys go into it (new stack) or
  # are imported from the old files (upgrade), before the services need them.
  stack_keys || exit 1

  GOOGLE_ENABLED="$googleform_flag" TYPEFORM_ENABLED="$typeform_flag" "$docker_compose_cmd" "${compose_files[@]}" up --build -d "$@"

  umami_credentials

  if [ "$fresh_install" = true ]; then
    echo ""
    echo "Master key fingerprint (write it down with the key backup; a restored key with another one is the wrong key):"
    admin_cli master-key-fingerprint 2>/dev/null
    if file_has .env PLATFORM_ADMIN_EMAILS; then
      echo ""
      echo "First sign-in: the one-time setup token below is shown once, here, and nowhere else."
      echo "It is valid for 60 minutes. Open the admin portal through an SSH tunnel to this host"
      echo "(ssh -L 8100:127.0.0.1:8100 <host>, then http://127.0.0.1:8100/setup) and enter it."
      echo "Lost it? ./deploy.sh setup-token --new"
      setup_token || true
    else
      echo "Set PLATFORM_ADMIN_EMAILS in .env, restart the admin service and run ./deploy.sh setup-token for the first sign-in."
    fi
  fi
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
