#!/usr/bin/env bash
# Upgrade acceptance by IMAGE SWAP, against REAL containers: the way production upgrades.
# Production never runs deploy.sh. It changes the image tags in its stack, restarts, and the services
# migrate themselves (DB_AUTO_MIGRATE=true). This check does the same:
#
#   (1) old     a stack of the previous release (V4 default v4.1.2): its own docker-compose.deployment.yml
#               (git show <tag>), its published images, installed with ITS deploy.sh (first install only),
#               then seeded: a workspace and a user, a form with six questions and three responses (through
#               the API), one waiting and one finished 4.1-style action job that carries its payload
#   (2) swap    only the image: lines of backend, admin, task-runner, document-sandbox, jobs-worker, auth and
#               webapp change (to the candidate), DB_AUTO_MIGRATE=true on every service, the new switches and
#               MAIL_* added the way a stack edit adds them, then `docker compose up -d`. No deploy.sh.
#   (3) checks  a migrations   b scrub of the old action jobs   c old data reads as before   d jobs worker
#               queues   e webhooks (the SSRF guard)   f drafts   g email action and respondent copy
#               h the actions executor role's restriction: recorded after the bare swap (INFO), then in force after
#                 the documented step (ensure-jobs-exec-role.sh as superuser, python -m backend.jobs.schema)
#
#   scripts/upgrade-image-swap-check.sh [--keep]
#
# Safe on a developer machine, like v4-compose-check.sh: its own compose project (bcswap<pid>), host ports
# from 8100 up that are free and bound to 127.0.0.1, new secrets, a mail sink (mailpit), and removal of every
# container, network, volume and image it created when it exits. Nothing else is touched.
#
# Parameters (environment):
#   SWAP_CHECK_OLD_TAG=v4.1.2       the release the stack starts on (files from `git show <tag>:...`, images
#                                   bettercollected/{backend,auth,webapp}:<tag>)
#   SWAP_CHECK_CANDIDATE=build      (default) images built from this checkout: bc-swapcheck-{backend,auth,
#                                   webapp}:local. Or a published tag, e.g. v4.2.0: bettercollected/*:<tag>
#   SWAP_CHECK_WEBAPP=build         (default with =build) | an image name for the webapp only
#   SWAP_CHECK_REUSE_IMAGES=1       use bc-swapcheck-*:local images that already exist instead of building
#   SWAP_CHECK_KEEP_IMAGES=1        do not remove the images this run built or pulled
#   SWAP_CHECK_MIN_FREE_MB=2500     free disk space below which the run does not start
# --keep leaves the stack running (the work directory is printed).
#
# Needs: bash, docker (compose v2), curl, openssl, script (util-linux), uv, git (for the old tag).
# Run it through .local/coord/heavy.sh on a shared machine. About 10 to 15 minutes with images in place.
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 1
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"

keep=0
while [ $# -gt 0 ]; do
  case "$1" in
    --keep) keep=1; shift ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done

for tool in docker curl openssl script uv git; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing tool: $tool" >&2; exit 2; }
done
docker compose version >/dev/null 2>&1 || { echo "docker compose v2 is required" >&2; exit 2; }

old_tag="${SWAP_CHECK_OLD_TAG:-v4.1.2}"
candidate="${SWAP_CHECK_CANDIDATE:-build}"
min_free_mb="${SWAP_CHECK_MIN_FREE_MB:-2500}"
git -C "$root" rev-parse -q --verify "refs/tags/$old_tag" >/dev/null || { echo "the tag $old_tag is not in this checkout" >&2; exit 2; }
work="$(mktemp -d)"
chmod 700 "$work"
pass=0
fail=0
notcovered=0
run_id="$$"
mail_container="bcswapmail$run_id"
recv_container="bcswaprecv$run_id"
project="bcswap$run_id"
S_DIR="$work/$project"
bg_pids=()
built_images=()
pulled_images=()
images_before="$(docker image ls --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | sort -u)"
started=$SECONDS
subnets_file="$work/handed-out-subnets"
RESULTS=()

# --- reporting ----------------------------------------------------------------------------------------
stamp() { printf '[%4ds]' $((SECONDS - started)); }
ok() { pass=$((pass + 1)); RESULTS+=("PASS $(stamp) $1"); echo "  PASS  $(stamp) $1"; }
bad() { fail=$((fail + 1)); RESULTS+=("FAIL $(stamp) $1"); echo "  FAIL  $(stamp) $1"; }
nc() { notcovered=$((notcovered + 1)); RESULTS+=("NOT COVERED $(stamp) $1"); echo "  NOT COVERED  $(stamp) $1"; }
check() { local desc="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi; }
expect() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$2', got '$3')"; fi; }
section() { echo "== $* ($((SECONDS - started)) s)"; }
absorb() { # a client's PASS/FAIL/NOTCOVERED lines count here; INFO and IDS lines are left to the caller
  local line
  while IFS= read -r line; do
    case "$line" in
      "PASS "*) pass=$((pass + 1)); RESULTS+=("PASS $(stamp) ${line#PASS }"); echo "  PASS  $(stamp) ${line#PASS }" ;;
      "FAIL "*) fail=$((fail + 1)); RESULTS+=("FAIL $(stamp) ${line#FAIL }"); echo "  FAIL  $(stamp) ${line#FAIL }" ;;
      "NOTCOVERED "*) notcovered=$((notcovered + 1)); RESULTS+=("NOT COVERED $(stamp) ${line#NOTCOVERED }"); echo "  NOT COVERED  $(stamp) ${line#NOTCOVERED }" ;;
      "INFO "*) echo "        ${line#INFO }" ;;
      "IDS "*) echo "$line" > "$work/ids" ;;
      *) echo "        $line" ;;
    esac
  done
}

# --- clean up everything this run created ---------------------------------------------------------------
cleanup() {
  local ids
  for pid in "${bg_pids[@]:-}"; do [ -n "$pid" ] && kill "$pid" >/dev/null 2>&1; done
  docker network ls -q --filter "name=^bcswapprobe${run_id}x" 2>/dev/null | xargs -r docker network rm >/dev/null 2>&1
  if [ "$keep" = 1 ]; then
    echo "--keep: project $project left running (work directory $work, mail sink $mail_container)"
    return
  fi
  docker rm -f -v "$mail_container" "$recv_container" >/dev/null 2>&1   # on the stack's network: first
  ids="$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
  # shellcheck disable=SC2086
  [ -z "$ids" ] || docker rm -f -v $ids >/dev/null 2>&1
  ids="$(docker network ls -q --filter "label=com.docker.compose.project=$project")"
  # shellcheck disable=SC2086
  [ -z "$ids" ] || docker network rm $ids >/dev/null 2>&1
  ids="$(docker volume ls -q --filter "label=com.docker.compose.project=$project")"
  # shellcheck disable=SC2086
  [ -z "$ids" ] || docker volume rm -f $ids >/dev/null 2>&1
  if [ "${SWAP_CHECK_KEEP_IMAGES:-0}" != 1 ]; then
    local image
    for image in "${built_images[@]:-}" "${pulled_images[@]:-}"; do
      [ -n "$image" ] || continue
      case "$images_before" in *"$image"*) continue ;; esac   # it was there before this run
      docker rmi "$image" >/dev/null 2>&1
    done
  fi
  rm -rf "$work"
}
trap cleanup EXIT
trap 'echo "interrupted"; exit 130' INT TERM

# --- helpers (as in v4-compose-check.sh) -------------------------------------------------------------------
used_ports=()
free_port() {
  local p
  for _ in $(seq 1 200); do
    p=$((8100 + RANDOM % 1900))
    case " ${used_ports[*]:-} " in *" $p "*) continue ;; esac
    if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then continue; fi
    if docker ps --format '{{.Ports}}' | grep -q ":$p->"; then continue; fi
    used_ports+=("$p")
    echo "$p"
    return
  done
  echo "no free port found" >&2
  return 1
}

# A /29 inside 172.30.0.0/16 that overlaps nothing (see v4-compose-check.sh), proven by creating it once.
free_subnet() {
  local candidate_net probe
  : >> "$subnets_file"
  for _ in $(seq 1 30); do
    candidate_net="$( {
        docker network ls -q | xargs -r docker network inspect --format '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}' 2>/dev/null
        ip -4 route show 2>/dev/null | awk '{print $1}'
        cat "$subnets_file"
      } | uv run --no-project python -I -c '
import ipaddress, random, sys
taken = []
for line in sys.stdin:
    line = line.strip()
    if not line or line == "default":
        continue
    try:
        net = ipaddress.ip_network(line, strict=False)
    except ValueError:
        continue
    if net.version == 4:
        taken.append(net)
third = list(range(100, 250))
random.shuffle(third)
for t in third:
    cand = ipaddress.ip_network(f"172.30.{t}.0/29")
    if not any(cand.overlaps(n) for n in taken):
        print(cand)
        sys.exit(0)
sys.exit(1)
')" || { echo "no free subnet found" >&2; return 1; }
    echo "$candidate_net" >> "$subnets_file"
    probe="bcswapprobe${run_id}x$RANDOM"
    if docker network create --subnet "$candidate_net" "$probe" >/dev/null 2>&1; then
      docker network rm "$probe" >/dev/null 2>&1
      echo "$candidate_net"
      return 0
    fi
  done
  echo "no free subnet found" >&2
  return 1
}

enough_disk() { # enough_disk <what>
  local free_mb docker_free
  free_mb="$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2 {print $4}')"
  docker_free="$(df -Pm /var/lib/docker 2>/dev/null | awk 'NR==2 {print $4}')"
  [ -n "$docker_free" ] && [ "$docker_free" -lt "$free_mb" ] && free_mb="$docker_free"
  if [ "$free_mb" -lt "$min_free_mb" ]; then
    echo "not enough free disk ($free_mb MB < $min_free_mb MB) to start: $1" >&2
    return 1
  fi
}

# the shell's own variables would win over a .env file: run everything hermetically
HERM=(env -i PATH="$PATH" HOME="${HOME:-/tmp}" USER="${USER:-}" LANG="${LANG:-C.UTF-8}" TERM="${TERM:-xterm}")
[ -z "${DOCKER_HOST:-}" ] || HERM+=(DOCKER_HOST="$DOCKER_HOST")
[ -z "${DOCKER_CONFIG:-}" ] || HERM+=(DOCKER_CONFIG="$DOCKER_CONFIG")
[ -z "${DOCKER_CONTEXT:-}" ] || HERM+=(DOCKER_CONTEXT="$DOCKER_CONTEXT")
[ -z "${XDG_RUNTIME_DIR:-}" ] || HERM+=(XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR")
hermetic() { "${HERM[@]}" "$@"; }

http_code() { curl -s -o /dev/null -m 6 -w '%{http_code}' "$@" 2>/dev/null; }
client() { uv run --no-project --quiet python -I "$root/scripts/upgrade_swap_check_client.py" "$@"; }

# extra compose files of the stack (-f ...), as a stack edit adds them
COMPOSE_EXTRA=()
dc() { (cd "$S_DIR" && hermetic docker compose -f docker-compose.deployment.yml "${COMPOSE_EXTRA[@]}" "$@" 2> >(grep -v 'level=warning' >&2)); }
psql_app() { dc exec -T app-postgres psql -U bettercollected -d bettercollected -Atq -c "$1" 2>/dev/null | tr -d '\r'; }

# Runs the OLD release's ./deploy.sh on a pseudo-terminal (it shows the setup token on a terminal only).
run_deploy() { # run_deploy <out>
  ( cd "$S_DIR" && timeout 2400 "${HERM[@]}" script -qefc "./deploy.sh" /dev/null < /dev/null ) > "$1" 2>&1
  return $?
}

wait_state() { # wait_state <service> <healthy|running> <seconds>
  local id st deadline=$((SECONDS + $3))
  while [ "$SECONDS" -lt "$deadline" ]; do
    id="$(dc ps -q "$1" 2>/dev/null | head -n 1)"
    if [ -n "$id" ]; then
      st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null)"
      case "$2:$st" in healthy:healthy|running:running|running:healthy) return 0 ;; esac
    fi
    sleep 3
  done
  return 1
}
wait_stack() { wait_state backend healthy "$1" && wait_state auth healthy "$1"; }

show_failures() { # the last log lines of every container that is not up (a diagnosis aid)
  local id name st
  for id in $(dc ps -aq 2>/dev/null); do
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")"
    case "$st" in healthy|running) continue ;; esac
    [ "$(docker inspect -f '{{.State.ExitCode}}' "$id")" = 0 ] && [ "$st" = exited ] && continue
    name="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id")"
    echo "        --- $name ($st), last log lines"
    docker logs --tail 15 "$id" 2>&1 | cut -c1-220 | sed 's/^/        /'
  done
}

service_state() {
  local id name st
  for id in $(dc ps -aq 2>/dev/null); do
    name="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id")"
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")"
    echo "$name=$st"
  done | sort
}
settle_services() { # wait, bounded, while a container is still "starting"
  local deadline=$((SECONDS + $1))
  while service_state | grep -q '=starting$'; do
    [ "$SECONDS" -lt "$deadline" ] && sleep 5 || return 1
  done
}

wait_log() { # wait_log <service> <fixed text> <seconds>
  local deadline=$((SECONDS + $3))
  while [ "$SECONDS" -lt "$deadline" ]; do
    dc logs --no-log-prefix "$1" 2>&1 | grep -qF -- "$2" && return 0
    sleep 3
  done
  return 1
}
logs_of() { dc logs --no-log-prefix "$1" 2>&1 | tr -d '\r'; }

# --- images ----------------------------------------------------------------------------------------------
img_backend="bc-swapcheck-backend:local"
img_auth="bc-swapcheck-auth:local"
img_webapp="bc-swapcheck-webapp:local"
img_umami="ghcr.io/umami-software/umami:postgresql-latest"
case "$candidate" in
  build) ;;
  *) img_backend="bettercollected/backend:$candidate"; img_auth="bettercollected/auth:$candidate"
     img_webapp="bettercollected/webapp:$candidate" ;;
esac
[ -z "${SWAP_CHECK_WEBAPP:-}" ] || img_webapp="$SWAP_CHECK_WEBAPP"   # the webapp alone from another image

build_image() { # build_image <tag> <dockerfile>
  if [ "${SWAP_CHECK_REUSE_IMAGES:-0}" = 1 ] && docker image inspect "$1" >/dev/null 2>&1; then
    echo "  reusing $1"
    return 0
  fi
  echo "  building $1 from $2 (a few minutes)"
  enough_disk "build $1" || return 1
  docker build -q -t "$1" -f "$2" "$root" >/dev/null || { echo "build of $1 failed" >&2; return 1; }
  built_images+=("$1")
}
pull_image() { # pull_image <image> (kept if it was there before)
  docker image inspect "$1" >/dev/null 2>&1 && return 0
  enough_disk "pull $1" || return 1
  echo "  pulling $1"
  docker pull -q "$1" >/dev/null || { echo "could not pull $1" >&2; return 1; }
  pulled_images+=("$1")
}

prepare_images() {
  section "images (candidate: ${candidate}, from $(git -C "$root" rev-parse --short HEAD))"
  if [ "$candidate" = build ]; then
    build_image "$img_backend" backend/Dockerfile || exit 2
    build_image "$img_auth" auth/Dockerfile || exit 2
    case "$img_webapp" in
      bc-swapcheck-webapp:local) build_image "$img_webapp" webapp/Dockerfile || exit 2 ;;
      *) pull_image "$img_webapp" || exit 2 ;;
    esac
  else
    for i in "$img_backend" "$img_auth" "$img_webapp"; do pull_image "$i" || exit 2; done
  fi
  for i in "bettercollected/backend:$old_tag" "bettercollected/auth:$old_tag" "bettercollected/webapp:$old_tag" \
      "postgres:15-alpine" "postgres:16-alpine" "nginx:1.28-alpine" axllent/mailpit:latest; do
    pull_image "$i" || exit 2
  done
  # Umami's registry (ghcr.io) refuses anonymous pulls on some hosts: fall back to a local copy
  if ! docker image inspect "$img_umami" >/dev/null 2>&1; then
    if timeout 400 docker pull -q "$img_umami" >/dev/null 2>&1; then
      pulled_images+=("$img_umami")
    else
      local local_umami
      local_umami="$(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep '^ghcr.io/umami-software/umami:' | grep -v none | head -n 1)"
      if [ -n "$local_umami" ]; then
        echo "  umami: postgresql-latest could not be pulled, using the local $local_umami"
        img_umami="$local_umami"
      fi
    fi
  fi
}

mail_port=""
mail_start() {
  mail_port="$(free_port)" || exit 2
  docker run -d --name "$mail_container" -p "127.0.0.1:$mail_port:8025" \
    -e MP_SMTP_AUTH_ACCEPT_ANY=1 -e MP_SMTP_AUTH_ALLOW_INSECURE=1 axllent/mailpit:latest >/dev/null || { echo "mail sink failed to start" >&2; exit 2; }
  sleep 2
  expect "the mail sink answers" "200" "$(http_code "http://127.0.0.1:$mail_port/api/v1/messages")"
}

# --- the stack's files ----------------------------------------------------------------------------------------
deploy_paths=(deploy.sh docker-compose.deployment.yml docker-compose.sso-deployment.yml nginx-deployment.conf
  Dockerfile.deployment.mongo-seed seed-data-deployment.js deploy postgres .env.deployment.example)

# The previous release's deployment files, as they were tagged (what an operator had checked out).
copy_old_layout() {
  mkdir -p "$S_DIR"
  git -C "$root" archive "$old_tag" -- "${deploy_paths[@]}" 2>/dev/null | tar -x -C "$S_DIR" || return 1
  chmod +x "$S_DIR/deploy.sh"
}

# The old compose file with free host ports on 127.0.0.1 and the OLD release's published images (its file
# tags them :nightly). Only this harness' substitutions; the stack is otherwise the release's own.
prepare_old_compose() {
  local file="$S_DIR/docker-compose.deployment.yml" hp new
  sed -i -E \
    -e "s#bettercollected/(backend|auth|webapp|integrations-google):nightly#bettercollected/\1:$old_tag#" \
    -e "s#ghcr.io/umami-software/umami:postgresql-latest#$img_umami#" "$file"
  : > "$S_DIR/ports.map"
  # shellcheck disable=SC2013  # one host port per word
  for hp in $(grep -oE "^[[:space:]]*-[[:space:]]*['\"]?(127\.0\.0\.1:)?[0-9]+:[0-9]+['\"]?[[:space:]]*$" "$file" \
      | sed -E "s/^[[:space:]]*-[[:space:]]*['\"]?(127\.0\.0\.1:)?([0-9]+):.*/\2/" | sort -u); do
    new="$(free_port)" || return 1
    sed -i -E "s/^([[:space:]]*-[[:space:]]*)['\"]?(127\.0\.0\.1:)?${hp}:([0-9]+)['\"]?[[:space:]]*\$/\1'127.0.0.1:${new}:\3'/" "$file"
    echo "$hp $new" >> "$S_DIR/ports.map"
  done
}
mapped() { awk -v p="$1" '$1 == p {print $2}' "$S_DIR/ports.map"; }

admin_email="admin@example.com"
write_root_env() { # operator values only; deploy.sh generates the rest
  local subnet gw admin_port
  subnet="$(free_subnet)" || return 1
  gw="${subnet%.0/29}.1"
  admin_port="$(free_port)" || return 1
  ( umask 077
    {
      echo "PLATFORM_ADMIN_EMAILS=$admin_email"
      echo "ADMIN_PORT=$admin_port"
      echo "ADMIN_EDGE_SUBNET=$subnet"
      echo "ADMIN_EDGE_GATEWAY=$gw"
    } >> "$S_DIR/.env" )
}

# --- the swap: what an operator edits in the stack -----------------------------------------------------------------
# Image tags only, in the compose file itself (every `image:` of a first-party service).
swap_images() {
  local file="$S_DIR/docker-compose.deployment.yml"
  sed -i -E \
    -e "s#image: bettercollected/backend:$old_tag#image: $img_backend#" \
    -e "s#image: bettercollected/auth:$old_tag#image: $img_auth#" \
    -e "s#image: bettercollected/webapp:$old_tag#image: $img_webapp#" "$file"
}

# Settings a stack edit adds (not part of the image swap): written as a second compose file, the way a stack
# file gets extra `environment:` lines. DB_AUTO_MIGRATE on every service; the six switches on the backend and the
# two that matter on the jobs worker; MAIL_* on backend, jobs-worker and auth pointing at the sink.
write_swap_override() {
  local mail
  mail="      MAIL_SMTP_SERVER: $mail_container
      MAIL_SMTP_PORT: \"1025\"
      MAIL_SENDER: noreply@example.com
      MAIL_USER: swapcheck
      MAIL_PASSWORD: swapcheck-not-a-secret
      MAIL_STARTTLS: \"false\"
      MAIL_SSL_TLS: \"false\"
      MAIL_USE_CREDENTIALS: \"false\"
      MAIL_VALIDATE_CERTS: \"false\""
  cat > "$S_DIR/docker-compose.swap.yml" <<EOF
services:
  backend:
    environment:
      DB_AUTO_MIGRATE: "true"
      FIELD_RULES_ENABLED: "true"
      CHOICE_LOGIC_ENABLED: "true"
      NEW_QUESTION_TYPES_ENABLED: "true"
      WEBHOOKS_ENABLED: "true"
      EMAIL_ACTIONS_ENABLED: "true"
      SAVE_DRAFTS_ENABLED: "true"
$mail
  jobs-worker:
    environment:
      DB_AUTO_MIGRATE: "true"
      WEBHOOKS_ENABLED: "true"
      EMAIL_ACTIONS_ENABLED: "true"
$mail
  auth:
    environment:
      DB_AUTO_MIGRATE: "true"
$mail
  admin:
    environment:
      DB_AUTO_MIGRATE: "true"
  task-runner:
    environment:
      DB_AUTO_MIGRATE: "true"
EOF
}

# the old stack's auth sends its sign-in codes to the sink (production has MAIL_* on auth)
write_old_mail_override() {
  cat > "$S_DIR/docker-compose.oldmail.yml" <<EOF
services:
  auth:
    environment:
      MAIL_SMTP_SERVER: $mail_container
      MAIL_SMTP_PORT: "1025"
      MAIL_SENDER: noreply@example.com
      MAIL_USER: swapcheck
      MAIL_PASSWORD: swapcheck-not-a-secret
      MAIL_STARTTLS: "false"
      MAIL_SSL_TLS: "false"
      MAIL_USE_CREDENTIALS: "false"
      MAIL_VALIDATE_CERTS: "false"
EOF
}

# --- the run -------------------------------------------------------------------------------------------------------
api() { echo "http://127.0.0.1:$S_BACKEND/api/v1"; }
cl() { client "$1" --api "$(api)" --mailpit "http://127.0.0.1:$mail_port" --state "$work/state.json" "${@:2}"; }

part_old() {
  section "(1) the $old_tag stack, installed with its own deploy.sh"
  enough_disk "old stack" || { bad "old stack not started (disk)"; return 1; }
  copy_old_layout || { bad "the $old_tag files could not be read from git"; return 1; }
  prepare_old_compose || { bad "ports for the old stack"; return 1; }
  write_root_env || { bad "root .env"; return 1; }
  # the operator's own settings: responding to a form is part of the product only with form creation on, which
  # every real deployment sets (it is off in the code and the example file)
  cp "$S_DIR/.env.deployment.example" "$S_DIR/.env.deployment"
  echo "API_ENABLE_FORM_CREATION=true" >> "$S_DIR/.env.deployment"
  chmod 600 "$S_DIR/.env.deployment"
  S_BACKEND="$(mapped 8000)"
  echo "  project $project, backend 127.0.0.1:$S_BACKEND, webapp 127.0.0.1:$(mapped 3000)"
  echo "  the $old_tag deploy.sh on a terminal (a few minutes) ..."
  local rc=0
  run_deploy "$work/old-deploy.out" || rc=$?
  expect "the $old_tag deploy.sh exits 0 on a fresh install (first install only)" "0" "$rc"
  if [ "$rc" != 0 ]; then tr -d '\033\r' < "$work/old-deploy.out" | grep -v 'Container\|Volume\|Network' | tail -n 25; show_failures; return 1; fi
  wait_stack 420 || { bad "the $old_tag stack became healthy"; service_state; show_failures; return 1; }
  ok "the $old_tag stack is healthy (backend, auth)"
  expect "the services run the published $old_tag images" "bettercollected/backend:$old_tag bettercollected/auth:$old_tag bettercollected/webapp:$old_tag" \
    "$(for s in backend auth webapp; do docker inspect -f '{{.Config.Image}}' "$(dc ps -q $s | head -n 1)"; done | tr '\n' ' ' | sed 's/ $//')"
  OLD_VERSION="$(psql_app "select version_num from app.alembic_version")"
  echo "  the app schema is at revision $OLD_VERSION"
  # the sink joins the stack's network; the old auth mails to it (a stack edit, not deploy.sh)
  docker network connect "${project}_default" "$mail_container" >/dev/null 2>&1 || { bad "the mail sink joined the stack's network"; return 1; }
  write_old_mail_override
  COMPOSE_EXTRA=(-f docker-compose.oldmail.yml)
  dc up -d --no-deps auth >/dev/null 2>&1 || { bad "old auth restarted with MAIL_*"; return 1; }
  wait_state auth healthy 180 || { bad "old auth healthy with MAIL_*"; return 1; }
  : > "$work/ids"
  absorb < <(cl seed)
  local ids wid fid rid
  ids="$(cat "$work/ids")"; wid="$(echo "$ids" | cut -d' ' -f2)"; fid="$(echo "$ids" | cut -d' ' -f3)"; rid="$(echo "$ids" | cut -d' ' -f4)"
  [ -n "$rid" ] || { bad "seeding gave the ids of a workspace, a form and a response"; return 1; }
  # two 4.1-style action jobs with their payload in the args (backend/tests/app/jobs/test_legacy_scrub.py::legacy_args)
  local aid="a1b2c3d4e5f60718293a4b5c" out
  out="$(dc exec -T app-postgres psql -U bettercollected -d bettercollected -Atq -v ON_ERROR_STOP=1 -v aid="$aid" -v fid="$fid" -v rid="$rid" -v wid="$wid" 2>&1 <<'SQL' | tr -d '\r'
SET search_path TO jobs, public;
WITH legacy AS (
  SELECT jsonb_build_object(
    'action',     jsonb_build_object('id', :'aid', 'secrets', jsonb_build_array(jsonb_build_object('value', 'swapcheck-action-secret')))::text,
    'form',       jsonb_build_object('form_id', :'fid')::text,
    'response',   jsonb_build_object('response_id', :'rid', 'answers', jsonb_build_object('q', 'SWAPCHECK-ANSWER-42'))::text,
    'user_email', 'legacy-responder@example.org',
    'workspace',  jsonb_build_object('id', :'wid', 'secrets', jsonb_build_object(:'aid', 'swapcheck-action-secret'))::text
  ) AS args
)
INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args, status)
SELECT 'actions', 'run_action', args, s FROM legacy,
  (VALUES ('todo'::jobs.procrastinate_job_status), ('succeeded'::jobs.procrastinate_job_status)) AS v(s)
RETURNING id || ':' || status;
SQL
)"
  WAITING_ID="$(echo "$out" | grep ':todo$' | cut -d: -f1)"; DONE_ID="$(echo "$out" | grep ':succeeded$' | cut -d: -f1)"
  [ -n "$WAITING_ID" ] && [ -n "$DONE_ID" ] || { bad "the 4.1-style action jobs were queued ($out)"; return 1; }
  ok "two 4.1-style action jobs with payload were queued (one waiting, one finished) on the old stack"
  expect "they carry the legacy keys" "2" "$(psql_app "select count(*) from jobs.procrastinate_jobs where queue_name='actions' and args ? 'response' and args ? 'action' and args ? 'form' and args ? 'workspace' and args ? 'user_email'")"
  SEED_IDS="$wid $fid $rid $aid"
  OLD_COMPOSE_NORMAL="$work/compose.old.normal"
  sed -E 's#^( *(\# )?image: ).*#\1IMAGE#' "$S_DIR/docker-compose.deployment.yml" > "$OLD_COMPOSE_NORMAL"
  OLD_RUNNING="$(dc ps --services --filter status=running | sort | tr '\n' ' ')"
  return 0
}

part_swap() {
  section "(2) the image swap (no deploy.sh)"
  swap_images
  sed -E 's#^( *(\# )?image: ).*#\1IMAGE#' "$S_DIR/docker-compose.deployment.yml" > "$work/compose.new.normal"
  expect "the swap changed image: lines only" "" "$(diff "$OLD_COMPOSE_NORMAL" "$work/compose.new.normal")"
  write_swap_override
  COMPOSE_EXTRA=(-f docker-compose.swap.yml)
  # one DB_AUTO_MIGRATE per service of the compose files (what production has), the six switches and MAIL_*
  expect "every running service of the old stack has a DB_AUTO_MIGRATE=true in the swapped stack (backend, jobs-worker, auth, admin, task-runner)" \
    "5" "$(dc config 2>/dev/null | grep -c 'DB_AUTO_MIGRATE: "\?true')"
  echo "  docker compose up -d ${OLD_RUNNING}"
  local swap_start=$SECONDS rc=0
  # shellcheck disable=SC2086
  dc up -d $OLD_RUNNING >"$work/swap-up.out" 2>&1 || rc=$?
  expect "docker compose up -d (the services of the old stack, as production restarts them) exits 0" "0" "$rc"
  [ "$rc" = 0 ] || { tail -n 20 "$work/swap-up.out"; show_failures; return 1; }
  # the recreated containers run the candidate images
  expect "backend, jobs-worker, auth and webapp run the candidate images" \
    "$img_backend $img_backend $img_auth $img_webapp" \
    "$(for s in backend jobs-worker auth webapp; do docker inspect -f '{{.Config.Image}}' "$(dc ps -q $s | head -n 1)"; done | tr '\n' ' ' | sed 's/ $//')"
  wait_stack 420 || { bad "backend and auth became healthy on the candidate (after $((SECONDS - swap_start)) s)"; service_state; show_failures
    logs_of backend | tail -n 25 | cut -c1-240 | sed 's/^/        backend: /'; return 1; }
  settle_services 240 || echo "  (a service was still starting after 240 s)"
  ok "backend and auth are healthy on the candidate ($((SECONDS - swap_start)) s after up -d)"
  local unhealthy
  unhealthy="$(service_state | grep -vE '=(healthy|running)$' | grep -vE '^(mongo-seed|mongodb)=' || true)"
  expect "every service is healthy or running after the swap" "" "$unhealthy"
  S_WEB="$(mapped 3000)"
  expect "the webapp serves (HTTP 200 or a redirect)" "yes" "$(case "$(http_code "http://127.0.0.1:$S_WEB/")" in 200|301|302|307|308) echo yes ;; esac)"
  return 0
}

checks_a_to_d() {
  local expect_head="${SWAP_CHECK_EXPECT_ALEMBIC:-0028}"
  section "(3a) migrations"
  local version="" deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    version="$(psql_app "select version_num from app.alembic_version")"
    [ "$version" = "$expect_head" ] && break
    sleep 3
  done
  expect "the app schema's alembic version is $expect_head (was $OLD_VERSION)" "$expect_head" "$version"
  logs_of backend > "$work/backend.log"
  logs_of jobs-worker > "$work/jobs-worker.log"
  # the backend and the jobs worker both migrate at start (advisory-locked): whichever gets the lock applies the
  # revisions and the other logs "nothing to apply"; so both logs are read
  cat "$work/backend.log" "$work/jobs-worker.log" > "$work/both.log"
  check "the backend log shows the migration (applied by it, or 'at head' after the jobs worker's)" \
    grep -qE "schema 'app' (migrated, applied .*$expect_head|: nothing to apply)|schema 'app' at head \($expect_head\)" "$work/backend.log"
  check "a service log shows the revisions applied up to $expect_head" grep -qE "DB_AUTO_MIGRATE: schema 'app' migrated, applied .*$expect_head" "$work/both.log"
  grep -hE "DB_AUTO_MIGRATE: schema 'app'|schema 'app' at head" "$work/backend.log" "$work/jobs-worker.log" | cut -c1-200 | sed 's/^/        /'

  section "(3b) the old action jobs are scrubbed"
  check "the backend log contains 'legacy action jobs scrubbed:'" grep -q 'legacy action jobs scrubbed:' "$work/backend.log"
  check "the log says 0 left (every service's scrub line)" bash -c '! grep -h "legacy action jobs scrubbed:" "$1" | grep -qv " 0 left"' _ "$work/both.log"
  grep -H 'legacy action jobs scrubbed:' "$work/backend.log" "$work/jobs-worker.log" | sed -E 's#^.*/([a-z-]+)\.log:#\1: #' | cut -c1-200 | sed 's/^/        /'
  expect "the scrub lines of the two services add up to 1 deleted (the finished job) and 1 rewritten (the waiting one)" "1 1" \
    "$(grep -h 'legacy action jobs scrubbed:' "$work/both.log" | sed -E 's/.*scrubbed: ([0-9]+) deleted, ([0-9]+) rewritten.*/\1 \2/' | awk '{d+=$1; r+=$2} END {print d, r}')"
  expect "the zero-count query returns 0" "0" "$(psql_app "SELECT count(*) FROM jobs.procrastinate_jobs WHERE queue_name='actions' AND task_name='run_action' AND (args ? 'response' OR args ? 'action' OR args ? 'form' OR args ? 'workspace' OR args ? 'user_email')")"
  local wid fid rid aid
  read -r wid fid rid aid <<< "$SEED_IDS"
  expect "the finished job is deleted" "0" "$(psql_app "select count(*) from jobs.procrastinate_jobs where id=$DONE_ID")"
  expect "the waiting job is still waiting (status todo)" "todo" "$(psql_app "select status from jobs.procrastinate_jobs where id=$WAITING_ID")"
  expect "the waiting job's args are ids plus run_token (action_id, form_id, response_id, run_token, workspace_id)" \
    "action_id,form_id,response_id,run_token,workspace_id" \
    "$(psql_app "select string_agg(k, ',' order by k) from (select jsonb_object_keys(args) k from jobs.procrastinate_jobs where id=$WAITING_ID) s")"
  expect "the waiting job's ids are the seeded action, form, response and workspace" "$aid $fid $rid $wid" \
    "$(psql_app "select args->>'action_id' || ' ' || (args->>'form_id') || ' ' || (args->>'response_id') || ' ' || (args->>'workspace_id') from jobs.procrastinate_jobs where id=$WAITING_ID")"
  expect "the run token is present and the rows hold no answer, secret or address" "yes 0" \
    "$(psql_app "select (length(args->>'run_token') > 10)::text from jobs.procrastinate_jobs where id=$WAITING_ID" | sed 's/true/yes/') $(psql_app "select count(*) from jobs.procrastinate_jobs where args::text ~ 'SWAPCHECK-ANSWER-42|swapcheck-action-secret|legacy-responder@example.org'")"

  section "(3c) old data reads as before"
  absorb < <(cl readback)

  section "(3d) the jobs worker"
  grep -E "jobs worker: queues|Starting worker on queues" "$work/jobs-worker.log" | cut -c1-200 | sed 's/^/        /'
  local q
  for q in default webhooks emails exports; do
    check "the jobs worker serves the '$q' queue" grep -qE "Starting worker on queues.*(^|[ ,])$q([ ,]|\$)" "$work/jobs-worker.log"
  done
  expect "no 'queue not served' warning in the jobs worker's log" "0" "$(grep -c "does not serve the '" "$work/jobs-worker.log")"

  section "(3h) the executor role's restriction"
  # backend/jobs/schema.py: a row-level policy keeps the actions executor (bc_jobs_exec, which runs creator code)
  # to the actions queue; its trigger functions belong to the NOLOGIN role bc_jobs_def. deploy.sh applies both. A stack
  # upgraded by swapping images does not (the backend's startup finds the queue table present and skips it): the 4.2
  # upgrade notes give one step for a stack that runs the executor on the Postgres queue.
  executor_state() { # rls, policies, function owner and security definer, bc_jobs_def exists, INSERT on events
    echo "rls=$(psql_app "select relrowsecurity from pg_class where oid='jobs.procrastinate_jobs'::regclass")" \
      "policies=$(psql_app "select count(*) from pg_policies where schemaname='jobs' and tablename='procrastinate_jobs'")" \
      "function_owner=$(psql_app "select proowner::regrole::text || '/definer=' || prosecdef::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='jobs' and proname='procrastinate_trigger_function_status_events_insert_v1'")" \
      "bc_jobs_def_exists=$(psql_app "select count(*)=1 from pg_roles where rolname='bc_jobs_def'")" \
      "executor_insert_on_events=$(psql_app "select has_table_privilege('bc_jobs_exec','jobs.procrastinate_events','INSERT')")"
  }
  local bare
  bare="$(executor_state)"
  RESULTS+=("INFO $(stamp) bare image swap leaves the executor unrestricted (expected; see the upgrade notes): $bare")
  echo "  INFO  $(stamp) bare image swap leaves the executor unrestricted (expected; see the upgrade notes): $bare"
  # the documented step, as an operator runs it: the release's script as the database superuser in the database
  # container, then the schema step in the backend's container
  local step_rc=0
  (cd "$S_DIR" && hermetic docker compose -f docker-compose.deployment.yml "${COMPOSE_EXTRA[@]}" exec -T app-postgres bash -s \
    < "$root/postgres/ensure-jobs-exec-role.sh") > "$work/ensure-role.out" 2>&1 || step_rc=$?
  expect "the documented step: postgres/ensure-jobs-exec-role.sh as the database superuser exits 0" "0" "$step_rc"
  tail -n 3 "$work/ensure-role.out" | cut -c1-200 | sed 's/^/        /'
  step_rc=0
  dc exec -T backend /api/backend/.venv/bin/python -m backend.jobs.schema > "$work/jobs-schema.out" 2>&1 || step_rc=$?
  expect "the documented step: python -m backend.jobs.schema in the backend container exits 0" "0" "$step_rc"
  tail -n 3 "$work/jobs-schema.out" | cut -c1-200 | sed 's/^/        /'
  RESULTS+=("INFO $(stamp) after the documented step: $(executor_state)")
  echo "  INFO  $(stamp) after the documented step: $(executor_state)"
  expect "row-level security is on for jobs.procrastinate_jobs, with the executor's restrictive policy and the open one" "t 2" \
    "$(psql_app "select relrowsecurity from pg_class where oid='jobs.procrastinate_jobs'::regclass") $(psql_app "select count(*) from pg_policies where schemaname='jobs' and tablename='procrastinate_jobs'")"
  expect "bc_jobs_def exists" "t" "$(psql_app "select count(*)=1 from pg_roles where rolname='bc_jobs_def'")"
  expect "the queue's trigger functions are owned by bc_jobs_def (SECURITY DEFINER)" "bc_jobs_def t" \
    "$(psql_app "select proowner::regrole::text || ' ' || prosecdef::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='jobs' and proname='procrastinate_trigger_function_status_events_insert_v1'" | sed 's/true/t/;s/ false/ f/')"
  expect "the executor's role (bc_jobs_exec) has no INSERT on procrastinate_events" "f" \
    "$(psql_app "select has_table_privilege('bc_jobs_exec','jobs.procrastinate_events','INSERT')")"
  # everything else of the stack still works after the step (the backend was not restarted)
  expect "the backend still answers after the step" "401" "$(http_code "http://127.0.0.1:$S_BACKEND/api/v1/auth/status")"
}

check_e_webhook() {
  section "(3e) webhooks"
  docker run -d --name "$recv_container" --network "${project}_default" --network-alias hook.example.com \
    --entrypoint /api/backend/.venv/bin/python "$img_backend" -I -c '
import socketserver
class H(socketserver.BaseRequestHandler):
    def handle(self):
        print("CONNECTION", flush=True)
        self.request.recv(1024)
class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
S(("0.0.0.0", 443), H).serve_forever()' >/dev/null 2>&1 || { bad "the test receiver container started"; return; }
  sleep 2
  absorb < <(cl webhook --receiver-url "https://hook.example.com/hook")
  expect "the receiver (hook.example.com on the stack's network, a private address) got no connection" "0" \
    "$(docker logs "$recv_container" 2>&1 | grep -c CONNECTION)"
  expect "the backend log carries no delivery to it" "0" "$(logs_of backend | grep -ciE 'hook\.example\.com')"
}

check_f_drafts() { section "(3f) drafts"; absorb < <(cl drafts); }
check_g_email() { section "(3g) email action and the respondent's copy"; absorb < <(cl email); }

# --- go --------------------------------------------------------------------------------------------------------------
OLD_VERSION=""; WAITING_ID=""; DONE_ID=""; SEED_IDS=""; OLD_COMPOSE_NORMAL=""; OLD_RUNNING=""; S_BACKEND=""; S_WEB=""
prepare_images
section "mail sink"
mail_start
if part_old && part_swap; then
  checks_a_to_d
  check_e_webhook
  check_f_drafts
  check_g_email
fi

section "result"
printf '%s\n' "${RESULTS[@]}" | sed 's/^/  /'
echo "== $pass passed, $fail failed, $notcovered not covered, in $((SECONDS - started)) s"
[ "$fail" -eq 0 ]
