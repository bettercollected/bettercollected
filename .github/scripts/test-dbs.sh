#!/usr/bin/env bash
# Throwaway test databases for CI jobs.
#
#   test-dbs.sh start postgres [mongo]   start them in the background (returns at once)
#   test-dbs.sh wait                     wait until every started one accepts connections
#
# Started from a step instead of job `services:` so that pulling and booting
# them overlaps with installing the dependencies (a job waits for its services,
# health checks included, before its first step). Data lives on tmpfs and
# durability is off: a test database lives for one job.
set -euo pipefail

LOGS=${RUNNER_TEMP:-/tmp}

start() {
    local name=$1
    shift
    nohup docker run -d --name "ci-$name" "$@" >"$LOGS/ci-$name.log" 2>&1 &
}

ready() {
    case $1 in
    # TCP, not the socket: the image's first-boot init runs a socket-only server
    postgres) docker exec ci-postgres pg_isready -q -h 127.0.0.1 -U postgres -d bettercollected_test ;;
    mongo) docker exec ci-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null ;;
    esac
}

case ${1:-} in
start)
    shift
    for db in "$@"; do
        echo "$db" >>"$LOGS/ci-dbs"
        case $db in
        postgres)
            start postgres -p 127.0.0.1:5432:5432 \
                -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=bettercollected_test \
                --tmpfs /var/lib/postgresql/data:rw postgres:16-alpine \
                -c fsync=off -c synchronous_commit=off -c full_page_writes=off
            ;;
        mongo)
            start mongo -p 127.0.0.1:27017:27017 --tmpfs /data/db:rw mongo:7
            ;;
        *)
            echo "unknown database: $db" >&2
            exit 2
            ;;
        esac
    done
    ;;
wait)
    started=$(cat "$LOGS/ci-dbs" 2>/dev/null || true)
    for _ in $(seq 1 240); do
        pending=""
        for db in $started; do
            ready "$db" 2>/dev/null || pending="$pending $db"
        done
        if [ -z "$pending" ]; then
            echo "ready: ${started//$'\n'/ }"
            exit 0
        fi
        sleep 0.5
    done
    echo "not ready after 120 s:$pending" >&2
    for db in $pending; do
        cat "$LOGS/ci-$db.log" >&2 || true
        docker logs "ci-$db" >&2 || true
    done
    exit 1
    ;;
*)
    echo "usage: $0 start <postgres|mongo>... | wait" >&2
    exit 2
    ;;
esac
