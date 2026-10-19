#!/bin/bash

# Everything this script creates (the root .env, the per-service env files, exports,
# backups, scratch files) is owner-only from the first byte, whatever the caller's umask.
umask 077

user_preference="$1"

# The services every deployment starts. `up -d NAME...` starts only the services
# it names (and what they depend on), so each one has to be listed here: the admin
# service (the portal), the jobs worker (the procrastinate `default` queue:
# delete_user and delete_response), the document sandbox (PDF import fails closed
# without it) and the task runner. The optional ones are added further down.
services_to_start=("mongodb" "mongo-seed" "webapp" "nginx" "backend" "auth" "postgresql" "temporal" "worker" "umami-postgresql" "umami" "admin" "jobs-worker" "document-sandbox" "task-runner")

# Determine the appropriate Docker Compose command. An array: "docker compose" (the
# plugin) is two words, and a quoted string of it would be looked up as one command
# name, which fails on a host that has only the plugin.
if command -v docker-compose &>/dev/null; then
  docker_compose_cmd=(docker-compose)
elif command -v docker &>/dev/null; then
  # Check if 'docker compose' is available
  if docker compose --help &>/dev/null; then
    docker_compose_cmd=(docker compose)
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

# --- the .env files, read the way docker compose reads them ---------------------------

# The value of the last assignment of VAR in FILE (an `export` prefix, blanks around
# the name, single or double quotes and a trailing ` #comment` on an unquoted value
# are understood); empty when there is none.
dotenv_value() {
  local line
  line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${2}[[:space:]]*=" "$1" 2>/dev/null | tail -n 1) || true
  [ -n "$line" ] || return 0
  printf '%s' "$(dotenv_unquote "${line#*=}")"
}

# The value part of an assignment: surrounding blanks, quotes and (unquoted) comment removed.
dotenv_unquote() {
  local text=$1
  text=${text#"${text%%[![:space:]]*}"}
  case "$text" in
    \"*) text=${text#\"}; text=${text%%\"*} ;;
    \'*) text=${text#\'}; text=${text%%\'*} ;;
    *) text=${text%%[[:space:]]\#*}; text=${text%"${text##*[![:space:]]}"} ;;
  esac
  printf '%s' "$text"
}

# The project name docker compose will use, from the same sources in the same order:
# the shell's COMPOSE_PROJECT_NAME, the one in the root .env, a top-level `name:` of
# the compose file, the name of this directory. It is exported afterwards, so compose
# and this script cannot disagree about which volumes are the stack's.
normalize_project() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-'; }
shell_project=$(normalize_project "${COMPOSE_PROJECT_NAME:-}")
dir_project=$(normalize_project "$(basename "$PWD")")
compose_project=$shell_project
[ -n "$compose_project" ] || compose_project=$(normalize_project "$(dotenv_value .env COMPOSE_PROJECT_NAME)")
[ -n "$compose_project" ] || compose_project=$(normalize_project "$(sed -n 's/^name:[[:space:]]*//p' docker-compose.deployment.yml 2>/dev/null | head -n 1)")
[ -n "$compose_project" ] || compose_project=$dir_project
export COMPOSE_PROJECT_NAME="$compose_project"

compose_files=(-f "docker-compose.deployment.yml")
sso_enabled=false
# compose substitutes the shell's SSO_ENABLED, else the root .env's, and the services
# read it as a boolean (true, 1, yes, on, t, y in any case): so does this.
sso_value=$(printf '%s' "${SSO_ENABLED-$(dotenv_value .env SSO_ENABLED)}" | tr '[:upper:]' '[:lower:]')
case "$sso_value" in
  true|1|yes|on|t|y)
    sso_enabled=true
    compose_files+=(-f "docker-compose.sso-deployment.yml")
    services_to_start+=("polis-postgres" "polis")
    ;;
esac

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

# What the services that are NOT settings-store readers read from their environment,
# beyond the few values docker-compose.deployment.yml sets itself. Each gets an env
# file of its own (service_env_file) holding only these names, so none of them receives
# Stripe, Google or mail secrets, the Mongo root URI or any key. A trailing * is a
# prefix. docs/settings-inventory.md lists the readers; a test compares the two.
webapp_env_keys=(INTERNAL_DOCKER_API_ENDPOINT_HOST API_ENDPOINT_HOST DASHBOARD_DOMAIN FORM_DOMAIN HTTP_SCHEME FORM_PRIVACY_POLICY_URL BASE_DEPLOY_PATH UNSPLASH_ACCESS_KEY GOOGLE_CLIENT_ID GOOGLE_PICKER_API_KEY UMAMI_WEBSITE_ID UMAMI_SCRIPT_URL CUSTOM_DOMAIN_APPLICATION_ID CUSTOM_DOMAIN_ASSERTION_KEYS CUSTOM_DOMAIN_ASSERTION_MODE CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN 'NEXT_PUBLIC_*' 'ELASTIC_APM_*')
worker_env_keys=(SERVER_URL NAMESPACE WORKER_QUEUE WORKERS COOKIE_DOMAIN MAX_THREAD_POOL_EXECUTORS 'ELASTIC_APM_*')
# the Typeform image is not built here; this is what its last released source read
typeform_env_keys=(DEBUG API_ROOT_PATH API_ENVIRONMENT API_VERSION AUTH_SERVER_URL MONGO_URI MONGO_DB TYPEFORM_SCOPE TYPEFORM_CLIENT_ID TYPEFORM_CLIENT_SECRET TYPEFORM_AUTH_URI TYPEFORM_TOKEN_URI TYPEFORM_REDIRECT_URI TYPEFORM_API_URI SENTRY_DSN 'ELASTIC_APM_*')

# --- helpers ---------------------------------------------------------------------------

# True when FILE has a non-empty VAR assignment.
file_has() {
  [ -n "$(dotenv_value "$1" "$2")" ]
}

# True when FILE assigns VAR at all (an empty value counts).
file_assigns() {
  grep -qE "^[[:space:]]*(export[[:space:]]+)?${2}[[:space:]]*=" "$1" 2>/dev/null
}

# Drops every assignment of VAR from the root .env.
env_unset() {
  local var=$1 tmp
  if [ -f .env ] && file_assigns .env "$var"; then
    tmp=$(mktemp .env.XXXXXX) || return 1
    grep -vE "^[[:space:]]*(export[[:space:]]+)?${var}[[:space:]]*=" .env > "$tmp" || true
    chmod 600 "$tmp"
    mv "$tmp" .env
  fi
}

# Appends VAR=VALUE to the root .env (dropping an earlier assignment of VAR first).
env_put() {
  env_unset "$1" || return 1
  printf '%s=%s\n' "$1" "$2" >> .env
}

# Creates the env file of a service that is not one of the settings-store readers
# (webapp, Temporal worker, Typeform), once, from the lines of .env.deployment it
# reads. It never gets anything else, so a bug in the public webapp or in the browser
# the worker drives cannot expose the backend's secrets. An existing file is never
# changed (only its mode is made private). An item ending in * is a name prefix.
service_env_file() {
  local file=$1 line name value item match tmp
  shift
  if [ -L "$file" ]; then
    echo "refused: $file is a symbolic link" >&2
    return 1
  fi
  if [ -e "$file" ]; then
    chmod 600 "$file" 2>/dev/null
    return 0
  fi
  tmp=$(mktemp .env.XXXXXX) || return 1
  if [ -f .env.deployment ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      name=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}\([A-Za-z_][A-Za-z0-9_]*\)[[:space:]]*=.*/\2/p')
      [ -n "$name" ] || continue
      match=false
      for item in "$@"; do
        case "$item" in
          *'*') [[ "$name" == "${item%\*}"* ]] && match=true ;;
          *) [ "$name" = "$item" ] && match=true ;;
        esac
      done
      [ "$match" = true ] || continue
      # an empty value would replace the service's own default with nothing
      value=$(dotenv_unquote "${line#*=}")
      [ -n "$value" ] || continue
      line=${line#"${line%%[![:space:]]*}"}
      printf '%s\n' "${line#export }" >> "$tmp"
    done < .env.deployment
  fi
  chmod 600 "$tmp"
  mv "$tmp" "$file"
}

# Runs `python -m backend.admin ARGS` in a one-off admin container: it has the
# admin database role and the master key and nothing else (never a generated
# key: `bootstrap-keys` refuses an environment that carries one). Extra
# `docker compose run` options go in the admin_cli_opts array.
admin_cli_opts=()
admin_cli() {
  "${docker_compose_cmd[@]}" "${compose_files[@]}" run --rm --no-deps -T "${admin_cli_opts[@]}" admin /api/backend/.venv/bin/python -m backend.admin "$@"
}

compose_config_json() {
  "${docker_compose_cmd[@]}" "${compose_files[@]}" config --format json
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
    env_put API_KEY "$(dotenv_value .env TEMPORAL_API_KEY)"
  fi
  if ! file_has .env AES_HEX_KEY && file_has .env AUTH_AES_HEX_KEY; then
    env_put AES_HEX_KEY "$(dotenv_value .env AUTH_AES_HEX_KEY)"
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

# Replaces Umami's built-in admin/umami login with a generated password, stored as
# the backend's UMAMI_PASSWORD setting. Umami's dashboard is published on the host's
# loopback only (the public port 3003 is nginx and passes the tracker script and the
# event endpoint, nothing else), but the built-in login must not outlive a deploy.
# Safe to repeat: it does nothing once the built-in login no longer works. Returns 0
# when the built-in login is gone (or was never there) and 1 when it may still work:
# the caller decides how loud that is.
umami_credentials() {
  local state password stamp scratch attempt
  local js="deploy/umami-rotate.js"
  local i
  for i in $(seq 1 30); do
    state=$("${docker_compose_cmd[@]}" "${compose_files[@]}" exec -T umami node - < "$js" 2>/dev/null)
    case "$state" in default_login=*) break ;; esac
    sleep 2
  done
  case "$state" in
    default_login=yes) ;;
    default_login=no) return 0 ;;
    *) echo "WARNING: could not check Umami's admin login (is the umami service healthy?). Re-run deploy.sh." >&2; return 1 ;;
  esac
  password=$(openssl rand -hex 24)
  seed_setting UMAMI_USERNAME admin || { echo "WARNING: could not store the Umami user name; Umami's login was not changed." >&2; return 1; }
  # the store first: a failure leaves Umami untouched. A failure after it is
  # repaired by the next run, which still finds the built-in login and stores
  # a new password.
  if ! printf '%s' "$password" | admin_cli settings-set UMAMI_PASSWORD --stdin --yes >/dev/null; then
    echo "WARNING: could not store the Umami password; Umami's login was not changed." >&2
    return 1
  fi
  # a few tries: Umami may still be settling right after its first start
  for attempt in 1 2 3; do
    if UMAMI_NEW_PASSWORD="$password" "${docker_compose_cmd[@]}" "${compose_files[@]}" exec -T -e UMAMI_NEW_PASSWORD umami node - < "$js" >/dev/null 2>&1; then
      break
    fi
    if [ "$attempt" -eq 3 ]; then
      echo "WARNING: Umami's built-in admin/umami login could not be replaced. Re-run deploy.sh; until then anyone" >&2
      echo "         who can reach the host's port 3004 (loopback) can sign in to Umami." >&2
      return 1
    fi
    sleep "${BC_DEPLOY_RETRY_SLEEP:-5}"
  done
  unset password
  # an old UMAMI_PASSWORD in .env.deployment is an environment value that would win
  # over the store: blank it (a private backup of the file is kept)
  if [ -f .env.deployment ] && file_has .env.deployment UMAMI_PASSWORD; then
    stamp=$(date +%Y%m%d%H%M%S)
    cp -p .env.deployment ".env.deployment.pre-umami.${stamp}" && chmod 600 ".env.deployment.pre-umami.${stamp}"
    scratch=$(private_dir) || return 1
    sed 's/^UMAMI_PASSWORD=.*/UMAMI_PASSWORD=/' .env.deployment > "$scratch/env" && cat "$scratch/env" > .env.deployment
    rm -rf "$scratch"
    echo "Blanked UMAMI_PASSWORD in .env.deployment (backup: .env.deployment.pre-umami.${stamp}, holds the old value)."
  fi
  echo "Replaced Umami's built-in admin/umami login with a generated password (the UMAMI_PASSWORD setting; not shown)."
  echo "To sign in to Umami yourself: ./deploy.sh settings-env-export --keys UMAMI_USERNAME,UMAMI_PASSWORD --out FILE"
  "${docker_compose_cmd[@]}" "${compose_files[@]}" up -d --force-recreate --no-deps backend jobs-worker >/dev/null \
    || echo "WARNING: could not restart the backend and the jobs worker to read the new Umami password; run ./deploy.sh again." >&2
  return 0
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
    if [ -n "$("${docker_compose_cmd[@]}" "${compose_files[@]}" ps -aq integrations-typeform 2>/dev/null)" ]; then
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
  # -e is false for a dangling symbolic link, and writing through one would put the
  # secrets wherever it points: refuse links too, and create the file exclusively.
  if [ -e "$out" ] || [ -L "$out" ]; then
    echo "refused: $out exists" >&2
    return 1
  fi
  dir=$(private_dir) || return 1
  admin_cli_opts=(--user "$(id -u):$(id -g)" -v "$dir:/out")
  admin_cli settings-env-export --keys "$keys" --out /out/export.env
  rc=$?
  admin_cli_opts=()
  if [ "$rc" -eq 0 ]; then
    if ( umask 077; set -C; cat "$dir/export.env" > "$out" ) 2>/dev/null && chmod 600 "$out"; then
      echo "written: $out (mode 600; delete it when done)"
    else
      echo "refused: $out could not be created exclusively" >&2
      rc=1
    fi
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
  "${docker_compose_cmd[@]}" "${compose_files[@]}" run --rm --no-deps admin /api/backend/.venv/bin/python -m backend.admin setup-token "$@"
}

# The services `up` is asked to start for a preference (both, googleform, typeform or
# none): the always-on list above plus the optional integrations. One name per line.
services_for() {
  local list=("${services_to_start[@]}")
  case "$1" in
    both) list+=("integrations-typeform" "integrations-googleform") ;;
    googleform) list+=("integrations-googleform") ;;
    typeform) list+=("integrations-typeform") ;;
  esac
  printf '%s\n' "${list[@]}"
}

# --- .env.deployment ----------------------------------------------------------------------
# The services' env file is the operator's own and is not tracked by git; the repository
# ships the template .env.deployment.example. A missing .env.deployment is created from
# the template, owner-only from the first byte. An existing one is never overwritten
# (also not when it is a link: it is the operator's), and a dangling link is refused
# rather than written through.
ensure_env_deployment() {
  [ -e .env.deployment ] && return 0
  if [ -L .env.deployment ]; then
    echo "refused: .env.deployment is a symbolic link that points nowhere; fix or remove it" >&2
    return 1
  fi
  if [ ! -f .env.deployment.example ]; then
    echo "refused: neither .env.deployment nor its template .env.deployment.example exists" >&2
    return 1
  fi
  if ! ( umask 077; set -C; cat .env.deployment.example > .env.deployment ) 2>/dev/null; then
    echo "refused: .env.deployment could not be created" >&2
    return 1
  fi
  chmod 600 .env.deployment
  echo "Created .env.deployment from .env.deployment.example (mode 600). Your own values go there; git ignores it."
}

# print-services only lists names and writes nothing
if [ "$user_preference" != "print-services" ]; then
  ensure_env_deployment || exit 1
fi

# --- host commands on the settings store ------------------------------------------------
# These need the stack's database up and the root .env of this stack.
case "$user_preference" in
  print-services)
    # what `./deploy.sh [PREFERENCE]` hands to `docker compose up -d` (tested against
    # `docker compose up --dry-run`)
    services_for "${2:-}"
    exit 0
    ;;
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
# is the sign of a stack that ran. This is also what keeps a stack whose data is in
# Mongo from getting a new response keyset: bootstrap-keys runs in a one-off
# container that has no Mongo credentials, so it can count only the Postgres side
# (users, responses); the Mongo side is decided here, by the volume, and below by a
# MONGO_URI in the files (an external Mongo this script cannot look into).
#
# The volumes are looked up under the project name compose will use (above). A stack
# found under a different name (the directory's, while COMPOSE_PROJECT_NAME was set
# later or elsewhere) is refused: compose would create a second, empty stack beside
# it and every password generated here would not match the first one's volumes.
stack_volume_names=(mongo-data app-postgres-data temporal-postgres-data umami-db-data)

# True when any volume of the compose project $1 exists: the stack's four data
# volumes by name, or anything labelled with the project.
project_has_volumes() {
  local name
  for name in "${stack_volume_names[@]}"; do
    docker volume inspect "${1}_${name}" &>/dev/null && return 0
  done
  [ -n "$(docker volume ls -q --filter "label=com.docker.compose.project=${1}" 2>/dev/null)" ]
}

stack_volumes_present=false
project_has_volumes "$compose_project" && stack_volumes_present=true
for other_project in "$dir_project" "$shell_project"; do
  [ -n "$other_project" ] && [ "$other_project" != "$compose_project" ] || continue
  # only a mismatch when the name compose uses has no volumes of its own
  [ "$stack_volumes_present" = false ] || continue
  if project_has_volumes "$other_project"; then
    echo "Volumes of a stack named '${other_project}' exist, but docker compose will use the project name '${compose_project}'" >&2
    echo "(COMPOSE_PROJECT_NAME in the shell or in .env, else the directory name). Generating passwords now would not" >&2
    echo "match those volumes. Set COMPOSE_PROJECT_NAME=${other_project} in .env to keep using that stack, or remove the" >&2
    echo "old volumes if it is not wanted, then run ./deploy.sh again." >&2
    exit 1
  fi
done

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
# owner-only before anything is appended (an .env the operator made may be 644), and
# a last line without a newline must not swallow the first appended assignment
chmod 600 .env
if [ -s .env ] && [ -n "$(tail -c 1 .env)" ]; then
  echo >> .env
fi
# the other files that hold or receive secrets
chmod 600 .env.deployment 2>/dev/null
if ! file_assigns .env UMAMI_APP_SECRET; then
  echo "UMAMI_APP_SECRET=$(openssl rand -hex 32)" >> .env
  echo "Generated a new UMAMI_APP_SECRET in .env (first run)."
fi

# Same mechanism for the application Postgres (plans/postgres-consolidation.md):
# docker-compose.deployment.yml substitutes the superuser password and the
# per-service role passwords, and postgres/init/01-roles-schemas.sh reads them on
# the volume's first start. Hex only, so they are safe inside DATABASE_URL.
for var in APP_POSTGRES_PASSWORD BC_APP_PASSWORD BC_AUTH_PASSWORD BC_GOOGLE_PASSWORD BC_JOBS_EXEC_PASSWORD BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD BC_TASKS_DATA_APP_PASSWORD BC_TASKS_DATA_GOOGLE_PASSWORD; do
  if ! file_assigns .env "$var"; then
    echo "${var}=$(openssl rand -hex 24)" >> .env
    echo "Generated a new ${var} in .env (first run)."
  fi
done

# The Temporal, Umami and Mongo databases are internal only, but no longer use the
# well-known password on a new volume. A volume created by an earlier release
# keeps the password it was created with, which is what compose uses when the
# variable is unset (docs/admin-service.md, "Internal credentials and ports").
# Fail closed: these three passwords are read only when their volume is created, so
# none is generated while ANY volume of the stack exists (under the project name
# compose uses; a stack under another name was refused above). A missing value then
# means the default of the volume's own release, never a new password that would not
# match what is stored.
if [ "$stack_volumes_present" = true ]; then
  for var in BC_TEMPORAL_DB_PASSWORD BC_UMAMI_DB_PASSWORD BC_MONGO_ROOT_PASSWORD; do
    if ! file_has .env "$var"; then
      echo "NOTE: ${var} is not set and this stack already has volumes: no new one is generated (it would not match them)."
    fi
  done
else
  if ! file_assigns .env BC_TEMPORAL_DB_PASSWORD; then
    echo "BC_TEMPORAL_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
    echo "Generated a new BC_TEMPORAL_DB_PASSWORD in .env (first run)."
  fi
  # Mongo's root password, for a new stack only: an upgrade keeps the MONGO_URI it
  # has (an operator's own MONGO_URI in .env.deployment counts as one).
  if [ "$legacy_keys" = false ] && ! file_has .env.deployment MONGO_URI \
     && ! file_assigns .env BC_MONGO_ROOT_PASSWORD; then
    echo "BC_MONGO_ROOT_PASSWORD=$(openssl rand -hex 24)" >> .env
    echo "Generated a new BC_MONGO_ROOT_PASSWORD in .env (first run)."
  fi
  if ! file_assigns .env BC_UMAMI_DB_PASSWORD; then
    echo "BC_UMAMI_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
    echo "Generated a new BC_UMAMI_DB_PASSWORD in .env (first run)."
  fi
fi

# These passwords go unencoded into database URLs (compose ADMIN_DATABASE_URL, the
# migration URL below, DATABASE_URL of every service, the seeded MONGO_URI): only
# URL-safe characters are accepted, because "@", "/", "#" or "?" would break the URL
# or point it elsewhere. Generated values are hex; this guards values set by hand.
# The Umami and Mongo passwords are checked when set (they may be unset): the others
# (APP_POSTGRES_PASSWORD, BC_TEMPORAL_DB_PASSWORD) are not part of a URL.
for var in BC_APP_PASSWORD BC_AUTH_PASSWORD BC_GOOGLE_PASSWORD BC_JOBS_EXEC_PASSWORD BC_ADMIN_PASSWORD BC_ADMIN_MIG_PASSWORD BC_TASKS_PASSWORD BC_TASKS_DATA_APP_PASSWORD BC_TASKS_DATA_GOOGLE_PASSWORD BC_UMAMI_DB_PASSWORD BC_MONGO_ROOT_PASSWORD; do
  case "$var" in
    BC_UMAMI_DB_PASSWORD|BC_MONGO_ROOT_PASSWORD) file_assigns .env "$var" || continue ;;
  esac
  value=$(dotenv_value .env "$var")
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
if ! file_has .env SETTINGS_MASTER_KEY; then
  if [ "$existing_stack" = true ] && [ "$legacy_keys" = false ]; then
    echo "SETTINGS_MASTER_KEY is not set in .env, but this stack has run before. If the settings store holds data," >&2
    echo "restore the key you backed up (a new one cannot open it); otherwise add SETTINGS_MASTER_KEY to .env." >&2
    exit 1
  fi
  # an empty assignment (SETTINGS_MASTER_KEY=) would be shadowed by a new line, not
  # replaced: drop it first
  env_put SETTINGS_MASTER_KEY "$(openssl rand -base64 48 | tr -d '\n')"
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
if ! file_has .env PLATFORM_ADMIN_EMAILS; then
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
# The admin settings are read by docker compose from the root .env only. A value in
# .env.deployment has no effect on the portal (it used to be listed there), so say so
# instead of letting an operator believe a restriction is in force.
for var in ADMIN_PORT ADMIN_ALLOWED_IPS ADMIN_ALLOWED_HOSTS ADMIN_PUBLIC_ORIGINS ADMIN_TRUSTED_PROXIES ADMIN_EDGE_SUBNET ADMIN_EDGE_GATEWAY; do
  if file_has .env.deployment "$var" && ! file_has .env "$var"; then
    echo "NOTE: ${var} is set in .env.deployment but the admin service ignores it there: put it in the root .env."
  fi
done
# The admin portal's address check treats the Docker gateway as a trusted address,
# because that is how a connection to 127.0.0.1:8100 arrives. A reverse proxy on this
# host in front of the portal would make every client look like that gateway, so
# these settings (which only matter behind a proxy or on another address) get a
# reminder. Reach the portal with an SSH tunnel instead (docs/admin-service.md).
for var in ADMIN_TRUSTED_PROXIES ADMIN_ALLOWED_HOSTS ADMIN_PUBLIC_ORIGINS; do
  if file_has .env "$var"; then
    echo "NOTE: ${var} is set. Never put a reverse proxy in front of the admin portal's port unless ADMIN_TRUSTED_PROXIES"
    echo "      and ADMIN_ALLOWED_IPS are set for it: see 'Network' in docs/admin-service.md. An SSH tunnel is the supported way in."
    break
  fi
done

# Single sign-on (docs/sso.md): off unless the root .env has SSO_ENABLED=true.
# Then Polis and its own Postgres run from the overlay
# docker-compose.sso-deployment.yml, with secrets generated here (once; hex
# only, DB_ENCRYPTION_KEY must be 32 characters). The operator sets
# SSO_POLIS_URL, SSO_REDIRECT_URI and SSO_SAML_AUDIENCE in the root .env.
# Without SSO nothing here is needed or generated.
if [ "$sso_enabled" = true ]; then
  for var in SSO_POLIS_URL SSO_REDIRECT_URI SSO_SAML_AUDIENCE; do
    if ! file_has .env "$var"; then
      echo "SSO_ENABLED=true needs ${var} in .env (see docs/sso.md)." >&2
      exit 1
    fi
  done
  for var in BC_POLIS_PASSWORD SSO_POLIS_API_KEY POLIS_CLIENT_SECRET_VERIFIER POLIS_NEXTAUTH_SECRET; do
    if ! file_assigns .env "$var"; then
      echo "${var}=$(openssl rand -hex 24)" >> .env
      echo "Generated a new ${var} in .env (first run with SSO)."
    fi
  done
  if ! file_assigns .env POLIS_DB_ENCRYPTION_KEY; then
    echo "POLIS_DB_ENCRYPTION_KEY=$(openssl rand -hex 16)" >> .env
    echo "Generated a new POLIS_DB_ENCRYPTION_KEY in .env (first run with SSO)."
  fi
fi

chmod 600 .env

# The env files of the services that are not settings-store readers (webapp, Temporal
# worker, Typeform): each holds only what that service reads, copied once from
# .env.deployment, mode 600. The Typeform service also needs the Mongo connection
# (it is not on the store); a new stack's MONGO_URI is in the store, not in the files,
# so it is written here from the generated root password.
service_env_file .env.webapp "${webapp_env_keys[@]}" || exit 1
service_env_file .env.worker "${worker_env_keys[@]}" || exit 1
service_env_file .env.typeform "${typeform_env_keys[@]}" || exit 1
if { [ "$user_preference" = typeform ] || [ "$user_preference" = both ]; } \
   && [ -f .env.typeform ] && ! file_has .env.typeform MONGO_URI && file_has .env BC_MONGO_ROOT_PASSWORD; then
  printf 'MONGO_URI=mongodb://root:%s@mongodb:27017\n' "$(dotenv_value .env BC_MONGO_ROOT_PASSWORD)" >> .env.typeform
fi

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
    #
    # bootstrap-keys can only count the data it can reach, and its one-off container
    # holds the admin database role and nothing else: no Mongo credentials. So the
    # Mongo half of "does this stack hold data?" is decided here, explicitly. A Mongo
    # volume of this stack (the upgrade branch above is taken for it, so this is a
    # second line of defence) or a MONGO_URI in the files (an external Mongo this
    # script cannot look into) means data may exist: refuse, never guess.
    if [ "$existing_stack" = true ] || file_has .env MONGO_URI || file_has .env.deployment MONGO_URI; then
      echo "" >&2
      echo "STOPPED before any service started, and no new keys were stored. This stack has a MongoDB (a volume of this" >&2
      echo "project, or a MONGO_URI in .env or .env.deployment) that may hold data, and the key generator cannot look" >&2
      echo "inside it: a new response keyset could not read what an old one encrypted. Put the keys this stack has" >&2
      echo "used (AUTH_JWT_SECRET, AUTH_AES_HEX_KEY, MASTER_ENCRYPTION_KEYSET) in .env, then run ./deploy.sh again; it" >&2
      echo "imports them (see 'Upgrading to 4.0' in docs/admin-service.md). A MongoDB that is known to be empty:" >&2
      echo "remove the MONGO_URI line." >&2
      return 1
    fi
    dir=$(private_dir) || return 1
    admin_cli_opts=(--user "$(id -u):$(id -g)" -v "$dir:/out")
    # its output is counts, names and the refusal reason: never key material
    boot_out=$(admin_cli bootstrap-keys $([ "$state" = partial ] && echo --fill-missing) --export-worker /out/worker.env 2>&1)
    rc=$?
    admin_cli_opts=()
    printf '%s\n' "$boot_out"
    if [ "$rc" -ne 0 ] && printf '%s\n' "$boot_out" | grep -qE 'stack_has_data|stack_unknown|existing_stack|keys_in_environment'; then
      rm -rf "$dir"
      echo "" >&2
      echo "STOPPED before any service started, and no new keys were stored. This database already holds data" >&2
      echo "(or that could not be established), and a new response keyset could not read what the old one" >&2
      echo "encrypted. Import the keys this stack has used instead: put AUTH_JWT_SECRET, AUTH_AES_HEX_KEY and" >&2
      echo "MASTER_ENCRYPTION_KEYSET in .env, then run ./deploy.sh again (it imports them; see" >&2
      echo "'Upgrading to 4.0' in docs/admin-service.md and ./deploy.sh settings-import --dry-run)." >&2
      return 1
    fi
    if [ "$rc" -eq 0 ]; then merge_worker_env "$dir/worker.env"; rc=$?; fi
    rm -rf "$dir"
    if [ "$rc" -ne 0 ]; then
      echo "Generating the stack's keys failed (see above). Fix the cause and run ./deploy.sh again: it continues where it stopped." >&2
      return 1
    fi
    fresh_install=true
    # remembered in .env until the first-sign-in notice below has been shown: a run
    # that stops after this point (a failed start, a closed terminal) would otherwise
    # never print the fingerprint or offer the setup token, because the next run finds
    # the keys complete
    env_put BC_FIRST_RUN_PENDING 1
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
  # The Mongo connection: the generated root password of a new stack, or the
  # original default for a stack whose files do not carry a MONGO_URI (the
  # template used to ship it). Never overwrites a stored value.
  if file_has .env BC_MONGO_ROOT_PASSWORD; then
    seed_setting MONGO_URI "mongodb://root:$(dotenv_value .env BC_MONGO_ROOT_PASSWORD)@mongodb:27017" || {
      echo "Could not seed the MONGO_URI setting." >&2
      return 1
    }
  elif [ "$existing_stack" = true ] || [ "$stack_volumes_present" = true ]; then
    seed_setting MONGO_URI "mongodb://root:root@mongodb:27017" || {
      echo "Could not seed the MONGO_URI setting." >&2
      return 1
    }
  fi
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
  # Pull every first-party image the stack runs, so no service keeps a stale cached
  # one. A failed pull (offline, a local build) is a warning: the cached images are used.
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" pull -q backend auth webapp worker \
    $([ "$googleform_flag" = true ] && echo integrations-googleform) \
    $([ "$typeform_flag" = true ] && echo integrations-typeform) \
    || echo "WARNING: could not pull all images; the images already on this host are used." >&2
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" up -d --wait app-postgres || exit 1
  # The admin service's schema and roles (idempotent), as the database superuser
  # inside the container, which already holds BC_ADMIN_*_PASSWORD. Then its own
  # migration chain as the migration role; the password goes in through the
  # environment, not the command line.
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh || exit 1
  admin_mig_password=$(dotenv_value .env BC_ADMIN_MIG_PASSWORD)
  DATABASE_URL="postgresql+asyncpg://bc_admin_mig:${admin_mig_password}@app-postgres:5432/bettercollected" \
    "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps -e DATABASE_URL backend /api/backend/.venv/bin/alembic -c /api/backend/backend/admin/alembic.ini upgrade head || exit 1
  unset admin_mig_password
  # a failed migration stops the deploy: the services would refuse the stale schema
  # anyway, and what follows (keys, the start) should not run against it
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps backend /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini upgrade head || exit 1
  # procrastinate's queue tables (jobs schema), applied once; a no-op afterwards
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps backend /api/backend/.venv/bin/python -m backend.jobs.schema || exit 1
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps auth /api/auth/.venv/bin/alembic -c /api/auth/alembic.ini upgrade head || exit 1
  if [ "$googleform_flag" = true ]; then
    "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps integrations-googleform alembic -c /api/integrations/google/alembic.ini upgrade head || exit 1
  fi
  # again, now that the other services' tables exist: the task runner's data
  # role is granted on them (a no-op when nothing changed)
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh || exit 1

  # The settings store exists now: the stack's keys go into it (new stack) or
  # are imported from the old files (upgrade), before the services need them.
  stack_keys || exit 1

  GOOGLE_ENABLED="$googleform_flag" TYPEFORM_ENABLED="$typeform_flag" "${docker_compose_cmd[@]}" "${compose_files[@]}" up --build -d "$@" || {
    echo "docker compose could not start the stack (see above). Fix the cause and run ./deploy.sh again: it continues where it stopped." >&2
    exit 1
  }

  # Umami's built-in admin/umami login must be gone before a new installation is
  # called done: a failure is fatal on a fresh install (the next run repairs it and
  # still prints the first-sign-in notice) and a warning on an upgrade.
  if ! umami_credentials; then
    if [ "$fresh_install" = true ] || file_has .env BC_FIRST_RUN_PENDING; then
      echo "STOPPED: Umami's built-in login could not be replaced on this new installation. The stack is running; run ./deploy.sh again." >&2
      exit 1
    fi
  fi

  # an interrupted first run (the keys exist, the notice below was never shown)
  if file_has .env BC_FIRST_RUN_PENDING; then
    fresh_install=true
  fi

  if [ "$fresh_install" = true ]; then
    echo ""
    echo "Master key fingerprint (write it down with the key backup; a restored key with another one is the wrong key):"
    admin_cli master-key-fingerprint 2>/dev/null
    if file_has .env PLATFORM_ADMIN_EMAILS; then
      if wait_admin_healthy; then
        echo ""
        echo "First sign-in: the one-time setup token below is shown once, here, and nowhere else."
        echo "It is valid for 60 minutes. Open the admin portal through an SSH tunnel to this host"
        echo "(ssh -L 8100:127.0.0.1:8100 <host>, then http://127.0.0.1:8100/setup) and enter it."
        echo "Lost it? ./deploy.sh setup-token --new"
        setup_token || true
        env_unset BC_FIRST_RUN_PENDING
      else
        echo "" >&2
        echo "The admin service did not become healthy, so no setup token is shown. Look at its log" >&2
        echo "(docker compose logs admin), then run ./deploy.sh again or ./deploy.sh setup-token --new." >&2
      fi
    else
      echo "Set PLATFORM_ADMIN_EMAILS in .env, restart the admin service and run ./deploy.sh setup-token for the first sign-in."
      env_unset BC_FIRST_RUN_PENDING
    fi
  fi
}

# Waits (BC_DEPLOY_ADMIN_WAIT_SECONDS, default 120) for the admin service's health check.
wait_admin_healthy() {
  local deadline=$((SECONDS + ${BC_DEPLOY_ADMIN_WAIT_SECONDS:-120})) id status
  while :; do
    id=$("${docker_compose_cmd[@]}" "${compose_files[@]}" ps -q admin 2>/dev/null)
    if [ -n "$id" ]; then
      status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null)
      [ "$status" = healthy ] && return 0
    fi
    [ "$SECONDS" -lt "$deadline" ] || return 1
    sleep 2
  done
}

function dockerdown() {
  "${docker_compose_cmd[@]}" "${compose_files[@]}" down
}

if [ "$user_preference" == down ]; then
  dockerdown
else
  # both, googleform, typeform or nothing: the always-on services plus the optional
  # integrations (services_for, which `./deploy.sh print-services` shows)
  start_list=()
  while IFS= read -r service; do
    start_list+=("$service")
  done < <(services_for "$user_preference")
  dockerup "${start_list[@]}"
fi
