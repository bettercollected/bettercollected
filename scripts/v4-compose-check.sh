#!/usr/bin/env bash
# End-to-end release acceptance of the 4.0 deployment, against REAL containers
# (docs/admin-service.md, "Release acceptance"). It runs the real ./deploy.sh in a
# throw-away copy of the repository's deployment files, against images built from
# this checkout, and checks what an operator would see:
#
#   (1) fresh     a new install on empty volumes, the first-run wizard, sign-in, the pages, a task run
#   (2) upgrade   a stack from the 3.x layout (the previous release's files and images, seeded with
#                 dummy data) taken over by the new ./deploy.sh: import, not bootstrap
#   (3) rollback  SETTINGS_STORE=off, then the previous release's files and images, then back
#   (4) negatives the portal is unreachable from outside, the master key is held by the right services,
#                 a minimal .env renders
#
#   scripts/v4-compose-check.sh [--parts 1,2,3,4 | --fresh --upgrade --rollback --negatives] [--keep]
#
# Safe on a developer machine: its own compose project names (bcv4f<pid>, bcv4u<pid>, the names of the
# throw-away directories), host ports from 8100 up that are free (everything is published on 127.0.0.1
# only), an unused subnet for the admin edge network, new secrets, and removal of every container,
# network, volume and image it created when it exits. It never touches a running stack: it does not
# use the default project name, and no fixed host port (3000-3003, 5432, 8000, 27017, ...) is bound
# by the stack under test (the copy of the compose file gets other host ports).
#
# What is real: deploy.sh, the compose file, postgres/, deploy/ and nginx-deployment.conf (copies of the
# checkout's), the images of the first-party services (built from this checkout), the migrations, the
# portal, the task runner. What is substituted, only in the throw-away copy: the `image:` lines (to the
# images below) and the host side of the published ports. Mail goes to a local sink (mailpit).
#
# Images (override mechanism, like ADMIN_CHECK_IMAGE in admin-compose-check.sh):
#   built from the checkout:  bc-v4check-backend:local (backend, admin, task runner, jobs worker,
#   document sandbox), bc-v4check-auth:local, bc-v4check-worker:local; the Google integration
#   (bc-v4check-google:local) with V4_CHECK_GOOGLE=1.
#   V4_CHECK_REUSE_IMAGES=1   use images with those tags that already exist instead of building
#   V4_CHECK_WEBAPP=nightly   (default) the published bettercollected/webapp:nightly; =build builds
#                             webapp/Dockerfile (slow); =<image> uses that image
#   V4_CHECK_OLD_TAG=v3.4.0   the previous release: its files come from `git show <tag>:...` and its
#                             images are bettercollected/{backend,auth,temporal-worker,webapp}:<tag>
#                             (V4_CHECK_OLD_WEBAPP=<image> overrides the webapp)
#   V4_CHECK_KEEP_IMAGES=1    do not remove the images this run built or pulled
# Also: --keep leaves the stacks running (the work directory is printed); V4_CHECK_MIN_FREE_MB (default
# 2500) is the free disk space below which a part is not started.
#
# Needs: bash, docker (compose v2), curl, openssl, script (util-linux), uv, git (for the previous release).
# Takes about 15 to 25 minutes with images in place (a cold start adds the pulls and builds).
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 1
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"

parts=""
keep=0
while [ $# -gt 0 ]; do
  case "$1" in
    --parts) parts="$parts,${2:-}"; shift 2 ;;
    --fresh) parts="$parts,1"; shift ;;
    --upgrade) parts="$parts,2"; shift ;;
    --rollback) parts="$parts,3"; shift ;;
    --negatives) parts="$parts,4"; shift ;;
    --keep) keep=1; shift ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done
[ -n "$parts" ] || parts=",1,2,3,4"
want() { case "$parts" in *",$1"*) return 0 ;; *) return 1 ;; esac; }

for tool in docker curl openssl script uv; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing tool: $tool" >&2; exit 2; }
done
docker compose version >/dev/null 2>&1 || { echo "docker compose v2 is required" >&2; exit 2; }

old_tag="${V4_CHECK_OLD_TAG:-v3.4.0}"
min_free_mb="${V4_CHECK_MIN_FREE_MB:-2500}"
work="$(mktemp -d)"
chmod 700 "$work"
pass=0
fail=0
skip=0
run_id="$$"
mail_container="bcv4mail$run_id"
mail_port=""
projects=()
extra_containers=("$mail_container")
extra_networks=()
bg_pids=()
built_images=()
pulled_images=()
images_before="$(docker image ls --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | sort -u)"
started=$SECONDS

# --- reporting ----------------------------------------------------------------------------------------
ok() { pass=$((pass + 1)); echo "  PASS  $1"; }
bad() { fail=$((fail + 1)); echo "  FAIL  $1"; }
skipped() { skip=$((skip + 1)); echo "  SKIP  $1"; }
check() { # check "<description>" <command...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi
}
expect() { # expect "<description>" "<expected>" "<actual>"
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$2', got '$3')"; fi
}
section() { echo "== $* ($((SECONDS - started)) s)"; }
# a client's PASS/FAIL lines count here; INFO lines are left to the caller
absorb() { # reads a client's output on stdin
  local line
  while IFS= read -r line; do
    case "$line" in
      "PASS "*) pass=$((pass + 1)); echo "  $line" ;;
      "FAIL "*) fail=$((fail + 1)); echo "  $line" ;;
      "INFO "*) echo "        ${line#INFO }" ;;
      *) echo "        $line" ;;
    esac
  done
}

# --- clean up everything this run created ---------------------------------------------------------------
cleanup() {
  local p ids
  for pid in "${bg_pids[@]:-}"; do [ -n "$pid" ] && kill "$pid" >/dev/null 2>&1; done
  if [ "$keep" = 1 ]; then
    echo "--keep: projects ${projects[*]:-none} left running (work directory $work, mail sink $mail_container)"
    return
  fi
  # the mail sink is on the stack's edge network: it goes first, or the network cannot be removed
  docker rm -f -v "${extra_containers[@]}" >/dev/null 2>&1
  for p in "${projects[@]:-}"; do
    [ -n "$p" ] || continue
    ids="$(docker ps -aq --filter "label=com.docker.compose.project=$p")"
    # shellcheck disable=SC2086
    [ -z "$ids" ] || docker rm -f -v $ids >/dev/null 2>&1
    ids="$(docker network ls -q --filter "label=com.docker.compose.project=$p")"
    # shellcheck disable=SC2086
    [ -z "$ids" ] || docker network rm $ids >/dev/null 2>&1
    ids="$(docker volume ls -q --filter "label=com.docker.compose.project=$p")"
    # shellcheck disable=SC2086
    [ -z "$ids" ] || docker volume rm -f $ids >/dev/null 2>&1
    docker rmi -f "${p}-mongo-seed:latest" >/dev/null 2>&1
  done
  [ "${#extra_networks[@]}" -eq 0 ] || docker network rm "${extra_networks[@]}" >/dev/null 2>&1
  if [ "${V4_CHECK_KEEP_IMAGES:-0}" != 1 ]; then
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

# --- helpers --------------------------------------------------------------------------------------------
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

free_subnet() { # a /29 inside 172.30.0.0/16 that no Docker network uses
  local used third
  used="$(docker network ls -q | xargs -r docker network inspect --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null)"
  for _ in $(seq 1 100); do
    third=$((100 + RANDOM % 150))
    case " $used " in *" 172.30.$third."*) continue ;; esac
    case " ${used_subnets:-} " in *" $third "*) continue ;; esac
    used_subnets="${used_subnets:-} $third"
    echo "172.30.$third.0/29"
    return
  done
  echo "no free subnet found" >&2
  return 1
}

enough_disk() { # enough_disk <what>
  local free_mb
  free_mb="$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2 {print $4}')"
  local docker_free
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
client() { uv run --no-project --quiet python -I "$root/scripts/v4_check_client.py" "$@"; }

# the compose project of a stack directory is its name (deploy.sh and compose agree on it)
S_DIR=""; S_PROJECT=""; S_ADMIN_PORT=""; S_WEB=""; S_BACKEND=""; S_N1=""; S_N2=""; S_N3=""; S_UMAMI=""
dc() { (cd "$S_DIR" && hermetic docker compose -f docker-compose.deployment.yml "$@" 2> >(grep -v 'level=warning' >&2)); }
admin_cli() { dc run --rm --no-deps -T admin /api/backend/.venv/bin/python -m backend.admin "$@"; }
sdeploy() { (cd "$S_DIR" && hermetic ./deploy.sh "$@"); }

# Runs ./deploy.sh on a pseudo-terminal (the setup token is shown on a terminal only), every output line
# prefixed with the time. Returns deploy.sh's exit status.
run_deploy() { # run_deploy <out> [deploy.sh args...]
  local out="$1"; shift
  ( cd "$S_DIR" && timeout 2400 "${HERM[@]}" script -qefc "./deploy.sh $*" /dev/null < /dev/null ) 2>&1 \
    | while IFS= read -r line; do printf '%s %s\n' "$(date +%s.%N)" "${line%$'\r'}"; done > "$out"
  return "${PIPESTATUS[0]}"
}
untimed() { sed -E 's/^[0-9]+\.[0-9]+ //' "$1"; }

# Copies the deployment files of a layout into a new directory named after its compose project.
#   new: the working tree of this checkout        old: <old tag> (git show)
# The new layout ships the template .env.deployment.example (deploy.sh creates the untracked
# .env.deployment from it on the first run, as on a fresh checkout); the old one tracked
# .env.deployment itself. The operator's own .env.deployment of this checkout is never copied.
deploy_paths=(deploy.sh docker-compose.deployment.yml docker-compose.sso-deployment.yml nginx-deployment.conf
  Dockerfile.deployment.mongo-seed seed-data-deployment.js deploy postgres)
new_paths=("${deploy_paths[@]}" .env.deployment.example)
old_paths=("${deploy_paths[@]}" .env.deployment)
copy_layout() { # copy_layout new|old <dir>
  local layout="$1" dir="$2" path
  mkdir -p "$dir"
  if [ "$layout" = new ]; then
    for path in "${new_paths[@]}"; do
      [ -e "$root/$path" ] && cp -a "$root/$path" "$dir/"
    done
  else
    git -C "$root" archive "$old_tag" -- "${old_paths[@]}" 2>/dev/null | tar -x -C "$dir" || return 1
  fi
  chmod +x "$dir/deploy.sh"
}

# Rewrites, in the copy of the compose file only: the first-party `image:` lines and the host side of
# every published port. Every published host port gets a free one on 127.0.0.1.
rewrite_compose() { # rewrite_compose <dir> new|old
  local dir="$1" layout="$2" file hp new
  file="$dir/docker-compose.deployment.yml"
  if [ "$layout" = new ]; then
    sed -i -E \
      -e "s#bettercollected/backend:nightly#$img_backend#" \
      -e "s#bettercollected/auth:nightly#$img_auth#" \
      -e "s#bettercollected/temporal-worker:nightly#$img_worker#" \
      -e "s#bettercollected/webapp:nightly#$img_webapp#" \
      -e "s#bettercollected/integrations-google:nightly#$img_google#" \
      -e "s#ghcr.io/umami-software/umami:postgresql-latest#$img_umami#" "$file"
  else
    sed -i -E \
      -e "s#bettercollected/backend:nightly#bettercollected/backend:$old_tag#" \
      -e "s#bettercollected/auth:nightly#bettercollected/auth:$old_tag#" \
      -e "s#bettercollected/temporal-worker:nightly#bettercollected/temporal-worker:$old_tag#" \
      -e "s#bettercollected/webapp:nightly#${V4_CHECK_OLD_WEBAPP:-bettercollected/webapp:$old_tag}#" \
      -e "s#ghcr.io/umami-software/umami:postgresql-latest#$img_umami#" "$file"
  fi
  : > "$dir/ports.map"
  # shellcheck disable=SC2013  # one host port per word
  for hp in $(grep -oE "^[[:space:]]*-[[:space:]]*['\"]?(127\.0\.0\.1:)?[0-9]+:[0-9]+['\"]?[[:space:]]*$" "$file" \
      | sed -E "s/^[[:space:]]*-[[:space:]]*['\"]?(127\.0\.0\.1:)?([0-9]+):.*/\2/" | sort -u); do
    new="$(free_port)" || return 1
    sed -i -E "s/^([[:space:]]*-[[:space:]]*)['\"]?(127\.0\.0\.1:)?${hp}:([0-9]+)['\"]?[[:space:]]*\$/\1'127.0.0.1:${new}:\3'/" "$file"
    echo "$hp $new" >> "$dir/ports.map"
  done
}
mapped() { awk -v p="$1" '$1 == p {print $2}' "$S_DIR/ports.map"; }

new_stack() { # new_stack <label> new|old   (sets S_*)
  local label="$1" layout="$2"
  S_PROJECT="bcv4${label}${run_id}"
  S_DIR="$work/$S_PROJECT"
  copy_layout "$layout" "$S_DIR" || return 1
  rewrite_compose "$S_DIR" "$layout" || return 1
  projects+=("$S_PROJECT")
  S_ADMIN_PORT="$(free_port)"
  read_ports
}

# the host ports of the stack's published ports, from the copy of the compose file in use
read_ports() {
  S_WEB="$(mapped 3000)"; S_BACKEND="$(mapped 8000)"; S_N1="$(mapped 3001)"; S_N2="$(mapped 3002)"
  S_N3="$(mapped 3003)"; S_UMAMI="$(mapped 3004)"
  [ -n "$S_UMAMI" ] || S_UMAMI="$S_N3"   # the 3.x layout publishes the dashboard on 3003
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

show_failures() { # the last log lines of every container that is not up (a diagnosis aid; logs hold no secrets)
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

service_state() { # the health (or state) of every container of the stack, one "name=state" per line
  local id name st
  for id in $(dc ps -aq 2>/dev/null); do
    name="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id")"
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")"
    echo "$name=$st"
  done | sort
}

# the secret values of the stack's root .env (names ending in PASSWORD, SECRET or KEY, and the keys)
collect_secrets() { # collect_secrets <out>
  local f="$S_DIR/.env"
  ( umask 077
    grep -E '^(SETTINGS_MASTER_KEY|API_KEY|AES_HEX_KEY|[A-Z_]*(PASSWORD|SECRET))=.{12,}' "$f" 2>/dev/null | sed -E 's/^[^=]*=//' > "$1" )
}
secret_hits() { # secret_hits <secrets file> <file...>: how many secret values occur in the files
  local n=0 f
  for f in "${@:2}"; do
    [ -s "$f" ] && n=$((n + $(grep -c -F -f "$1" "$f")))
  done
  echo "$n"
}
# the lines of the files that hold a secret value, with every value replaced (a diagnosis aid)
show_secret_hits() { # show_secret_hits <secrets file> <file...>
  awk 'NR == FNR { s[++n] = $0; next }
       { line = $0
         for (i = 1; i <= n; i++) while ((p = index(line, s[i])) > 0) line = substr(line, 1, p - 1) "<secret>" substr(line, p + length(s[i]))
         if (line != $0) print "        hit: " substr(line, 1, 200) }' "$1" "${@:2}" | head -n 5
}

# --- images ---------------------------------------------------------------------------------------------
img_backend="bc-v4check-backend:local"
img_auth="bc-v4check-auth:local"
img_worker="bc-v4check-worker:local"
img_google="bc-v4check-google:local"
img_webapp="bettercollected/webapp:nightly"
img_umami="ghcr.io/umami-software/umami:postgresql-latest"

build_image() { # build_image <tag> <dockerfile>
  if [ "${V4_CHECK_REUSE_IMAGES:-0}" = 1 ] && docker image inspect "$1" >/dev/null 2>&1; then
    echo "  reusing $1"
    return 0
  fi
  echo "  building $1 from $2 (a few minutes)"
  enough_disk "build $1" || return 1
  docker build -q -t "$1" -f "$2" "$root" >/dev/null || { echo "build of $1 failed" >&2; return 1; }
  built_images+=("$1")
}

prepare_images() {
  section "images"
  build_image "$img_backend" backend/Dockerfile || exit 2
  build_image "$img_auth" auth/Dockerfile || exit 2
  build_image "$img_worker" temporal/worker/Dockerfile || exit 2
  [ "${V4_CHECK_GOOGLE:-0}" != 1 ] || build_image "$img_google" integrations/google/Dockerfile || exit 2
  case "${V4_CHECK_WEBAPP:-nightly}" in
    nightly) echo "  webapp: the published bettercollected/webapp:nightly (not built from this checkout)" ;;
    build)
      img_webapp="bc-v4check-webapp:local"
      build_image "$img_webapp" webapp/Dockerfile || exit 2 ;;
    *) img_webapp="$V4_CHECK_WEBAPP"; echo "  webapp: $img_webapp" ;;
  esac
  pulled_images+=("$img_webapp" "temporalio/auto-setup:latest" "postgres:15-alpine" "postgres:16-alpine" "mongo:latest" "nginx:1.28-alpine")
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
  mail_start
}

mail_start() {
  mail_port="$(free_port)" || exit 2
  docker run -d --name "$mail_container" -p "127.0.0.1:$mail_port:8025" \
    -e MP_SMTP_AUTH_ACCEPT_ANY=1 -e MP_SMTP_AUTH_ALLOW_INSECURE=1 axllent/mailpit:latest >/dev/null || { echo "mail sink failed to start" >&2; exit 2; }
  sleep 2
  expect "the mail sink answers" "200" "$(http_code "http://127.0.0.1:$mail_port/api/v1/messages")"
}

# --- what every part needs from the stack's root .env ------------------------------------------------------
admin_email="admin@example.com"
write_root_env() { # operator values only; deploy.sh generates the rest
  local subnet gw
  subnet="$(free_subnet)" || return 1
  gw="${subnet%.0/29}.1"
  ( umask 077
    {
      echo "PLATFORM_ADMIN_EMAILS=$admin_email"
      echo "ADMIN_PORT=$S_ADMIN_PORT"
      echo "ADMIN_EDGE_SUBNET=$subnet"
      echo "ADMIN_EDGE_GATEWAY=$gw"
    } >> "$S_DIR/.env" )
}

mail_attach() { # the sink joins the stack's admin-edge network (the only network the portal is on)
  docker network connect "${S_PROJECT}_admin-edge" "$mail_container" >/dev/null 2>&1 || true
}

portal() { echo "http://127.0.0.1:$S_ADMIN_PORT"; }
cl() { # cl <command> [args]: the portal client for the current stack
  client "$1" --base "$(portal)" --state "$S_DIR/portal-state.json" --mailpit "http://127.0.0.1:$mail_port" \
    --email "$admin_email" --mail-server "$mail_container" --mail-port 1025 "${@:2}"
}

# --- the checks -------------------------------------------------------------------------------------------
fresh_done=0
# V4_CHECK_GOOGLE=1 also deploys the Google integration (./deploy.sh googleform)
google_arg=""; google_service=""; google_reporting=""
if [ "${V4_CHECK_GOOGLE:-0}" = 1 ]; then google_arg="googleform"; google_service="integrations-googleform"; google_reporting=",google"; fi

part_fresh() {
  section "(1) fresh install"
  enough_disk "fresh install" || { bad "fresh install not started (disk)"; return; }
  new_stack f new || { bad "fresh stack could not be prepared"; return; }
  write_root_env || { bad "root .env"; return; }
  echo "  project $S_PROJECT, admin 127.0.0.1:$S_ADMIN_PORT, webapp $S_WEB, backend $S_BACKEND, nginx $S_N1/$S_N2/$S_N3, umami $S_UMAMI"
  local out="$work/fresh-deploy.out" events="$work/fresh.events" ps_samples="$work/fresh.ps"
  docker events --filter "label=com.docker.compose.project=$S_PROJECT" --filter type=container \
    --format '{{.TimeNano}} {{.Action}} {{index .Actor.Attributes "com.docker.compose.service"}} {{.Actor.Attributes.name}}' > "$events" 2>/dev/null &
  bg_pids+=($!)
  local ev_pid=$!
  # shellcheck disable=SC2009  # the host process list is what is sampled
  ( while :; do ps -eo args 2>/dev/null | grep -E '^(docker|docker-compose|bash|sh|\./deploy\.sh|openssl|script|env|timeout|psql|\S*/(docker|openssl|script)) ' | grep -v grep >> "$ps_samples"; sleep 0.2; done ) &
  bg_pids+=($!)
  local ps_pid=$!

  echo "  ./deploy.sh on a terminal (a few minutes) ..."
  local rc=0
  run_deploy "$out" $google_arg || rc=$?
  sleep 2; kill "$ps_pid" "$ev_pid" >/dev/null 2>&1
  expect "deploy.sh exits 0 on a fresh install" "0" "$rc"
  if [ "$rc" != 0 ]; then untimed "$out" | tr -d '\033' | grep -v 'Container\|Volume\|Network' | tail -n 20; show_failures; return; fi
  # the copy had only the template: deploy.sh created .env.deployment from it, owner-only
  expect ".env.deployment was created from .env.deployment.example, mode 600, and said so" "same 600 1" \
    "$(cmp -s "$S_DIR/.env.deployment" "$S_DIR/.env.deployment.example" && echo same) $(stat -c %a "$S_DIR/.env.deployment" 2>/dev/null) $(untimed "$out" | grep -c 'Created .env.deployment from .env.deployment.example')"
  fresh_assertions "$out" "$events" "$ps_samples"
  fresh_second_run
  fresh_published_ports
  fresh_umami_nginx
  fresh_portal
  fresh_done=1
}

fresh_assertions() { # <deploy output> <events> <ps samples>
  local out="$1" events="$2" ps_samples="$3" plain
  plain="$work/fresh-deploy.plain"
  untimed "$out" > "$plain"
  # services
  local states unhealthy
  states="$(service_state)"
  unhealthy="$(printf '%s\n' "$states" | grep -vE '^(mongo-seed)=' | grep -vE '=(healthy|running)$' || true)"
  expect "every service is healthy or running" "" "$unhealthy"
  local svc
  for svc in admin task-runner jobs-worker document-sandbox backend auth webapp worker nginx umami temporal mongodb app-postgres $google_service; do
    case "$(printf '%s\n' "$states" | grep "^$svc=" | head -n 1)" in
      "$svc=healthy"|"$svc=running") ok "$svc is up" ;;
      *) bad "$svc is up ($(printf '%s\n' "$states" | grep "^$svc=" | head -n 1))" ;;
    esac
  done
  # migrations
  local app_head auth_head adm_head app_cur auth_cur adm_cur
  app_head="$(docker run --rm --entrypoint /api/backend/.venv/bin/alembic "$img_backend" -c /api/backend/alembic.ini heads 2>/dev/null | awk '{print $1}' | head -n 1)"
  auth_head="$(docker run --rm --entrypoint /api/auth/.venv/bin/alembic "$img_auth" -c /api/auth/alembic.ini heads 2>/dev/null | awk '{print $1}' | head -n 1)"
  adm_head="$(docker run --rm --entrypoint /api/backend/.venv/bin/alembic "$img_backend" -c /api/backend/backend/admin/alembic.ini heads 2>/dev/null | awk '{print $1}' | head -n 1)"
  psql_q() { dc exec -T app-postgres psql -U bettercollected -d bettercollected -Atc "$1" 2>/dev/null | tr -d '\r'; }
  app_cur="$(psql_q 'select version_num from app.alembic_version')"
  auth_cur="$(psql_q 'select version_num from auth.alembic_version')"
  adm_cur="$(psql_q 'select version_num from admin.alembic_version')"
  expect "the app schema is at the image's head" "$app_head" "$app_cur"
  expect "the auth schema is at the image's head" "$auth_head" "$auth_cur"
  expect "the admin schema is at the image's head" "$adm_head" "$adm_cur"
  expect "the settings store exists (settings schema migrated)" "t" "$(psql_q "select to_regclass('settings.entries') is not null")"
  # bootstrap-keys ran, before any service started
  check "bootstrap-keys ran (five keys generated, values not shown)" grep -q '^generated=5 (values are not shown)' "$plain"
  local boot_at first_start
  boot_at="$(grep -m1 ' generated=5 (values' "$out" | cut -d' ' -f1)"
  first_start="$(grep -E ' start (admin|backend|auth|webapp|worker|jobs-worker|task-runner|mongo-seed|nginx|umami|mongodb|temporal) ' "$events" | grep -v -- '-run-' | head -n 1 | cut -d' ' -f1)"
  if [ -n "$boot_at" ] && [ -n "$first_start" ]; then
    # the output line is stamped when it was read, the events when they happened
    if awk -v b="$boot_at" -v s="$first_start" 'BEGIN { exit !(b * 1000000000 < s) }'; then
      ok "bootstrap-keys output precedes the first service start"
    else
      bad "bootstrap-keys output precedes the first service start"
    fi
  else
    bad "bootstrap-keys ordering could not be established (boot '$boot_at', first start '$first_start')"
  fi
  local first_service_after_keys
  first_service_after_keys="$(grep -n -m1 -E 'Container .*-(backend|auth|webapp|worker|admin)-1 +(Creating|Created|Starting|Started)' "$plain" | cut -d: -f1)"
  local boot_line
  boot_line="$(grep -n -m1 '^generated=5' "$plain" | cut -d: -f1)"
  if [ -n "$boot_line" ] && [ -n "$first_service_after_keys" ]; then
    if [ "$boot_line" -lt "$first_service_after_keys" ]; then ok "in the deploy output, bootstrap-keys comes before the services' creation"; else bad "in the deploy output, bootstrap-keys comes before the services' creation"; fi
  else
    skipped "output order of bootstrap-keys and service creation (compose progress not found in the output)"
  fi
  # the fingerprint and the token: shown once
  local token_lines fp_notice fp
  token_lines="$(grep -cE '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$' "$plain")"
  expect "the setup token is printed exactly once on the terminal" "1" "$token_lines"
  fp_notice="$(grep -c '^Master key fingerprint' "$plain")"
  expect "the master key fingerprint notice is printed once" "1" "$fp_notice"
  fp="$(grep -A1 '^Master key fingerprint' "$plain" | grep -oE '[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}' | head -n 1)"
  check "the fingerprint has the documented shape" test -n "$fp"
  FRESH_FP="$fp"
  FRESH_TOKEN="$(grep -E '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$' "$plain" | head -n 1)"
  expect "the printed fingerprint is the master key's" "master_key_fingerprint $fp" "$(sdeploy master-key-fingerprint 2>/dev/null | tr -d '\r' | tail -n 1)"
  # secrets
  collect_secrets "$work/fresh.secrets"
  local count
  count="$(wc -l < "$work/fresh.secrets" | tr -d ' ')"
  check "the root .env holds generated secrets (checked below: $count values)" test "$count" -ge 10
  # the keys of the store: exported once (break-glass) only to widen the value list, then deleted
  rm -f "$S_DIR/keys-export.env"
  if sdeploy settings-env-export --keys AUTH_JWT_SECRET,AUTH_AES_HEX_KEY,AUTH_INTERNAL_NOTIFY_KEY,TEMPORAL_API_KEY,MASTER_ENCRYPTION_KEYSET --out "$S_DIR/keys-export.env" >/dev/null 2>&1; then
    sed -E 's/^[^=]*=//; s/^"(.*)"$/\1/' "$S_DIR/keys-export.env" | awk 'length($0) >= 12' >> "$work/fresh.secrets"
    rm -f "$S_DIR/keys-export.env"
  else
    bad "the store's keys could be exported to widen the secret check"
  fi
  # the token is on the terminal by design: take it out before looking for secrets
  grep -v -E '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$' "$plain" > "$work/fresh-deploy.notoken"
  expect "no secret value (generated or stored) is in the deploy output" "0" "$(secret_hits "$work/fresh.secrets" "$work/fresh-deploy.notoken")"
  sort -u "$ps_samples" > "$work/fresh.ps.sorted"
  expect "no secret value appears in the process list during the deploy" "0" "$(secret_hits "$work/fresh.secrets" "$work/fresh.ps.sorted")"
  show_secret_hits "$work/fresh.secrets" "$work/fresh.ps.sorted"
  expect "the setup token is not in the process list" "0" "$(grep -c -F "$FRESH_TOKEN" "$work/fresh.ps.sorted")"
  # docker inspect: command lines, entrypoints, labels, binds, mounts, never the environment
  local ids id leaks=0 inspect_out="$work/fresh.inspect"
  : > "$inspect_out"
  for id in $(dc ps -aq); do
    docker inspect -f '{{json .Path}} {{json .Args}} {{json .Config.Cmd}} {{json .Config.Entrypoint}} {{json .Config.Labels}} {{json .HostConfig.Binds}} {{json .Mounts}}' "$id" >> "$inspect_out"
    docker top "$id" -eo args 2>/dev/null >> "$inspect_out"
  done
  leaks="$(secret_hits "$work/fresh.secrets" "$inspect_out")"
  expect "no secret value in docker inspect (command, labels, mounts) or docker top of any container" "0" "$leaks"
  expect "no secret value is in the setup token's logs (every container's log)" "0" "$(for id in $(dc ps -aq); do docker logs "$id" 2>&1; done > "$work/fresh.logs"; secret_hits "$work/fresh.secrets" "$work/fresh.logs")"
  expect "the setup token is in no container log" "0" "$(grep -c -F "$FRESH_TOKEN" "$work/fresh.logs")"
  # per-service env scoping: webapp, worker (and the Typeform file) without secrets
  local name
  for name in webapp worker; do
    id="$(dc ps -q "$name" | head -n 1)"
    docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$id" > "$work/fresh.env.$name"
    local allowed_re='^(API_KEY|AES_HEX_KEY)='
    local hits
    hits="$(grep -c -F -f "$work/fresh.secrets" "$work/fresh.env.$name" || true)"
    if [ "$name" = worker ]; then
      hits="$(grep -vE "$allowed_re" "$work/fresh.env.$name" | grep -c -F -f "$work/fresh.secrets" || true)"
    fi
    expect "$name holds no secret value in its environment (the worker keeps only its two keys)" "0" "$hits"
    expect "$name has no master key and no database URL" "0" "$(grep -cE '^(SETTINGS_MASTER_KEY|DATABASE_URL|MONGO_URI|STRIPE_[A-Z_]*|GOOGLE_CLIENT_SECRET|MAIL_PASSWORD)=' "$work/fresh.env.$name")"
  done
  expect "the worker's two keys are the only secrets in its env" "AES_HEX_KEY API_KEY" "$(grep -E '^(API_KEY|AES_HEX_KEY)=.' "$work/fresh.env.worker" | cut -d= -f1 | sort | tr '\n' ' ' | sed 's/ $//')"
  # the Typeform service is a separate image that is not started here: its environment is checked as rendered
  local tf
  tf="$(dc config --format json 2>/dev/null | docker run --rm -i --entrypoint /api/backend/.venv/bin/python "$img_backend" -I -c '
import json, sys
s = json.load(sys.stdin)["services"]["integrations-typeform"]
env = s.get("environment") or {}
print(",".join(sorted(k for k in env if k in ("SETTINGS_MASTER_KEY", "DATABASE_URL", "STRIPE_SECRET", "GOOGLE_CLIENT_SECRET", "MAIL_PASSWORD") or k.endswith("_PASSWORD") or k.startswith("BC_"))) + "|" + ",".join(sorted(k for k in env if k.startswith(("AUTH_", "MASTER_")))))' 2>/dev/null)"
  expect "the Typeform service (rendered, not started) gets its three keys and no master key, database URL or secret of the backend" "|AUTH_AES_HEX_KEY,AUTH_JWT_SECRET,MASTER_ENCRYPTION_KEYSET" "$tf"
  check "the env files deploy.sh wrote are owner-only (mode 600)" test "$(stat -c %a "$S_DIR/.env" "$S_DIR/.env.webapp" "$S_DIR/.env.worker" "$S_DIR/.env.typeform" | sort -u | tr -d '\n')" = 600
  # umami: the built-in login is gone
  local umami_code
  umami_code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"username":"admin","password":"umami"}' "http://127.0.0.1:$S_UMAMI/api/auth/login")"
  expect "Umami rejects its built-in admin/umami login" "401" "$umami_code"
  # a second run changes nothing and shows nothing again
  FRESH_STORE_VERSIONS="$(for k in AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET; do sdeploy settings-history "$k" 2>/dev/null | tail -n 1; done | tr '\n' ' ')"
  expect "each stored key has exactly one version" "versions=1 versions=1 versions=1 " "$FRESH_STORE_VERSIONS"
  # a non-terminal run refuses to show a token
  local nt
  nt="$(sdeploy setup-token </dev/null 2>&1 | tr -d '\r')"
  case "$nt" in *"shown on a terminal only"*) ok "setup-token refuses without a terminal" ;; *) bad "setup-token refuses without a terminal" ;; esac
  expect "and prints no token then" "0" "$(printf '%s\n' "$nt" | grep -cE '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$')"
}

fresh_second_run() {
  section "(1) second ./deploy.sh on the same stack"
  local out="$work/fresh-deploy2.out" rc=0
  run_deploy "$out" $google_arg || rc=$?
  expect "a second deploy.sh run exits 0" "0" "$rc"
  local plain="$work/fresh-deploy2.plain"
  untimed "$out" > "$plain"
  expect "it prints no setup token" "0" "$(grep -cE '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$' "$plain")"
  expect "it prints no fingerprint notice" "0" "$(grep -c '^Master key fingerprint' "$plain")"
  expect "it generates nothing new" "0" "$(grep -c '^Generated a new' "$plain")"
  expect "it runs no bootstrap" "0" "$(grep -c '^generated=' "$plain")"
  local versions
  versions="$(for k in AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET; do sdeploy settings-history "$k" 2>/dev/null | tail -n 1; done | tr '\n' ' ')"
  expect "the stored keys are unchanged (still one version each)" "$FRESH_STORE_VERSIONS" "$versions"
  local unhealthy
  unhealthy="$(service_state | grep -vE '^(mongo-seed)=' | grep -vE '=(healthy|running)$' || true)"
  expect "every service is still healthy" "" "$unhealthy"
}

fresh_published_ports() {
  section "(1) published ports"
  local listing="$work/fresh.ports"
  docker ps --filter "label=com.docker.compose.project=$S_PROJECT" --format '{{.Label "com.docker.compose.service"}} {{.Ports}}' > "$listing"
  expect "nothing is published on 7234 (Temporal), 27017 (Mongo) or 5432 (Postgres)" "0" "$(grep -cE ':(7234|27017|5432)->' "$listing")"
  expect "the admin portal is published on 127.0.0.1 only" "127.0.0.1:$S_ADMIN_PORT->8000/tcp" "$(grep '^admin ' "$listing" | grep -oE '[0-9.:]+:'"$S_ADMIN_PORT"'->8000/tcp' | head -n 1)"
  expect "the Umami dashboard is published on 127.0.0.1 only" "127.0.0.1:$S_UMAMI->3000/tcp" "$(grep '^umami ' "$listing" | grep -oE '[0-9.:]+:'"$S_UMAMI"'->3000/tcp' | head -n 1)"
  expect "no port of the stack is bound to 0.0.0.0 or ::" "0" "$(grep -cE '(0\.0\.0\.0|\[::\]):[0-9]+->' "$listing")"
  expect "only admin, backend, nginx, umami and webapp publish a port" "admin backend nginx umami webapp" "$(grep -E ':[0-9]+->' "$listing" | awk '{print $1}' | sort -u | tr '\n' ' ' | sed 's/ $//')"
}

fresh_umami_nginx() {
  section "(1) the public Umami port (nginx 3003)"
  expect "GET /script.js is served" "200" "$(http_code "http://127.0.0.1:$S_N3/script.js")"
  local post
  post="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$S_N3/api/send")"
  case "$post" in 404|403|502|503) bad "POST /api/send reaches Umami (got $post)" ;; *) ok "POST /api/send reaches Umami (status $post)" ;; esac
  post="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '[]' "http://127.0.0.1:$S_N3/api/batch")"
  case "$post" in 404|403|502|503) bad "POST /api/batch reaches Umami (got $post)" ;; *) ok "POST /api/batch reaches Umami (status $post)" ;; esac
  expect "GET /api/send is refused" "403" "$(http_code "http://127.0.0.1:$S_N3/api/send")"
  expect "the login page is a 404" "404" "$(http_code "http://127.0.0.1:$S_N3/login")"
  expect "the root is a 404" "404" "$(http_code "http://127.0.0.1:$S_N3/")"
  expect "the API login is a 404" "404" "$(http_code -X POST -d '{}' "http://127.0.0.1:$S_N3/api/auth/login")"
  expect "the heartbeat is a 404" "404" "$(http_code "http://127.0.0.1:$S_N3/api/heartbeat")"
}

fresh_portal() {
  section "(1) the portal: gate, wizard, sign-in, pages, a task"
  mail_attach
  expect "the portal answers /healthz on the loopback" "200" "$(http_code "$(portal)/healthz")"
  cl negatives | absorb
  V4_SETUP_TOKEN="$FRESH_TOKEN" cl wizard --fingerprint "$FRESH_FP" | absorb
  cl signin | absorb
  cl pages --expect-services "backend,auth$google_reporting" | absorb
  cl task --task keyset.verify --param targets__responses=on --timeout 120 | tee "$work/fresh.task" | absorb
  expect "the task runner executed the read-only task to success" "task_state=succeeded" "$(grep -o 'task_state=[a-z]*' "$work/fresh.task" | head -n 1)"
  if ! grep -q 'task_state=succeeded' "$work/fresh.task"; then dc logs --tail 25 task-runner 2>&1 | cut -c1-220 | sed 's/^/        runner: /'; fi
  expect "the audit log chain verifies (python -m backend.admin audit-verify)" "0" "$(admin_cli audit-verify >/dev/null 2>&1; echo $?)"
  expect "/setup is still a bare 404 after sign-in" "404" "$(http_code "$(portal)/setup")"
}

# (4) --------------------------------------------------------------------------------------------------
part_negatives() {
  section "(4) negatives"
  if [ "$fresh_done" != 1 ]; then
    skipped "the runtime negatives need the fresh stack of part 1 (run with --fresh --negatives)"
  else
    negatives_runtime
  fi
  negatives_rendered
}

negatives_runtime() {
  local admin_id
  admin_id="$(dc ps -q admin | head -n 1)"
  local net="${S_PROJECT}_default"
  # a sibling container on the default network
  local sib
  sib="$(docker run --rm --network "$net" curlimages/curl:latest -s -o /dev/null -m 5 -w '%{http_code}' http://admin:8000/healthz 2>/dev/null; echo "rc=$?")"
  case "$sib" in *"rc=6"*|*"rc=7"*|*"rc=28"*|*"000"*) ok "a sibling container cannot resolve or reach the admin service by name" ;; *) bad "a sibling container cannot reach the admin service by name ($sib)" ;; esac
  sib="$(docker run --rm --network "$net" --add-host=host.docker.internal:host-gateway curlimages/curl:latest -s -o /dev/null -m 5 -w '%{http_code}' "http://host.docker.internal:$S_ADMIN_PORT/healthz" 2>/dev/null; echo "rc=$?")"
  case "$sib" in *"rc=7"*|*"rc=28"*|*"rc=52"*|*"rc=56"*|*"000"*) ok "a sibling container cannot reach the portal through the host's address either" ;; *) bad "a sibling container cannot reach the portal through the host ($sib)" ;; esac
  local admin_ip
  admin_ip="$(docker inspect -f "{{(index .NetworkSettings.Networks \"${S_PROJECT}_admin-edge\").IPAddress}}" "$admin_id")"
  sib="$(docker run --rm --network "$net" curlimages/curl:latest -s -o /dev/null -m 5 -w '%{http_code}' "http://$admin_ip:8000/healthz" 2>/dev/null; echo "rc=$?")"
  case "$sib" in *"200"*) bad "a sibling container reached the admin-edge address $admin_ip ($sib)" ;; *) ok "a sibling container cannot reach the admin-edge address" ;; esac
  # a Host outside the allowlist
  expect "a Host outside the allowlist gets a bare 404" "404" "$(http_code -H 'Host: attacker.example' "$(portal)/login")"
  expect "the right name with another port gets a bare 404" "404" "$(http_code -H "Host: 127.0.0.1:1" "$(portal)/login")"
  expect "no body is returned for it" "0" "$(curl -s -m 5 -H 'Host: attacker.example' "$(portal)/login" | wc -c | tr -d ' ')"
  # the admin port is not on 0.0.0.0, and not on the LAN address
  expect "docker publishes the admin port on 127.0.0.1 only" "127.0.0.1:$S_ADMIN_PORT" "$(docker port "$admin_id" 8000/tcp | tr '\n' ' ' | sed 's/ $//')"
  expect "nothing listens on 0.0.0.0 or :: at the admin port" "0" "$(ss -Hltn "sport = :$S_ADMIN_PORT" 2>/dev/null | awk '{print $4}' | grep -cE '^(0\.0\.0\.0|\*|\[::\]):')"
  local lan
  lan="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -n 1)"
  if [ -n "$lan" ] && [ "${lan#127.}" = "$lan" ]; then
    local rc=0
    curl -s -o /dev/null -m 4 "http://$lan:$S_ADMIN_PORT/healthz" || rc=$?
    expect "the LAN address $lan refuses the admin port (curl exit 7)" "7" "$rc"
  else
    skipped "no LAN address on this host"
  fi
  # the master key: which running containers hold it (docker inspect, by value)
  local key holders id svc
  key="$(grep '^SETTINGS_MASTER_KEY=' "$S_DIR/.env" | cut -d= -f2-)"
  holders=""
  for id in $(dc ps -aq); do
    svc="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id")"
    if docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$id" | grep -qF "$key"; then holders="$holders $svc"; fi
  done
  # shellcheck disable=SC2086  # the container names are words
  holders="$(printf '%s\n' $holders | sort -u | tr '\n' ' ' | sed 's/ $//')"
  expect "docker inspect: the master key is in the four store readers' environment (those running), the admin service and the task runner only" \
    "$(printf '%s\n' admin auth backend $google_service jobs-worker task-runner | sort | tr '\n' ' ' | sed 's/ $//')" "$holders"
  local fileholders=""
  for f in .env.webapp .env.worker .env.typeform .env.deployment; do
    grep -qF "$key" "$S_DIR/$f" 2>/dev/null && fileholders="$fileholders $f"
  done
  expect "no env file except the root .env holds the master key" "" "$fileholders"
}

negatives_rendered() {
  local tmp="$work/render" env_file="$work/render.env" rendered
  mkdir -p "$tmp"; chmod 700 "$tmp"
  cp "$root/docker-compose.deployment.yml" "$tmp/"
  # the shipped template, as deploy.sh creates .env.deployment from it (never this checkout's own file)
  ( umask 077; cp "$root/.env.deployment.example" "$tmp/.env.deployment" )
  # the variables the compose file marks required, with throw-away values, plus the operator's
  ( umask 077
    # shellcheck disable=SC2016  # the pattern is literal text
    for v in $(grep -o '\${[A-Z_]*:?' "$root/docker-compose.deployment.yml" | tr -d '${:?' | sort -u); do
      echo "$v=$(openssl rand -hex 12)"
    done
    echo "PLATFORM_ADMIN_EMAILS=$admin_email"
    echo "ADMIN_ALLOWED_IPS=127.0.0.1/32" ) > "$env_file"
  rendered="$(hermetic docker compose --env-file "$env_file" -f "$tmp/docker-compose.deployment.yml" config --format json 2>"$work/render.err")"
  if [ -n "$rendered" ]; then
    ok "docker compose config renders a minimal .env (the operator's two values plus what deploy.sh generates)"
  else
    bad "docker compose config renders a minimal .env"
    return
  fi
  local props
  props="$(printf '%s' "$rendered" | uv run --no-project --quiet python -I -c '
import json, sys
s = json.load(sys.stdin)["services"]
env = lambda n: s[n].get("environment") or {}
print("published=" + ",".join(sorted("%s=%s:%s" % (n, p.get("host_ip") or "*", p["published"]) for n, b in s.items() for p in b.get("ports") or [])))
print("holders=" + ",".join(sorted(n for n in s if "SETTINGS_MASTER_KEY" in env(n))))
print("worker=" + ",".join(sorted(env("worker"))))
print("webapp_secret_names=" + ",".join(sorted(k for k in env("webapp") if k.endswith(("SECRET", "PASSWORD", "KEY")) or k in ("DATABASE_URL", "MONGO_URI"))))
print("typeform_master_key=%s" % ("SETTINGS_MASTER_KEY" in env("integrations-typeform")))
print("store_required=" + ",".join(sorted(n for n in s if env(n).get("SETTINGS_STORE") == "required")))' 2>/dev/null)"
  gotp() { printf '%s\n' "$props" | grep "^$1="; }
  expect "rendered (unmodified compose file): the published ports are exactly the documented ones; 7234, 27017 and 5432 are not among them, 3004 and the admin port are on 127.0.0.1" \
    "published=admin=127.0.0.1:8100,backend=*:8000,nginx=*:3001,nginx=*:3002,nginx=*:3003,umami=127.0.0.1:3004,webapp=*:3000" "$(gotp published)"
  expect "rendered: the master key is held by the four store readers, the admin service and the task runner only" \
    "holders=admin,auth,backend,integrations-googleform,jobs-worker,task-runner" "$(gotp holders)"
  expect "rendered: the worker's environment has no master key and no database URL" "worker=AES_HEX_KEY,API_KEY,TEMPORAL_SERVER_URL" "$(gotp worker)"
  expect "rendered: the webapp's environment names no secret" "webapp_secret_names=" "$(gotp webapp_secret_names)"
  # a secret in .env.deployment reaches the four store readers and nothing else (compose inlines env_file)
  printf 'STRIPE_SECRET=DUMMY-env-deployment-secret\nMONGO_URI=mongodb://root:DUMMY-env-deployment-secret@mongodb:27017\n' > "$tmp/.env.deployment"
  printf 'UNSPLASH_ACCESS_KEY=DUMMY-webapp\n' > "$tmp/.env.webapp"
  printf 'COOKIE_DOMAIN=example.test\n' > "$tmp/.env.worker"
  expect "rendered: a secret in .env.deployment reaches the four store readers only" "auth,backend,integrations-googleform,jobs-worker" \
    "$(hermetic docker compose --env-file "$env_file" -f "$tmp/docker-compose.deployment.yml" config --format json 2>/dev/null \
      | uv run --no-project --quiet python -I -c '
import json, sys
s = json.load(sys.stdin)["services"]
print(",".join(sorted(n for n, b in s.items() if "DUMMY-env-deployment-secret" in json.dumps(b))))' 2>/dev/null)"
  expect "rendered: Typeform has no master key" "typeform_master_key=False" "$(gotp typeform_master_key)"
  expect "rendered: the four store readers require the store" "store_required=auth,backend,integrations-googleform,jobs-worker" "$(gotp store_required)"
  # the literal four-variable file (the operator's two, the master key and one password) is refused by design
  local four="$work/four.env" err
  printf 'PLATFORM_ADMIN_EMAILS=%s\nADMIN_ALLOWED_IPS=127.0.0.1/32\nSETTINGS_MASTER_KEY=%s\nAPP_POSTGRES_PASSWORD=x\n' "$admin_email" "$(openssl rand -base64 24)" > "$four"
  err="$(hermetic docker compose --env-file "$four" -f "$tmp/docker-compose.deployment.yml" config -q 2>&1 || true)"
  case "$err" in *"set by deploy.sh in the root .env"*) ok "four variables alone are refused with the pointer to deploy.sh (compose never starts a database without passwords)" ;; *) bad "four variables alone are refused with the pointer to deploy.sh" ;; esac
}

# (2) and (3) ------------------------------------------------------------------------------------------
# The previous release's host needs `docker-compose`; this host may have only the plugin, so the old
# deploy.sh runs with a one-line shim for it (the release's own script is unchanged).
make_shim() {
  mkdir -p "$work/shim"
  printf '#!/bin/sh\nexec docker compose "$@"\n' > "$work/shim/docker-compose"
  chmod +x "$work/shim/docker-compose"
}

ensure_old_images() {
  local image
  for image in "bettercollected/backend:$old_tag" "bettercollected/auth:$old_tag" "bettercollected/temporal-worker:$old_tag" \
      "${V4_CHECK_OLD_WEBAPP:-bettercollected/webapp:$old_tag}"; do
    docker image inspect "$image" >/dev/null 2>&1 && continue
    enough_disk "pull $image" || return 1
    echo "  pulling $image"
    docker pull -q "$image" >/dev/null || { echo "could not pull $image" >&2; return 1; }
    pulled_images+=("$image")
  done
}

# The shipped 3.x .env.deployment carries the repository's published keys. An operator replaced them;
# so does the check (new random values), keeping the same names.
OLD_KEYSET=""; OLD_JWT=""; OLD_FERNET=""
old_keys() {
  local f="$S_DIR/.env.deployment" tmp
  OLD_FERNET="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
  OLD_JWT="$(openssl rand -hex 32)"
  OLD_KEYSET="$(docker run --rm --entrypoint /api/backend/.venv/bin/python "bettercollected/backend:$old_tag" -I -c '
import base64, io, tink
from tink import aead, cleartext_keyset_handle
aead.register()
handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
buffer = io.StringIO()
cleartext_keyset_handle.write(tink.JsonKeysetWriter(buffer), handle)
print(base64.b64encode(buffer.getvalue().encode()).decode())' 2>/dev/null | tr -d '\n')"
  [ -n "$OLD_KEYSET" ] || return 1
  tmp="$(mktemp -p "$work")"
  grep -vE '^(AUTH_AES_HEX_KEY|AUTH_JWT_SECRET|AES_HEX_KEY|GOOGLE_AES_KEY|MASTER_ENCRYPTION_KEYSET)=' "$f" > "$tmp"
  { echo "AUTH_AES_HEX_KEY=$OLD_FERNET"; echo "AUTH_JWT_SECRET=$OLD_JWT"; echo "AES_HEX_KEY=$OLD_FERNET"
    echo "GOOGLE_AES_KEY=$OLD_FERNET"; echo "MASTER_ENCRYPTION_KEYSET=$OLD_KEYSET"
    # the 3.x backend does not start without it and the shipped file has no line for it
    echo "UNSPLASH_ACCESS_KEY=dummy-photo-key"; } >> "$tmp"
  cat "$tmp" > "$f"; rm -f "$tmp"; chmod 600 "$f"
}

# the previous release's files over the directory (git pull / checkout of a tag), keeping the
# operator's own files: .env, .env.deployment and the per-service env files (the operator copies
# .env.deployment aside and back across the update, docs/admin-service.md "Before you start")
overlay_layout() { # overlay_layout new|old
  local layout="$1" tmp="$work/overlay-$1" path
  rm -rf "$tmp"
  copy_layout "$layout" "$tmp" || return 1
  for path in "${deploy_paths[@]}" .env.deployment.example; do
    rm -rf "${S_DIR:?}/$path"
    [ -e "$tmp/$path" ] && cp -a "$tmp/$path" "$S_DIR/"
  done
  rewrite_compose "$S_DIR" "$layout"
  read_ports
}

old_deploy() { # old_deploy <out>: the previous release's deploy.sh, no terminal
  ( cd "$S_DIR" && timeout 1800 "${HERM[@]}" PATH="$work/shim:$PATH" ./deploy.sh ) > "$1" 2>&1
}

mongo_counts() { # workspaces,forms,responses,users
  dc exec -T mongodb mongosh --quiet -u root -p root --authenticationDatabase admin --eval \
    'const b=db.getSiblingDB("bettercollected_backend"), a=db.getSiblingDB("bettercollected_auth"); print([b.workspaces.countDocuments(), b.forms.countDocuments(), b.form_responses.countDocuments(), a.users.countDocuments()].join(","))' \
    2>/dev/null | tr -d '\r' | tail -n 1
}

store_snapshot() { # a digest of the settings store (versions of every key, never values) and the keys' history
  local keys="AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET AUTH_INTERNAL_NOTIFY_KEY TEMPORAL_API_KEY" k
  for k in $keys; do printf '%s %s\n' "$k" "$(admin_cli settings-history "$k" 2>/dev/null | tail -n 1 | tr -d '\r')"; done
  dc exec -T app-postgres psql -U bettercollected -d bettercollected -Atc \
    "select count(*) || ' rows, last change ' || coalesce(max(updated_at)::text, '-') from settings.${SETTINGS_TABLE:-entries}" 2>/dev/null | tr -d '\r'
}

get_setup_token() {
  ( cd "$S_DIR" && timeout 300 "${HERM[@]}" script -qefc "./deploy.sh setup-token" /dev/null < /dev/null ) 2>&1 | tr -d '\r' \
    | grep -E '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$' | head -n 1
}

wait_stack() { # wait_stack <seconds>: backend and auth healthy
  wait_state backend healthy "$1" && wait_state auth healthy "$1"
}

part_upgrade() {
  section "(2) upgrade from $old_tag"
  enough_disk "upgrade" || { bad "upgrade not started (disk)"; return; }
  git -C "$root" rev-parse -q --verify "refs/tags/$old_tag" >/dev/null || { bad "the tag $old_tag is not in this checkout"; return; }
  make_shim
  ensure_old_images || { bad "the previous release's images could not be pulled"; return; }
  new_stack u old || { bad "upgrade stack could not be prepared"; return; }
  echo "  project $S_PROJECT (the $old_tag layout: its compose file, .env.deployment and images)"
  old_keys || { bad "keys for the old stack"; return; }
  local out="$work/old-deploy.out"
  echo "  the old ./deploy.sh ..."
  old_deploy "$out" || { bad "the previous release's deploy.sh ran"; tail -n 20 "$out"; return; }
  ok "the previous release's deploy.sh ran"
  wait_stack 420 || { bad "the old stack became healthy"; service_state; return; }
  ok "the old stack is healthy (backend, auth)"
  expect "the old layout publishes Temporal's port (as 3.x did)" "1" "$(docker ps --filter "label=com.docker.compose.project=$S_PROJECT" --format '{{.Ports}}' | grep -c ':[0-9]*->7233/tcp')"
  # fake data through the release's own models and encryption
  local seeded
  seeded="$(dc run --rm --no-deps -T -v "$root/scripts/v4_check_seed.py:/seed.py:ro" backend /api/backend/.venv/bin/python /seed.py 2>&1 | grep '^seeded ' | tail -n 1)"
  expect "dummy workspaces, forms, responses and users were seeded" "seeded workspaces=2 forms=3 responses=6 users=4" "$seeded"
  local pg_rc=0
  dc exec -T app-postgres psql -U bettercollected -d bettercollected -v ON_ERROR_STOP=1 -q >/dev/null 2>"$work/pguser.err" <<'SQL' || pg_rc=$?
INSERT INTO auth.users (id, doc, _bc_checksum)
VALUES ('0123456789abcdef01234567', '{"_id": {"$oid": "0123456789abcdef01234567"}, "email": "pg-user@example.test"}'::jsonb, 'acceptance-check');
SQL
  expect "a dummy user row gives the Postgres side data (as a dual-write stack has)" "0" "$pg_rc"
  local before after
  before="$(mongo_counts)"
  expect "the old stack holds the seeded documents (workspaces,forms,responses,users)" "2,3,6,4" "$before"
  collect_secrets "$work/upgrade.secrets"
  { echo "$OLD_KEYSET"; echo "$OLD_JWT"; echo "$OLD_FERNET"; } >> "$work/upgrade.secrets"

  # the operator updates the files (git pull) and adds the one new value; the harness adds its ports
  overlay_layout new || { bad "the new files over the old stack"; return; }
  write_root_env || return
  printf 'TASK_RUNNER_MONGO_URI=mongodb://root:root@mongodb:27017\n' >> "$S_DIR/.env"
  echo "  the new ./deploy.sh on a terminal ..."
  local rc=0
  run_deploy "$work/upgrade-deploy.out" || rc=$?
  expect "the new deploy.sh exits 0 on the 3.x stack" "0" "$rc"
  untimed "$work/upgrade-deploy.out" | tr -d '\r' > "$work/upgrade-deploy.plain"
  if [ "$rc" != 0 ]; then tail -n 40 "$work/upgrade-deploy.plain"; return; fi
  local plain="$work/upgrade-deploy.plain"
  check "it went the import path (settings imported from the files)" grep -q '^Importing the settings found in the compose configuration' "$plain"
  expect "it did not bootstrap keys" "0" "$(grep -c '^generated=' "$plain")"
  expect "it reported no conflict" "0" "$(grep -c '^conflict ' "$plain")"
  check "it compared the store with the files, with no difference" grep -q '^Comparing the store with the files' "$plain"
  expect "it printed no setup token and no fingerprint notice (not a new install)" "0" \
    "$(grep -cE '^([A-Z2-7]{4}(-[A-Z2-7]{4}){7}|Master key fingerprint.*)$' "$plain")"
  grep -v -E '^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$' "$plain" > "$work/upgrade-deploy.notoken"
  expect "no secret value (old or generated) is in the deploy output" "0" "$(secret_hits "$work/upgrade.secrets" "$work/upgrade-deploy.notoken")"
  wait_stack 300   # the deploy recreates the backend last (Umami's login): give it time
  local unhealthy
  unhealthy="$(service_state | grep -vE '^(mongo-seed)=' | grep -vE '=(healthy|running)$' || true)"
  expect "every service is healthy or running after the upgrade" "" "$unhealthy"
  for svc in admin task-runner jobs-worker document-sandbox; do
    case "$(service_state | grep "^$svc=")" in "$svc=healthy"|"$svc=running") ok "$svc runs (new in the start list)" ;; *) bad "$svc runs" ;; esac
  done
  expect "Temporal's port is not published any more" "0" "$(docker ps --filter "label=com.docker.compose.project=$S_PROJECT" --format '{{.Ports}}' | grep -c ':[0-9]*->7233/tcp')"
  expect "Umami's dashboard moved to 127.0.0.1 (3004) and nginx serves the tracker only" "404" "$(http_code "http://127.0.0.1:$S_N3/login")"
  expect "Umami rejects its built-in login after the upgrade" "401" "$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"username":"admin","password":"umami"}' "http://127.0.0.1:$S_UMAMI/api/auth/login")"
  expect "the settings differ from the files nowhere (settings-drift exits 0)" "0" "$(sdeploy settings-drift >"$work/drift.out" 2>&1; echo $?)"
  expect "settings-drift reports no differing key" "0" "$(grep -c '^differs ' "$work/drift.out")"
  # data intact and decryptable
  after="$(mongo_counts)"
  expect "the documents are all still there" "$before" "$after"
  # the keys: imported, not generated
  local k exported="$S_DIR/keys-export.env" stored
  rm -f "$exported"
  if sdeploy settings-env-export --keys MASTER_ENCRYPTION_KEYSET,AUTH_JWT_SECRET,AUTH_AES_HEX_KEY --out "$exported" >/dev/null 2>&1; then
    stored="$(sed -E 's/^[^=]*=//; s/^"(.*)"$/\1/' "$exported" | sort | tr '\n' ' ')"
    expect "the stored keyset, session secret and encryption key are the 3.x stack's own (unchanged)" \
      "$(printf '%s\n' "$OLD_KEYSET" "$OLD_JWT" "$OLD_FERNET" | sort | tr '\n' ' ')" "$stored"
    rm -f "$exported"
  else
    bad "the stored keys could be exported for comparison"
  fi
  for k in AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET; do
    expect "$k has exactly one stored version (the import)" "versions=1" "$(sdeploy settings-history "$k" 2>/dev/null | tail -n 1 | tr -d '\r')"
  done
  # bootstrap-keys refuses on this stack
  local boot
  boot="$(admin_cli bootstrap-keys 2>&1; echo "rc=$?")"
  case "$boot" in *"refused: stack_has_data"*"rc=1"*|*"refused: stack_has_data"*"rc=2"*) ok "bootstrap-keys refuses on this stack (stack_has_data)" ;; *) bad "bootstrap-keys refuses on this stack with stack_has_data ($(printf '%s' "$boot" | tr '\n' ' ' | cut -c1-160))" ;; esac
  expect "and stored no new key" "versions=1" "$(sdeploy settings-history MASTER_ENCRYPTION_KEYSET 2>/dev/null | tail -n 1 | tr -d '\r')"
  # prune: a dry run reports and changes nothing
  local env_sum dep_sum
  env_sum="$(sha256sum "$S_DIR/.env" | cut -d' ' -f1)"; dep_sum="$(sha256sum "$S_DIR/.env.deployment" | cut -d' ' -f1)"
  local prune
  prune="$(sdeploy settings-prune 2>&1; echo "rc=$?")"
  printf '%s\n' "$prune" | grep -v -F "$OLD_KEYSET" > "$work/prune.out"
  check "settings-prune (dry run) lists what it would remove" grep -q 'would_prune' "$work/prune.out"
  check "settings-prune (dry run) says nothing was written" grep -q 'dry run: nothing written' "$work/prune.out"
  expect "settings-prune (dry run) exits 0" "rc=0" "$(tail -n 1 "$work/prune.out")"
  expect "settings-prune (dry run) prints no secret value" "0" "$(secret_hits "$work/upgrade.secrets" "$work/prune.out")"
  expect "the dry run changed neither .env nor .env.deployment" "$env_sum $dep_sum" "$(sha256sum "$S_DIR/.env" | cut -d' ' -f1) $(sha256sum "$S_DIR/.env.deployment" | cut -d' ' -f1)"
  expect "the dry run left no .pruned or .pre-v4 file" "0" "$(find "$S_DIR" -maxdepth 1 \( -name "*.pruned" -o -name "*.pre-v4.*" \) | wc -l | tr -d " ")"
  expect "the MAIL, SSO and typeform-only values are kept (never offered for removal)" "0" "$(grep -cE '^ +would_prune (MAIL_|SSO_)' "$work/prune.out")"
  # conflicts are reported, never chosen: the two readers of SENTRY_DEBUG disagree (a hand-edited compose file)
  cp "$S_DIR/docker-compose.deployment.yml" "$work/compose.good"
  sed -i -E '/^  backend:/,/^    env_file:/ s/^    environment:$/&\n      SENTRY_DEBUG: "false"/; /^  auth:/,/^    env_file:/ s/^    environment:$/&\n      SENTRY_DEBUG: "true"/' "$S_DIR/docker-compose.deployment.yml"
  local conflict
  conflict="$(sdeploy settings-import --dry-run 2>&1; echo "rc=$?")"
  case "$conflict" in *"conflict SENTRY_DEBUG"*) ok "services that disagree on a value are reported as a conflict" ;; *) bad "services that disagree on a value are reported as a conflict" ;; esac
  case "$conflict" in *"rc=0") bad "a conflict makes the import exit non-zero" ;; *) ok "a conflict makes the import exit non-zero" ;; esac
  case "$conflict" in *"imported SENTRY_DEBUG"*) bad "the import chose a side" ;; *) ok "the import did not choose a side" ;; esac
  cp "$work/compose.good" "$S_DIR/docker-compose.deployment.yml"
  expect "nothing was stored for the conflicting key" "versions=0" "$(sdeploy settings-history SENTRY_DEBUG 2>/dev/null | tail -n 1 | tr -d '\r')"

  upgrade_portal
  UPGRADE_COUNTS="$before"
  UPGRADE_SNAPSHOT="$(store_snapshot)"
  part_rollback_stack
}

upgrade_portal() {
  section "(2) the upgraded stack through the portal"
  mail_attach
  local token
  token="$(get_setup_token)"
  check "setup-token shows a token on a terminal" test -n "$token"
  V4_SETUP_TOKEN="$token" cl wizard | absorb
  cl signin | absorb
  cl pages --expect-services backend,auth | absorb
  cl task --task responses.check_undecryptable --param stores=mongo --timeout 180 | tee "$work/upgrade.task" | absorb
  if ! grep -q 'task_state=succeeded' "$work/upgrade.task"; then dc logs --tail 25 task-runner 2>&1 | cut -c1-220 | sed 's/^/        runner: /'; fi
  expect "the dry run of responses.check_undecryptable succeeded" "task_state=succeeded" "$(grep -o 'task_state=[a-z]*' "$work/upgrade.task" | head -n 1)"
  check "it scanned the seeded responses (6) and none fails to decrypt" grep -qE 'task_event=.*responses=6.*does_not_decrypt=0|task_event=.*does_not_decrypt=0.*responses=6' "$work/upgrade.task"
}

UPGRADE_COUNTS=""; UPGRADE_SNAPSHOT=""
part_rollback_stack() {
  want 3 || return 0
  section "(3) rollback"
  # 3a: the store off, the new images
  printf 'SETTINGS_STORE=off\n' >> "$S_DIR/.env"
  local rc=0
  run_deploy "$work/rollback-off.out" || rc=$?
  expect "deploy.sh with SETTINGS_STORE=off exits 0" "0" "$rc"
  wait_stack 300 || bad "the stack became healthy with the store off"
  expect "the services run with SETTINGS_STORE=off" "off" "$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$(dc ps -q backend | head -n 1)" | sed -n 's/^SETTINGS_STORE=//p')"
  expect "the backend serves from environment values" "200" "$(http_code "http://127.0.0.1:$S_BACKEND/api/v1/public/v1/openapi.json")"
  expect "the auth service answers through the backend (signed-out status is 401, not 5xx)" "401" "$(http_code "http://127.0.0.1:$S_BACKEND/api/v1/auth/status")"
  expect "the data is intact" "$UPGRADE_COUNTS" "$(mongo_counts)"
  expect "the store is untouched" "$UPGRADE_SNAPSHOT" "$(store_snapshot)"
  expect "settings-drift is still clean" "0" "$(sdeploy settings-drift >/dev/null 2>&1; echo $?)"
  # 3b: back on
  sed -i '/^SETTINGS_STORE=off$/d' "$S_DIR/.env"
  rc=0
  run_deploy "$work/rollback-on.out" || rc=$?
  expect "deploy.sh with the store back on exits 0" "0" "$rc"
  wait_stack 300 || bad "the stack became healthy with the store back on"
  expect "the services read the store again" "required" "$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$(dc ps -q backend | head -n 1)" | sed -n 's/^SETTINGS_STORE=//p')"
  expect "the backend serves again" "200" "$(http_code "http://127.0.0.1:$S_BACKEND/api/v1/public/v1/openapi.json")"
  expect "the data is intact" "$UPGRADE_COUNTS" "$(mongo_counts)"
  expect "the store is still untouched" "$UPGRADE_SNAPSHOT" "$(store_snapshot)"
  # 3c: the previous release's files and images over the upgraded stack
  section "(3) rollback to the previous release ($old_tag files and images)"
  overlay_layout old || { bad "the previous release's files"; return; }
  local old_out="$work/rollback-old.out"
  if old_deploy "$old_out"; then ok "the previous release's deploy.sh ran over the upgraded stack"; else bad "the previous release's deploy.sh ran over the upgraded stack"; tail -n 20 "$old_out"; fi
  if wait_stack 420; then
    ok "backend and auth of $old_tag are healthy on the upgraded database"
  else
    bad "backend and auth of $old_tag are healthy on the upgraded database"
    for c in backend auth; do dc logs --tail 5 "$c" 2>&1 | sed 's/^/        /' | cut -c1-200; done
  fi
  expect "the previous release's backend serves (its API answers, and its docs page, which it pinned on, too)" "401 200" "$(http_code "http://127.0.0.1:$S_BACKEND/api/v1/auth/status") $(http_code "http://127.0.0.1:$S_BACKEND/api/v1/docs")"
  expect "the data is intact" "$UPGRADE_COUNTS" "$(mongo_counts)"
  expect "the previous release's images are the ones running" "bettercollected/backend:$old_tag" "$(docker inspect -f '{{.Config.Image}}' "$(dc ps -q backend | head -n 1)")"
  # and forward again
  overlay_layout new || { bad "the new files again"; return; }
  rc=0
  run_deploy "$work/rollback-forward.out" || rc=$?
  expect "the new deploy.sh runs again over it (exit 0)" "0" "$rc"
  wait_stack 300 || bad "the stack became healthy again on the new release"
  expect "the data is still intact" "$UPGRADE_COUNTS" "$(mongo_counts)"
  expect "the store is still untouched" "$UPGRADE_SNAPSHOT" "$(store_snapshot)"
  expect "settings-drift is clean again" "0" "$(sdeploy settings-drift >/dev/null 2>&1; echo $?)"
}

# prepare images, run the parts ------------------------------------------------------------------------
FRESH_FP=""; FRESH_TOKEN=""; FRESH_STORE_VERSIONS=""
if want 1 || want 2 || want 3 || want 4; then prepare_images; fi
want 1 && part_fresh
want 4 && part_negatives
if want 2 || want 3; then part_upgrade; fi   # the rollback (3) runs on the upgraded stack

section "result"
echo "== $pass passed, $fail failed, $skip skipped in $((SECONDS - started)) s"
[ "$fail" -eq 0 ]
