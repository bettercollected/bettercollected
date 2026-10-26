#!/usr/bin/env bash
# Decides what a CI run covers; writes step outputs to $GITHUB_OUTPUT (or stdout).
#
# Pull requests: only the suites the changed files can affect. Push to develop or
# a release/** branch, the nightly schedule and a manual run (scope "full"): every
# suite. There is one persistence mode (Postgres is the only store since 4.1).
#
# Path rules are deliberately conservative: a file that is not known to be
# prose or to belong to one service runs everything. Tests read files across
# the repository (workflow env, compose files, deploy scripts, docs/spec cases,
# the settings inventory, webapp sources), so those are listed explicitly.
#
# Inputs (env): EVENT (github.event_name), SCOPE (workflow_dispatch input),
# CHANGED_FILES (optional, newline separated; default: the PR merge commit's
# diff against its base, HEAD^1..HEAD).
set -euo pipefail

full=false
case "${EVENT:-pull_request}" in
pull_request) ;;
workflow_dispatch) [ "${SCOPE:-full}" = full ] && full=true ;;
*) full=true ;;
esac

# Postgres backend shards. A shard job has ~45 s of fixed cost on a hosted
# runner (setup, database start, pytest start-up and collection), so more
# shards help less and less, and every job counts against the organisation's
# 20 concurrent jobs. Measured PR wall time: 8 shards ~140 s, 12 ~107 s.
# Full runs are not waited on, so they use fewer, longer shards.
BACKEND_SHARDS=12
[ "$full" = true ] && BACKEND_SHARDS=8
# a manual run may try another count (to measure)
if [[ "${SHARDS:-}" =~ ^[0-9]+$ ]] && [ "$SHARDS" -ge 1 ] && [ "$SHARDS" -le 16 ]; then
    BACKEND_SHARDS=$SHARDS
fi

backend=false auth=false google=false common=false webapp=false smoke=false executor=false
everything() { backend=true auth=true google=true common=true webapp=true smoke=true executor=true; }

if [ "$full" = true ] || [ "${EVENT:-pull_request}" != pull_request ]; then
    everything
else
    if [ -z "${CHANGED_FILES+x}" ]; then
        # HEAD is the PR merge commit; its first parent is the base branch.
        CHANGED_FILES=$(git diff --name-only HEAD^1 HEAD) || CHANGED_FILES="(unknown)"
    fi
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        case "$f" in
        docs/spec/* | docs/settings-inventory.md) everything ;; # read by the test suites
        docs/*) ;;                                              # prose
        webapp/src/constants/theme.ts) webapp=true common=true backend=true ;;
        webapp/*) webapp=true common=true ;; # common scans the webapp for settings names
        backend/backend/app/constants/themes.py) backend=true common=true webapp=true ;;
        backend/*) backend=true common=true ;;
        auth/*) auth=true common=true ;;
        integrations/google/*) google=true common=true ;;
        common/*) backend=true auth=true google=true common=true ;;
        temporal/actions-executor/*) executor=true backend=true common=true ;;
        temporal/*) backend=true common=true ;;
        scripts/smoke/*) smoke=true ;; # the smoke suite's self-test
        .github/workflows/smoke-production.yml) smoke=true ;;
        .github/workflows/smoke-dry-run.yml) smoke=true common=true ;; # common reads its keyset
        */*) everything ;; # .github, postgres, deploy, scripts, other integrations, ...
        *.md) ;;           # top-level prose: README, CHANGELOG, ...
        *) everything ;;   # top-level config the tests read (compose, deploy.sh, .env examples, .nvmrc)
        esac
    done <<<"$CHANGED_FILES"
fi

# Backend matrix: Postgres in shards. They run without Mongo (no server,
# MONGO_URI empty, as on a fresh install): every group is on Postgres, so the
# services must start and serve without it. The tests that drive Mongo
# themselves (marker "mongo": the import from 4.0, the migration CLI, store-wide
# tasks) run in one more Postgres job, with Mongo.
#
# Every job runs against POSTGRES_IMAGE (ci.yml: the oldest supported major
# version) except one, against POSTGRES_IMAGE_NEWEST: the tests of the migration
# chains and of the database role scripts (postgres/), where a behaviour change
# between major versions would show.
entry() { # label group splits ignore mongo(present|absent) marker [postgres(newest)] [paths]
    echo "{\"mode\":\"$1\",\"group\":$2,\"splits\":$3,\"ignore\":\"$4\",\"mongo\":\"$5\",\"marker\":\"$6\",\"postgres\":\"${7:-}\",\"paths\":\"${8:-}\"}"
}
entries=()
for g in $(seq 1 "$BACKEND_SHARDS"); do
    entries+=("$(entry "no Mongo" "$g" "$BACKEND_SHARDS" "" absent "not mongo")")
done
entries+=("$(entry "Mongo-driven tests" 1 1 "" present mongo)")
entries+=("$(entry "newest server: migrations and roles" 1 1 "" absent "not mongo" \
    newest "tests/admin tests/app/db tests/app/migrate")")
matrix="{\"include\":[$(
    IFS=,
    echo "${entries[*]}"
)]}"

out=${GITHUB_OUTPUT:-/dev/stdout}
{
    echo "full=$full"
    echo "backend=$backend"
    echo "auth=$auth"
    echo "google=$google"
    echo "common=$common"
    echo "webapp=$webapp"
    echo "smoke=$smoke"
    echo "executor=$executor"
    echo "backend_matrix=$matrix"
} >>"$out"
echo "full=$full backend=$backend auth=$auth google=$google common=$common webapp=$webapp smoke=$smoke executor=$executor" >&2
