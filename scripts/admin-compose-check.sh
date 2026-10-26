#!/usr/bin/env bash
# Acceptance check for the internal admin service's compose wiring, against REAL
# containers (docs/admin-service.md). Safe on a developer machine: it uses its own
# compose project, random free loopback ports, a pinned network subnet that is not
# in use, throw-away volumes and secrets, and removes everything when it exits. It
# never touches a running stack and publishes nothing but the admin port on 127.0.0.1.
#
#   scripts/admin-compose-check.sh
#
# Besides the admin service it checks the deployment properties around it: a
# minimal operator-provided .env renders, no internal port is published, no
# Temporal service is part of the stack, no service outside the settings-store readers
# receives the secrets of a populated .env.deployment, no built-in credentials
# remain on a new stack (the Mongo seed leaves no seeduser; Umami's dashboard is not
# published, nginx passes only its tracker), and the host commands deploy.sh runs
# (bootstrap-keys, import, drift) work through compose.
#
# Needs: bash, docker (with compose 2.24.4 or newer), curl, openssl. By default it builds the
# backend image from this checkout (tag bc-admin-check:local, replaced if it exists, removed afterwards).
# To test an existing image instead: ADMIN_CHECK_IMAGE=<image> (never removed). KEEP=1 leaves the project up.
set -uo pipefail
# same as deploy.sh: see the note there about containers on two networks
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 1
for tool in docker curl openssl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing tool: $tool" >&2; exit 2; }
done
docker compose version >/dev/null 2>&1 || { echo "docker compose v2 is required" >&2; exit 2; }

project="bcadmincheck$$"
work="$(mktemp -d)"
image="${ADMIN_CHECK_IMAGE:-bc-admin-check:local}"
built_image=0
pass=0
fail=0
skip=0
envfile=""

compose_files=(-f "$root/docker-compose.deployment.yml" -f "$work/override.yml")
dc() { docker compose -p "$project" "${compose_files[@]}" --env-file "$envfile" "$@" 2> >(grep -v "level=warning" >&2); }

extra_containers=()
extra_networks=()
cleanup() {
  if [ "${KEEP:-}" = "1" ]; then
    echo "KEEP=1: project $project left running (work dir $work)"
    return
  fi
  if [ -n "$envfile" ]; then
    dc down -v --remove-orphans --timeout 5 >/dev/null 2>&1
  fi
  if [ "${#extra_containers[@]}" -gt 0 ]; then docker rm -f "${extra_containers[@]}" >/dev/null 2>&1; fi
  if [ "${#extra_networks[@]}" -gt 0 ]; then docker network rm "${extra_networks[@]}" >/dev/null 2>&1; fi
  if [ "$built_image" = 1 ]; then docker rmi "$image" >/dev/null 2>&1; fi
  rm -rf "$work"
}
trap cleanup EXIT

ok() { pass=$((pass + 1)); echo "  PASS  $1"; }
bad() { fail=$((fail + 1)); echo "  FAIL  $1"; }
check() { # check "<description>" <command...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi
}
expect() { # expect "<description>" "<expected>" "<actual>"
  if [ "$2" = "$3" ]; then ok "$1 ($3)"; else bad "$1 (expected $2, got $3)"; fi
}

free_port() {
  local p
  for _ in $(seq 1 50); do
    p=$((8100 + RANDOM % 900))
    if ! (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then echo "$p"; return; fi
  done
  echo "no free port found" >&2
  return 1
}

free_subnet() { # a /29 inside 172.30.0.0/16 that no Docker network uses
  local used third
  used="$(docker network ls -q | xargs -r docker network inspect \
    --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null)"
  for _ in $(seq 1 50); do
    third=$((100 + RANDOM % 150))
    case " $used " in *" 172.30.$third."*) continue ;; esac
    echo "172.30.$third.0/29"
    return
  done
  echo "no free subnet found" >&2
  return 1
}

# python in the backend image: print the HTTP status or the error class
probe_py='
import sys, urllib.request, urllib.error
try:
    r = urllib.request.urlopen(sys.argv[1], timeout=4)
    print("status:%d" % r.status)
except urllib.error.HTTPError as e:
    print("status:%d" % e.code)
except Exception as e:
    print("error:%s" % type(e).__name__)
'
sibling_probe() { # a throw-away container on the default network
  docker run --rm --network "${project}_default" --user 65534:65534 \
    --entrypoint /api/backend/.venv/bin/python "$image" -I -c "$probe_py" "$@" 2>/dev/null | tail -n 1
}

http_code() { curl -s -o /dev/null -m 5 -w '%{http_code}' "$@" 2>/dev/null; }

wait_health() { # wait_health <seconds>; prints the final status
  local deadline=$((SECONDS + $1)) st=""
  while [ "$SECONDS" -lt "$deadline" ]; do
    st="$(docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q admin)" 2>/dev/null)"
    if [ "$st" = "healthy" ]; then break; fi
    sleep 2
  done
  echo "$st"
}

# --- image and throw-away settings ---------------------------------------------------
echo "== setup (project $project)"
if [ -z "${ADMIN_CHECK_IMAGE:-}" ]; then
  # always test this checkout: drop a leftover tag from an earlier run first
  docker rmi "$image" >/dev/null 2>&1
  echo "  building $image from backend/Dockerfile (a few minutes)"
  docker build -q -t "$image" -f backend/Dockerfile . >/dev/null || { echo "image build failed" >&2; exit 2; }
  built_image=1
elif ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "ADMIN_CHECK_IMAGE $image does not exist" >&2
  exit 2
fi
port="$(free_port)" || exit 2
subnet="$(free_subnet)" || exit 2
gateway="${subnet%.0/29}.1"
admin_pw="$(openssl rand -hex 16)"
mig_pw="$(openssl rand -hex 16)"
master_key="$(openssl rand -base64 48 | tr -d '\n')"
umami_pw="$(openssl rand -hex 16)"
mongo_pw="$(openssl rand -hex 16)"

# The four services that read .env.deployment get a copy of the shipped template, never
# the operator's own (untracked) .env.deployment this checkout may have (`!override`
# replaces the list; Compose 2.24.4 or newer).
( umask 077; cp "$root/.env.deployment.example" "$work/.env.deployment" )
{
  printf 'services:\n  admin:\n    image: %s\n' "$image"
  printf '  backend:\n    image: %s\n    env_file: !override\n      - path: %s\n' "$image" "$work/.env.deployment"
  for svc in jobs-worker auth integrations-googleform; do
    printf '  %s:\n    env_file: !override\n      - path: %s\n' "$svc" "$work/.env.deployment"
  done
} > "$work/override.yml"
skeleton_env="$work/skeleton.env"
full_env="$work/full.env"
(
  umask 077
  {
    # every variable the compose file marks as required (:?), with a throw-away
    # value; the admin passwords and the master key below are the ones that matter
    # here. This is all deploy.sh generates into .env: the keys the services share
    # live in the settings store, so they are not needed to read the file.
    for v in $(grep -o '\${[A-Z_]*:?' "$root/docker-compose.deployment.yml" | tr -d '${:?' | sort -u); do
      case "$v" in BC_ADMIN_PASSWORD|BC_ADMIN_MIG_PASSWORD|SETTINGS_MASTER_KEY) continue ;; esac
      echo "$v=$(openssl rand -hex 16)"
    done
    echo "BC_ADMIN_PASSWORD=$admin_pw"
    echo "BC_ADMIN_MIG_PASSWORD=$mig_pw"
    echo "SETTINGS_MASTER_KEY=$master_key"
    # what deploy.sh generates for a new stack's internal databases
    echo "BC_UMAMI_DB_PASSWORD=$umami_pw"
    echo "BC_MONGO_ROOT_PASSWORD=$mongo_pw"
    echo "ADMIN_PORT=$port"
    echo "ADMIN_EDGE_SUBNET=$subnet"
    echo "ADMIN_EDGE_GATEWAY=$gateway"
  } > "$skeleton_env"
  { cat "$skeleton_env"
    echo "PLATFORM_ADMIN_EMAILS=check.admin@example.test"
  } > "$full_env"
)
envfile="$skeleton_env"
echo "  admin port 127.0.0.1:$port, admin-edge $subnet (gateway $gateway)"

# --- (e) compose config parses with and without the optional variables -----------------
echo "== (e) docker compose config"
check "config parses without the optional variables" dc config -q
envfile="$full_env"
check "config parses with the optional variables" dc config -q
envfile="$skeleton_env"
# a fresh checkout before deploy.sh ran: no .env.deployment (it is not tracked) and no
# per-service env file next to the compose file
mkdir -m 700 "$work/fresh"
cp "$root/docker-compose.deployment.yml" "$work/fresh/"
check "config parses on a fresh checkout without .env.deployment or the per-service env files" \
  docker compose -p "$project" -f "$work/fresh/docker-compose.deployment.yml" --env-file "$skeleton_env" config -q
if command -v git >/dev/null 2>&1 && git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
  check "the template .env.deployment.example is tracked and .env.deployment is git-ignored" \
    bash -c 'cd "$1" && git ls-files --error-unmatch .env.deployment.example && git check-ignore -q .env.deployment && [ -z "$(git ls-files .env.deployment)" ]' _ "$root"
else
  skip=$((skip + 1))
  echo "  SKIP  not a git checkout: .env.deployment tracking not checked"
fi
layout_py='
import json, sys
c = json.load(sys.stdin)
s = c["services"]
on = lambda net: sorted(n for n, v in s.items() if net in (v.get("networks") or {}))
print("edge=" + ",".join(on("admin-edge")))
print("db=" + ",".join(on("admin-db")))
print("db_internal=%s" % c["networks"]["admin-db"].get("internal"))
print("pg_ports=%d" % len(s["app-postgres"].get("ports") or []))
print("admin_env_file=%s" % ("env_file" in s["admin"]))
print("admin_ports=" + ",".join("%s:%s" % (p.get("host_ip"), p.get("published")) for p in s["admin"]["ports"]))
'
layout="$(dc config --format json 2>/dev/null | docker run --rm -i --entrypoint /api/backend/.venv/bin/python "$image" -I -c "$layout_py" 2>/dev/null)"
got() { printf '%s\n' "$layout" | grep "^$1="; }
expect "only admin is on admin-edge" "edge=admin" "$(got edge)"
expect "admin-db is shared by admin and app-postgres only" "db=admin,app-postgres" "$(got db)"
expect "admin-db is internal" "db_internal=True" "$(got db_internal)"
expect "app-postgres publishes no port" "pg_ports=0" "$(got pg_ports)"
expect "admin has no env_file" "admin_env_file=False" "$(got admin_env_file)"
expect "admin publishes on loopback only" "admin_ports=127.0.0.1:$port" "$(got admin_ports)"

# --- (g) the deployment around it: ports, keys, credentials -----------------------------
# The env file is exactly what deploy.sh leaves in .env for a new stack (the
# required passwords, the master key, the two internal database passwords) plus
# the operator's values; the stack's shared keys are in the settings store.
echo "== (g) published ports, master key holders, built-in credentials"
props_py='
import json, sys
c = json.load(sys.stdin)
s = c["services"]
store = ["backend", "jobs-worker", "auth", "integrations-googleform"]
env = lambda n: s[n].get("environment") or {}
print("published=" + ",".join(sorted(n for n, v in s.items() if v.get("ports"))))
print("temporal_services=" + ",".join(sorted(n for n in s if n in ("temporal", "worker", "postgresql"))))
print("master_key_holders=" + ",".join(sorted(n for n, v in s.items() if "SETTINGS_MASTER_KEY" in env(n))))
print("store_required=" + ",".join(n for n in store if env(n).get("SETTINGS_STORE") == "required"))
print("pins=%d" % sum(1 for n in store[:1] + store[2:] for k in ("DEBUG", "API_DOCS_ENABLED") if k in env(n)))
print("umami_db_pw=" + env("umami-postgresql")["POSTGRES_PASSWORD"])
print("mongo_pw=" + env("mongodb")["MONGO_INITDB_ROOT_PASSWORD"])
print("mongo_seed_pw=" + env("mongo-seed")["MONGO_ROOT_PASSWORD"])
print("umami_url_default=%s" % ("umami:umami@" in env("umami")["DATABASE_URL"]))
pub = lambda n: ",".join(sorted("%s:%s" % (p.get("host_ip") or "*", p.get("published")) for p in s[n]["ports"]))
print("umami_ports=" + pub("umami"))
print("nginx_ports=" + pub("nginx"))
print("stored_keys_empty=%s" % all(env("backend")[k] == "" for k in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET")))
'
# the legacy-mongo profile renders MongoDB too (4.1: started only for the import from 4.0)
props="$(dc --profile legacy-mongo config --format json 2>/dev/null | docker run --rm -i --entrypoint /api/backend/.venv/bin/python "$image" -I -c "$props_py" 2>/dev/null)"
gotp() { printf '%s\n' "$props" | grep "^$1="; }
expect "only the intended services publish a port" "published=admin,backend,nginx,umami,webapp" "$(gotp published)"
expect "no Temporal, Temporal database or Temporal worker service (not part of the stack since 4.1)" "temporal_services=" "$(gotp temporal_services)"
expect "the master key reaches the store readers, the admin service and the task runner only" \
  "master_key_holders=admin,auth,backend,integrations-googleform,jobs-worker,task-runner" "$(gotp master_key_holders)"
expect "the services read the settings store (required)" "store_required=backend,jobs-worker,auth,integrations-googleform" "$(gotp store_required)"
expect "DEBUG and API_DOCS_ENABLED are not pinned" "pins=0" "$(gotp pins)"
expect "umami's database has the generated password" "umami_db_pw=$umami_pw" "$(gotp umami_db_pw)"
expect "mongo's root has the generated password" "mongo_pw=$mongo_pw" "$(gotp mongo_pw)"
expect "the seed job uses the same password" "mongo_seed_pw=$mongo_pw" "$(gotp mongo_seed_pw)"
expect "umami does not connect with the built-in password" "umami_url_default=False" "$(gotp umami_url_default)"
expect "umami's dashboard is published on the loopback only" "umami_ports=127.0.0.1:3004" "$(gotp umami_ports)"
expect "nginx publishes the webapp ports and the Umami tracker port" "nginx_ports=*:3001,*:3002,*:3003" "$(gotp nginx_ports)"
expect "the stored keys render empty (read the store)" "stored_keys_empty=True" "$(gotp stored_keys_empty)"

# --- (i) what each service receives --------------------------------------------------
# The compose file is rendered from a copy next to a .env.deployment that holds every
# secret an operator may keep there (as an upgraded stack does), plus the per-service
# env files deploy.sh writes. Only the four services that read the settings store (and
# so hold the master key anyway) may carry those values; the public webapp must not.
echo "== (i) what each service receives (rendered with a populated .env.deployment)"
render="$work/render"
mkdir -m 700 "$render"
cp "$root/docker-compose.deployment.yml" "$render/"
dummies=(
  "STRIPE_SECRET=DUMMY-stripe-secret-1" "STRIPE_WEBHOOK_SECRET=DUMMY-stripe-webhook-2"
  "GOOGLE_CLIENT_SECRET=DUMMY-google-secret-3" "MAIL_PASSWORD=DUMMY-mail-password-4"
  "MONGO_URI=mongodb://root:DUMMY-mongo-root-5@mongodb:27017" "MASTER_ENCRYPTION_KEYSET=DUMMY-keyset-6"
  "AUTH_JWT_SECRET=DUMMY-jwt-secret-7" "AUTH_AES_HEX_KEY=DUMMY-aes-key-8" "TYPEFORM_CLIENT_SECRET=DUMMY-typeform-9"
)
printf '%s\n' "${dummies[@]}" > "$render/.env.deployment"
printf 'UNSPLASH_ACCESS_KEY=DUMMY-unsplash\n' > "$render/.env.webapp"
holders_py='
import json, sys
c = json.load(sys.stdin)["services"]
dummy = dict(a.split("=", 1) for a in sys.argv[1:])
store = {"backend", "jobs-worker", "auth", "integrations-googleform"}
outside = sorted({"%s>%s" % (k, s) for k, v in dummy.items() for s, b in c.items() if v in json.dumps(b) and s not in store})
print("outside_store=" + ",".join(outside))
env = lambda n: ",".join(sorted((c[n].get("environment") or {}).keys()))
print("webapp_own_file=%s" % ((c["webapp"].get("environment") or {}).get("UNSPLASH_ACCESS_KEY")))
print("env_file_users=" + ",".join(sorted(n for n, b in c.items() if b.get("env_file"))))
print("caps_dropped=" + ",".join(sorted(n for n, b in c.items() if b.get("cap_drop") == ["ALL"])))
print("no_new_privileges=" + ",".join(sorted(n for n, b in c.items() if "no-new-privileges:true" in (b.get("security_opt") or []))))
'
holders="$(docker compose -p "$project" -f "$render/docker-compose.deployment.yml" --env-file "$skeleton_env" config --format json 2>/dev/null \
  | docker run --rm -i --entrypoint /api/backend/.venv/bin/python "$image" -I -c "$holders_py" "${dummies[@]}" 2>/dev/null)"
goth() { printf '%s\n' "$holders" | grep "^$1="; }
expect "no secret of .env.deployment reaches a service outside the store readers" "outside_store=" "$(goth outside_store)"
expect "the webapp reads its own env file" "webapp_own_file=DUMMY-unsplash" "$(goth webapp_own_file)"
expect "the webapp and the internal services drop every capability" "caps_dropped=admin,document-sandbox,task-runner,webapp" "$(goth caps_dropped)"
expect "every first-party service is barred from gaining privileges" \
  "no_new_privileges=admin,auth,backend,document-sandbox,integrations-googleform,jobs-worker,task-runner,webapp" "$(goth no_new_privileges)"

# --- (j) nginx passes Umami's tracker and nothing else ---------------------------------
echo "== (j) the public Umami port passes only the tracker script and the event endpoint"
mkdir -m 755 "$work/upstream"
echo "tracker" > "$work/upstream/script.js"
echo "login page" > "$work/upstream/login"
umami_conf="$work/umami.conf"
sed -n '/^# Umami (self-hosted analytics)/,$p' "$root/nginx-deployment.conf" > "$umami_conf"
nx_net="${project}_nxcheck"
nx_up="${project}-nxcheck-upstream"
nx_proxy="${project}-nxcheck-proxy"
extra_networks+=("$nx_net")
extra_containers+=("$nx_up" "$nx_proxy")
docker network create "$nx_net" >/dev/null
docker run -d --name "$nx_up" --network "$nx_net" --network-alias umami --user 65534:65534 \
  -v "$work/upstream:/srv:ro" --entrypoint /api/backend/.venv/bin/python "$image" -I -m http.server 3000 --directory /srv >/dev/null
docker run -d --name "$nx_proxy" --network "$nx_net" -v "$umami_conf:/etc/nginx/conf.d/umami.conf:ro" nginx:1.28-alpine >/dev/null
sleep 3
check "the nginx configuration is valid" docker exec "$nx_proxy" nginx -t
nx_ip="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$nx_net\").IPAddress}}" "$nx_proxy")"
expect "GET /script.js is passed to Umami" "200" "$(http_code "http://$nx_ip:3003/script.js")"
expect "POST /api/send is passed to Umami (the stand-in answers 501 to a POST)" "501" "$(http_code -X POST -d '{}' "http://$nx_ip:3003/api/send")"
expect "GET /api/send is refused" "403" "$(http_code "http://$nx_ip:3003/api/send")"
expect "the login page is not reachable" "404" "$(http_code "http://$nx_ip:3003/login")"
expect "the API is not reachable" "404" "$(http_code "http://$nx_ip:3003/api/auth/login")"
expect "the root is not reachable" "404" "$(http_code "http://$nx_ip:3003/")"
docker rm -f "$nx_up" "$nx_proxy" >/dev/null 2>&1
docker network rm "$nx_net" >/dev/null 2>&1

# --- skeleton mode ---------------------------------------------------------------------
echo "== skeleton mode (no admin list: the bare gate)"
if ! dc up -d admin >"$work/up.log" 2>&1; then
  bad "stack starts"
  tail -n 20 "$work/up.log"
  echo "== $pass passed, $fail failed"
  exit 1
fi
nets() { docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$1" | tr ' ' '\n' | sed "s/^${project}_//" | sort | tr '\n' ' ' | xargs; }
expect "app-postgres is on default and admin-db" "admin-db default" "$(nets "$(dc ps -q app-postgres)")"
expect "admin is on admin-db and admin-edge" "admin-db admin-edge" "$(nets "$(dc ps -q admin)")"
expect "(d) healthcheck reports healthy in skeleton mode" "healthy" "$(wait_health 120)"
admin_id="$(dc ps -q admin)"
edge_ip="$(docker inspect -f "{{(index .NetworkSettings.Networks \"${project}_admin-edge\").IPAddress}}" "$admin_id")"

echo "== (a) host reaches the service through the real gateway address"
expect "host: GET /healthz on 127.0.0.1:$port" "200" "$(http_code "http://127.0.0.1:$port/healthz")"
expect "host: GET / is a bare 404 in skeleton mode" "404" "$(http_code "http://127.0.0.1:$port/")"

echo "== (b) not reachable from the LAN address"
lan="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -n 1)"
if [ -z "$lan" ]; then lan="$(hostname -I 2>/dev/null | awk '{print $1}')"; fi
if [ -z "$lan" ] || [ "${lan#127.}" != "$lan" ]; then
  lan=""
  skip=$((skip + 1))
  echo "  SKIP  no LAN address on this host"
else
  rc=0
  curl -s -o /dev/null -m 4 "http://$lan:$port/healthz" || rc=$?
  expect "connection to $lan:$port is refused (curl exit 7)" "7" "$rc"
fi

echo "== (c) a sibling container on the default network"
expect "sibling: http://admin:8000/ does not resolve (admin is not on default)" "error:URLError" "$(sibling_probe http://admin:8000/)"
res="$(sibling_probe "http://$edge_ip:8000/")"
case "$res" in
  status:200|status:30*) bad "sibling: admin-edge address $edge_ip:8000 reached the portal ($res)" ;;
  *) ok "sibling: admin-edge address $edge_ip:8000 is not reachable ($res)" ;;
esac

echo "== (f) hardening of the admin container"
py="/api/backend/.venv/bin/python"
expect "root filesystem is read-only" "true" "$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$admin_id")"
expect "runs as a non-root user" "65534:65534" "$(docker inspect -f '{{.Config.User}}' "$admin_id")"
expect "cap_drop ALL" "[ALL]" "$(docker inspect -f '{{.HostConfig.CapDrop}}' "$admin_id")"
expect "no effective capability" "0000000000000000" "$(docker exec "$admin_id" $py -I -c "print([l.split()[1] for l in open('/proc/self/status') if l.startswith('CapEff')][0])" 2>/dev/null)"
expect "no-new-privileges" "true" "$(docker inspect -f '{{range .HostConfig.SecurityOpt}}{{.}} {{end}}' "$admin_id" | grep -q 'no-new-privileges' && echo true)"
expect "cannot write outside /tmp" "denied" "$(docker exec "$admin_id" $py -I -c "
try:
    open('/api/backend/probe', 'w'); print('writable')
except OSError:
    print('denied')" 2>/dev/null)"
expect "can write in /tmp" "writable" "$(docker exec "$admin_id" $py -I -c "
open('/tmp/probe', 'w'); print('writable')" 2>/dev/null)"

# --- full mode -------------------------------------------------------------------------
echo "== full mode (throw-away bc_admin database, master key and admin list)"
if dc exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh >/dev/null 2>&1; then ok "admin roles and schema created"; else bad "admin roles script"; fi
if dc run --rm --no-deps -T -e "DATABASE_URL=postgresql+asyncpg://bc_admin_mig:${mig_pw}@app-postgres:5432/bettercollected" \
     admin /api/backend/.venv/bin/alembic -c /api/backend/backend/admin/alembic.ini upgrade head >"$work/migrate.log" 2>&1; then
  ok "admin migrations applied"
else
  bad "admin migrations"
  tail -n 5 "$work/migrate.log"
fi
dc exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh >/dev/null 2>&1
envfile="$full_env"
dc up -d --force-recreate --no-deps admin >"$work/up2.log" 2>&1 || { bad "full-mode start"; tail -n 20 "$work/up2.log"; }
expect "(d) healthcheck reports healthy in full mode" "healthy" "$(wait_health 120)"
if docker logs "$(dc ps -q admin)" 2>&1 | grep -q "portal disabled"; then bad "full mode started the portal"; else ok "full mode started the portal (no bare-gate warning)"; fi
expect "host: GET /healthz" "200" "$(http_code "http://127.0.0.1:$port/healthz")"
expect "host: GET /login (sign-in page) through the gateway" "200" "$(http_code "http://127.0.0.1:$port/login")"
body="$(curl -s -m 5 "http://127.0.0.1:$port/login")"
case "$body" in *"<form"*) ok "sign-in page contains the form" ;; *) bad "sign-in page contains the form" ;; esac
code="$(http_code "http://127.0.0.1:$port/")"
case "$code" in 200) bad "host: GET / without a session is served (200)" ;; *) ok "host: GET / without a session is not served ($code)" ;; esac
expect "host: wrong Host header is a 404" "404" "$(http_code -H 'Host: evil.example' "http://127.0.0.1:$port/login")"
expect "sibling: http://admin:8000/login does not resolve" "error:URLError" "$(sibling_probe http://admin:8000/login)"
if [ -n "$lan" ]; then
  rc=0
  curl -s -o /dev/null -m 4 "http://$lan:$port/login" || rc=$?
  expect "LAN address refused in full mode" "7" "$rc"
fi

echo "== bc_admin database access"
super() { dc exec -T app-postgres psql -qAt -U bettercollected -d bettercollected -c "$1" 2>&1; }
pgrun() { dc exec -T -e "PGPASSWORD=$admin_pw" app-postgres psql -qAt -h app-postgres -U bc_admin -d bettercollected -c "$1" 2>&1; }
super "create table if not exists app.admin_check_probe(x int)" >/dev/null
expect "bc_admin can read its own schema" "0" "$(pgrun 'select count(*) from admin.sessions' | head -n 1)"
out="$(pgrun 'select * from app.admin_check_probe')"
case "$out" in *"permission denied"*) ok "bc_admin cannot read the app schema" ;; *) bad "bc_admin cannot read the app schema ($out)" ;; esac
out="$(pgrun 'update admin.audit_log set action = action')"
case "$out" in *"permission denied"*) ok "bc_admin cannot update the audit log" ;; *) bad "bc_admin cannot update the audit log ($out)" ;; esac
super "drop table if exists app.admin_check_probe" >/dev/null

echo "== (h) host commands through compose, as deploy.sh runs them"
# bootstrap-keys refuses a database whose data it cannot count (fail closed), so
# the application tables have to exist, as they do when deploy.sh gets this far:
# the real app migrations, and a minimal auth.users (the auth image is not built
# here), then the roles script again for the counting function's grants.
if dc run --rm --no-deps -T backend /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini upgrade head >"$work/app-migrate.log" 2>&1; then
  ok "application migrations applied"
else
  bad "application migrations"
  tail -n 5 "$work/app-migrate.log"
fi
super "create table if not exists auth.users(id text primary key, doc jsonb, plan text)" >/dev/null
dc exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh >/dev/null 2>&1
cli_opts=()
cli() { dc run --rm --no-deps -T "${cli_opts[@]}" admin /api/backend/.venv/bin/python -m backend.admin "$@"; }
cli_out="$work/cli.out"
expect "the one-off admin container has none of the stack's keys in its environment" "[]" \
  "$(dc run --rm --no-deps -T --entrypoint /api/backend/.venv/bin/python admin -I -c \
     "import os; print(sorted(k for k in os.environ if k.startswith(('AUTH_', 'TEMPORAL_API', 'MASTER_ENC', 'API_KEY', 'AES_'))))" 2>/dev/null | tail -n 1)"
expect "a new store holds no AUTH_JWT_SECRET" "0" "$(cli settings-history AUTH_JWT_SECRET 2>/dev/null | sed -n 's/^versions=//p')"
outdir="$work/export"
mkdir -m 700 "$outdir"
cli_opts=(--user "$(id -u):$(id -g)" -v "$outdir:/out")
cli bootstrap-keys --export-worker /out/worker.env >"$cli_out" 2>&1
expect "bootstrap-keys succeeds" "0" "$?"
cli_opts=()
expect "bootstrap-keys prints only counts, names and the fingerprint" "0" \
  "$(grep -cvE '^(generated[ =]|keyset_fingerprint |master_key_fingerprint |worker_keys_written |back up SETTINGS_MASTER_KEY)' "$cli_out")"
expect "the worker key file is private" "600" "$(stat -c %a "$outdir/worker.env" 2>/dev/null)"
expect "the worker key file holds API_KEY and AES_HEX_KEY" "2" "$(grep -cE '^(API_KEY|AES_HEX_KEY)=.' "$outdir/worker.env" 2>/dev/null)"
leaked=0
while IFS= read -r line; do
  [ -n "${line#*=}" ] && grep -qF -- "${line#*=}" "$cli_out" && leaked=1
done < "$outdir/worker.env"
expect "no generated key value appears in the command's output" "0" "$leaked"
expect "the store holds AUTH_JWT_SECRET afterwards" "1" "$(cli settings-history AUTH_JWT_SECRET 2>/dev/null | sed -n 's/^versions=//p')"
cli bootstrap-keys >/dev/null 2>&1
expect "a second bootstrap-keys is refused" "1" "$?"
expect "bootstrap-keys stored the respondent identity key too (one version)" "1" "$(cli settings-history RESPONDENT_IDENTITY_KEY 2>/dev/null | sed -n 's/^versions=//p')"
super "insert into auth.users(id, doc) values ('0', '{}')" >/dev/null
cli bootstrap-keys --fill-missing >"$cli_out" 2>&1
rc=$?
super "delete from auth.users where id = '0'" >/dev/null
expect "bootstrap-keys refuses a database that holds a user, even with --fill-missing" "1" "$rc"
check "the refusal names stack_has_data and points at the import" grep -q 'stack_has_data.*settings-import' "$cli_out"
dc config --format json 2>/dev/null | cli settings-import --from-compose-config --dry-run >"$cli_out" 2>&1
rc=$?
# The shipped .env.deployment.example has http://localhost URLs, which the registry
# refuses (exit 1): they stay environment values. What must not happen: a
# conflict between services, or a refused key of the stack itself.
if grep -q '^would_import=' "$cli_out" && ! grep -qE '^(conflict |refused (AUTH_JWT_SECRET|AUTH_AES_HEX_KEY|AUTH_INTERNAL_NOTIFY_KEY|TEMPORAL_API_KEY|MASTER_ENCRYPTION_KEYSET) )' "$cli_out" && [ "$rc" -le 1 ]; then
  ok "settings-import --dry-run reads the compose configuration from stdin (exit $rc: counts, no conflict)"
else
  bad "settings-import --dry-run reads the compose configuration from stdin (exit $rc)"
  grep -E '^(conflict|refused|[a-z_]+=[0-9])' "$cli_out" | head -n 12  # names and counts only
fi
dc config --format json 2>/dev/null | cli settings-drift --from-compose-config >"$cli_out" 2>&1
rc=$?
expect "settings-drift reports nothing that differs" "0" "$rc"
[ "$rc" -eq 0 ] || grep -E '^(differs|[a-z_]+=[0-9])' "$cli_out" | head -n 12
rm -rf "$outdir"

echo "== (k) the Mongo seed leaves no built-in user, seeds no data and keeps its password off the command line"
envfile="$skeleton_env"
dc --profile legacy-mongo up -d --wait mongodb >"$work/mongo-up.log" 2>&1
mongo_rc=$?
sleep 1
if [ "$mongo_rc" -eq 0 ]; then
  mongo_cli() { dc exec -T mongodb mongosh --quiet -u root -p "$mongo_pw" --authenticationDatabase admin --eval "$1" 2>/dev/null | tail -n 1; }
  # a volume from an earlier release has the user the seed used to create
  mongo_cli 'db.getSiblingDB("bettercollected_backend").createUser({user:"seeduser",pwd:"seeduser",roles:[{role:"readWrite",db:"bettercollected_backend"}]})' >/dev/null
  expect "an old volume has the built-in user (the starting point)" "1" "$(mongo_cli 'db.getSiblingDB("bettercollected_backend").getUsers().users.length')"
  # and the reference data an earlier release seeded (it waits there for the import into Postgres)
  mongo_cli 'db.getSiblingDB("bettercollected_backend").allowed_origins.insertOne({origin:"http://localhost:3000"})' >/dev/null
  for _ in 1 2; do
    dc --profile legacy-mongo run --rm --no-deps -T mongo-seed >"$work/seed.log" 2>&1
    expect "mongo-seed runs against the generated root password" "0" "$?"
  done
  expect "the seed removed the built-in user and created none" "0" "$(mongo_cli 'db.getSiblingDB("bettercollected_backend").getUsers().users.length')"
  # reference data is seeded into Postgres since 4.1 (deploy.sh, python -m backend.seed_refdata)
  expect "the seed leaves the existing reference data as it is" "1" "$(mongo_cli 'db.getSiblingDB("bettercollected_backend").allowed_origins.countDocuments()')"
  expect "the seed writes no reference data" "0" "$(mongo_cli 'db.getSiblingDB("bettercollected_backend").forms_plugin_configs.countDocuments()')"
  check "the built-in login no longer works" bash -c "! docker exec $(dc ps -q mongodb) mongosh --quiet -u seeduser -p seeduser --authenticationDatabase bettercollected_backend --eval 1"
  expect "the seed's command line carries no password" "0" "$(docker image inspect "$(dc images -q mongo-seed | head -n 1)" --format '{{json .Config.Cmd}}' 2>/dev/null | grep -c 'root:')"
  dc rm -sf mongo-seed >/dev/null 2>&1
else
  bad "mongodb starts"
  tail -n 10 "$work/mongo-up.log"
fi

echo "== network attachment is stable without COMPOSE_PARALLEL_LIMIT (5 fresh creations)"
envfile="$skeleton_env"
lost=0
for _ in 1 2 3 4 5; do
  dc down -v --remove-orphans --timeout 2 >/dev/null 2>&1
  (unset COMPOSE_PARALLEL_LIMIT; dc up -d admin >/dev/null 2>&1)
  [ "$(nets "$(dc ps -q app-postgres)")" = "admin-db default" ] || lost=$((lost + 1))
  [ "$(nets "$(dc ps -q admin)")" = "admin-db admin-edge" ] || lost=$((lost + 1))
done
expect "no container lost a network in 5 plain up runs" "0" "$lost"

echo
echo "== $pass passed, $fail failed, $skip skipped"
[ "$fail" -eq 0 ]
