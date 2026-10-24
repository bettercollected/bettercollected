#!/usr/bin/env bash
# Decides what a CI run covers; writes step outputs to $GITHUB_OUTPUT (or stdout).
#
# Pull requests: the Postgres persistence mode only, and only the suites the
# changed files can affect. Push to develop or a release/** branch, the nightly schedule and a manual
# run (scope "full"): every suite in every mode.
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
SIDE_SHARDS=2 # mongo and dual (full runs), without the admin suite
# a manual run may try another count (to measure)
if [[ "${SHARDS:-}" =~ ^[0-9]+$ ]] && [ "$SHARDS" -ge 1 ] && [ "$SHARDS" -le 16 ]; then
    BACKEND_SHARDS=$SHARDS
fi

backend=false auth=false google=false common=false webapp=false
everything() { backend=true auth=true google=true common=true webapp=true; }

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
        temporal/*) backend=true common=true ;;
        */*) everything ;; # .github, postgres, deploy, scripts, other integrations, ...
        *.md) ;;           # top-level prose: README, CHANGELOG, ...
        *) everything ;;   # top-level config the tests read (compose, deploy.sh, .env examples, .nvmrc)
        esac
    done <<<"$CHANGED_FILES"
fi

# Backend matrix: Postgres in shards always; Mongo and dual (without the admin
# suite, which does not depend on the mode) only on full runs.
#
# The Postgres shards run without Mongo (no server, MONGO_URI on a closed
# port): every group is on Postgres, so the services must start and serve
# without it. The tests that drive Mongo themselves (marker "mongo": store
# parity, the migration CLI, store-wide tasks) run in one more Postgres job,
# with Mongo.
entry() { # mode read_source write_mode group splits ignore mongo(present|absent) marker
    echo "{\"mode\":\"$1\",\"read_source\":\"$2\",\"write_mode\":\"$3\",\"group\":$4,\"splits\":$5,\"ignore\":\"$6\",\"mongo\":\"$7\",\"marker\":\"$8\"}"
}
entries=()
for g in $(seq 1 "$BACKEND_SHARDS"); do
    entries+=("$(entry "postgres, no Mongo" postgres postgres "$g" "$BACKEND_SHARDS" "" absent "not mongo")")
done
entries+=("$(entry "postgres, Mongo-driven tests" postgres postgres 1 1 "" present mongo)")
modes='["postgres"]'
if [ "$full" = true ]; then
    for mode in mongo dual; do
        write=""
        [ "$mode" = dual ] && write=dual
        for g in $(seq 1 "$SIDE_SHARDS"); do
            entries+=("$(entry "$mode" "" "$write" "$g" "$SIDE_SHARDS" "--ignore=tests/admin" present "")")
        done
    done
    modes='["mongo","dual","postgres"]'
fi
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
    echo "modes=$modes"
    echo "backend_matrix=$matrix"
} >>"$out"
echo "full=$full backend=$backend auth=$auth google=$google common=$common webapp=$webapp modes=$modes" >&2
