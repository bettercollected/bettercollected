#!/usr/bin/env bash
# Acceptance check for the internal admin service's compose wiring, against REAL
# containers (docs/admin-service.md). Safe on a developer machine: it uses its own
# compose project, random free loopback ports, a pinned network subnet that is not
# in use, throw-away volumes and secrets, and removes everything when it exits. It
# never touches a running stack and publishes nothing but the admin port on 127.0.0.1.
#
#   scripts/admin-compose-check.sh
#
# Needs: bash, docker (with compose v2), curl, openssl. By default it builds the
# backend image from this checkout (tag bc-admin-check:local, removed afterwards).
# To test another image: ADMIN_CHECK_IMAGE=<image>. KEEP=1 leaves the project up.
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

cleanup() {
  if [ "${KEEP:-}" = "1" ]; then
    echo "KEEP=1: project $project left running (work dir $work)"
    return
  fi
  if [ -n "$envfile" ]; then
    dc down -v --remove-orphans --timeout 5 >/dev/null 2>&1
  fi
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
if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "  building $image from backend/Dockerfile (a few minutes the first time)"
  docker build -q -t "$image" -f backend/Dockerfile . >/dev/null || { echo "image build failed" >&2; exit 2; }
  built_image=1
fi
port="$(free_port)" || exit 2
subnet="$(free_subnet)" || exit 2
gateway="${subnet%.0/29}.1"
admin_pw="$(openssl rand -hex 16)"
mig_pw="$(openssl rand -hex 16)"
master_key="$(openssl rand -base64 48 | tr -d '\n')"

printf 'services:\n  admin:\n    image: %s\n' "$image" > "$work/override.yml"
skeleton_env="$work/skeleton.env"
full_env="$work/full.env"
(
  umask 077
  {
    # every variable the compose file marks as required (:?), with a throw-away
    # value; the admin passwords below are the ones that matter here
    for v in $(grep -o '\${[A-Z_]*:?' "$root/docker-compose.deployment.yml" | tr -d '${:?' | sort -u); do
      case "$v" in BC_ADMIN_PASSWORD|BC_ADMIN_MIG_PASSWORD) continue ;; esac
      echo "$v=$(openssl rand -hex 16)"
    done
    echo "BC_ADMIN_PASSWORD=$admin_pw"
    echo "BC_ADMIN_MIG_PASSWORD=$mig_pw"
    echo "ADMIN_PORT=$port"
    echo "ADMIN_EDGE_SUBNET=$subnet"
    echo "ADMIN_EDGE_GATEWAY=$gateway"
  } > "$skeleton_env"
  { cat "$skeleton_env"
    echo "SETTINGS_MASTER_KEY=$master_key"
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

# --- skeleton mode ---------------------------------------------------------------------
echo "== skeleton mode (no master key, no admin list)"
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

echo
echo "== $pass passed, $fail failed, $skip skipped"
[ "$fail" -eq 0 ]
