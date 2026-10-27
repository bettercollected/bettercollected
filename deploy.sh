#!/bin/bash

# Everything this script creates (the root .env, the per-service env files, exports,
# backups, scratch files) is owner-only from the first byte, whatever the caller's umask.
umask 077

user_preference="$1"

# The Typeform integration was removed in 4.1: the preferences that asked for it
# (typeform, both) are refused before anything is changed, so a deploy never runs
# with another set of services than the operator asked for.
refuse_typeform_preference() {
  case "$1" in
    typeform|both)
      echo "refused: './deploy.sh $1' is no longer supported: the Typeform integration was removed in 4.1." >&2
      echo "Run ./deploy.sh googleform for the stack with the Google Forms integration, or ./deploy.sh" >&2
      echo "without a preference for the stack without it. Nothing was changed." >&2
      exit 2 ;;
  esac
}
refuse_typeform_preference "$user_preference"
[ "$user_preference" != print-services ] || refuse_typeform_preference "${2:-}"

# The services every deployment starts. `up -d NAME...` starts only the services
# it names (and what they depend on), so each one has to be listed here: the admin
# service (the portal), the jobs worker (the procrastinate `default` queue:
# delete_user and delete_response), the document sandbox (PDF import fails closed
# without it) and the task runner. The optional ones are added further down.
# MongoDB is not among them: since 4.1 it starts only under the legacy-mongo
# profile, for the one-time import of a 4.0 stack's data (legacy_mongo_import).
# Temporal is not among them either: since 4.1 background work runs on the Postgres job
# queue (the jobs worker), and a stack from before 4.1 has its Temporal retired by
# retire_temporal after the roll.
services_to_start=("webapp" "nginx" "backend" "auth" "umami-postgresql" "umami" "admin" "jobs-worker" "document-sandbox" "task-runner")

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
#                            Umami secret
#   the settings store       AUTH_JWT_SECRET, AUTH_AES_HEX_KEY,
#                            AUTH_INTERNAL_NOTIFY_KEY, TEMPORAL_API_KEY, the
#                            response keyset and RESPONDENT_IDENTITY_KEY
#                            (`bootstrap-keys`; nothing printed). An upgrade gets
#                            the last one in the store and in .env (ensure_identity_key)
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
#  - deploy.sh itself reads the SSO values from the root .env to add the Polis
#    overlay (single sign-on stays environment-driven in this release);
#  - the admin service mails sign-in codes with MAIL_* from the environment
#    (until the admin mail settings are set up in the portal).
env_driven_keys=(SSO_ENABLED SSO_POLIS_URL SSO_POLIS_API_KEY SSO_REDIRECT_URI SSO_SAML_AUDIENCE MAIL_USER MAIL_PASSWORD MAIL_SMTP_SERVER MAIL_SMTP_PORT MAIL_SENDER MAIL_STARTTLS MAIL_SSL_TLS MAIL_USE_CREDENTIALS MAIL_VALIDATE_CERTS)

# What the webapp (not a settings-store reader) reads from its environment, beyond the
# few values docker-compose.deployment.yml sets itself. It gets an env file of its own
# (service_env_file) holding only these names, so it receives no Stripe, Google or mail
# secrets, no Mongo root URI and no key. A trailing * is a
# prefix. docs/settings-inventory.md lists the readers; a test compares the two.
webapp_env_keys=(INTERNAL_DOCKER_API_ENDPOINT_HOST API_ENDPOINT_HOST DASHBOARD_DOMAIN FORM_DOMAIN HTTP_SCHEME FORM_PRIVACY_POLICY_URL BASE_DEPLOY_PATH UNSPLASH_ACCESS_KEY GOOGLE_CLIENT_ID GOOGLE_PICKER_API_KEY UMAMI_WEBSITE_ID UMAMI_SCRIPT_URL CUSTOM_DOMAIN_APPLICATION_ID CUSTOM_DOMAIN_ASSERTION_KEYS CUSTOM_DOMAIN_ASSERTION_MODE CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN 'NEXT_PUBLIC_*' 'ELASTIC_APM_*')

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
  # a last line without a newline would swallow the assignment appended below
  if [ -s .env ] && [ -n "$(tail -c 1 .env)" ]; then
    echo >> .env || return 1
  fi
  printf '%s=%s\n' "$1" "$2" >> .env
}

# Creates the env file of a service that is not one of the settings-store readers
# (the webapp), once, from the lines of .env.deployment it reads. It never gets
# anything else, so a bug in the public webapp cannot expose the backend's secrets. An existing file is never
# changed (only its mode is made private). An item ending in * is a name prefix.
service_env_file() {
  local file=$1 line name value item match tmp copied
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
  copied=""
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
      case ", $copied," in *", $name,"*) ;; *) copied="${copied:+$copied, }$name" ;; esac
    done < .env.deployment
  fi
  chmod 600 "$tmp"
  mv "$tmp" "$file"
  # names only, never a value: what the operator sees moved into the service's file
  if [ -n "$copied" ]; then
    echo "Created ${file} from .env.deployment with: ${copied}"
  elif [ ! -f .env.deployment ]; then
    echo "Created ${file}: .env.deployment is missing, so nothing was copied."
  else
    echo "Created ${file}: .env.deployment has none of the settings this service reads."
  fi
}

# Runs `python -m backend.admin ARGS` in a one-off admin container: it has the
# admin database role and the master key and nothing else (never a generated
# key: `bootstrap-keys` refuses an environment that carries one). Extra
# `docker compose run` options go in the admin_cli_opts array.
admin_cli_opts=()
# the command admin_cli runs, as an array a caller can start itself (admin_cli_cmd)
admin_cli_words() {
  admin_cli_cmd=("${docker_compose_cmd[@]}" "${compose_files[@]}" run --rm --no-deps -T "${admin_cli_opts[@]}" admin /api/backend/.venv/bin/python -m backend.admin "$@")
}
admin_cli() {
  admin_cli_words "$@"
  "${admin_cli_cmd[@]}"
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

# The files (names only, joined with "and") in which the operator set a MONGO_URI of
# their own: the root .env and .env.deployment. Empty when neither has a value.
operator_mongo_uri_files() {
  local file out=""
  for file in .env .env.deployment; do
    if file_has "$file" MONGO_URI; then out="${out:+$out and }$file"; fi
  done
  printf '%s' "$out"
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

# ./deploy.sh settings-prune [--apply] [--swap]
# Removes from .env and .env.deployment the settings the store already holds
# with the same value (docs/admin-service.md). Without --apply it only reports.
# --typeform and --no-typeform (from before the Typeform removal) are ignored.
settings_prune() {
  local args=() arg keep=() dir rc stamp
  for arg in "$@"; do
    case "$arg" in
      --typeform|--no-typeform) echo "$arg is ignored: the Typeform integration was removed in 4.1." >&2 ;;
      *) args+=("$arg") ;;
    esac
  done
  local name
  for name in "${env_driven_keys[@]}"; do keep+=(--keep "$name"); done
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

# The services `up` is asked to start for a preference (googleform or none; typeform
# and both are refused above): the always-on list above plus the optional
# integration. One name per line.
services_for() {
  local list=("${services_to_start[@]}")
  case "$1" in
    googleform) list+=("integrations-googleform") ;;
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
  settings-set|settings-clear|settings-restore|settings-history|settings-verify|master-key-fingerprint)
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
# (temporal-postgres-data is Temporal's database of a stack from before 4.1: no longer
# created, kept when it exists, and still the sign of a stack that ran)
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
# A stack from before 4.1 whose data is still in MongoDB: its Mongo volume (or the
# operator's own MONGO_URI, an external Mongo) and no record of a finished import.
# Its data is imported into Postgres once, before the services start
# (legacy_mongo_import); a new stack never has either and never starts Mongo.
# BC_LEGACY_MONGO_IMPORTED in the root .env records the import (any value: a stack
# that already serves everything from Postgres sets it by hand to skip the import).
legacy_mongo_import=false
if ! file_has .env BC_LEGACY_MONGO_IMPORTED \
   && { [ "$existing_stack" = true ] || file_has .env.deployment MONGO_URI; }; then
  legacy_mongo_import=true
fi
if file_has .env BC_LEGACY_MONGO_IMPORTED && file_has .env.deployment MONGO_URI; then
  echo "NOTE: MONGO_URI is set in .env.deployment, but this stack's Mongo data was imported (BC_LEGACY_MONGO_IMPORTED"
  echo "      in .env). The backend checks that Mongo at every start and refuses to start when it cannot reach it:"
  echo "      remove the line (blank it) unless you are going back to 4.0."
fi
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

# The Umami and Mongo databases are internal only, but no longer use the
# well-known password on a new volume. A volume created by an earlier release
# keeps the password it was created with, which is what compose uses when the
# variable is unset (docs/admin-service.md, "Internal credentials and ports").
# Temporal's database (BC_TEMPORAL_DB_PASSWORD) is not generated any more: Temporal
# is not part of the stack since 4.1; an old volume of it is kept as it is.
# Fail closed: these passwords are read only when their volume is created, so
# none is generated while ANY volume of the stack exists (under the project name
# compose uses; a stack under another name was refused above). A missing value then
# means the default of the volume's own release, never a new password that would not
# match what is stored.
if [ "$stack_volumes_present" = true ]; then
  for var in BC_UMAMI_DB_PASSWORD BC_MONGO_ROOT_PASSWORD; do
    # Mongo's only matters to a stack that has its volume (the import from 4.0)
    [ "$var" != BC_MONGO_ROOT_PASSWORD ] || [ "$existing_stack" = true ] || continue
    if ! file_has .env "$var"; then
      echo "NOTE: ${var} is not set and this stack already has volumes: no new one is generated (it would not match them)."
    fi
  done
else
  # No Mongo root password: a new stack never starts MongoDB (4.1). An upgrade
  # keeps the one its volume was created with.
  if ! file_assigns .env BC_UMAMI_DB_PASSWORD; then
    echo "BC_UMAMI_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
    echo "Generated a new BC_UMAMI_DB_PASSWORD in .env (first run)."
  fi
fi

# These passwords go unencoded into database URLs (compose ADMIN_DATABASE_URL, the
# migration URL below, DATABASE_URL of every service, the seeded MONGO_URI): only
# URL-safe characters are accepted, because "@", "/", "#" or "?" would break the URL
# or point it elsewhere. Generated values are hex; this guards values set by hand.
# The Umami and Mongo passwords are checked when set (they may be unset): the other
# (APP_POSTGRES_PASSWORD) is not part of a URL.
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
  echo "NOTE: SSO is on. Polis's egress must not reach private addresses (RFC 1918, link-local,"
  echo "      loopback, the Docker networks): see 'Polis egress' in docs/sso.md for the firewall rule."
fi

chmod 600 .env

# The env file of the webapp (not a settings-store reader): it holds only what the
# webapp reads, copied once from .env.deployment, mode 600. An .env.typeform or
# .env.worker left by an earlier release is no longer used.
service_env_file .env.webapp "${webapp_env_keys[@]}" || exit 1

# The stack's keys (AUTH_JWT_SECRET, AUTH_AES_HEX_KEY, AUTH_INTERNAL_NOTIFY_KEY,
# TEMPORAL_API_KEY, MASTER_ENCRYPTION_KEYSET, RESPONDENT_IDENTITY_KEY) live in the settings store. Runs
# after the database and its migrations are in place and before any service
# starts, because the services refuse to start without them.
function stack_keys() {
  local state rc mongo_uri_files count
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
    # its output is counts, names and the refusal reason: never key material
    boot_out=$(admin_cli bootstrap-keys $([ "$state" = partial ] && echo --fill-missing) 2>&1)
    rc=$?
    printf '%s\n' "$boot_out"
    if [ "$rc" -ne 0 ] && printf '%s\n' "$boot_out" | grep -qE 'stack_has_data|stack_unknown|existing_stack|keys_in_environment'; then
      echo "" >&2
      echo "STOPPED before any service started, and no new keys were stored. This database already holds data" >&2
      echo "(or that could not be established), and a new response keyset could not read what the old one" >&2
      echo "encrypted. Import the keys this stack has used instead: put AUTH_JWT_SECRET, AUTH_AES_HEX_KEY and" >&2
      echo "MASTER_ENCRYPTION_KEYSET in .env, then run ./deploy.sh again (it imports them; see" >&2
      echo "'Upgrading to 4.0' in docs/admin-service.md and ./deploy.sh settings-import --dry-run)." >&2
      return 1
    fi
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

  chmod 600 .env
  # Values the services used to get pinned by the compose file, now plain settings
  seed_setting UMAMI_URL "http://umami:3000" || {
    echo "Could not seed the UMAMI_URL setting." >&2
    return 1
  }
  # The Mongo connection, only for the import of a stack from before 4.1 (a new
  # stack stores none): the root password its volume was created with (generated
  # by 4.0), or the original default for a stack whose files do not carry a
  # MONGO_URI (the template used to ship it). The operator's own MONGO_URI always
  # comes first: when .env or .env.deployment sets one, the local URI below is not
  # generated or stored at all (an external Mongo is never replaced by the stack's
  # own). seed_setting never overwrites a stored value; the import clears it once
  # the data is in Postgres.
  if [ "$legacy_mongo_import" = true ] && [ "$existing_stack" = true ]; then
    mongo_uri_files=$(operator_mongo_uri_files)
    if [ -n "$mongo_uri_files" ]; then
      if file_has .env.deployment MONGO_URI; then
        echo "NOTE: MONGO_URI is set in ${mongo_uri_files}: that value is the operator's own and is kept; the stack's local Mongo URI is not stored."
      else
        # Only the root .env has it, and no service reads the root .env: without a value in
        # .env.deployment or the store the import could not reach that Mongo, and by then
        # the services would already be stopped. Stop here, before anything is stopped.
        count=$(store_versions MONGO_URI) || count=""
        if [ "${count:-0}" -gt 0 ]; then
          echo "NOTE: MONGO_URI is set in .env, and the settings store holds one too: the stored value is used and the stack's local Mongo URI is not stored."
        else
          echo "" >&2
          echo "STOPPED before any service was stopped: MONGO_URI is set in the root .env only. No service reads MONGO_URI from the root" >&2
          echo ".env, so the import of this stack's MongoDB data could not reach that Mongo (and the stack's own Mongo URI is not stored" >&2
          echo "over yours). Move the MONGO_URI line from .env to .env.deployment, then run ./deploy.sh again. Nothing was changed." >&2
          return 1
        fi
      fi
    elif file_has .env BC_MONGO_ROOT_PASSWORD; then
      seed_setting MONGO_URI "mongodb://root:$(dotenv_value .env BC_MONGO_ROOT_PASSWORD)@mongodb:27017" || {
        echo "Could not seed the MONGO_URI setting." >&2
        return 1
      }
    else
      seed_setting MONGO_URI "mongodb://root:root@mongodb:27017" || {
        echo "Could not seed the MONGO_URI setting." >&2
        return 1
      }
    fi
  fi
}

# The respondent identity key (docs/respondent-identity.md): the 4.1 backend refuses to
# start without it. A new stack gets it from `bootstrap-keys`; a stack upgrading from 4.0
# has its other keys already (in the store, or in the files they are imported from), so
# `bootstrap-keys` is not run and nothing else would create it. Where the backend reads
# it from: the shell or the root .env (compose substitutes it into the service's
# environment, which beats .env.deployment: a value only there never arrives, so it is
# copied into .env here, unprinted), else the settings store (an environment value wins).
# When neither has one it is generated here once: into the settings store
# (`settings-import`, which never overwrites) and into the root .env, the way an upgrade
# treats its other keys (the files keep them until `settings-prune`, and
# `SETTINGS_STORE=off` reads only the environment). Never overwritten, never printed
# (identity_pass prints its fingerprint). Refused when
#  - this database already has a key check (a 4.1 backend started with some key) and no
#    key can be found: a new key would not match what that one converted;
#  - .env and the store both hold a key and nothing says they are the same one: the
#    script cannot compare them without printing either. A key it generated itself is
#    recorded as BC_IDENTITY_KEY_SHA256 (a hash of 32 random bytes) and passes;
#    BC_IDENTITY_KEY_SOURCE=env says the .env key is the intended one;
#  - SETTINGS_STORE=off and the key is only in the store.
#
# While the key's file exists, the traps below remove it on every way out. Two rules keep
# them dependable, because bash is easy to catch out here:
#  - no command substitution ($(...), `...`, <(...)) while they are armed. Bash parses
#    each one again when it is evaluated and, if a signal arrives during that parse, runs
#    the trap in the middle of it, where the handler fails to parse
#    ("trap: line 2: unexpected EOF while looking for matching `)'"), is dropped, and the
#    script carries on as if nothing had been sent. What the region needs (the user id,
#    the directory) is computed before it.
#  - the import runs as a background job the script waits for: bash runs a trap only once
#    a foreground command ends, so a signal sent to the script alone would otherwise wait
#    for the import; `wait` returns at once and the handler stops the job.
identity_tmp_dir=""
identity_import_pid=""
identity_cleanup() {
  local waited=0
  if [ -n "$identity_import_pid" ]; then
    kill "$identity_import_pid" 2>/dev/null
    # docker compose stops its container before it exits; a client that ignores the signal is killed
    while kill -0 "$identity_import_pid" 2>/dev/null && [ "$waited" -lt 150 ]; do
      sleep 0.1
      waited=$((waited + 1))
    done
    kill -9 "$identity_import_pid" 2>/dev/null
    wait "$identity_import_pid" 2>/dev/null
    identity_import_pid=""
  fi
  [ -z "$identity_tmp_dir" ] || rm -rf "$identity_tmp_dir"
  identity_tmp_dir=""
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | cut -d' ' -f1
  else
    printf '%s' "$1" | shasum -a 256 | cut -d' ' -f1
  fi
}

ensure_identity_key() {
  local count rows key dir rc uid_gid store_off=false
  case "$(printf '%s' "${SETTINGS_STORE-$(dotenv_value .env SETTINGS_STORE)}" | tr '[:upper:]' '[:lower:]')" in
    off) store_off=true ;;
  esac
  if [ -n "${RESPONDENT_IDENTITY_KEY:-}" ]; then
    echo "RESPONDENT_IDENTITY_KEY is set in the shell: it is used as it is, none is generated."
    return 0
  fi
  if ! file_has .env RESPONDENT_IDENTITY_KEY && file_has .env.deployment RESPONDENT_IDENTITY_KEY; then
    if ! env_put RESPONDENT_IDENTITY_KEY "$(dotenv_value .env.deployment RESPONDENT_IDENTITY_KEY)"; then
      echo "Could not copy RESPONDENT_IDENTITY_KEY from .env.deployment into .env. Nothing was started." >&2
      return 1
    fi
    chmod 600 .env
    echo "RESPONDENT_IDENTITY_KEY was set only in .env.deployment, which does not reach the backend's environment: it is copied into .env (the value is not shown)."
  fi
  count=$(store_versions RESPONDENT_IDENTITY_KEY) || count=""
  if [ -z "$count" ]; then
    echo "Could not read the settings store for RESPONDENT_IDENTITY_KEY." >&2
    return 1
  fi
  if file_has .env RESPONDENT_IDENTITY_KEY; then
    if [ "$count" -gt 0 ] && [ "${BC_IDENTITY_KEY_SOURCE:-}" != env ] \
       && [ "$(dotenv_value .env BC_IDENTITY_KEY_SHA256)" != "$(sha256_of "$(dotenv_value .env RESPONDENT_IDENTITY_KEY)")" ]; then
      echo "" >&2
      echo "STOPPED before any service started: RESPONDENT_IDENTITY_KEY is set in .env and the settings store holds one too, and" >&2
      echo "this script cannot tell whether they are the same key (it never prints either). The backend uses the one in .env." >&2
      echo "If they differ, stored identities would be matched with the wrong key. If the key in .env is the one this stack has" >&2
      echo "used, run BC_IDENTITY_KEY_SOURCE=env ./deploy.sh; otherwise remove it from .env (docs/respondent-identity.md)." >&2
      return 1
    fi
    echo "RESPONDENT_IDENTITY_KEY is set in .env: it is used as it is, none is generated."
    return 0
  fi
  if [ "$count" -gt 0 ]; then
    # a new stack (bootstrap-keys) or an earlier run: the store has it, which is where the backend reads it
    if [ "$store_off" = true ]; then
      echo "" >&2
      echo "STOPPED before any service started: SETTINGS_STORE=off makes the services read environment values only, but" >&2
      echo "RESPONDENT_IDENTITY_KEY is only in the settings store. Put the key this stack has used in .env as" >&2
      echo "RESPONDENT_IDENTITY_KEY=... (or remove SETTINGS_STORE=off) and run ./deploy.sh again (docs/respondent-identity.md)." >&2
      return 1
    fi
    return 0
  fi
  rows=$("${docker_compose_cmd[@]}" "${compose_files[@]}" exec -T app-postgres psql -U bettercollected -d bettercollected -Atc \
    "SELECT count(*) FROM app.respondent_identity_key_check" 2>/dev/null | tr -d '\r' | tail -n 1)
  if [ "$rows" != 0 ]; then
    echo "" >&2
    echo "STOPPED before any service started: this database was already used with a respondent identity key (or that" >&2
    echo "could not be established), but RESPONDENT_IDENTITY_KEY is set nowhere (not in .env or the settings store)." >&2
    echo "A new key would not match the identities stored with the old one, so none is generated." >&2
    echo "Put the key this stack has used in .env as RESPONDENT_IDENTITY_KEY=... and run ./deploy.sh again" >&2
    echo "(docs/respondent-identity.md)." >&2
    return 1
  fi
  key=$(openssl rand -hex 32) || return 1
  uid_gid="$(id -u):$(id -g)"
  dir=$(private_dir) || return 1
  # the scratch directory goes on every way out, a signal included
  identity_tmp_dir=$dir
  trap identity_cleanup EXIT
  trap 'identity_cleanup; exit 130' INT
  trap 'identity_cleanup; exit 143' TERM HUP
  # no command substitution from here to the `trap -` below (see identity_cleanup)
  # a private file in a private directory, removed right after; the value is never an argument
  printf 'RESPONDENT_IDENTITY_KEY=%s\n' "$key" > "$dir/identity.env"
  admin_cli_opts=(--user "$uid_gid" -v "$dir:/work")
  admin_cli_words settings-import --env-file /work/identity.env
  "${admin_cli_cmd[@]}" > "$dir/import.out" 2>&1 &
  identity_import_pid=$!
  wait "$identity_import_pid"
  rc=$?
  identity_import_pid=""
  admin_cli_opts=()
  # what the import said (never the key: the line that names it is replaced), while the directory exists
  if [ "$rc" -ne 0 ]; then
    sed 's/^refused RESPONDENT_IDENTITY_KEY .*/refused RESPONDENT_IDENTITY_KEY (the generated value was not accepted)/' "$dir/import.out" >&2
  fi
  identity_cleanup
  trap - EXIT INT TERM HUP
  if [ "$rc" -ne 0 ]; then
    unset key
    echo "Could not store a new RESPONDENT_IDENTITY_KEY (see above). Nothing was started." >&2
    return 1
  fi
  if ! env_put RESPONDENT_IDENTITY_KEY "$key" || ! env_put BC_IDENTITY_KEY_SHA256 "$(sha256_of "$key")"; then
    unset key
    echo "A new RESPONDENT_IDENTITY_KEY is in the settings store, but .env could not be written. Nothing was started." >&2
    echo "Fix .env (is it writable?) and run ./deploy.sh again: the store's key is kept." >&2
    return 1
  fi
  unset key
  chmod 600 .env
  echo "Generated a new RESPONDENT_IDENTITY_KEY in the settings store and in .env (the value is not shown)."
  echo "  Keep it with the other keys: it cannot be recreated, and a different key makes every stored anonymous"
  echo "  response unfindable by its respondent (docs/respondent-identity.md). Its fingerprint is printed below."
}

# Runs the one-time conversion of the stored respondent identities once the new backend
# is up (`python -m backend.identity_rekey`, docs/respondent-identity.md): the backend
# also does it by itself in the background after it starts, and a one-off here makes
# sure it has run by the time deploy.sh ends, whichever finishes first (a Postgres
# advisory lock lets one process run it at a time; a skipped run, exit 2, is retried).
# Prints counts and the key's fingerprint only. A key that is missing or is not the one
# that converted the stored identities (exit 3, 4) is an error: the backend will not
# serve without it. A pass that is still running elsewhere or leaves values is a warning.
identity_pass() {
  local attempt=0 max out rc report fp left
  max=${BC_DEPLOY_IDENTITY_PASS_TRIES:-12}
  while [ "$attempt" -lt "$max" ]; do
    attempt=$((attempt + 1))
    out=$("${docker_compose_cmd[@]}" "${compose_files[@]}" run --rm --no-deps -T backend /api/backend/.venv/bin/python -m backend.identity_rekey 2>&1)
    rc=$?
    report=$(printf '%s\n' "$out" | grep -E '^\{.*"key_fingerprint"' | tail -n 1)
    fp=$(printf '%s' "$report" | sed -n 's/.*"key_fingerprint": *"\([0-9a-f]*\)".*/\1/p')
    case "$rc" in
      0)
        left=$(printf '%s' "$report" | sed -n 's/.*"remaining": *\({[^}]*}\).*/\1/p')
        echo "Respondent identity key fingerprint: ${fp:-unknown} (write it down with the key backup; a different one later means a different key)."
        echo "Stored respondent identities are all converted (remaining: ${left:-none})."
        return 0 ;;
      3|4)
        printf '%s\n' "$out" | tail -n 5 >&2
        echo "" >&2
        echo "The respondent identity key is missing, unusable or not the one the stored identities were converted with" >&2
        echo "(exit $rc of backend.identity_rekey). The backend will not serve anonymous submissions with it." >&2
        echo "Put the right RESPONDENT_IDENTITY_KEY in .env (docs/respondent-identity.md) and run ./deploy.sh again." >&2
        return 1 ;;
      2) ;;                                         # the backend's own pass holds the lock: wait for it
      *) [ "$attempt" -lt 2 ] || break ;;           # 1: values remain or the run failed: once more
    esac
    sleep "${BC_DEPLOY_RETRY_SLEEP:-5}"
  done
  printf '%s\n' "$out" | tail -n 5 >&2
  echo "WARNING: the respondent identity pass did not finish in this run (exit $rc): the backend runs it in the background" >&2
  echo "         and again a few minutes after each start. Check its log, then run it by hand until it exits 0:" >&2
  echo "         docker compose run --rm --no-deps backend /api/backend/.venv/bin/python -m backend.identity_rekey" >&2
  echo "         Key fingerprint: ${fp:-unknown}." >&2
  return 0
}

# --- Temporal (retired in 4.1) ------------------------------------------------------------
# Since 4.1 background work (account and response deletion, imports, actions) runs on the
# Postgres job queue, and the compose file starts neither Temporal, its database nor the
# Temporal worker. A stack from before 4.1 still has those containers. After the new
# release is up (so nothing new goes to Temporal any more), retire_temporal
#   1. puts every scheduled response deletion on the job queue (the schedules that live
#      in Temporal would otherwise vanish with it): `backend.migrate jobs-sweep`, which
#      is idempotent;
#   2. waits, bounded (BC_TEMPORAL_DRAIN_SECONDS, default 300), until Temporal runs no
#      workflow: an account deletion that is in flight finishes through the new backend's
#      /temporal/* routes, which the old worker still calls with its own copy of the key;
#   3. removes the old containers (worker, Temporal, its database) and keeps the
#      database volume. BC_TEMPORAL_DRAIN=skip removes them without waiting.
# Any failure stops the deploy with the stack running and the old containers untouched;
# running ./deploy.sh again repeats it.

# The job kinds that an operator pinned to Temporal in .env.deployment cannot run in a
# stack without it: refused before anything is changed. (JOBS_BACKEND is an environment-only
# setting, tier T5: the settings store cannot hold it, so the files are the only place to look;
# compose passes nothing else to the services.)
refuse_temporal_job_backend() {
  local line name value found=""
  [ -f .env.deployment ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    name=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}\(JOBS_BACKEND\(__[A-Za-z0-9_]\{1,\}\)\{0,1\}\)[[:space:]]*=.*/\2/p')
    [ -n "$name" ] || continue
    value=$(dotenv_unquote "${line#*=}" | tr '[:upper:]' '[:lower:]')
    [ "$value" = temporal ] && found="${found:+$found, }$name"
  done < .env.deployment
  [ -n "$found" ] || return 0
  echo "refused: .env.deployment routes background jobs to Temporal (${found}). Temporal is not part of the stack since 4.1:" >&2
  echo "the jobs run on the Postgres queue. Remove those lines (or set them to postgres) and run ./deploy.sh again." >&2
  echo "Nothing was changed." >&2
  return 1
}

# The store switches of 4.0 (DB_READ_SOURCE, DB_WRITE_MODE and their __<group> overrides) choose
# between MongoDB and Postgres. The 4.1 compose file does not set them any more, so a value left in
# .env.deployment (which every service reads) reaches the services, and a 4.1 service refuses to
# start on any value but postgres: refused here instead, before anything is changed, with the names
# (never the values). Unset, empty and postgres are fine. A value only in the root .env or the shell
# reaches nothing and is ignored.
refuse_stale_db_flags() {
  local line name value found=""
  [ -f .env.deployment ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    name=$(printf '%s\n' "$line" | sed -nE 's/^[[:space:]]*(export[[:space:]]+)?(DB_(READ_SOURCE|WRITE_MODE)(__[A-Za-z0-9_]+)?)[[:space:]]*=.*/\2/p')
    [ -n "$name" ] || continue
    value=$(dotenv_unquote "${line#*=}" | tr '[:upper:]' '[:lower:]')
    case "$value" in ""|postgres) continue ;; esac
    found="${found:+$found, }$name"
  done < .env.deployment
  [ -n "$found" ] || return 0
  echo "refused: .env.deployment still sets ${found}. Since 4.1 every service is served from Postgres and these settings" >&2
  echo "are retired: a service refuses to start with any value but postgres. Remove those lines (or set them to postgres)" >&2
  echo "and run ./deploy.sh again. Nothing was changed." >&2
  return 1
}

# The container ids of this compose project's service $1, in any state.
project_containers() {
  docker ps -aq --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" --filter "label=com.docker.compose.service=$1" 2>/dev/null
}

# How many workflows Temporal (container $1) still runs; -1 when it cannot be asked.
# Schedules are system workflows and not counted: they were moved to the queue.
temporal_running() {
  local out
  local ns
  # the namespace the old stack used: the backend's TEMPORAL_NAMESPACE, the worker's NAMESPACE (.env.worker, else .env.deployment)
  ns=$(dotenv_value .env.deployment TEMPORAL_NAMESPACE)
  [ -n "$ns" ] || ns=$(dotenv_value .env.worker NAMESPACE)
  [ -n "$ns" ] || ns=$(dotenv_value .env.deployment NAMESPACE)
  out=$(docker exec "$1" temporal workflow list --address temporal:7233 --namespace "${ns:-default}" --query 'ExecutionStatus="Running"' --limit 200 2>&1) || { echo -1; return 0; }
  printf '%s\n' "$out" | grep -E '^[[:space:]]*Running[[:space:]]' | grep -vc 'temporal-sys-' || true
}

retire_temporal() {
  local tid name out rc scheduled deadline running id
  tid=$(project_containers temporal | head -n 1)
  [ -n "$tid" ] || return 0   # a new stack, or Temporal was retired by an earlier run
  name=$(docker inspect -f '{{.Name}}' "$tid" 2>/dev/null | tr -d '/')
  echo ""
  echo "TEMPORAL: this stack still runs Temporal, which is not part of it since 4.1 (background work runs on the Postgres"
  echo "job queue). Moving what it holds onto the queue, then removing it; its database volume is kept."
  # The sweep reads Postgres only: it needs no MONGO_URI (an imported stack has none).
  out=$("${docker_compose_cmd[@]}" "${compose_files[@]}" run --rm --no-deps -T backend /api/backend/.venv/bin/python -m backend.migrate jobs-sweep --backend postgres 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '%s\n' "$out" | tail -n 8 >&2
    echo "" >&2
    echo "STOPPED: the scheduled response deletions could not be put on the job queue (see above). The stack runs 4.1; the" >&2
    echo "old Temporal containers were left in place. Fix the cause and run ./deploy.sh again." >&2
    return 1
  fi
  scheduled=$(printf '%s\n' "$out" | sed -n 's/^[[:space:]]*"scheduled": *\([0-9][0-9]*\).*/\1/p' | tail -n 1)
  echo "Scheduled response deletions on the job queue: ${scheduled:-unknown} (already queued ones are not repeated)."
  if [ "${BC_TEMPORAL_DRAIN:-}" = skip ]; then
    echo "NOTE: BC_TEMPORAL_DRAIN=skip: not waiting for workflows that are still running in Temporal."
  elif [ "$(docker inspect -f '{{.State.Running}}' "$tid" 2>/dev/null)" != true ]; then
    echo "Temporal is not running: nothing to wait for."
  else
    deadline=$((SECONDS + ${BC_TEMPORAL_DRAIN_SECONDS:-300}))
    while :; do
      running=$(temporal_running "$tid")
      [ "$running" = 0 ] && break
      if [ "$SECONDS" -ge "$deadline" ]; then
        echo "" >&2
        if [ "$running" = -1 ]; then
          echo "STOPPED: Temporal could not be asked which workflows it still runs." >&2
        else
          echo "STOPPED: Temporal still runs ${running} workflow(s) after ${BC_TEMPORAL_DRAIN_SECONDS:-300} s." >&2
        fi
        echo "The stack runs 4.1 and the old Temporal containers were left in place. List them with:" >&2
        echo "  docker exec ${name} temporal workflow list --address temporal:7233 --query 'ExecutionStatus=\"Running\"'" >&2
        echo "Run ./deploy.sh again once they have finished; to remove Temporal without waiting (what is still running is" >&2
        echo "lost), run BC_TEMPORAL_DRAIN=skip ./deploy.sh." >&2
        return 1
      fi
      echo "Waiting for Temporal: ${running} workflow(s) still running ..."
      sleep "${BC_TEMPORAL_DRAIN_POLL:-5}"
    done
    echo "Temporal runs no workflow."
  fi
  # the worker first, then Temporal, then its database (the one holding the temporal volume)
  for id in $(project_containers worker) "$tid"; do
    docker rm -f "$id" >/dev/null 2>&1 || echo "WARNING: could not remove the container ${id:0:12}; remove it by hand." >&2
  done
  for id in $(project_containers postgresql); do
    if docker inspect -f '{{range .Mounts}}{{.Name}} {{end}}' "$id" 2>/dev/null | grep -q '_temporal-postgres-data'; then
      docker rm -f "$id" >/dev/null 2>&1 || echo "WARNING: could not remove the container ${id:0:12}; remove it by hand." >&2
    fi
  done
  echo "Removed the Temporal, Temporal worker and Temporal database containers."
  echo "The volume ${compose_project}_temporal-postgres-data is kept (rolling back to 4.0 uses it); remove it with 'docker volume rm' once 4.1 has run well."
}

# A value the webapp reads: from its own env file (.env.webapp, what it gets), else
# from .env.deployment (where .env.webapp was copied from).
webapp_value() {
  local found
  found=$(dotenv_value .env.webapp "$1")
  [ -n "$found" ] || found=$(dotenv_value .env.deployment "$1")
  printf '%s' "$found"
}

# The web app's public origins, one per line: HTTP_SCHEME (default https, the
# webapp's own default) with DASHBOARD_DOMAIN and FORM_DOMAIN. Nothing when neither
# domain is set (a local stack: the compose file publishes the webapp on localhost).
refdata_origins() {
  local scheme domain var
  scheme=$(webapp_value HTTP_SCHEME)
  scheme=${scheme%%:*}
  [ -n "$scheme" ] || scheme=https
  for var in DASHBOARD_DOMAIN FORM_DOMAIN; do
    domain=$(webapp_value "$var")
    domain=${domain#*://}
    domain=${domain%%/*}
    if [ -n "$domain" ]; then
      printf '%s://%s\n' "$scheme" "$domain"
    fi
  done
}

# The reference data a new stack needs (the allowed origins, the Google Forms
# provider) is served from Postgres since 4.1: seed it there with the stack's own
# origins, never the localhost ones of a local trial. Each table is seeded only while
# it is empty. A new stack has no MONGO_URI, so the backend's check for reference
# data still only in Mongo never contacts one. $1: whether Google Forms is enabled.
seed_refdata() {
  local origin args=()
  while IFS= read -r origin; do
    [ -n "$origin" ] && args+=(--origin "$origin")
  done < <(refdata_origins)
  if [ "${#args[@]}" -eq 0 ]; then
    echo "NOTE: DASHBOARD_DOMAIN and FORM_DOMAIN are not set: the allowed origins are the local web app ports"
    echo "      (or the origin of API_CLIENT_URL, when that is not a local address)."
  else
    echo "Allowed origins of this stack: $(printf '%s ' "${args[@]}" | sed 's/--origin //g')"
  fi
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps backend \
    /api/backend/.venv/bin/python -m backend.seed_refdata "${args[@]}" --google-enabled "$1"
}

# --- the import of a stack from before 4.1 (MongoDB) -----------------------------------
# docs/postgres-cutover-runbook.md, "Upgrading to 4.1". Since 4.1 every service is
# served from Postgres and MongoDB is not part of the stack. A stack whose data is
# still in Mongo has it imported once, here, before any service of this release
# starts: for auth, the Google integration and the backend, in that order (the
# runbook's), `preflight`, `backfill` and `verify` of each service's own migration
# CLI, in a one-off container of the new image. Any failure stops the deploy with
# the counts, before a service starts; nothing is deleted. On success the
# MONGO_URI is cleared (the store keeps its versions, `settings-restore` brings it
# back), BC_LEGACY_MONGO_IMPORTED is recorded in the root .env, and MongoDB is
# stopped and its container removed. Its volume is always kept.

# compose with the legacy-mongo profile: the only way MongoDB starts. Used for MongoDB's
# own container only: a command under the profile creates every volume of the profile's
# services, and a stack without a Mongo volume must not get an (empty) one.
legacy_dc() {
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" --profile legacy-mongo "$@"
}

legacy_run() {
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" run --rm --no-deps -T "$@"
}

# legacy_migrate auth|google|backend ARGS: the service's migration CLI in a one-off
# container (the service's database role and settings, MONGO_URI included)
legacy_migrate() {
  local name=$1
  shift
  case "$name" in
    auth) legacy_run auth /api/auth/.venv/bin/python -m auth.migrate "$@" ;;
    google) legacy_run integrations-googleform python -m googleform.migrate "$@" ;;
    backend) legacy_run backend /api/backend/.venv/bin/python -m backend.migrate "$@" ;;
  esac
}

# The collections a preflight or verify report (JSON on stdin) shows a problem
# for, one line each, counts only (never the sample ids).
legacy_problems() {
  awk '
    function flush(   k, line, bad) {
      if (name == "") return
      line = "  " name ": mongo=" (("mongo" in c) ? c["mongo"] : "?") " postgres=" (("postgres" in c) ? c["postgres"] : "?")
      for (k in c) if (k != "mongo" && k != "postgres" && c[k] > 0) { line = line " " k "=" c[k]; bad = 1 }
      if (bad) print line
      delete c
      name = ""
    }
    /"collection":/ { flush(); v = $2; gsub(/[",]/, "", v); name = v; next }
    /"(mongo|postgres|missing_in_postgres|missing_in_mongo|mismatched|drifted|tombstoned|invalid_ids|duplicates)":/ {
      k = $1; gsub(/[":]/, "", k); v = $2; gsub(/,/, "", v)
      if (v ~ /^[0-9]+$/) c[k] = v + 0
    }
    END { flush() }
  '
}

# MongoDB stopped and its container removed (a stopped container with `restart:
# always` would come back with the Docker daemon). The volume is kept.
legacy_mongo_stop() {
  [ "$existing_stack" = true ] || return 0
  legacy_dc rm -s -f mongodb mongo-seed >/dev/null 2>&1 \
    || echo "WARNING: could not stop MongoDB; stop it with: docker compose -f docker-compose.deployment.yml --profile legacy-mongo rm -s -f mongodb" >&2
}

legacy_mongo_failed() { # legacy_mongo_failed <what> <log>
  legacy_mongo_stop
  echo "" >&2
  echo "STOPPED before any service of this release started: $1. Nothing was deleted: the Mongo data and its" >&2
  echo "volume are kept, and the services stay stopped. Full output (counts and ids, no values): $2." >&2
  echo "Fix the cause (docs/postgres-cutover-runbook.md, 'Upgrading to 4.1') and run ./deploy.sh again: the import" >&2
  echo "resumes where it stopped. Or go back to 4.0: check out the 4.0 release and run its ./deploy.sh." >&2
  return 1
}

legacy_mongo_import() { # legacy_mongo_import <google forms enabled: true|false>
  local stamp log name step out rc count dir
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  log="legacy-mongo-import.${stamp}.log"
  ( umask 077; : > "$log" )
  echo ""
  echo "UPGRADE TO 4.1: this stack's data is still in MongoDB. It is imported into Postgres now, before the"
  echo "services start (docs/postgres-cutover-runbook.md, 'Upgrading to 4.1'). The services stay stopped until"
  echo "it is done. The Mongo volume is kept."
  # nothing may write Mongo between the copy and the check: the services of the
  # running release are stopped first (they start again, from the new images, below)
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" stop backend jobs-worker auth integrations-googleform task-runner >/dev/null 2>&1
  if [ "$existing_stack" = true ]; then
    legacy_dc up -d --wait mongodb || { legacy_mongo_failed "MongoDB did not start" "$log"; return 1; }
  fi
  # the Google integration's schema, when this stack does not run it: its Mongo
  # data (credentials) is imported all the same
  if [ "$1" != true ]; then
    legacy_run integrations-googleform alembic -c /api/integrations/google/alembic.ini upgrade head >>"$log" 2>&1 \
      || { legacy_mongo_failed "the Google integration's schema could not be migrated" "$log"; return 1; }
  fi
  for name in auth google backend; do
    for step in preflight backfill verify; do
      echo "Import: $name $step ..."
      out=$(legacy_migrate "$name" "$step" 2>>"$log")
      rc=$?
      printf '== %s %s (exit %s)\n%s\n' "$name" "$step" "$rc" "$out" >> "$log"
      [ "$rc" -eq 0 ] && continue
      case "$step" in
        preflight)
          echo "The $name preflight found documents the import cannot take (invalid ids, duplicate unique keys):" >&2
          printf '%s\n' "$out" | legacy_problems >&2 ;;
        backfill)
          echo "The $name backfill stopped with an error. Per collection:" >&2
          legacy_migrate "$name" status 2>>"$log" | grep -E '^  ' >&2 ;;
        verify)
          echo "The $name verify found differences between MongoDB and Postgres:" >&2
          printf '%s\n' "$out" | legacy_problems >&2 ;;
      esac
      legacy_mongo_failed "the $name $step failed (exit $rc)" "$log"
      return 1
    done
  done
  echo "Imported and verified. Per collection (MongoDB, Postgres):"
  for name in auth google backend; do
    legacy_migrate "$name" status 2>>"$log" | grep -E '^  ' | sed "s/^/$name /"
  done
  # The services no longer read MongoDB. A MONGO_URI left in the store or in
  # .env.deployment would make the backend check Mongo at every start (and refuse
  # it once Mongo is stopped): cleared in the store (its versions are kept), and
  # blanked in .env.deployment (a private backup of the file is kept).
  count=$(store_versions MONGO_URI) || count=""
  if [ "${count:-0}" -gt 0 ]; then
    out=$(admin_cli settings-clear MONGO_URI --confirm MONGO_URI --yes 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ] && ! printf '%s\n' "$out" | grep -q 'not_set'; then
      printf '%s\n' "$out" >&2
      legacy_mongo_failed "the MONGO_URI setting could not be cleared" "$log"
      return 1
    fi
  fi
  if file_assigns .env.deployment MONGO_URI; then
    cp -p .env.deployment ".env.deployment.pre-4.1.${stamp}" && chmod 600 ".env.deployment.pre-4.1.${stamp}"
    dir=$(private_dir) || return 1
    sed -E 's/^([[:space:]]*(export[[:space:]]+)?MONGO_URI[[:space:]]*=).*/\1/' .env.deployment > "$dir/env" \
      && cat "$dir/env" > .env.deployment
    rm -rf "$dir"
    echo "Blanked MONGO_URI in .env.deployment (backup: .env.deployment.pre-4.1.${stamp}, holds the old value)."
  fi
  env_put BC_LEGACY_MONGO_IMPORTED "$stamp"
  chmod 600 .env
  legacy_mongo_stop
  echo "MongoDB is stopped and its container removed. Its volume (${compose_project}_mongo-data) is kept: keep it,"
  echo "and an encrypted dump of it, until 4.1 has run well for a while; never delete it in the same step."
  if file_has .env TASK_RUNNER_MONGO_URI; then
    echo "NOTE: TASK_RUNNER_MONGO_URI is still set in .env. MongoDB is stopped: remove it (and TASK_RUNNER_MONGO_DB)."
  fi
  echo ""
}

fresh_install=false

# Common docker function
function dockerup() {
  googleform_flag=false

  # Loop through the arguments in "$@"
  for arg in "$@"; do
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
  "${docker_compose_cmd[@]}" -f "docker-compose.deployment.yml" pull -q backend auth webapp \
    $([ "$googleform_flag" = true ] && echo integrations-googleform) \
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
  # the respondent identity key: a stack upgrading from 4.0 has none yet
  ensure_identity_key || exit 1

  # A stack from before 4.1: its Mongo data goes into Postgres first, verified,
  # before any service of this release starts. Stops the deploy on any failure.
  if [ "$legacy_mongo_import" = true ]; then
    legacy_mongo_import "$googleform_flag" || exit 1
  fi

  # A new stack's reference data, before the backend first starts. Only while the
  # first run is pending (set when a new stack's keys are generated, kept until the
  # first-run notice is shown): an upgraded stack's reference data is imported from
  # Mongo instead (docs/postgres-cutover-runbook.md), never seeded over.
  if file_has .env BC_FIRST_RUN_PENDING; then
    seed_refdata "$googleform_flag" || {
      echo "Seeding the reference data into Postgres failed (see above). Fix the cause and run ./deploy.sh again." >&2
      exit 1
    }
  fi

  # Typeform leftovers from before 4.1 (no longer in the compose file): say so, never remove them.
  # Only this compose project's container counts: another stack on the host is not ours to report.
  if [ -n "$(docker ps -aq --filter label=com.docker.compose.project="$COMPOSE_PROJECT_NAME" --filter label=com.docker.compose.service=integrations-typeform 2>/dev/null)" ]; then
    echo "WARNING: an integrations-typeform container from an earlier release still exists. Typeform was removed in 4.1; remove that container when you no longer need it." >&2
  fi
  if [ -f .env.worker ]; then
    echo "NOTE: .env.worker from an earlier release still exists. The Temporal worker is not part of the stack any more, so nothing reads it" >&2
    echo "      (nor the worker's API_KEY and AES_HEX_KEY copies in .env); keep them only if you may roll back to 4.0." >&2
  fi
  if [ -f .env.typeform ]; then
    echo "WARNING: .env.typeform from an earlier release still exists. It holds the Typeform client secret and a database URI and is no longer used: delete it (rm .env.typeform)." >&2
  fi
  "${docker_compose_cmd[@]}" "${compose_files[@]}" up --build -d "$@" || {
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

  # the stored respondent identities, converted once the 4.1 backend is up (and the key's
  # fingerprint, to write down); fatal only for a key that is wrong, never for a slow pass
  identity_pass || exit 1

  # a stack from before 4.1 still runs Temporal: its work goes to the queue, then it is removed
  retire_temporal || exit 1

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
  # googleform or nothing: the always-on services plus the optional
  # integrations (services_for, which `./deploy.sh print-services` shows)
  start_list=()
  while IFS= read -r service; do
    start_list+=("$service")
  done < <(services_for "$user_preference")
  refuse_temporal_job_backend || exit 1
  refuse_stale_db_flags || exit 1
  dockerup "${start_list[@]}"
fi
